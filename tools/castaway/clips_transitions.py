"""Tier 1: gait transitions (start/stop), in-place turns and sudden direction changes. All planted in world space."""
import numpy as np

import clipkit as CK
import gaitkit as GK
import params as PR
import pathgait as PG
import rigkit as RK
import steps as ST
from clipkit import clip, smooth
from kin import Rz
from clips_locomotion import WALK, RUN, BRISK

TAU = 2 * np.pi
CURVES = {}          # clip name -> dict(speed=[...], yaw=[...]) for the metadata


def _record(name, path, seconds):
    n = int(round(seconds * 30)) + 1
    ts = np.arange(n) / 30.0
    CURVES[name] = dict(speed=[round(float(path.at(t)[2]), 4) for t in ts], yaw=[round(float(path.at(t)[1]), 3) for t in ts],
                        distance=round(float(np.linalg.norm(path.at(seconds)[0])), 3))


def make(name, g, seconds, path, steps, group="transition", ref=None, **meta):
    ref = ref or g.v

    def fn(t):
        prm, opts, info = PG.frame(t, g, path, steps, ref)
        return prm, opts
    _record(name, path, seconds)
    clip(name, group, seconds, loop=False, root="inplace_path", **meta)(RK.with_blinks(fn, seconds, abs(hash(name)) % 97, every=(2.0, 3.0)))
    return fn


# ------------------------------------------------------------------------------------------------ starts
def start_clip(name, g, ramp, desc, next_clip, **meta):
    swing = (1 - g.duty) * g.T
    seconds = swing + g.T                                   # ends at the second left heel strike = loop phase 0
    nf = int(round(seconds * 30))
    seconds = nf / 30.0
    path = PG.Path(lambda t: g.v * smooth(t / ramp), lambda t: 0.0, seconds)
    steps = PG.build_steps(path, g, swing, "L", n_steps=3)
    make(name, g, seconds, path, steps, desc=desc, next_clip=next_clip, next_phase=0.0, start_pose="stand", end_pose=f"{next_clip}@0.0",
         interrupt="after_step", blend_in=0.1, blend_out=0.0, speed_curve=True, **meta)


start_clip("walk_start", WALK, 1.30, "Standing to walking: the left foot leads, speed ramps 0 -> 1.30 m/s over 1.3 s (feed the controller the exported speed curve). Ends at the left heel strike = `walk` loop phase 0.", "walk")
start_clip("run_start", RUN, 1.0, "Standing to running: crouched lean, three accelerating strides, ends at the left heel strike = `run` loop phase 0.", "run")


# ------------------------------------------------------------------------------------------------ stops
def stop_clip(name, g, desc, to_pose="stand", t_dec=0.30, dec=1.15, rem=0.42, tail=0.45):
    """Gait -> standing. Regular steps under the decelerating path, then a lead step (landing `rem` m ahead of where the body
    will stop) and a closing step beside it. The clip starts at a left heel strike (loop phase 0)."""
    T = g.T
    swing = (1 - g.duty) * T
    path = PG.Path(lambda t: g.v * (1 - smooth((t - t_dec) / dec)), lambda t: 0.0, 8.0)
    X_end = -path.at(8.0)[0][1]
    cands = []
    for k in range(0, 8):
        cands.append(("L", k * T))
        cands.append(("R", T / 2 + k * T))
    best = min(cands, key=lambda c: abs((X_end + path.at(c[1])[0][1]) - rem) + (0.0 if c[1] > t_dec else 5.0))
    lead_side, t_lead = best
    close_side = "R" if lead_side == "L" else "L"
    t_close = t_lead + T / 2
    seconds = round((t_close + tail) * 30) / 30.0
    lat = {"L": g.x, "R": -g.x}
    toe = {"L": g.toe_out, "R": -g.toe_out}
    steps = PG.build_steps(path, g, 0.0, "L", n_steps=8, steady_start=True)
    for side, t_final, f_final, yaw_f in ((lead_side, t_lead, X_end - 0.025, 0.0), (close_side, t_close, X_end + 0.020, 0.0)):
        keep = [st for st in steps[side] if st.t0 < t_final - 1e-6]
        keep.append(ST.Step(t_final, 99.0, lat[side] * 1.05, f_final, toe[side] * 0.3))
        steps[side] = keep
    make(name, g, seconds, path, steps, desc=desc, start_pose=f"{name.split('_stop')[0]}@0.0", end_pose=to_pose, interrupt="none",
         blend_in=0.1, blend_out=0.25, speed_curve=True)


