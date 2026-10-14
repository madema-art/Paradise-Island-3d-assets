"""Coconut interaction clips (competition, handling, carrying, celebration).

The coconut is driven by the `coconut_attach` bone: a clip that uses the coconut keys that bone's world pose, so the
viewer/game just parents the coconut mesh to the bone. Coconut radius 0.062 m.

Paired clips (tug of war) are authored in mirrored coordinates: place monkey B 0.60 m in front of monkey A (B.position =
A.position + A.forward * 0.60) and rotate B by 180 degrees; both then hold the SAME coconut at every frame.
"""
import math

from mathutils import Matrix, Vector

import anim_lib as A
from anim_lib import State, V, P, eul, lerp, smooth, seg
from clips_behavior import shoulders, sit_base, tail_sit
from clips_core import (CLIPS, clip, foot_to, gait_state, hand_to, keypose_fn, lerp_state, probe, reach_clamp,
                        side_sign, standing_state)
from clips_locomotion import WALK

TAU = math.tau
C0 = P(0.0, 0.56, 0.062)       # coconut resting on the ground in front of the monkey


def lerp_vec(a, b, t):
    return Vector(a).lerp(Vector(b), t)


def hold_hands(st, C, rot=(0, 0, 0), grip=0.75, spread=0.0, behind=0.040, tilt=0.0):
    """Both hands gripping the coconut at C from the sides, palms facing each other."""
    sh = shoulders(st)
    R = eul(*rot)
    for s in A.SIDES:
        x = side_sign(s)
        off = R @ V(x * (0.062 + spread), behind, 0.0)
        hand_to(st, s, Vector(C) + off, tilt, yaw=0, roll=x * 90)
        A.grip(st, s, grip, thumb=min(1.0, grip + 0.1))
        st.put(f"pole_elbow_{s}", sh[s] + V(x * 0.11, 0.12, -0.04))
    st.coconut = (Vector(C), rot)
    return st


def crouch_body(drop=-0.03, pitch=6.0, flex=6.0, y=0.0):
    st = standing_state()
    st.root_loc = V(0, -y, drop)
    st.root_rot = (pitch, 0, 0)
    A.spine_pose(st, s1=(flex, 0, 0), s2=(flex, 0, 0), s3=(flex * 0.8, 0, 0))
    A.head_look(st, pitch=8)
    return st


def reach_end():
    st = crouch_body(-0.030, 7.0, 4.0, y=0.095)
    hold_hands(st, C0, grip=0.62, spread=0.004)
    A.head_look(st, pitch=8)
    A.ears(st, back=-8)
    return st


def hold_sit(C_off=V(0, -0.075, -0.145)):
    st = sit_base()
    sh = shoulders(st)
    C = (sh["L"] + sh["R"]) * 0.5 + C_off
    hold_hands(st, C, grip=0.72)
    A.head_look(st, pitch=34)
    st.coconut_home = C
    return st


# ---------------------------------------------------------------------------- approach / reach / grab
APPROACH = dict(WALK, stride_h=0.15, stride_f=0.15, duty=0.70, lift_h=0.014, lift_f=0.016, drop=-0.036, bob=0.002, sway=0.004,
                lat=2.0, head_pitch=6, head_bob=1.0, tail_up=-6, tail_sway=3, tail_wave=2, flex=0.0, pelvis_pitch=1.0,
                offsets=dict(foot_L=0.0, hand_R=0.14, foot_R=0.5, hand_L=0.64))


@clip("coconut_approach", 30, loop=True, group="coconut", speed_mps=round(0.15 / (0.70 * 1.0), 3),
      description="Low stalking walk towards a coconut: crouched, head forward, ears pricked, tail low and still. 0.21 m/s at 1.0 s per cycle.")
def coconut_approach(phase):
    st = gait_state(phase, APPROACH)
    A.ears(st, back=-7)
    st.rot("spine3", rx=5)
    return st


@clip("coconut_reach", 33, loop=False, group="coconut", coconut_start="ground, 0.56 m ahead of the root (P(0,0.56,0.062))",
      description="Steps in from standing and reaches for a coconut resting 0.56 m ahead: left hand tests the top, then both hands close around it. "
                  "The coconut stays on the ground (coconut_attach is keyed at its resting place).")
