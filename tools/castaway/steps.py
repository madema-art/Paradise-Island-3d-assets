"""
Foot-step planner: feet are planted in WORLD space during stance (heel strike -> flat -> heel-off -> toe-off) and swing on
arcs between steps. The character root follows a virtual world path (position, yaw) given by the clip, so the baked clip
(root fixed) shows planted feet that move backwards under the body at exactly the clip's ground speed.

Foot pose in the baked (body) frame = inverse root transform applied to the world foot pose.
"""
from dataclasses import dataclass, field

import numpy as np

from kin import Rz, Rx, axis_angle
from pose_lib import RIG

HEEL_OFF = {t: RIG.foot_pts[t]["heel"] for t in ("L", "R")}
BALL_OFF = {t: RIG.foot_pts[t]["ball"] for t in ("L", "R")}
ANKLE_Z = RIG.ankle_rest["L"][2]


@dataclass
class Step:
    t0: float                 # heel strike time
    t1: float                 # toe-off time
    x: float                  # world position of the flat foot's ankle (x lateral, f forward)
    f: float
    yaw: float = 0.0          # world yaw (deg)
    z: float = 0.0            # surface height under the foot
    tilt: float = 0.0         # surface pitch (deg), for slopes
    note: str = ""


@dataclass
class Cfg:
    heel_pitch: float = 16.0      # toes-up angle at heel strike
    toe_pitch: float = 34.0       # heel-up angle at toe-off
    roll_on: float = 0.14         # fraction of stance spent rolling on the heel
    heel_off: float = 0.50        # fraction of stance when the heel lifts
    lift: float = 0.13            # swing foot clearance (m)
    lift_peak: float = 0.45       # where in the swing the clearance peaks
    toe_clear: float = 8.0        # extra toe-up in mid swing
    swing_ease: float = 0.55      # 0 = linear, 1 = fully smoothed horizontal travel


def _rot(yaw, pitch):
    return Rz(yaw) @ Rx(pitch)


def _ankle_from_pivot(side, pivot, pivot_pos, yaw, pitch, z_base):
    """Ankle world position when the heel/ball pivot sits at pivot_pos (x, f) on a surface z_base."""
    pts = {"heel": HEEL_OFF[side], "ball": BALL_OFF[side]}[pivot]
    R = _rot(yaw, pitch)
    piv = np.array([pivot_pos[0], -pivot_pos[1], z_base])
    return piv - R @ pts


def _flat_ankle(step):
    return np.array([step.x, -step.f, ANKLE_Z + step.z])


def _contact_points(side, step):
    """World (x, f) of the heel and ball for the flat foot on this step."""
    R = _rot(step.yaw, 0.0)
    a = np.array([step.x, -step.f, 0.0])
    h = a + R @ HEEL_OFF[side]
    b = a + R @ BALL_OFF[side]
    return (h[0], -h[1]), (b[0], -b[1])


def _angdiff(a, b):
    return (b - a + 180.0) % 360.0 - 180.0


def stance_pose(side, step, s, cfg):
    """s in [0, 1] through the stance. Returns ankle (3), pitch, yaw."""
    (hx, hf), (bx, bf) = _contact_points(side, step)
    z = step.z
    if s < cfg.roll_on:
        u = s / cfg.roll_on
        pitch = -cfg.heel_pitch * (1 - u) ** 1.6
        return _ankle_from_pivot(side, "heel", (hx, hf), step.yaw, pitch, z), pitch
    if s < cfg.heel_off:
        return _flat_ankle(step), 0.0
    u = (s - cfg.heel_off) / (1 - cfg.heel_off)
    pitch = cfg.toe_pitch * u ** 1.5
    return _ankle_from_pivot(side, "ball", (bx, bf), step.yaw, pitch, z), pitch


def foot_state(t, steps, side, cfg=Cfg()):
    """Pose of one foot at time t. Returns dict(ankle, pitch, yaw, stance, z_contact)."""
    if not steps:
        return dict(ankle=np.array([RIG.ankle_rest[side][0], 0, ANKLE_Z]), pitch=0.0, yaw=0.0, stance=True, s=0.3)
    if t <= steps[0].t0:
        st = steps[0]
        return dict(ankle=_flat_ankle(st), pitch=0.0, yaw=st.yaw, stance=True, s=0.3)
    if t >= steps[-1].t1:
        st = steps[-1]
        return dict(ankle=_flat_ankle(st), pitch=0.0, yaw=st.yaw, stance=True, s=0.3)
    for i, st in enumerate(steps):
        if st.t0 <= t <= st.t1:
            s = (t - st.t0) / max(st.t1 - st.t0, 1e-6)
            a, pitch = stance_pose(side, st, s, cfg)
            return dict(ankle=a, pitch=pitch, yaw=st.yaw, stance=True, s=s)
        if i + 1 < len(steps) and st.t1 < t < steps[i + 1].t0:
            nx = steps[i + 1]
            s = (t - st.t1) / (nx.t0 - st.t1)
            a0, p0 = stance_pose(side, st, 1.0, cfg)
            a1, p1 = stance_pose(side, nx, 0.0, cfg)
            e = cfg.swing_ease * (s * s * (3 - 2 * s)) + (1 - cfg.swing_ease) * s
            a = a0 + (a1 - a0) * e
            lift = cfg.lift * (np.sin(np.pi * s ** (np.log(0.5) / np.log(cfg.lift_peak))) ** 1.15)
            a = a + np.array([0, 0, lift])
            sm = lambda u: u * u * (3 - 2 * u)
            if s < 0.45:
                pitch = p0 + (-cfg.toe_clear - p0) * sm(s / 0.45)
            else:
                pitch = -cfg.toe_clear + (p1 + cfg.toe_clear) * sm((s - 0.45) / 0.55)
            yaw = st.yaw + _angdiff(st.yaw, nx.yaw) * e
            return dict(ankle=a, pitch=pitch, yaw=yaw, stance=False, s=-1.0)
    st = steps[-1]
    return dict(ankle=_flat_ankle(st), pitch=0.0, yaw=st.yaw, stance=True, s=0.3)


def to_body_foot(fs, root_pos, root_yaw, side):
    """World foot state -> params vector entries (ankle in body frame, pitch, roll, yaw)."""
    a = Rz(-root_yaw) @ (fs["ankle"] - np.asarray(root_pos, float))
    return np.concatenate([a, [fs["pitch"], 0.0, fs["yaw"] - root_yaw]])


def regular_steps(side, v, T, duty, t_start, n, x, phase=0.0, yaw=0.0, z=0.0):
    """Steps for a steady gait moving along -Y at speed v (world f = v*t). The ankle sits under the body at mid-stance."""
    out = []
    for k in range(-2, n + 2):
        t0 = t_start + (k + phase) * T
        f = v * (t0 + duty * T * 0.5)
        out.append(Step(t0, t0 + duty * T, x, f, yaw, z))
    return out
