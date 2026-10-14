"""
Pose authoring layer for the castaway: Pose (what you set per frame) -> solved skeleton via analytic FK/IK.

Everything is in the same world axes as the model: faces -Y, +X = his left, +Z up. Angles in degrees.
Helpers return Pose edits so clips stay short: spine/neck distribution, hand grips, face expressions, foot placement,
prop-relative hand targets.
"""
import json
import os
from collections import defaultdict

import numpy as np

from kin import (I3, Rx, Rz, Skeleton, TwoBoneIK, axis_angle, euler, frame, twist_about, unit)

HERE = os.path.dirname(os.path.abspath(__file__))
SIDES = ("L", "R")
SIGN = {"L": 1.0, "R": -1.0}
FINGERS = ("index", "middle", "ring", "pinky")
FPS = 30


def lerp(a, b, t):
    return a + (b - a) * t


def smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def seg(t, a, b):
    return float(np.clip((t - a) / (b - a), 0.0, 1.0)) if b != a else (1.0 if t >= b else 0.0)


class Rig:
    """Static data derived from the rest pose: IK chains, hand frames, foot contact points."""

    def __init__(self, path=None):
        self.sk = Skeleton(path)
        sk = self.sk
        meta = json.load(open(path or os.path.join(HERE, "rest_pose.json")))
        self.lm = {k: v for k, v in meta.get("landmarks", {}).items()}
        self.ik = {}
        for t in SIDES:
            self.ik[("arm", t)] = TwoBoneIK(sk, f"upper_arm_{t}", f"forearm_{t}", f"hand_{t}", fallback_pole=(0, 1, 0))
            self.ik[("leg", t)] = TwoBoneIK(sk, f"thigh_{t}", f"shin_{t}", f"foot_{t}", fallback_pole=(0, -1, 0))
        self.hand_rest = {}
        for t in SIDES:
            d, fw, n = (np.array(v) for v in self.lm[f"hand_frame_{t}"])
            self.hand_rest[t] = dict(d=d, fw=fw, n=n, F=frame(d, n))
        # palm contact centre relative to the wrist, in the hand's rest-world axes
        self.palm_off = {t: sk.head[sk.i(f"attach_hand_{t}")] - sk.head[sk.i(f"hand_{t}")] for t in SIDES}
        # foot contact points relative to the ankle (rest-world axes): heel, ball, toe tip
        self.foot_pts = {}
        for t in SIDES:
            a = sk.head[sk.i(f"foot_{t}")]
            self.foot_pts[t] = dict(heel=np.array([0.0, 0.056, -a[2]]), ball=np.array([0.0, -0.150, -a[2]]),
                                    toe=np.array([0.0, -0.238, -a[2] + 0.004]), ankle_h=a[2])
        self.ankle_rest = {t: sk.head[sk.i(f"foot_{t}")].copy() for t in SIDES}
        self.shoulder_rest = {t: sk.head[sk.i(f"upper_arm_{t}")].copy() for t in SIDES}
        self.hip_rest = {t: sk.head[sk.i(f"thigh_{t}")].copy() for t in SIDES}
        self.wrist_rest = {t: sk.head[sk.i(f"hand_{t}")].copy() for t in SIDES}
        self.flex_axis = {t: unit(np.cross(self.hand_rest[t]["d"], self.hand_rest[t]["n"])) for t in SIDES}
        self.head_c = np.array(self.lm["head_c"])
        self.eye_c = {t: np.array(self.lm[f"eye_{t}"]) for t in SIDES}


RIG = Rig()


class Pose:
    """One frame. Defaults reproduce the rest A-pose."""

    def __init__(self):
        self.root_pos = np.zeros(3)
        self.root_yaw = 0.0
        self.pelvis_off = np.zeros(3)
        self.fk = defaultdict(lambda: np.zeros(3))      # bone -> (pitch, roll, yaw) added together
        self.tr = defaultdict(lambda: np.zeros(3))      # bone -> world-axis translation offset
        self.arm = {"L": None, "R": None}               # dict(target, twist, pole, hand) when IK driven
        self.leg = {"L": None, "R": None}
        self.hand_fk = {"L": np.zeros(3), "R": np.zeros(3)}   # (pitch, roll, yaw) of the hand relative to the forearm (FK mode)
        self.fingers = {t: {} for t in SIDES}            # finger -> (flex deltas [mcp,pip,dip], spread)
        self.thumb = {"L": (0.0, 0.0, 0.0, 0.0), "R": (0.0, 0.0, 0.0, 0.0)}   # (opposition, flex1, flex2, flex3)
        self.toes = {"L": 0.0, "R": 0.0}
        self.hallux = {"L": 0.0, "R": 0.0}
        self.props = {}                                  # bone -> (pos, euler world delta)
        self.arm_fk = {"L": None, "R": None}             # FK arm: (upper (p,r,y), forearm (p,r,y))
        self.report = {}

    def copy(self):
        import copy
        return copy.deepcopy(self)