def coconut_reach(phase):
    stand = standing_state()
    stand.coconut = (C0, (0, 0, 0))
    mid = crouch_body(-0.024, 5.0, 3.0, y=0.055)
    mid.coconut = (C0, (0, 0, 0))
    hand_to(mid, "L", C0 + V(0.040, 0.050, 0.074), -32)
    A.grip(mid, "L", 0.25)
    mid.put("pole_elbow_L", P(0.10, 0.20, 0.17) + V(0, -0.04, 0))
    A.head_look(mid, pitch=8, yaw=-4)
    keys = [(0.0, stand), (0.50, mid), (1.0, reach_end())]
    return keypose_fn(keys)(phase)


@clip("coconut_grab_lift", 54, loop=False, group="coconut",
      description="Both hands tighten on the coconut, drag it in and haul it up as the monkey sits back onto its haunches; "
                  "ends holding the coconut at the chest (first frame of coconut_hold_idle).")
def coconut_grab_lift(phase):
    a = reach_end()
    b = hold_sit()
    body = lerp_state(a, b, smooth(seg(phase, 0.22, 0.95)))
    Cb = b.coconut[0]
    e = smooth(seg(phase, 0.18, 0.92))
    C = lerp_vec(C0, Cb, e) + V(0, 0, 0.045 * math.sin(math.pi * e)) + V(0, 0.0, 0)
    jerk = 0.012 * math.sin(math.pi * seg(phase, 0.18, 0.45)) * math.sin(seg(phase, 0.18, 0.45) * TAU)
    hold_hands(body, C + V(0, jerk, 0), grip=lerp(0.62, 0.78, smooth(seg(phase, 0.1, 0.5))))
    A.head_look(body, pitch=lerp(8, 34, smooth(seg(phase, 0.4, 0.95))), yaw=0)
    return reach_clamp(body)


@clip("coconut_hold_idle", 120, loop=True, group="coconut",
      description="Seated, cradling the coconut at the chest: slow turning of the nut in the hands, sniffing, glances around.")
def coconut_hold_idle(phase):
    st = sit_base()
    ph = phase * TAU
    breath = math.sin(2 * ph)
    st.pelvis_off = st.pelvis_off + V(0, 0, 0.0008 * breath)
    A.spine_pose(st, s2=(0.8 * breath, 0, 0), s3=(1.2 * breath, 0, 1.5 * math.sin(ph)))
    sh = shoulders(st)
    C = (sh["L"] + sh["R"]) * 0.5 + V(0, -0.075, -0.145) + V(0, 0, 0.004 * breath)
    hold_hands(st, C, rot=(8 * math.sin(ph), 5 * math.sin(2 * ph), 24 * math.sin(ph + 0.5)), grip=0.70 + 0.04 * math.sin(2 * ph))
    sniff = max(0.0, math.sin(2 * ph - 0.6)) ** 2
    A.head_look(st, yaw=14 * math.sin(ph + 1.0), pitch=34 + 12 * sniff, roll=2 * math.sin(ph))
    st.rot("jaw", rx=2 * sniff)
    A.ears(st, flick=3 * max(0, math.sin(3 * ph)) ** 6)
    tail_sit(st, sway=7 * math.sin(ph), phase=ph)
    return st


@clip("coconut_inspect", 96, loop=True, group="coconut",
      description="Holds the coconut up in front of the face and rotates it through a full turn (hands re-grip), sniffing and head-bobbing.")
def coconut_inspect(phase):
    st = sit_base()
    ph = phase * TAU
    sh = shoulders(st)
    C = (sh["L"] + sh["R"]) * 0.5 + V(0, -0.080, -0.060) + V(0, 0, 0.004 * math.sin(2 * ph))
    hold_hands(st, C, rot=(10 * math.sin(2 * ph), 0, 360.0 * phase), grip=0.66 + 0.1 * math.sin(4 * ph))
    A.head_look(st, yaw=8 * math.sin(2 * ph), pitch=24 + 8 * math.sin(4 * ph), roll=4 * math.sin(2 * ph))
    st.rot("jaw", rx=1.5 + 1.5 * math.sin(8 * ph))
    A.eyes_look(st, pitch=-4)
    A.ears(st, back=-6)
    tail_sit(st, sway=5 * math.sin(ph))
    A.spine_pose(st, s3=(-3, 0, 0))
    return st


@clip("coconut_guard", 60, loop=True, group="coconut",
      description="Possessive guarding: hunched over the coconut hugged to the belly, shoulders rolled in, fast suspicious head scans, ears flat, jaw twitching.")
