"""Sitting, grooming and personality clips + static interaction poses."""
import math

from mathutils import Vector

import anim_lib as A
from anim_lib import State, V, P, eul, lerp, smooth, seg
from clips_core import (CLIPS, clip, foot_to, hand_to, keypose_fn, lerp_state, probe, quad_stance, reach_clamp,
                        side_sign, standing_state)

TAU = math.tau


# ---------------------------------------------------------------------------- sitting building blocks
def tail_sit(st, lift=0.0, sway=0.0, wave=0.0, phase=0.0):
    """Seated tail: the root points down, so curl it back over the first segments and let it rest on the ground."""
    for i in range(1, 11):
        base = 19 if i <= 3 else (4 if i <= 6 else -1)
        st.rot(f"tail_{i}", rx=base + lift * (i / 10), rz=sway * (0.4 + 0.08 * i) + wave * math.sin(phase - i * 0.5))


def sit_base(tail_up=48):
    """Upright seated posture: pelvis dropped to the ground, spine vertical, feet planted in front."""
    st = State()
    st.pelvis_off = V(0, 0.045, -0.165)
    A.spine_pose(st, pelvis=(-62, 0, 0), s1=(-6, 0, 0), s2=(-6, 0, 0), s3=(-4, 0, 0))
    A.head_look(st, pitch=80)      # the torso is ~78 degrees up, so the head needs ~80 to look level
    for s in A.SIDES:
        x = side_sign(s)
        foot_to(st, s, P(x * 0.075, 0.075, 0.034), 0, yaw=x * 12)
        st.put(f"pole_knee_{s}", P(x * 0.115, 0.17, 0.14))
    tail_sit(st)
    return st


def shoulders(st):
    return {s: probe(st, f"upper_arm_{s}") for s in A.SIDES}


def hands_rest_on_knees(st, grip=0.3):
    sh = shoulders(st)
    for s in A.SIDES:
        x = side_sign(s)
        hand_to(st, s, sh[s] + V(x * 0.012, -0.075, -0.195), -5)
        A.grip(st, s, grip)
        st.put(f"pole_elbow_{s}", sh[s] + V(x * 0.12, 0.11, -0.05))
    return st


def sit_pose(grip=0.3, tail_up=48):
    return hands_rest_on_knees(sit_base(tail_up), grip)


def blend_stand_sit(t):
    """Body (FK/root) from stand to sit; limbs are overridden by the caller."""
    a, b = standing_state(), sit_base()
    return lerp_state(a, b, t)


@clip("sit_down", 39, loop=False, group="posture", description="Standing quadruped to upright sit, hands lifting onto the knees. Ends on the first frame of sit_idle.")
def sit_down(phase):
    stand = standing_state()
    k1 = lerp_state(stand, sit_base(), 0.38)
    k2 = lerp_state(stand, sit_base(), 0.80)
    for s in A.SIDES:
        x = side_sign(s)
        hand_to(k1, s, stand.ctrl[f"ik_hand_{s}"][0], 0)
        hand_to(k2, s, stand.ctrl[f"ik_hand_{s}"][0] + V(0, -0.02, 0.03), -20)
        foot_to(k1, s, lerp_vec(stand.ctrl[f"ik_foot_{s}"][0], P(x * 0.075, 0.075, 0.034), 0.45), 0, yaw=x * 5)
        foot_to(k2, s, P(x * 0.075, 0.075, 0.034), 0, yaw=x * 10)
        k1.put(f"pole_elbow_{s}", P(x * 0.095, 0.20, 0.16))
        k2.put(f"pole_elbow_{s}", P(x * 0.115, 0.20, 0.17))
        k1.put(f"pole_knee_{s}", P(x * 0.10, 0.20, 0.13))
        k2.put(f"pole_knee_{s}", P(x * 0.115, 0.17, 0.14))
    reach_clamp(k1)
    sh2 = shoulders(k2)
    for s in A.SIDES:
        x = side_sign(s)
        hand_to(k2, s, sh2[s] + V(x * 0.012, -0.085, -0.200), -22)
        k2.put(f"pole_elbow_{s}", sh2[s] + V(x * 0.12, 0.11, -0.05))
    keys = [(0.0, stand), (0.30, k1), (0.62, k2), (1.0, sit_pose())]
    return keypose_fn(keys)(phase)


