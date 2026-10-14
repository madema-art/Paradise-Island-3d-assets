"""
Parameter-level authoring: a clip is a function (or keyposes) producing a *parameter set*; `build()` turns it into a Pose and
solves it. Parameters are plain numpy vectors so keyposes can be interpolated with splines.

Frames: world == the (fixed) root frame. IK targets can also be given relative to the pelvis / chest / head, following their
current orientation ("space").
"""
import numpy as np
from scipy.spatial.transform import Rotation as Rot

import pose_lib as PL
from kin import I3, Rx, Rz, axis_angle, euler, unit
from pose_lib import RIG, SIDES, SIGN, Pose, solve

FACE_KEYS = ["jaw", "jaw_side", "smile_L", "smile_R", "frown", "pucker", "lip_up", "lip_low", "brow_L", "brow_R", "furrow",
             "blink_L", "blink_R", "wide", "squint", "cheek", "jaw_fwd"]
FIN_NAMES = ["index", "middle", "ring", "pinky"]
GRIP_KEYS = [f"{f}{k}" for f in FIN_NAMES for k in range(3)] + ["spread", "th_opp", "th_1", "th_2", "th_3"]   # 17


def grip_vec(name, amount=1.0, spread=0.0):
    g = PL.GRIPS[name]
    v = []
    for fi, fn in enumerate(FIN_NAMES):
        f = g["f"]
        if name == "point":
            f = (-5, -8, -4) if fn == "index" else (66, 78, 52)
        v += [x * amount for x in f]
    v.append(spread)
    v += [x * amount for x in g["th"]]
    return np.array(v, float)


def DEFAULT():
    d = {
        "root": np.zeros(4),            # x, y, z, yaw (anchored clips only; locomotion keeps this at zero)
        "pel": np.zeros(6),             # dx, dy, dz, pitch, roll, yaw
        "pel_auto": np.array([0.0, 0.0, 0.0]),   # enabled, margin (m), extra
        "sp": np.zeros(3), "hd": np.zeros(3), "eye": np.zeros(2),
        "look": np.zeros(4),            # target xyz + amount
        "armL_w": np.zeros(1), "armR_w": np.zeros(1),             # IK weight when arm_mode is 'blend' (0 = FK, 1 = IK)
        "armL": np.zeros(6), "armR": np.zeros(6),                 # FK: fwd, out, twist, elbow, wrist flex, wrist dev
        "armL_ik": np.zeros(10), "armR_ik": np.zeros(10),         # IK: palm xyz, finger dir xyz, palm normal xyz, pole twist
        "fL": np.zeros(17), "fR": np.zeros(17),
        "ftL": np.zeros(6), "ftR": np.zeros(6),                    # ankle xyz target + foot rot (pitch, roll, yaw)
        "toeL": np.zeros(2), "toeR": np.zeros(2),                  # toes curl, hallux curl
        "poleL": np.zeros(3), "poleR": np.zeros(3),                # optional knee pole directions (0 = default)
        "face": np.zeros(len(FACE_KEYS)),
        "staff": np.concatenate([RIG.sk.head[RIG.sk.i("prop_staff")], np.zeros(3)]),   # position (staff butt = bone head) + euler delta; default = parked
        "aux": np.concatenate([RIG.sk.head[RIG.sk.i("prop_aux")], np.zeros(3)]),
    }
    return d


REST_FOOT = {t: RIG.ankle_rest[t] for t in SIDES}


def default_feet(d=None):
    d = d or DEFAULT()
    for t in SIDES:
        d[f"ft{t}"] = np.concatenate([REST_FOOT[t], np.zeros(3)])
    return d


def base():
    return default_feet(DEFAULT())


def mix(a, b, t):
    return {k: a[k] + (b[k] - a[k]) * t for k in a}


def copy(d):
    return {k: v.copy() for k, v in d.items()}


def update(d, **kw):
    d = copy(d)
    for k, v in kw.items():
        v = np.asarray(v, float)
        if k in d and d[k].shape != v.shape:
            if v.size <= d[k].size:
                nv = d[k].copy()
                nv[:v.size] = v.ravel()
                v = nv
        d[k] = v
    return d


def foot_target(side, f, x=None, yaw=0.0, pitch=0.0, roll=0.0, lift=0.0, pivot="flat"):
    """Ankle target + rotation for a sole placed at forward distance `f` (positive = forward), lateral x (default rest x)."""
    x = RIG.ankle_rest[side][0] if x is None else x
    pts = RIG.foot_pts[side]
    R = Rz(yaw) @ Rx(pitch) @ axis_angle([0, 1, 0], roll)
    key = {"flat": "ball", "heel": "heel", "ball": "ball", "toe": "toe"}[pivot]
    if pivot == "flat":
        # reference: ankle directly above (x, -f) at rest height, foot flat
        ankle = np.array([x, -f, RIG.ankle_rest[side][2] + lift])
        return np.concatenate([ankle, [pitch, roll, yaw]])
    piv = np.array([x, -f, lift]) - R @ pts[key]
    return np.concatenate([piv, [pitch, roll, yaw]])


