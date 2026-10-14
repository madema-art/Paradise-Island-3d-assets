"""Steady-state walk/run generator built on the step planner."""
from dataclasses import dataclass, field

import numpy as np

import params as PR
import steps as ST
from clipkit import smooth
from kin import Rz
from pose_lib import RIG
import rigkit as RK

TAU = 2 * np.pi


@dataclass
class Gait:
    T: float = 1.12
    v: float = 1.45
    duty: float = 0.62
    x: float = 0.092                    # lateral ankle offset (half step width)
    toe_out: float = 6.0
    foot: ST.Cfg = field(default_factory=ST.Cfg)
    z0: float = -0.030                  # pelvis drop in mid-stance (knees stay softly bent)
    bob: float = 0.020
    sway: float = 0.020
    roll: float = 3.0
    pyaw: float = 5.0
    syaw: float = 9.0
    arm: float = 24.0
    elbow0: float = 16.0
    elbow1: float = 16.0
    lean: float = 2.0
    out: float = -19.0
    head_stab: float = 0.85
    spine_roll: float = 1.5
    run: bool = False
    gripL: str = "relaxed"
    gripR: str = "relaxed"


def make_steps(g, n=3):
    cyc = int(np.ceil(n))
    L = ST.regular_steps("L", g.v, g.T, g.duty, 0.0, cyc, +g.x, 0.0, +g.toe_out)
    R = ST.regular_steps("R", g.v, g.T, g.duty, 0.0, cyc, -g.x, 0.5, -g.toe_out)
    return L, R


def gait_params(t, g, steps=None, base=None):
    """One frame of a steady gait. Returns (prm, opts) with arms in FK mode (callers may override the arms)."""
    L, R = steps or make_steps(g)
    p = base or RK.stand()
    ph = (t / g.T) % 1.0
    root = np.array([0.0, -g.v * t, 0.0])
    fl = ST.foot_state(t, L, "L", g.foot)
    fr = ST.foot_state(t, R, "R", g.foot)
    p["ftL"] = ST.to_body_foot(fl, root, 0.0, "L")
    p["ftR"] = ST.to_body_foot(fr, root, 0.0, "R")
    # weight-bearing weights for the pelvis sway (smooth hump during stance)
    wl = np.sin(np.pi * fl["s"]) if fl["stance"] else 0.0
    wr = np.sin(np.pi * fr["s"]) if fr["stance"] else 0.0
    c = np.cos(TAU * ph)
    bobv = g.bob * np.cos(2 * TAU * (ph - g.duty * 0.5)) if not g.run else g.bob * np.cos(2 * TAU * (ph - g.duty * 0.5))
    dx = g.sway * (wl - wr)
    roll = -g.roll * (wl - wr)
    pyaw = -g.pyaw * c
    syaw = g.syaw * c
    p["pel"] = np.array([dx, 0.0, g.z0 + bobv, 0.0, roll, pyaw])
    p["pel_auto"] = np.array([1.0, 0.02, 0.0])
    p["sp"] = np.array([g.lean, -roll * 0.6 + g.spine_roll * np.sin(TAU * ph), syaw])
    p["hd"] = np.array([-g.lean * 0.7, roll * 0.3, -(pyaw + syaw) * g.head_stab])
    # arms: opposite to the legs
    swing = g.arm
    fwdL = -swing * c
    fwdR = +swing * c
    eL = g.elbow0 + g.elbow1 * (0.5 + 0.5 * (fwdL / max(swing, 1e-6)))
    eR = g.elbow0 + g.elbow1 * (0.5 + 0.5 * (fwdR / max(swing, 1e-6)))
    p["armL"] = np.array([fwdL, g.out, 0.0, eL, 0, 0])
    p["armR"] = np.array([fwdR, g.out, 0.0, eR, 0, 0])
    p["fL"] = RK.G(g.gripL)
    p["fR"] = RK.G(g.gripR)
    for side, fs in (("L", fl), ("R", fr)):
        tp = max(fs["pitch"], 0.0)
        p["toe" + side] = np.array([-0.9 * tp, -0.9 * tp])      # toes stay flat on the ground while the heel lifts
    opts = dict(arm_mode=("fk", "fk"), stance=(True, True), world=dict(pos=tuple(root), yaw=0.0))
    return p, opts
