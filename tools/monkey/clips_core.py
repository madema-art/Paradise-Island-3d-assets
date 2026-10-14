"""
Shared building blocks for the clip library: rest anchors, gait generator, keypose blending,
and the clip registry.  All positions are Blender world coordinates of the unposed monkey.
"""
import math
from copy import deepcopy

from mathutils import Vector

import anim_lib as A
from anim_lib import State, V, P, eul, lerp, smooth, seg

# ---------------------------------------------------------------------------- rest anchors
KNUCKLE_Z, BALL_Z = 0.0065, 0.0075      # knuckle / ball-of-foot height when planted
HAND_X, FOOT_X = 0.060, 0.054
HAND_F, FOOT_F = 0.337, 0.085           # forward distance of knuckle / ball at rest
SHOULDER_F, SHOULDER_X, SHOULDER_Z = 0.268, 0.062, 0.242
HIP_F, HIP_X, HIP_Z = 0.012, 0.046, 0.214
PELVIS_Z = 0.236

CLIPS = {}      # name -> dict(frames, loop, fn, meta)
RIG = None      # set by animate_monkey.py so clips can probe bone positions


def clip(name, frames, loop=True, **meta):
    """Decorator: register fn(phase)->State as a clip."""
    def deco(fn):
        CLIPS[name] = dict(frames=frames, loop=loop, fn=fn, meta=meta)
        return fn
    return deco


def side_sign(s):
    return 1.0 if s == "L" else -1.0


# ---------------------------------------------------------------------------- limb placement
def place_hand(st, s, knuckle, pitch=0.0, yaw=0.0, roll=0.0):
    """Put the hand so its knuckle line is at `knuckle`, pivoting about the knuckles."""
    wrist = A.wrist_from_knuckle(Vector(knuckle), pitch)
    st.put(f"ik_hand_{s}", wrist, (pitch, roll, yaw))


def place_foot(st, s, ball, pitch=0.0, yaw=0.0, roll=0.0):
    ankle = A.ankle_from_ball(Vector(ball), pitch)
    st.put(f"ik_foot_{s}", ankle, (pitch, roll, yaw))


def rest_poles(st, **kw):
    """Elbow/knee pole targets at rest, relative to the posed body (they ride the root)."""
    for s in A.SIDES:
        x = side_sign(s)
        st.put(f"pole_elbow_{s}", P(x * 0.080, 0.205, 0.130))
        st.put(f"pole_knee_{s}", P(x * 0.085, 0.230, 0.120))


def world_pole(st, root_matrix_fn=None):
    pass


def quad_stance(st, bob=0.0):
    """All four limbs planted at the rest stance."""
    for s in A.SIDES:
        x = side_sign(s)
        place_hand(st, s, P(x * HAND_X, HAND_F, KNUCKLE_Z + bob * 0))
        place_foot(st, s, P(x * FOOT_X, FOOT_F, BALL_Z))
    rest_poles(st)
    return st


# ---------------------------------------------------------------------------- gait
def foot_cycle(p, duty, stride, lift):
    """Return (f_offset, height, in_stance, u) for a limb with local phase p in [0,1)."""
    p %= 1.0
    if p < duty:
        u = p / duty
        return stride * (0.5 - u), 0.0, True, u
    s = (p - duty) / (1.0 - duty)
    e = smooth(s)
    return stride * (-0.5 + e), lift * math.sin(math.pi * s) ** 0.8, False, s


def pitch_profile(stance, u, heel_in, toe_out, swing_peak):
    """Foot/hand pitch (toe-down positive) through the cycle."""
    if stance:
        if u < 0.35:
            return lerp(heel_in, 0.0, smooth(u / 0.35))
        return lerp(0.0, toe_out, smooth((u - 0.35) / 0.65) ** 1.5)
    if u < 0.3:
        return lerp(toe_out, swing_peak, smooth(u / 0.3))
    return lerp(swing_peak, heel_in, smooth((u - 0.3) / 0.7))