# --------------------------------------------------------------------------------------------------------------------
# spine / head
SPINE_W = {"spine1": 0.25, "spine2": 0.30, "spine3": 0.25, "spine4": 0.20}
NECK_W = {"neck1": 0.22, "neck2": 0.30, "head": 0.48}


def add_fk(p, bone, pitch=0.0, roll=0.0, yaw=0.0):
    p.fk[bone] = p.fk[bone] + np.array([pitch, roll, yaw], float)


def spine(p, pitch=0.0, roll=0.0, yaw=0.0):
    for b, w in SPINE_W.items():
        add_fk(p, b, pitch * w, roll * w, yaw * w)


def head(p, pitch=0.0, roll=0.0, yaw=0.0):
    for b, w in NECK_W.items():
        add_fk(p, b, pitch * w, roll * w, yaw * w)


def pelvis(p, pitch=0.0, roll=0.0, yaw=0.0):
    add_fk(p, "pelvis", pitch, roll, yaw)


def eyes(p, yaw=0.0, pitch=0.0, converge=0.0):
    """Gaze (degrees). +yaw = look to his left, +pitch = look down."""
    add_fk(p, "eye_L", pitch, 0, yaw - converge)
    add_fk(p, "eye_R", pitch, 0, yaw + converge)


# --------------------------------------------------------------------------------------------------------------------
# hands
GRIPS = {
    # name: per finger [mcp, pip, dip] deltas relative to the relaxed rest curl, thumb (opp, f1, f2, f3)
    "rest": dict(f=(0, 0, 0), th=(0, 0, 0, 0)),
    "relaxed": dict(f=(8, 10, 6), th=(0, 2, 4, 2)),
    "open": dict(f=(-28, -38, -18), th=(-10, -6, -8, -6)),
    "flat": dict(f=(-34, -55, -32), th=(-14, -8, -10, -8)),
    "fist": dict(f=(62, 70, 48), th=(18, 10, 18, 14)),
    "grip_staff": dict(f=(52, 62, 40), th=(20, 8, 16, 12)),
    "grip_thin": dict(f=(60, 74, 50), th=(22, 12, 18, 14)),
    "grip_big": dict(f=(40, 48, 26), th=(16, 6, 12, 8)),
    "cup": dict(f=(22, 30, 14), th=(10, 6, 8, 6)),
    "point": dict(f=(None, None, None), th=(0, 0, 0, 0)),
    "pinch": dict(f=(30, 40, 24), th=(30, 14, 22, 16)),
}


def grip(p, side, name="relaxed", amount=1.0, spread=0.0, **overrides):
    g = GRIPS[name]
    p.thumb[side] = tuple(np.array(g["th"], float) * amount)
    for i, fn in enumerate(FINGERS):
        f = g["f"]
        if name == "point":
            f = (-5, -8, -4) if fn == "index" else (66, 78, 52)
        val = np.array(f, float) * amount
        p.fingers[side][fn] = (val, spread * (1.0 - 0.33 * i) if spread else 0.0)
    for fn, (vals, spr) in overrides.items():
        p.fingers[side][fn] = (np.array(vals, float), spr)


def grip_lerp(p, side, a, b, t):
    ga, gb = GRIPS[a], GRIPS[b]
    grip(p, side, a, 1.0)
    pa = {k: v for k, v in p.fingers[side].items()}
    th_a = p.thumb[side]
    grip(p, side, b, 1.0)
    for fn in FINGERS:
        p.fingers[side][fn] = (lerp(pa[fn][0], p.fingers[side][fn][0], t), lerp(pa[fn][1], p.fingers[side][fn][1], t))
    p.thumb[side] = tuple(lerp(np.array(th_a), np.array(p.thumb[side]), t))