stop_clip("walk_stop", WALK, "Walking to standing: starts at a left heel strike (`walk` phase 0), speed decays 1.30 -> 0 m/s, the right foot leads the stop and the left closes beside it.")
stop_clip("walk_brisk_stop", BRISK, "Brisk walk to standing (starts at `walk_brisk` phase 0).", t_dec=0.20, dec=0.90)
stop_clip("run_stop", RUN, "Running to standing: braking strides with a backward lean, ends upright (starts at `run` phase 0).", t_dec=0.10, dec=0.95, rem=0.50)


# ------------------------------------------------------------------------------------------------ turns
def turn_clip(name, yaw_total, desc, T=1.0, duty=0.72, seconds=None, first="L", lean_roll=0.0, **meta):
    g = GK.Gait(T=T, v=0.0, duty=duty, x=0.100, toe_out=4.0, arm=6.0, lean=0.0, z0=-0.02, bob=0.008, sway=0.012, roll=2.0, pyaw=3.0,
                syaw=4.0, foot=ST.Cfg(lift=0.07, toe_pitch=22.0, heel_pitch=6.0))
    swing = (1 - g.duty) * T
    seconds = seconds or (swing + 1.6 * T)
    seconds = round(seconds * 30) / 30.0
    ramp0, ramp1 = 0.10, seconds - 0.25
    path = PG.Path(lambda t: 0.0, lambda t: yaw_total * smooth((t - ramp0) / (ramp1 - ramp0)), seconds)
    steps = PG.build_steps(path, g, swing + 0.05, first, n_steps=3)
    # last steps: freeze everything after the final landing (turn complete)
    make(name, g, seconds, path, steps, desc=desc, start_pose="stand", end_pose="stand", interrupt="none", blend_in=0.15, blend_out=0.2,
         yaw_deg=yaw_total, ref=1.0, **meta)


turn_clip("turn_left_90", 90.0, "Stepping turn on the spot, 90 degrees to the left (head and chest lead, feet re-plant). The controller rotates the heading using the exported yaw curve; the root bone does not rotate.", first="L")
turn_clip("turn_right_90", -90.0, "Stepping turn on the spot, 90 degrees to the right.", first="R")
turn_clip("turn_180", 180.0, "About-face: 180 degree stepping turn to the left in four steps.", T=0.9, seconds=2.1, first="L")


# ------------------------------------------------------------------------------------------------ sudden direction changes
def cut_clip(name, sign, desc):
    g = RUN
    seconds = round((g.T * 1.5) * 30) / 30.0
    ramp0, ramp1 = 0.10, 0.50
    path = PG.Path(lambda t: g.v * (1.0 - 0.28 * np.sin(np.pi * np.clip((t - 0.1) / 0.55, 0, 1)) ** 2),
                   lambda t: sign * 70.0 * smooth((t - ramp0) / (ramp1 - ramp0)), seconds)
    steps = PG.build_steps(path, g, (1 - g.duty) * g.T, "L", n_steps=3, lat_scale=1.0, steady_start=True)
    base = make.__wrapped__ if hasattr(make, "__wrapped__") else None

    def fn(t):
        prm, opts, info = PG.frame(t, g, path, steps, g.v)
        lean = sign * 10.0 * np.sin(np.pi * np.clip((t - 0.05) / 0.6, 0, 1))
        prm["pel"][4] += -lean * 0.5
        prm["sp"][1] += -lean
        prm["hd"][2] += sign * 18.0 * np.sin(np.pi * np.clip((t - 0.0) / 0.5, 0, 1))
        prm["hd"][1] += lean * 0.6
        return prm, opts
    _record(name, path, seconds)
    clip(name, "transition", seconds, loop=False, root="inplace_path", desc=desc, start_pose="run@0.0", end_pose="run@0.5", interrupt="none",
         blend_in=0.1, blend_out=0.15, yaw_deg=sign * 70.0, speed_curve=True)(RK.with_blinks(fn, seconds, 77))


cut_clip("run_cut_left", +1.0, "Sudden 70 degree direction change to the left while running: speed dips ~28 %, body leans into the turn, head leads.")
cut_clip("run_cut_right", -1.0, "Sudden 70 degree direction change to the right while running.")