def lerp_vec(a, b, t):
    return Vector(a).lerp(Vector(b), t)


@clip("stand_up", 39, loop=False, group="posture", description="Time-reverse of sit_down: seated to standing quadruped.")
def stand_up(phase):
    return sit_down(1.0 - phase)


@clip("sit_idle", 120, loop=True, group="posture", description="Seated rest: breathing, slow head scans, fingers flexing on the knees, tail resting on the ground, ear flicks.")
def sit_idle(phase):
    st = sit_pose(grip=0.25)
    ph = phase * TAU
    breath = math.sin(2 * ph)
    st.pelvis_off = st.pelvis_off + V(0, 0, 0.0008 * breath)
    A.spine_pose(st, s2=(0.8 * breath, 0, 0), s3=(1.4 * breath, 0, 2 * math.sin(ph)))
    A.head_look(st, yaw=18 * math.sin(ph) + 6 * math.sin(3 * ph), pitch=2 * math.sin(2 * ph) - 4, roll=3 * math.sin(ph + 1))
    A.eyes_look(st, yaw=-6 * math.sin(ph))
    A.ears(st, flick=5 * max(0, math.sin(3 * ph + 1.0)) ** 6, back=1)
    for s in A.SIDES:
        A.grip(st, s, 0.22 + 0.06 * math.sin(2 * ph + (0 if s == "L" else 1.5)))
    tail_sit(st, lift=3 * math.sin(ph), sway=8 * math.sin(ph + 0.5), wave=2, phase=ph)
    return st


@clip("groom", 96, loop=True, group="behavior",
      description="Self-grooming while seated: left forearm held up, right hand combing and pinching the fur, head bowed, lip-smacking.")
def groom(phase):
    st = sit_base(tail_up=48)
    ph = phase * TAU
    A.head_look(st, yaw=10 * math.sin(ph), pitch=30 + 4 * math.sin(2 * ph))
    A.spine_pose(st, s2=(2, 0, 0), s3=(4, 0, 0))
    sh = shoulders(st)
    # presented left forearm
    lw = sh["L"] + V(0.020, -0.105, -0.075)
    hand_to(st, "L", lw, -55, yaw=-10)
    A.grip(st, "L", 0.45)
    st.put("pole_elbow_L", sh["L"] + V(0.10, 0.12, -0.06))
    # right hand strokes along the forearm and pinches
    a = 0.5 + 0.5 * math.sin(3 * ph)
    rw = sh["R"] + V(-0.030 + 0.02 * a, -0.085 - 0.04 * a, -0.060 - 0.02 * math.sin(6 * ph))
    hand_to(st, "R", rw, -30, yaw=18)
    A.grip(st, "R", 0.35 + 0.35 * (0.5 + 0.5 * math.sin(9 * ph)))
    st.put("pole_elbow_R", sh["R"] + V(-0.12, 0.12, -0.05))
    st.rot("jaw", rx=4.0 * max(0.0, math.sin(6 * ph + 1.0)))
    A.eyes_look(st, yaw=14, pitch=10)
    A.ears(st, back=3)
    return st


@clip("look_around", 120, loop=True, group="behavior",
      description="Standing observation: slow scan left, up, right and down with the chest following the head, ear swivels and a little weight shift.")