def coconut_guard(phase):
    st = sit_base()
    ph = phase * TAU
    A.spine_pose(st, pelvis=(-8, 0, 0), s1=(14, 0, 0), s2=(18, 0, 0), s3=(14, 0, 0))
    sh = shoulders(st)
    C = (sh["L"] + sh["R"]) * 0.5 + V(0, -0.050, -0.150)
    hold_hands(st, C, rot=(0, 0, 4 * math.sin(2 * ph)), grip=0.9, spread=-0.004, behind=0.050)
    scan = math.sin(ph) * (0.6 + 0.4 * math.sin(3 * ph))
    A.head_look(st, yaw=48 * scan, pitch=30 + 5 * math.sin(4 * ph), roll=-5 * scan)
    A.eyes_look(st, yaw=-10 * scan)
    st.rot("jaw", rx=3 + 5 * max(0.0, math.sin(5 * ph)) ** 2)
    A.ears(st, back=30)
    tail_sit(st, lift=14, sway=10 * math.sin(2 * ph), wave=4, phase=ph)
    return st


# ---------------------------------------------------------------------------- the paired tug of war
TUG_D, TUG_F, TUG_Z, TUG_AMP = 1.08, 0.54, 0.100, 0.030


def tug_state(phase, role):
    """Crouched tug of war. role 'holder' gains when delta>0, 'challenger' when delta<0 (mirrored).

    Monkey B is placed TUG_D m in front of A and rotated 180 degrees, so a coconut at forward distance f_c from A is at
    TUG_D - f_c from B. We keep f_A + f_B = TUG_D by giving B f_c = TUG_F + delta and A f_c = TUG_F - delta.
    """
    ph = phase * TAU
    delta = TUG_AMP * (math.sin(3 * ph) + 0.25 * math.sin(6 * ph + 0.8))
    sgn = 1.0 if role == "holder" else -1.0
    gain = max(0.0, min(1.2, sgn * delta / TUG_AMP))        # this monkey is pulling the nut in
    lurch = max(0.0, min(1.2, -sgn * delta / TUG_AMP))      # this monkey is being dragged forward
    st = crouch_body(-0.058, 2.5 - 6.0 * gain + 3.0 * lurch, 6.0 - 4.0 * gain, y=0.0)
    st.root_loc = V(0, -0.058 * lurch + 0.025 * gain, -0.058 - 0.010 * gain)
    f_c = TUG_F - sgn * delta
    C = P(0.0, f_c, TUG_Z + 0.004 * math.sin(6 * ph))
    hold_hands(st, C, rot=(3.0 * sgn * delta / TUG_AMP, 0, 5 * math.sin(3 * ph) * sgn), grip=0.9, spread=0.003, behind=0.046)
    A.head_look(st, pitch=6 - 10 * gain + 6 * lurch, yaw=3 * math.sin(3 * ph))
    st.rot("jaw", rx=5 + 7 * gain)
    A.ears(st, back=22)
    A.tail_pose(st, curl_up=26 + 10 * gain, sway=8 * math.sin(3 * ph + 1.0), wave=3, phase=ph * 3)
    A.spine_pose(st, s3=(0, 0, 3 * math.sin(3 * ph) * sgn))
    return reach_clamp(st)


def _tug_meta(role, partner):
    return dict(group="coconut", pair="tug_of_war", role=role, partner_clip=partner, partner_root_offset=[0.0, -TUG_D, 0.0],
                partner_yaw_deg=180,
                description=f"Tug of war ({role}). Place the partner monkey {TUG_D} m in front (A.position + A.forward * {TUG_D}) rotated "
                            f"180 degrees and play both loops together: the coconut is at the same world position in both clips every frame "
                            f"(bone coconut_attach on either monkey).")


CLIPS["coconut_tug_holder"] = dict(frames=36, loop=True, fn=lambda ph: tug_state(ph, "holder"),
                                   meta=_tug_meta("holder", "coconut_tug_challenger"))
CLIPS["coconut_tug_challenger"] = dict(frames=36, loop=True, fn=lambda ph: tug_state(ph, "challenger"),
                                       meta=_tug_meta("challenger", "coconut_tug_holder"))


# ---------------------------------------------------------------------------- celebration / loss / carry
@clip("coconut_triumph", 66, loop=False, group="coconut",
      description="Triumph: sits tall, thrusts the coconut overhead with a whooping gape and a head-back shake, then lowers it to the chest (ends on coconut_hold_idle frame 0).")