def gait_state(phase, g, travel=1.0):
    """Quadruped diagonal-sequence walk/run. g = parameter dict (see walk/scurry)."""
    st = State()
    ph = phase * math.tau
    # body motion
    st.root_loc = V(g["sway"] * math.sin(ph + g.get("sway_phase", 0.6)), 0.0,
                    g["bob"] * math.cos(2 * ph + g.get("bob_phase", 0.0)) + g.get("drop", 0.0))
    st.root_rot = (g.get("rock", 0.0) * math.sin(2 * ph + g.get("rock_phase", 0.5)), g.get("roll", 0.0) * math.sin(ph),
                   g.get("yaw", 0.0) * math.sin(ph + 0.4))
    hl, hr, fl, fr = g["offsets"]["hand_L"], g["offsets"]["hand_R"], g["offsets"]["foot_L"], g["offsets"]["foot_R"]
    for s, off in (("L", hl), ("R", hr)):
        x = side_sign(s)
        f, h, stance, u = foot_cycle(phase - off, g["duty"], g["stride_h"], g["lift_h"])
        pitch = pitch_profile(stance, u, -g["heel_h"], g["toe_h"], g["peak_h"])
        place_hand(st, s, P(x * g.get("hand_x", HAND_X) + (0 if stance else x * g["abd"] * math.sin(math.pi * u)),
                            g["center_h"] + f, KNUCKLE_Z + h), pitch)
        A.grip(st, s, g.get("stance_curl_h", 0.0) if stance else g["swing_curl"] * (1 - smooth(u)))
    for s, off in (("L", fl), ("R", fr)):
        x = side_sign(s)
        f, h, stance, u = foot_cycle(phase - off, g["duty"], g["stride_f"], g["lift_f"])
        pitch = pitch_profile(stance, u, -g["heel_f"], g["toe_f"], g["peak_f"])
        place_foot(st, s, P(x * g.get("foot_x", FOOT_X) + (0 if stance else x * g["abd"] * math.sin(math.pi * u)),
                            g["center_f"] + f, BALL_Z + h), pitch)
        A.toe_grip(st, s, g.get("stance_curl_f", 0.0) if stance else g["swing_curl"] * 0.8 * (1 - smooth(u)))
    rest_poles(st)
    # spine: lateral wave + flex/extend on the bound
    fl_amp = g.get("flex", 0.0)
    A.spine_pose(st, pelvis=(g.get("pelvis_pitch", 0.0) - fl_amp * 0.6 * math.cos(2 * ph + g.get("flex_phase", 1.0)), 0, 0),
                 s1=(fl_amp * math.cos(2 * ph + g.get("flex_phase", 1.0)), 0, g["lat"] * math.sin(ph + 0.2)),
                 s2=(fl_amp * 0.8 * math.cos(2 * ph + g.get("flex_phase", 1.0)), 0, g["lat"] * math.sin(ph + 0.5)),
                 s3=(fl_amp * 0.6 * math.cos(2 * ph + g.get("flex_phase", 1.0)), 0, g["lat"] * math.sin(ph + 0.9)))
    A.head_look(st, yaw=-g["lat"] * 1.4 * math.sin(ph + 0.6), pitch=g.get("head_pitch", -6.0) +
                g.get("head_bob", 2.0) * math.cos(2 * ph + 1.0))
    A.tail_pose(st, curl_up=g.get("tail_up", 8.0), sway=g.get("tail_sway", 6.0) * math.sin(ph), wave=g.get("tail_wave", 5.0),
                phase=ph * 1.0)
    A.ears(st, flick=1.5 * math.sin(ph * 2))
    st.rot("jaw", rx=g.get("jaw", 0.0))
    return st