def to_body(pt, root_pos, root_yaw):
    """World point -> body (root) frame."""
    return Rz(-root_yaw) @ (np.asarray(pt, float) - np.asarray(root_pos, float))


# -------------------------------------------------------------------------------------------------------- build
ELBOW_SIGN = {}


def _elbow_sign(side):
    if side in ELBOW_SIGN:
        return ELBOW_SIGN[side]
    ik = RIG.ik[("arm", side)]
    a2 = ik.a2_rest
    R = axis_angle(ik.n_rest, 20.0)
    moved = R @ a2
    ELBOW_SIGN[side] = 1.0 if moved[1] < a2[1] else -1.0       # forward = -Y: a flexing elbow brings the hand forward
    return ELBOW_SIGN[side]


def arm_fk(p, side, v):
    """FK arm: fwd/out/twist at the shoulder (degrees; fwd + = swing forward, out + = away from the body), elbow flexion,
    wrist flexion (+ = fingers swing forward) and wrist deviation."""
    fwd, out, tw, elb, wf, wd = v
    s = SIGN[side]
    ik = RIG.ik[("arm", side)]
    Du = axis_angle([0, 1, 0], -s * out) @ axis_angle([1, 0, 0], -fwd) @ axis_angle(ik.a1_rest, tw)
    p._extraD[f"upper_arm_{side}"] = Du
    p._extraD[f"forearm_{side}"] = axis_angle(ik.n_rest, _elbow_sign(side) * elb)
    p._extraD[f"hand_{side}"] = axis_angle([1, 0, 0], -wf) @ axis_angle([0, 1, 0], -s * wd)


def build(prm, solve_it=True):
    p = Pose()
    p._extraD = {}
    root = prm["root"]
    p.root_pos = root[:3].copy()
    p.root_yaw = float(root[3])
    pel = prm["pel"]
    p.pelvis_off = pel[:3].copy()
    PL.pelvis(p, pel[3], pel[4], pel[5])
    PL.spine(p, *prm["sp"])
    PL.head(p, *prm["hd"])
    PL.eyes(p, prm["eye"][0], prm["eye"][1])
    # fingers / toes
    for t, k in (("L", "fL"), ("R", "fR")):
        v = prm[k]
        for fi, fn in enumerate(FIN_NAMES):
            p.fingers[t][fn] = (v[fi * 3: fi * 3 + 3].copy(), float(v[12]) * (1.0 - 0.33 * fi))
        p.thumb[t] = tuple(v[13:17])
    for t in SIDES:
        p.toes[t], p.hallux[t] = float(prm[f"toe{t}"][0]), float(prm[f"toe{t}"][1])
    fv = prm["face"]
    kw = {k: float(fv[i]) for i, k in enumerate(FACE_KEYS)}
    smile_L, smile_R = kw.pop("smile_L"), kw.pop("smile_R")
    brow_L, brow_R = kw.pop("brow_L"), kw.pop("brow_R")
    blink_L, blink_R = kw.pop("blink_L"), kw.pop("blink_R")
    PL.face(p, smile_L=smile_L, smile_R=smile_R, brow_L=brow_L, brow_R=brow_R, blink_L=blink_L, blink_R=blink_R, **kw)
    for key, spec in (("staff", "prop_staff"), ("aux", "prop_aux")):
        v = prm[key]
        p.props[spec] = (v[:3], euler(*v[3:6]))
    return p


ARM_MODE = {}      # per clip: {'L': 'fk'|'ik', 'R': ...}; set by the clip wrapper through `finish()`
SPACES = {"world": None, "pelvis": "pelvis", "chest": "spine4", "head": "head"}


