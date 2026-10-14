"""Staff handling for clips: where the staff is (butt position + axis), where each hand grips it, and the matching IK hand targets.

All positions are in the baked (root-fixed) world frame, z up, forward = -Y (so `f` = forward distance as elsewhere).
Gripping conventions (verified in the skinned sheets): `palm_ref` is the world direction from the staff axis towards the
palm; the thumb ends on the `thumb_up` side (towards the staff tip for an upright staff).
"""
import numpy as np

import params as PR
import rigkit as RK
from kin import axis_angle, unit
from rigkit import hand_on_staff, ik_hand, set_staff

STAFF_LEN = RK.STAFF_LEN
UP = np.array([0, 0, 1.0])
FWD = np.array([0, -1.0, 0])


def P(x, f, z):
    return np.array([x, -f, z], float)


def axis_from(pitch=0.0, roll=0.0, yaw=0.0):
    """Unit axis (butt -> tip) from tilt angles: pitch + = tip forward, roll + = tip to his left, yaw about the vertical."""
    a = np.array([0.0, 0.0, 1.0])
    a = axis_angle([1, 0, 0], -pitch) @ a      # forward tilt: the tip moves towards -Y
    a = axis_angle([0, 1, 0], -roll) @ a      # lean left (+x)
    a = axis_angle([0, 0, 1], yaw) @ a
    return unit(a)


def tilt_from(axis):
    a = unit(axis)
    return float(np.degrees(np.arctan2(-a[1], a[2]))), float(np.degrees(np.arctan2(a[0], a[2])))


def grip_hand(side, butt, axis, along, mode="side", roll=0.0, twist=0.0):
    """IK vector for `side` gripping the staff `along` metres from the butt. mode picks the palm approach direction:
    side   : palm faces the staff from the body's inner side (relaxed grip at the hip, hand beside the staff)
    over   : overhand, palm faces down onto a horizontal / forward-leaning staff
    under  : underhand, palm faces up
    back   : palm faces the staff from behind (hand behind the staff, e.g. leaning on it with both hands)
    front  : palm faces the staff from in front
    """
    s = 1.0 if side == "L" else -1.0
    a = unit(axis)
    ref = {"side": np.array([-s, 0.0, 0.0]), "outer": np.array([s, 0.0, 0.0]), "over": np.array([0.0, 0.0, 1.0]), "under": np.array([0.0, 0.0, -1.0]),
           "back": np.array([0.0, 1.0, 0.0]), "front": np.array([0.0, -1.0, 0.0])}[mode]
    return hand_on_staff(side, butt, a, along, ref, roll=roll, extra_twist=twist)


def put(p, butt, axis):
    """Place the staff (butt position, unit axis towards the tip)."""
    return set_staff(p, np.asarray(butt, float), unit(axis))


def hold(p, butt, axis, right=None, left=None):
    """Place the staff and set IK targets: right/left = (along, mode[, roll, twist]) or None (leave the hand alone)."""
    p = put(p, butt, axis)
    for side, spec in (("R", right), ("L", left)):
        if spec is None:
            continue
        along, mode = spec[0], spec[1]
        roll = spec[2] if len(spec) > 2 else 0.0
        twist = spec[3] if len(spec) > 3 else 0.0
        p[f"arm{side}_ik"] = grip_hand(side, butt, axis, along, mode, roll, twist)
        p[f"f{side}"] = RK.G("grip_staff")
    return p


def hold_hand_point(p, side, hand_pt, butt, along=None, mode="side", roll=0.0, twist=0.0):
    """Hand at a given point; the staff axis is chosen so that it passes through the grip point from `butt`."""
    hand_pt = np.asarray(hand_pt, float)
    butt = np.asarray(butt, float)
    d = hand_pt - butt
    L = np.linalg.norm(d)
    axis = d / L
    along = L if along is None else along
    return axis, along


def offset_from_hand(side, axis, mode, along=None):
    """Vector from the grip point on the staff axis to the palm centre (HAND_OFFSET towards the palm)."""
    s = 1.0 if side == "L" else -1.0
    a = unit(axis)
    ref = {"side": np.array([-s, 0.0, 0.0]), "outer": np.array([s, 0.0, 0.0]), "over": np.array([0.0, 0.0, 1.0]), "under": np.array([0.0, 0.0, -1.0]),
           "back": np.array([0.0, 1.0, 0.0]), "front": np.array([0.0, -1.0, 0.0])}[mode]
    r = unit(ref - a * (ref @ a))
    return r * RK.HAND_OFFSET


# ---------------------------------------------------------------------------------------------------- staff-state keys
def SS(x, f, z, pitch, roll=0.0, yaw=0.0, along=1.0, wR=1.0, wL=0.0, alongL=1.5):
    """Staff state key: butt position (x, forward f, height z), axis tilt, right/left grip distance from the butt and IK weights."""
    return np.array([x, -f, z, pitch, roll, yaw, along, wR, wL, alongL], float)


def kv(t, keys_, ease="smooth"):
    """Smoothly interpolate [(time, vector)] (clamped)."""
    ts = np.array([k[0] for k in keys_], float)
    V = np.array([np.asarray(k[1], float) for k in keys_])
    t = float(np.clip(t, ts[0], ts[-1]))
    i = int(np.clip(np.searchsorted(ts, t, side="right") - 1, 0, len(ts) - 2))
    u = (t - ts[i]) / max(ts[i + 1] - ts[i], 1e-9)
    u = u * u * (3 - 2 * u)
    return V[i] * (1 - u) + V[i + 1] * u


def apply_state(p, s, right_mode="side", left_mode="back", grip="grip_staff"):
    """Place the staff from a state vector and set the IK targets of the hands (weights in s[7], s[8]) for 'blend' arm mode."""
    butt = s[:3]
    axis = axis_from(s[3], s[4], s[5])
    p = put(p, butt, axis)
    p["armR_ik"] = grip_hand("R", butt, axis, s[6], right_mode)
    p["armL_ik"] = grip_hand("L", butt, axis, s[9], left_mode)
    p["armR_w"] = np.array([s[7]])
    p["armL_w"] = np.array([s[8]])
    if s[7] > 0.5:
        p["fR"] = RK.G(grip)
    if s[8] > 0.5:
        p["fL"] = RK.G(grip)
    return p


def opts_blend():
    return dict(arm_mode=("blend", "blend"), arm_space=("world", "world"), stance=(True, True))
