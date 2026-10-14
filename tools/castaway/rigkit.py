"""Authoring helpers shared by the clip modules: standing base poses, breathing/blinking layers, staff grips, foot helpers."""
import numpy as np

import params as PR
from clipkit import keys, offset, pulse, seg, smooth
from kin import I3, Rx, Rz, axis_angle, euler, unit
from pose_lib import GRIPS, RIG, SIDES, SIGN

TAU = 2 * np.pi

# arm FK vectors are relative to the rest A-pose (30 deg abduction): (fwd, out, twist, elbow, wrist flex, wrist dev)
ARM_HANG = np.array([2.0, -21.0, 0.0, 12.0, 0.0, 0.0])


def G(name, amount=1.0, spread=0.0):
    return PR.grip_vec(name, amount, spread)


def stand(arm_L=None, arm_R=None, grip="relaxed", mood=0.0):
    """Relaxed standing pose parameters (feet at rest, arms hanging)."""
    p = PR.base()
    p["armL"] = np.array(ARM_HANG if arm_L is None else arm_L, float)
    p["armR"] = np.array(ARM_HANG if arm_R is None else arm_R, float)
    p["fL"] = G(grip, 1.0)
    p["fR"] = G(grip, 1.0)
    face_neutral(p, mood)
    return p


def face_neutral(p, mood=0.0):
    """Friendly, slightly amused resting expression with a touch of asymmetry."""
    f = p["face"]
    f[PR.FACE_KEYS.index("smile_L")] = 0.10 + 0.25 * mood
    f[PR.FACE_KEYS.index("smile_R")] = 0.07 + 0.25 * mood
    f[PR.FACE_KEYS.index("brow_L")] = 0.06
    f[PR.FACE_KEYS.index("brow_R")] = 0.13
    return p


def fset(p, **kw):
    """Set named face channels (returns a copy)."""
    p = PR.copy(p)
    for k, v in kw.items():
        p["face"][PR.FACE_KEYS.index(k)] = v
    return p


def fadd(p, **kw):
    p = PR.copy(p)
    for k, v in kw.items():
        p["face"][PR.FACE_KEYS.index(k)] += v
    return p


def breathing(p, t, period=4.2, amp=1.0, phase=0.0):
    """Chest/shoulder breathing as additive parameter changes."""
    s = np.sin(TAU * (t / period + phase))
    q = PR.copy(p)
    q["sp"] = q["sp"] + np.array([-1.3 * amp * s, 0, 0])
    q["hd"] = q["hd"] + np.array([0.6 * amp * s, 0, 0])
    q["armL"] = q["armL"] + np.array([0, 0.8 * amp * s, 0, 0, 0, 0])
    q["armR"] = q["armR"] + np.array([0, 0.8 * amp * s, 0, 0, 0, 0])
    q["pel"] = q["pel"] + np.array([0, 0, 0.0012 * amp * s, 0, 0, 0])
    return q


def blink_curve(t, at, dur=0.15):
    x = (t - at) / dur
    if x < 0 or x > 1:
        return 0.0
    return float(np.sin(np.pi * x) ** 0.8)


def blinks(p, t, times, dur=0.15, amount=1.0):
    q = PR.copy(p)
    b = max([blink_curve(t, a, dur) for a in times] + [0.0]) * amount
    i, j = PR.FACE_KEYS.index("blink_L"), PR.FACE_KEYS.index("blink_R")
    q["face"][i] = max(q["face"][i], b)
    q["face"][j] = max(q["face"][j], b)
    return q


def auto_blinks(seconds, seed, every=(2.6, 4.6)):
    rng = np.random.default_rng(seed)
    t, out = rng.uniform(0.4, 1.2), []
    while t < seconds - 0.3:
        out.append(float(t))
        t += rng.uniform(*every)
    return out


def with_blinks(fn, seconds, seed=1, every=(2.6, 4.6)):
    times = auto_blinks(seconds, seed, every)

    def wrapped(t):
        prm, opts = fn(t)
        return blinks(prm, t, times), opts
    return wrapped