# --------------------------------------------------------------------------------------------------------------------
# face
def face(p, jaw=0.0, jaw_side=0.0, smile=0.0, smile_L=None, smile_R=None, frown=0.0, pucker=0.0, lip_up=0.0, lip_low=0.0,
         brow_raise=0.0, brow_L=None, brow_R=None, furrow=0.0, blink=0.0, blink_L=None, blink_R=None, wide=0.0,
         squint=0.0, cheek=0.0, jaw_fwd=0.0):
    """Facial expression controls. All 0..1 unless noted. jaw in degrees (open), jaw_side in degrees (+ = to his left)."""
    add_fk(p, "jaw", jaw, 0, jaw_side)
    if jaw_fwd:
        p.tr["jaw"] = p.tr["jaw"] + np.array([0, -jaw_fwd, 0])
    sl = smile if smile_L is None else smile_L
    sr = smile if smile_R is None else smile_R
    for t, sm in (("L", sl), ("R", sr)):
        s = SIGN[t]
        up = sm * 0.011 - frown * 0.006
        out = sm * 0.009 - pucker * 0.010
        p.tr[f"lip_corner_{t}"] = p.tr[f"lip_corner_{t}"] + np.array([s * out, -pucker * 0.004, up])
        p.tr[f"cheek_{t}"] = p.tr[f"cheek_{t}"] + np.array([0, -0.001 * sm, (sm * 0.007 + cheek * 0.008 + squint * 0.004)])
    p.tr["lip_up"] = p.tr["lip_up"] + np.array([0, -pucker * 0.006, lip_up * 0.006 + (sl + sr) * 0.5 * 0.002])
    p.tr["lip_low"] = p.tr["lip_low"] + np.array([0, -pucker * 0.005, lip_low * 0.006 - (sl + sr) * 0.5 * 0.001])
    bl = brow_L if brow_L is not None else brow_raise
    br = brow_R if brow_R is not None else brow_raise
    for t, b in (("L", bl), ("R", br)):
        s = SIGN[t]
        for part, k_up, k_in in (("in", 1.0, 1.0), ("mid", 1.0, 0.0), ("out", 0.8, -0.3)):
            up = b * 0.010 * k_up - furrow * 0.006 * (1.0 if part == "in" else 0.5) - squint * 0.002
            inward = -s * furrow * 0.006 * k_in
            p.tr[f"brow_{part}_{t}"] = p.tr[f"brow_{part}_{t}"] + np.array([inward, 0, up])
    cl = blink if blink_L is None else blink_L
    cr = blink if blink_R is None else blink_R
    for t, c in (("L", cl), ("R", cr)):
        up = c * 24.0 - wide * 9.0 + squint * 8.0
        low = -(c * 15.0) - wide * 3.0 - squint * 8.0
        add_fk(p, f"lid_up_{t}", up, 0, 0)
        add_fk(p, f"lid_low_{t}", low, 0, 0)


# --------------------------------------------------------------------------------------------------------------------
# limbs
def arm_ik(p, side, target, hand_dirs=None, hand_rel=None, twist=0.0, pole=None):
    """Drive an arm with IK. target = world position of the WRIST. hand_dirs = (finger_dir, palm_normal) world vectors
    (absolute hand orientation); hand_rel = (pitch, roll, yaw) relative to the forearm instead."""
    p.arm[side] = dict(target=np.asarray(target, float), twist=twist, pole=pole, hand_dirs=hand_dirs, hand_rel=hand_rel)


def arm_to_point(p, side, palm_point, finger_dir, palm_n, twist=0.0, pole=None):
    """Place the palm centre at palm_point with the hand oriented by (finger_dir, palm_normal) in world."""
    Dh = hand_delta(side, finger_dir, palm_n)
    Rw = Dh @ RIG.sk.Rrest[RIG.sk.i(f"hand_{side}")]
    wrist = np.asarray(palm_point, float) - Dh @ RIG.palm_off[side]
    arm_ik(p, side, wrist, hand_dirs=(finger_dir, palm_n), twist=twist, pole=pole)
    return wrist


def hand_delta(side, finger_dir, palm_n):
    r = RIG.hand_rest[side]
    Fn = frame(finger_dir, palm_n)
    return Fn @ r["F"].T


def leg_ik(p, side, ankle, foot_rot=None, twist=0.0, pole=None):
    """foot_rot = world delta rotation matrix of the foot (default: rest, flat)."""
    p.leg[side] = dict(target=np.asarray(ankle, float), twist=twist, pole=pole, foot_rot=I3 if foot_rot is None else foot_rot)


def foot_at(p, side, xy, yaw=0.0, pitch=0.0, pivot="flat", lift=0.0, roll=0.0):
    """Place the foot with the given sole pivot on/above the ground. pitch>0 = toes down (heel up).
    pivot: 'flat' (heel point as reference, usually with pitch 0), 'heel', 'ball', 'toe'. xy = pivot point world (x,y)."""
    pts = RIG.foot_pts[side]
    R = Rz(yaw) @ Rx(pitch) @ axis_angle([0, 1, 0], roll)
    key = {"flat": "ball", "heel": "heel", "ball": "ball", "toe": "toe"}[pivot]
    pivot_off = pts[key]
    ankle_off = np.zeros(3)
    target_pivot = np.array([xy[0], xy[1], lift])
    ankle = target_pivot + R @ (ankle_off - pivot_off)
    leg_ik(p, side, ankle, foot_rot=R)
    return ankle


def foot_pos_from_ankle(ankle, side, yaw=0.0, pitch=0.0):
    """Sole contact points in world for a given ankle placement (for QA)."""
    pts = RIG.foot_pts[side]
    R = Rz(yaw) @ Rx(pitch)
    return {k: ankle + R @ v for k, v in pts.items() if k != "ankle_h"}