def look_around(phase):
    st = standing_state()
    keys = [(0.00, (0, -6)), (0.14, (48, -4)), (0.30, (52, -18)), (0.46, (4, -26)), (0.62, (-50, -8)), (0.80, (-46, 6)), (1.0, (0, -6))]
    yaw, pitch = 0.0, -6.0
    for (t0, (y0, p0)), (t1, (y1, p1)) in zip(keys[:-1], keys[1:]):
        if t0 <= phase <= t1:
            e = smooth(seg(phase, t0, t1))
            yaw, pitch = lerp(y0, y1, e), lerp(p0, p1, e)
    ph = phase * TAU
    A.head_look(st, yaw=yaw, pitch=pitch, roll=-0.12 * yaw, neck_share=0.6)
    A.spine_pose(st, s2=(0, 0, 0.12 * yaw), s3=(0, 0, 0.18 * yaw))
    A.eyes_look(st, yaw=0.3 * yaw)
    A.ears(st, flick=3 * math.sin(yaw * 0.1 + ph), back=-4)
    st.root_loc = V(0.006 * math.sin(ph), 0, 0.002 * math.sin(2 * ph))
    A.tail_pose(st, curl_up=8 + 3 * math.sin(ph), sway=9 * math.sin(ph + 1.0), wave=4, phase=ph)
    return st


@clip("scratch", 48, loop=True, group="behavior",
      description="Seated, leaning away and raking the flank with the right hind foot (6 strokes per loop) while looking down at it.")
def scratch(phase):
    st = sit_base(tail_up=40)
    ph = phase * TAU
    A.spine_pose(st, s1=(0, 5, 0), s2=(0, 5, 0), s3=(0, 4, 0))
    A.head_look(st, yaw=-26, pitch=14)
    sh = shoulders(st)
    rake = math.sin(6 * ph)
    foot_to(st, "R", P(-0.070, 0.115 + 0.030 * rake, 0.150 + 0.010 * math.cos(6 * ph)), 25, yaw=-20, roll=-18)
    st.put("pole_knee_R", P(-0.14, 0.13, 0.20))
    A.toe_grip(st, "R", 0.55 + 0.25 * rake)
    hand_to(st, "L", sh["L"] + V(0.06, -0.045, -0.205), -5)
    A.grip(st, "L", 0.3)
    hand_to(st, "R", sh["R"] + V(-0.02, -0.07, -0.19), -5)
    st.put("pole_elbow_L", sh["L"] + V(0.12, 0.11, -0.05))
    st.put("pole_elbow_R", sh["R"] + V(-0.12, 0.11, -0.05))
    st.rot("jaw", rx=2)
    A.ears(st, flick=2 * rake)
    return st


@clip("investigate", 96, loop=True, group="behavior",
      description="Foraging inspection: nose to the ground, sniffing bobs, left hand patting and raking at the surface.")
def investigate(phase):
    st = standing_state()
    ph = phase * TAU
    st.root_rot = (4.0, 0, 0)
    st.root_loc = V(0, 0, -0.004)
    sniff = 0.5 + 0.5 * math.sin(6 * ph)
    A.spine_pose(st, s1=(3, 0, 0), s2=(4, 0, 0), s3=(5, 0, 0))
    A.head_look(st, yaw=14 * math.sin(ph), pitch=36 + 5 * sniff, neck_share=0.5)
    A.eyes_look(st, pitch=-8)
    for s in A.SIDES:
        base = st.ctrl[f"ik_hand_{s}"][0]
    # left hand pats twice per loop
    pat = max(0.0, math.sin(4 * ph)) ** 1.5
    wl = st.ctrl["ik_hand_L"][0]
    hand_to(st, "L", wl + V(0, -0.045 * pat + 0.02, 0.030 * pat), -18 * pat)
    A.grip(st, "L", 0.55 * pat)
    A.tail_pose(st, curl_up=-2, sway=10 * math.sin(ph + 0.4), wave=3, phase=ph)
    A.ears(st, flick=2 * math.sin(3 * ph))
    st.rot("jaw", rx=1.5 * sniff)
    return st


@clip("curious", 60, loop=False, group="behavior",
      description="Curious reaction: rises on the front limbs, stretches the neck and tilts the head side to side with ears pricked, then settles.")