def coconut_triumph(phase):
    a = hold_sit()
    up = sit_base()
    A.spine_pose(up, pelvis=(-4, 0, 0), s1=(-6, 0, 0), s2=(-9, 0, 0), s3=(-9, 0, 0))
    shu = shoulders(up)
    Cu = (shu["L"] + shu["R"]) * 0.5 + V(0, -0.040, 0.205)
    hold_hands(up, Cu, grip=0.8, spread=-0.002)
    A.head_look(up, pitch=-28)
    up.rot("jaw", rx=16)
    A.ears(up, back=-10)
    tail_sit(up, lift=24)
    sh2 = lerp_state(up, up, 0)
    hold_hands(sh2, Cu + V(0, 0, 0.012), rot=(0, 7, 0), grip=0.8)
    A.head_look(sh2, pitch=-34, roll=6)
    sh3 = lerp_state(up, up, 0)
    hold_hands(sh3, Cu + V(0, 0, 0.012), rot=(0, -7, 0), grip=0.8)
    A.head_look(sh3, pitch=-34, roll=-6)
    sh2.rot("jaw", rx=3)
    keys = [(0.0, a), (0.30, up), (0.46, sh2), (0.60, sh3), (0.74, up), (1.0, hold_sit())]
    return keypose_fn(keys)(phase)


@clip("coconut_lose", 42, loop=False, group="coconut",
      description="Loses the coconut: yanked forward, hands pried open, coconut leaves (ends 0.30 m in front), monkey slumps, ears flat, head low.")
def coconut_lose(phase):
    a = hold_sit()
    Ca = a.coconut[0]
    far = Ca + V(0, -0.30, -0.02)
    pulled = hold_sit(V(0, -0.075 - 0.10, -0.145 + 0.02))
    open_ = sit_base()
    sh = shoulders(open_)
    for s in A.SIDES:
        x = side_sign(s)
        hand_to(open_, s, sh[s] + V(x * 0.03, -0.18, -0.15), -10)
        A.grip(open_, s, 0.0)
        open_.put(f"pole_elbow_{s}", sh[s] + V(x * 0.12, 0.08, -0.05))
    open_.coconut = (far, (30, 0, 40))
    A.head_look(open_, pitch=26, yaw=-8)
    A.ears(open_, back=26)
    open_.rot("jaw", rx=6)
    slump = sit_base()
    A.spine_pose(slump, s1=(8, 0, 0), s2=(12, 0, 0), s3=(10, 0, 0))
    shs = shoulders(slump)
    for s in A.SIDES:
        x = side_sign(s)
        hand_to(slump, s, shs[s] + V(x * 0.02, -0.07, -0.20), -5)
        A.grip(slump, s, 0.1)
        slump.put(f"pole_elbow_{s}", shs[s] + V(x * 0.12, 0.11, -0.05))
    slump.coconut = (far, (30, 0, 40))
    A.head_look(slump, pitch=42, yaw=-14)
    A.ears(slump, back=28)
    tail_sit(slump, sway=-6)
    keys = [(0.0, a), (0.18, pulled), (0.38, open_), (1.0, slump)]
    return keypose_fn(keys)(phase)


CARRY = dict(WALK, stride_h=0.15, stride_f=0.15, duty=0.67, lift_h=0.020, lift_f=0.024, drop=-0.014, bob=0.004, sway=0.010,
             roll=2.5, lat=3.0, head_pitch=-2, tail_up=14, tail_sway=7,
             offsets=dict(foot_L=0.0, hand_R=0.33, foot_R=0.67, hand_L=0.0))


@clip("coconut_carry_walk", 24, loop=True, group="coconut", speed_mps=round(0.15 / (0.67 * 24 / 30), 3),
      description="Tripod walk carrying the coconut pressed to the chest with the left arm. Contact speed 0.28 m/s at 0.8 s per cycle.")
def coconut_carry_walk(phase):
    st = gait_state(phase, CARRY)
    W = Matrix.Translation(st.root_loc) @ eul(*st.root_rot).to_4x4()
    Cl = P(0.020, 0.325, 0.128)
    C = W @ Cl
    hand_to(st, "L", C + V(0.066, 0.040, 0.0), 0, roll=90)
    A.grip(st, "L", 0.78, thumb=0.8)
    st.put("pole_elbow_L", W @ P(0.11, 0.20, 0.17))
    st.coconut = (C, (0, 0, 0))
    A.head_look(st, pitch=-3)
    return st


CLIPS["pose_coconut_hold"] = dict(frames=1, loop=False, fn=lambda ph: hold_sit(),
                                  meta=dict(group="pose", description="Seated, holding the coconut at the chest."))