# ---------------------------------------------------------------------------- keypose blending
def lerp_state(a, b, t):
    """Blend two States (roots, FK, controls, pelvis offset, coconut)."""
    st = State()
    st.root_loc = a.root_loc.lerp(b.root_loc, t)
    st.root_rot = tuple(lerp(x, y, t) for x, y in zip(a.root_rot, b.root_rot))
    st.pelvis_off = a.pelvis_off.lerp(b.pelvis_off, t)
    for k in set(a.fk) | set(b.fk):
        va, vb = a.fk.get(k, [0, 0, 0]), b.fk.get(k, [0, 0, 0])
        st.fk[k] = [lerp(x, y, t) for x, y in zip(va, vb)]
    for k in set(a.ctrl) | set(b.ctrl):
        ca, cb = a.ctrl.get(k) or b.ctrl.get(k), b.ctrl.get(k) or a.ctrl.get(k)
        st.ctrl[k] = (ca[0].lerp(cb[0], t), tuple(lerp(x, y, t) for x, y in zip(ca[1], cb[1])))
    if a.coconut is not None or b.coconut is not None:
        ca = a.coconut or b.coconut
        cb = b.coconut or a.coconut
        st.coconut = (ca[0].lerp(cb[0], t), tuple(lerp(x, y, t) for x, y in zip(ca[1], cb[1])))
    return st


def keypose_fn(keys, ease=smooth):
    """keys = [(time 0..1, State)]; returns fn(phase) interpolating with easing between neighbours."""
    keys = sorted(keys, key=lambda k: k[0])

    def fn(phase):
        if phase <= keys[0][0]:
            return deepcopy(keys[0][1])
        for (t0, a), (t1, b) in zip(keys[:-1], keys[1:]):
            if phase <= t1:
                return lerp_state(a, b, ease((phase - t0) / (t1 - t0)))
        return deepcopy(keys[-1][1])
    return fn


def standing_state():
    st = State()
    quad_stance(st)
    A.tail_pose(st, curl_up=6.0)
    return st


def probe(st, bone, tail=False):
    """World position of a bone head (or tail) for the FK/root part of `st` (IK limbs excluded)."""
    RIG.apply(st)
    pb = RIG.pose.bones[bone]
    return (pb.tail if tail else pb.head).copy()


def hand_to(st, s, wrist, pitch=0.0, yaw=0.0, roll=0.0):
    st.put(f"ik_hand_{s}", Vector(wrist), (pitch, roll, yaw))


def foot_to(st, s, ankle, pitch=0.0, yaw=0.0, roll=0.0):
    st.put(f"ik_foot_{s}", Vector(ankle), (pitch, roll, yaw))


ARM_REACH, LEG_REACH = 0.249, 0.238
CLAMP_MAX = {"mm": 0.0}   # largest hand/foot target shift made by reach_clamp during the current clip


def _clamp_to_reach(h, origin, length):
    """Slide a contact point horizontally (keeping its height) until the limb can reach it."""
    d = h - origin
    dz = d.z
    if abs(dz) >= length:
        return Vector((h.x, h.y, origin.z + math.copysign(length * 0.97, dz)))
    reach_h = math.sqrt(length * length - dz * dz)
    dxy = Vector((d.x, d.y, 0.0))
    if dxy.length > reach_h:
        dxy = dxy.normalized() * reach_h
        return Vector((origin.x + dxy.x, origin.y + dxy.y, h.z))
    return h


def reach_clamp(st, margin=0.010):
    """Keep hand/foot targets within what the arms/legs can reach (hands slide in as the chest rises)."""
    for s in A.SIDES:
        sh = probe(st, f"upper_arm_{s}")
        h, r = st.ctrl[f"ik_hand_{s}"]
        h2 = _clamp_to_reach(h, sh, ARM_REACH - margin)
        CLAMP_MAX["mm"] = max(CLAMP_MAX["mm"], (h2 - h).length * 1000)
        st.ctrl[f"ik_hand_{s}"] = (h2, r)
        hp = probe(st, f"thigh_{s}")
        f, r = st.ctrl[f"ik_foot_{s}"]
        f2 = _clamp_to_reach(f, hp, LEG_REACH - margin)
        CLAMP_MAX["mm"] = max(CLAMP_MAX["mm"], (f2 - f).length * 1000)
        st.ctrl[f"ik_foot_{s}"] = (f2, r)
    return st