def curious(phase):
    stand = standing_state()
    a = standing_state()
    a.root_rot = (-6, 0, 0)
    a.root_loc = V(0, 0, -0.010)
    A.spine_pose(a, s1=(-3, 0, 0), s2=(-4, 0, 0), s3=(-5, 0, 0))
    A.head_look(a, pitch=-12, roll=17)
    A.ears(a, back=-10)
    A.tail_pose(a, curl_up=16)
    b = standing_state()
    b.root_rot = (-6, 0, 0)
    b.root_loc = V(0, 0, -0.010)
    A.spine_pose(b, s1=(-3, 0, 0), s2=(-4, 0, 0), s3=(-5, 0, 0))
    A.head_look(b, pitch=-8, roll=-15, yaw=8)
    A.ears(b, back=-10)
    A.tail_pose(b, curl_up=16, sway=8)
    reach_clamp(a)
    reach_clamp(b)
    keys = [(0.0, stand), (0.25, a), (0.55, b), (0.80, a), (1.0, stand)]
    return keypose_fn(keys)(phase)


@clip("startled", 36, loop=False, group="behavior", travel_m=-0.10,
      description="Startle: flinch, a jolt backwards 0.10 m (root travel baked in, towards +Y) landing in a low alert crouch with ears flat, mouth open and tail whipped up.")
def startled(phase):
    stand = standing_state()
    flinch = standing_state()
    flinch.root_loc = V(0, 0.004, -0.014)
    flinch.root_rot = (6, 0, 0)
    A.spine_pose(flinch, s1=(6, 0, 0), s2=(6, 0, 0), s3=(5, 0, 0))
    A.head_look(flinch, pitch=-22, roll=8)
    A.ears(flinch, back=34)
    flinch.rot("jaw", rx=8)
    A.tail_pose(flinch, curl_up=36, sway=-14)

    def airborne(y, z):
        st = State()
        st.root_loc = V(0, y, z)
        st.root_rot = (-12, 0, 0)
        for s in A.SIDES:
            x = side_sign(s)
            A.grip(st, s, 0.3)
        A.spine_pose(st, s1=(-5, 0, 0), s2=(-6, 0, 0), s3=(-6, 0, 0))
        shs = shoulders(st)
        for s in A.SIDES:
            x = side_sign(s)
            hand_to(st, s, shs[s] + V(x * 0.010, -0.110, -0.165), -28)
            hp = probe(st, f"thigh_{s}")
            foot_to(st, s, hp + V(x * 0.012, -0.030, -0.175), 22)
            st.put(f"pole_elbow_{s}", shs[s] + V(x * 0.10, 0.11, -0.04))
            st.put(f"pole_knee_{s}", hp + V(x * 0.12, -0.03, 0.02))
        A.spine_pose(st, s1=(-5, 0, 0), s2=(-6, 0, 0), s3=(-6, 0, 0))
        A.head_look(st, pitch=-18)
        A.ears(st, back=36)
        st.rot("jaw", rx=9)
        A.tail_pose(st, curl_up=44, sway=10)
        return st

    land = State()
    land.root_loc = V(0, 0.10, -0.018)
    land.root_rot = (4, 0, 0)
    for s in A.SIDES:
        x = side_sign(s)
        hand_to(land, s, P(x * 0.062, 0.292, 0.032) + V(0, 0.10, 0), -2)
        foot_to(land, s, P(x * 0.050, 0.016, 0.034) + V(0, 0.10, 0), 0)
        land.put(f"pole_elbow_{s}", P(x * 0.095, 0.20, 0.15) + V(0, 0.10, 0))
        land.put(f"pole_knee_{s}", P(x * 0.10, 0.22, 0.12) + V(0, 0.10, 0))
    A.spine_pose(land, s1=(5, 0, 0), s2=(6, 0, 0), s3=(5, 0, 0))
    A.head_look(land, pitch=-14, yaw=6)
    A.ears(land, back=30)
    land.rot("jaw", rx=6)
    A.tail_pose(land, curl_up=30)
    hold = lerp_state(land, land, 0)
    A.head_look(hold, yaw=-10)
    reach_clamp(flinch)
    reach_clamp(land)
    keys = [(0.0, stand), (0.12, flinch), (0.30, airborne(0.05, 0.05)), (0.52, land), (0.75, land), (1.0, hold)]
    return keypose_fn(keys)(phase)