def look_at(p, target, amount=1.0):
    p = PR.copy(p)
    p["look"] = np.array([target[0], target[1], target[2], amount], float)
    return p


def head_eye(p, yaw=0.0, pitch=0.0, roll=0.0, eyes_yaw=0.0, eyes_pitch=0.0):
    p = PR.copy(p)
    p["hd"] = p["hd"] + np.array([pitch, roll, yaw])
    p["eye"] = p["eye"] + np.array([eyes_yaw, eyes_pitch])
    return p


# ---------------------------------------------------------------------------------------------------- staff + hands
STAFF_LEN = 2.10
HAND_OFFSET = 0.022          # staff centre sits this far from the palm centre, towards the palm normal


def hand_on_staff(side, butt, axis, along, palm_ref, roll=0.0, extra_twist=0.0):
    """IK vector (palm xyz, finger dir xyz, palm normal xyz, twist) gripping a staff.
    butt: world position of the staff butt, axis: unit vector butt->tip, along: distance from the butt along the staff,
    palm_ref: direction (world) from the staff centre towards the palm (perpendicular to the staff is enforced)."""
    a = unit(np.asarray(axis, float))
    centre = np.asarray(butt, float) + a * along
    r = np.asarray(palm_ref, float)
    r = unit(r - a * (r @ a))
    r = axis_angle(a, roll) @ r
    n = -r                                                   # palm normal points from the palm towards the staff
    d = unit(np.cross(a, n))
    palm = centre + r * HAND_OFFSET
    return np.concatenate([palm, d, n, [extra_twist]])


def staff_state(butt, axis_dir):
    """(position, euler delta) for the prop_staff bone from a butt position and axis direction (rest axis is +Z)."""
    a = unit(np.asarray(axis_dir, float))
    z = np.array([0, 0, 1.0])
    v = np.cross(z, a)
    c = float(z @ a)
    if np.linalg.norm(v) < 1e-9:
        R = np.eye(3) if c > 0 else np.diag([1, -1, -1.0])
    else:
        vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
        R = np.eye(3) + vx + vx @ vx / (1 + c)
    from scipy.spatial.transform import Rotation as Rot
    # euler(pitch, roll, yaw) = Rz(yaw) Ry(roll) Rx(pitch): solve numerically from the matrix
    ang = Rot.from_matrix(R).as_euler("ZYX", degrees=True)   # yaw, roll(y), pitch(x)
    return np.concatenate([np.asarray(butt, float), [ang[2], ang[1], ang[0]]])


def set_staff(p, butt, axis_dir):
    p = PR.copy(p)
    p["staff"] = staff_state(butt, axis_dir)
    return p


def set_aux(p, pos, axis_dir):
    p = PR.copy(p)
    p["aux"] = staff_state(pos, axis_dir)
    return p


def staff_butt_axis(p):
    v = p["staff"]
    R = euler(*v[3:6])
    return v[:3], R @ np.array([0, 0, 1.0])


_HANG = {}


def hang_ik(side):
    """IK vector (palm point, finger dir, palm normal, twist) of the relaxed hanging hand in the rest-aligned frame."""
    if side not in _HANG:
        p, sol = PR.finish(stand())
        ib = RIG.sk.i(f"hand_{side}")
        Dh = sol.Q[ib]
        r = RIG.hand_rest[side]
        palm = sol.head(f"attach_hand_{side}")
        _HANG[side] = np.concatenate([palm, Dh @ r["d"], Dh @ r["n"], [0.0]])
    return _HANG[side].copy()


def ik_hand(point, finger_dir, palm_n, twist=0.0):
    return np.concatenate([np.asarray(point, float), unit(finger_dir), unit(palm_n), [twist]])


def FT(side, x, f, z, pitch=0.0, roll=0.0, yaw=0.0):
    """Foot target vector from forward distance f (positive = forward)."""
    return np.array([x, -f, z, pitch, roll, yaw], float)


ANKLE_Z = float(RIG.ankle_rest["L"][2])
HIP_Z = float(RIG.hip_rest["L"][2])