# --------------------------------------------------------------------------------------------------------------------
def solve(p, extra_D=None, extra_tr=None):
    """Evaluate a Pose. Returns Solved (kin) and fills p.report with IK misses."""
    sk = RIG.sk
    D = {}
    tw = {}
    D["root"] = Rz(p.root_yaw)
    tw["root"] = np.asarray(p.root_pos, float)
    tw["pelvis"] = np.asarray(p.pelvis_off, float)
    for b, a in p.fk.items():
        if np.any(a):
            D[b] = D.get(b, I3) @ euler(*a)
    for b, o in p.tr.items():
        if np.any(o):
            tw[b] = tw.get(b, np.zeros(3)) + o
    # fingers
    for t in SIDES:
        s = SIGN[t]
        r = RIG.hand_rest[t]
        fa = RIG.flex_axis[t]
        for fn, (vals, spr) in p.fingers[t].items():
            for k in range(3):
                bn = f"f_{fn}_{k + 1}_{t}"
                R = axis_angle(fa, vals[k])
                if k == 0 and spr:
                    R = axis_angle(r["n"], spr) @ R
                D[bn] = R
        th = p.thumb[t]
        opp, f1, f2, f3 = th
        if any(th):
            # opposition swings the metacarpal across the palm (about the finger direction x palm normal axis), flexion curls it
            D[f"f_thumb_1_{t}"] = axis_angle(r["n"], -opp * s * 0.9) @ axis_angle(fa, f1)
            D[f"f_thumb_2_{t}"] = axis_angle(fa, f2)
            D[f"f_thumb_3_{t}"] = axis_angle(fa, f3)
        if p.toes[t]:
            for nm in ("toe2", "toe3", "toe4", "toe5"):
                D[f"{nm}_1_{t}"] = Rx(p.toes[t])
        if p.hallux[t]:
            D[f"hallux_1_{t}"] = Rx(p.hallux[t])
            D[f"hallux_2_{t}"] = Rx(p.hallux[t] * 0.7)
    if extra_D:
        D.update(extra_D)
    if extra_tr:
        tw.update(extra_tr)
    # props: world-space pose of free bones
    for bn, (pos, rot) in p.props.items():
        D[bn] = rot if isinstance(rot, np.ndarray) else euler(*rot)
        tw[bn] = np.asarray(pos, float) - sk.head[sk.i(bn)]
    sol0 = sk.evaluate(D, tw)
    report = {}
    for kind, sides in (("arm", p.arm), ("leg", p.leg)):
        for t, spec in sides.items():
            if spec is None:
                continue
            ik = RIG.ik[(kind, t)]
            iu = sk.i(ik.upper)
            par = sk.parent[iu]
            S = sol0.Hw[iu]
            Qp = sol0.Q[par]
            pole = spec["pole"] if spec["pole"] is not None else Qp @ ik.pole_rest
            Qu, Ql, E, Tact, miss = ik.solve(S, spec["target"], pole, spec["twist"])
            D[ik.upper] = Qp.T @ Qu
            D[ik.lower] = Qu.T @ Ql
            if kind == "arm":
                if spec["hand_dirs"] is not None:
                    Dh = hand_delta(t, *spec["hand_dirs"])
                    Dh_local = Ql.T @ Dh
                elif spec["hand_rel"] is not None:
                    Dh_local = euler(*spec["hand_rel"])
                else:
                    Dh_local = I3
                D[ik.end] = Dh_local
                twist = twist_about(Dh_local, RIG.ik[(kind, t)].a2_rest)
                if abs(twist) > 0.01:
                    ax = ik.a2_rest
                    D[f"forearm_tw1_{t}"] = axis_angle(ax, 0.35 * twist)
                    D[f"forearm_tw2_{t}"] = axis_angle(ax, 0.70 * twist)
            else:
                D[ik.end] = Ql.T @ spec["foot_rot"]
            report[f"{kind}_{t}"] = miss
    sol = sk.evaluate(D, tw)
    sol.D = D
    p.report = report
    return sol


# --------------------------------------------------------------------------------------------------------------------
def wrist_world(sol, side):
    return sol.head(f"hand_{side}")


def palm_world(sol, side):
    return sol.head(f"attach_hand_{side}")


def ground_points(sol, side):
    sk = RIG.sk
    foot = f"foot_{side}"
    Rw = sol.rot(foot)
    ank = sol.head(foot)
    pts = RIG.foot_pts[side]
    Rrest = sk.Rrest[sk.i(foot)]
    Dw = Rw @ Rrest.T
    return {k: ank + Dw @ v for k, v in pts.items() if k != "ankle_h"}