@clip("threat_display", 60, loop=True, group="social",
      description="Threat display: low forward crouch, ears flat, mouth open in a gape, jerky head bobs, and a hand slap on the ground (once per loop).")
def threat_display(phase):
    st = standing_state()
    ph = phase * TAU
    st.root_loc = V(0, -0.012 * smooth(math.sin(ph) * 0.5 + 0.5), -0.022)
    st.root_rot = (7, 0, 0)
    A.spine_pose(st, s1=(5, 0, 0), s2=(6, 0, 0), s3=(6, 0, 0))
    bob = max(0.0, math.sin(2 * ph)) ** 2
    A.head_look(st, pitch=10 + 8 * bob, yaw=5 * math.sin(2 * ph))
    st.rot("jaw", rx=8 + 3 * bob)
    A.ears(st, back=32)
    A.tail_pose(st, curl_up=32 + 6 * math.sin(2 * ph), wave=2, phase=ph)
    # right hand slap
    lift = smooth(seg(phase, 0.28, 0.46)) * (1 - smooth(seg(phase, 0.46, 0.52)))
    wr = st.ctrl["ik_hand_R"][0]
    hand_to(st, "R", wr + V(0, -0.03 * lift, 0.10 * lift), -35 * lift)
    A.grip(st, "R", 0.5 * lift)
    st.rot("spine3", ry=-5 * lift)
    return st


@clip("social_greet", 60, loop=True, group="social",
      description="Friendly greeting while seated: head bobs, rapid lip-smacking jaw chatter, ears forward, relaxed hands.")
def social_greet(phase):
    st = sit_pose(grip=0.25)
    ph = phase * TAU
    chatter = 0.5 + 0.5 * math.sin(10 * ph)
    A.head_look(st, yaw=8 * math.sin(ph), pitch=0 + 7 * math.sin(2 * ph), roll=5 * math.sin(ph + 1))
    st.rot("jaw", rx=7 * chatter)
    A.ears(st, back=-9, flick=2 * math.sin(4 * ph))
    tail_sit(st, sway=9 * math.sin(ph))
    A.spine_pose(st, s3=(1.5 * math.sin(2 * ph), 0, 0))
    return st


# ---------------------------------------------------------------------------- static interaction poses (single frame)
def static(name, desc, fn):
    CLIPS[name] = dict(frames=1, loop=False, fn=lambda ph, f=fn: f(), meta=dict(group="pose", description=desc))


def _pose_stand():
    return standing_state()


def _pose_crouch():
    st = standing_state()
    st.root_loc = V(0, 0, -0.042)
    st.root_rot = (5, 0, 0)
    A.spine_pose(st, s1=(6, 0, 0), s2=(7, 0, 0), s3=(6, 0, 0))
    A.head_look(st, pitch=-12)
    A.tail_pose(st, curl_up=-8)
    A.ears(st, back=8)
    return st


def _pose_present():
    st = standing_state()
    st.root_rot = (10, 0, 0)
    st.root_loc = V(0, 0, 0.0)
    A.spine_pose(st, pelvis=(-4, 0, 0), s3=(4, 0, 0))
    A.head_look(st, yaw=58, pitch=-4)
    A.tail_pose(st, curl_up=62)
    A.ears(st, back=-4)
    return st


def _pose_threat():
    return threat_display(0.0)


static("pose_stand", "Neutral standing quadruped.", _pose_stand)
static("pose_crouch", "Low alert crouch, ready to dart or pounce.", _pose_crouch)
static("pose_present", "Rear presented to a partner, head turned back, tail raised (social presenting).", _pose_present)
static("pose_threat", "Frozen threat posture: crouched, ears flat, mouth gaping.", _pose_threat)
static("pose_sit", "Upright seated posture, hands on knees.", lambda: sit_pose())