def finish(prm, arm_mode=("fk", "fk"), arm_space=("world", "world"), stance=(False, False), extra=None, ground=0.0):
    """Turn a parameter set into a solved pose. Returns (Pose, Solved)."""
    sk = RIG.sk
    p = build(prm)
    # FK arms (also used as the FK half of a blend)
    for t, mode in zip(SIDES, arm_mode):
        if mode in ("fk", "blend"):
            arm_fk(p, t, prm[f"arm{t}"])
    p.pelvis_off = p.pelvis_off.copy()
    # foot IK (body frame)
    for t in SIDES:
        v = prm[f"ft{t}"]
        PL.leg_ik(p, t, v[:3], foot_rot=Rz(v[5]) @ Rx(v[3]) @ axis_angle([0, 1, 0], v[4]))
        if np.any(prm[f"pole{t}"]):
            p.leg[t]["pole"] = unit(prm[f"pole{t}"])
        if ground is not None:          # keep the foot on or above the ground plane (no sinking while it rotates)
            R = p.leg[t]["foot_rot"]
            pts = RIG.foot_pts[t]
            low = min((R @ pts[k])[2] for k in ("heel", "ball", "toe"))
            z = p.leg[t]["target"][2] + low
            if z < ground:
                p.leg[t]["target"] = p.leg[t]["target"] + np.array([0, 0, ground - z])
    D_extra = dict(p._extraD)
    sol0 = solve(p, extra_D=D_extra)
    # IK arms; targets in a body frame need the torso orientation
    for t, mode, space in zip(SIDES, arm_mode, arm_space):
        if mode == "fk":
            continue
        v = prm[f"arm{t}_ik"]
        pt, fd, pn = v[:3].copy(), v[3:6].copy(), v[6:9].copy()
        if space != "world":
            b = SPACES[space]
            ib = sk.i(b)
            Q = sol0.Q[ib]
            H0 = sk.head[ib]
            pt = sol0.Hw[ib] + Q @ (pt - H0)
            fd, pn = Q @ fd, Q @ pn
        PL.arm_to_point(p, t, pt, fd, pn, twist=float(v[9]))
    blend_miss = {}
    if "blend" in arm_mode:
        sol_ik = solve(p, extra_D=D_extra)
        for t, mode in zip(SIDES, arm_mode):
            if mode != "blend":
                continue
            w = float(np.clip(prm[f"arm{t}_w"][0], 0.0, 1.0))
            blend_miss[f"arm_{t}"] = p.report.get(f"arm_{t}", 0.0) * w          # the IK reach error counts in proportion to the IK weight
            for bone in (f"upper_arm_{t}", f"forearm_{t}", f"hand_{t}", f"forearm_tw1_{t}", f"forearm_tw2_{t}"):
                Rf = D_extra.get(bone, I3)
                Ri = sol_ik.D.get(bone, I3)
                rel = Rot.from_matrix(Rf.T @ Ri).as_rotvec()
                D_extra[bone] = Rf @ Rot.from_rotvec(rel * w).as_matrix()
            p.arm[t] = None
    # auto pelvis height so the stance legs can reach their targets
    auto = prm["pel_auto"]
    if auto[0] > 0.5:
        sol1 = solve(p, extra_D=D_extra)
        excess = 0.0
        for t, st in zip(SIDES, stance):
            if not st:
                continue
            ik = RIG.ik[("leg", t)]
            hip = sol1.head(f"thigh_{t}")
            ankle = p.root_pos + Rz(p.root_yaw) @ p.leg[t]["target"]        # IK targets are root-local
            reach = (ik.L1 + ik.L2) * (0.985 - auto[1])
            dh = np.hypot(*(ankle[:2] - hip[:2]))
            allowed = np.sqrt(max(reach ** 2 - dh ** 2, 0.0))
            excess = max(excess, (hip[2] - ankle[2]) - allowed)
        if excess > 0:
            p.pelvis_off = p.pelvis_off + np.array([0, 0, -excess])
        p.pelvis_off = p.pelvis_off + np.array([0, 0, auto[2]])
    # look-at (after the torso has settled)
    look = prm["look"]
    if look[3] > 1e-4:
        sol1 = solve(p, extra_D=D_extra)
        _look(p, sol1, p.root_pos + Rz(p.root_yaw) @ look[:3], float(look[3]))
    sol = solve(p, extra_D=D_extra)
    p.report.update(blend_miss)
    p._extraD = D_extra
    return p, sol


def _yaw_pitch(v):
    return np.degrees(np.arctan2(v[0], -v[1])), -np.degrees(np.arctan2(v[2], np.hypot(v[0], v[1])))


def _look(p, sol, target, amount):
    sk = RIG.sk
    ih = sk.i("head")
    Qh = sol.Q[ih]
    head = sol.Hw[ih] + sol.Rw[ih] @ np.array([0.0, 0.0, 0.0])
    eye_c = sol.Hw[ih] + Qh @ (RIG.head_c - sk.head[ih])
    v = np.asarray(target, float) - eye_c
    yaw_t, pitch_t = _yaw_pitch(v)
    cur = Qh @ np.array([0.0, -1.0, 0.0])
    yaw_c, pitch_c = _yaw_pitch(cur)
    dy = (yaw_t - yaw_c + 180) % 360 - 180
    dp = pitch_t - pitch_c
    dy, dp = dy * amount, dp * amount
    hy = float(np.clip(dy * 0.6, -60, 60))
    hp = float(np.clip(dp * 0.6, -35, 40))
    PL.head(p, hp, 0.0, hy)
    ey = float(np.clip(dy - hy, -30, 30))
    ep = float(np.clip(dp - hp, -25, 25))
    PL.eyes(p, ey, ep)
