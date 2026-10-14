"""Gait along an arbitrary virtual root path (start, stop, turns, direction changes), built on the step planner.

The clip is baked with the root fixed; the *world* path (speed, yaw) the controller should reproduce is exported as metadata.
Feet are planted in world space at the position of the path at mid-stance, so feet never slide if the controller follows the
exported speed/yaw curves.
"""
from dataclasses import dataclass, field

import numpy as np

import params as PR
import rigkit as RK
import steps as ST
from clipkit import smooth, seg
from gaitkit import Gait
from kin import Rz

TAU = 2 * np.pi


class Path:
    """Virtual root path from speed and yaw functions of time (integrated at 240 Hz)."""

    def __init__(self, speed_fn, yaw_fn, t_end, dt=1 / 240.0):
        self.t = np.arange(0, t_end + 2.0 + dt, dt)
        self.dt = dt
        self.yaw = np.array([yaw_fn(t) for t in self.t])
        self.v = np.array([speed_fn(t) for t in self.t])
        pos = np.zeros((len(self.t), 3))
        for i in range(1, len(self.t)):
            y = np.radians(self.yaw[i - 1])
            hd = np.array([np.sin(y), -np.cos(y), 0.0])
            pos[i] = pos[i - 1] + hd * self.v[i - 1] * dt
        self.pos = pos

    def at(self, t):
        if t < 0:                       # steady run-in before the clip starts: extrapolate backwards along the initial heading
            y = np.radians(self.yaw[0])
            hd = np.array([np.sin(y), -np.cos(y), 0.0])
            return self.pos[0] + hd * self.v[0] * t, float(self.yaw[0]), float(self.v[0])
        t = np.clip(t, self.t[0], self.t[-1])
        i = min(int(t / self.dt), len(self.t) - 2)
        u = t / self.dt - i
        return self.pos[i] * (1 - u) + self.pos[i + 1] * u, float(self.yaw[i] * (1 - u) + self.yaw[i + 1] * u), float(self.v[i] * (1 - u) + self.v[i + 1] * u)


def build_steps(path, g, t_first_land, side_first="L", n_steps=8, hold_start=None, hold_end=None, lat_scale=1.0, init_f=0.0, final_f=None,
                final_t=None, steady_start=False):
    """Steps for both feet. Left lands first at t_first_land (if side_first == 'L'). Positions: under the path at mid-stance."""
    T = g.T
    swing = (1 - g.duty) * T
    steps = {"L": [], "R": []}
    lat = {"L": +g.x * lat_scale, "R": -g.x * lat_scale}
    toe = {"L": +g.toe_out, "R": -g.toe_out}
    other = "R" if side_first == "L" else "L"
    # initial planted feet (standing) until they lift
    land = {side_first: t_first_land, other: t_first_land + T / 2}
    for side in ("L", "R"):
        lift = land[side] - swing
        if not steady_start:
            steps[side].append(ST.Step(-20.0, lift, lat[side], 0.0 if side == "L" else 0.0, 0.0))
    for k in range(-3 if steady_start else 0, n_steps):
        for side in ("L", "R"):
            t0 = land[side] + k * T
            t1 = t0 + g.duty * T
            tm = 0.5 * (t0 + t1)
            if final_t is not None and t1 > final_t:
                continue
            pm, ym, _ = path.at(tm)
            wp = pm + Rz(ym) @ np.array([lat[side], 0.0, 0.0])
            steps[side].append(ST.Step(t0, t1, wp[0], -wp[1], ym + toe[side]))
    return steps


def frame(t, g, path, steps, speed_ref, extra=None):
    """Params for time t. `speed_ref`: speed at which arm swing/bob are at full strength."""
    p = RK.stand()
    pos, yaw, v = path.at(t)
    s = float(np.clip(v / speed_ref, 0.0, 1.4))
    fl = ST.foot_state(t, steps["L"], "L", g.foot)
    fr = ST.foot_state(t, steps["R"], "R", g.foot)
    p["ftL"] = ST.to_body_foot(fl, pos, yaw, "L")
    p["ftR"] = ST.to_body_foot(fr, pos, yaw, "R")
    # gait phase for the upper body: use the left foot's cycle (phase of the nearest step)
    ph = 0.0
    sl = steps["L"]
    for i, st in enumerate(sl):
        t0 = st.t0
        if t0 <= t:
            ph = ((t - t0) / g.T) % 1.0
    c = np.cos(TAU * ph)
    wl = np.sin(np.pi * fl["s"]) if fl["stance"] and fl["s"] >= 0 else 0.0
    wr = np.sin(np.pi * fr["s"]) if fr["stance"] and fr["s"] >= 0 else 0.0
    bobv = g.bob * s * np.cos(2 * TAU * (ph - g.duty * 0.5))
    roll = -g.roll * s * (wl - wr)
    pyaw = -g.pyaw * s * c
    syaw = g.syaw * s * c
    lean = g.lean * s
    p["pel"] = np.array([g.sway * s * (wl - wr), 0.0, (g.z0 * s) + bobv, 0.0, roll, pyaw])
    p["pel_auto"] = np.array([1.0, -0.014 + 0.044 * float(np.clip(s * 2.0, 0.0, 1.0)), 0.0])
    p["sp"] = np.array([lean, -roll * 0.6, syaw])
    p["hd"] = np.array([-lean * 0.7, roll * 0.3, -(pyaw + syaw) * g.head_stab])
    sw = g.arm * s
    fwdL, fwdR = -sw * c, +sw * c
    k = 1.0 if g.arm < 1e-6 else 0.5 + 0.5 * (fwdL / max(sw, 1e-6))
    eL = RK.ARM_HANG[3] + (g.elbow0 - RK.ARM_HANG[3] + g.elbow1 * (0.5 + 0.5 * (fwdL / max(sw, 1e-6)))) * s
    eR = RK.ARM_HANG[3] + (g.elbow0 - RK.ARM_HANG[3] + g.elbow1 * (0.5 + 0.5 * (fwdR / max(sw, 1e-6)))) * s
    outv = RK.ARM_HANG[1] + (g.out - RK.ARM_HANG[1]) * s
    p["armL"] = np.array([fwdL + RK.ARM_HANG[0], outv, 0.0, eL, 0, 0])
    p["armR"] = np.array([fwdR + RK.ARM_HANG[0], outv, 0.0, eR, 0, 0])
    p["fL"] = RK.G(g.gripL)
    p["fR"] = RK.G(g.gripR)
    for side, fs in (("L", fl), ("R", fr)):
        tp = max(fs["pitch"], 0.0)
        p["toe" + side] = np.array([-0.9 * tp, -0.9 * tp])
    opts = dict(arm_mode=("fk", "fk"), stance=(True, True), world=dict(pos=tuple(pos), yaw=yaw))
    return p, opts, dict(v=v, yaw=yaw, pos=pos, s=s)
