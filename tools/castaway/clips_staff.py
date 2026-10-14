"""Tier 1: walking staff / fishing pole carried and used for support: idles, gait with a planted staff, start/stop."""
import numpy as np

import clipkit as CK
import gaitkit as GK
import params as PR
import pathgait as PG
import rigkit as RK
import staffkit as SK
import steps as ST
from clipkit import clip, keys, smooth
from clips_locomotion import WALK
from clips_transitions import CURVES, _record
from kin import Rz

TAU = 2 * np.pi


def opts_ik(L="ik", R="ik"):
    return dict(arm_mode=(L, R), arm_space=("world", "world"), stance=(True, True))


@clip("_staff_test", "test", 1.0, loop=True, desc="grip test")
def staff_test(t):
    p = RK.stand()
    butt = SK.P(-0.30, 0.25, 0.0)
    axis = SK.axis_from(pitch=4.0, roll=-2.0)
    p = SK.hold(p, butt, axis, right=(1.00, "side"), left=(1.50, "back"))
    return p, opts_ik()


# ---------------------------------------------------------------------------------------------------- staff tracks
HAND_REST = np.array([-0.27, -0.12, 1.02])          # right hand grip point in the body frame (x, y(-forward), z)
PLANT_OFF = np.array([-0.38, -0.20, 0.0])           # butt relative to the left foot plant, in the heading frame


def plants_from_steps(stepsL, yaw_of=None, off=PLANT_OFF):
    """[(t_land, t_lift, world_pos)] for a staff that moves with the left foot."""
    out = []
    for st in stepsL:
        wp = np.array([st.x, -st.f, 0.0])
        out.append((st.t0, st.t1, wp + Rz(st.yaw) @ off))
    return out


def staff_world(t, plants, arc=0.10):
    """World butt position at time t (planted between land and lift, smooth arc between plants)."""
    if t <= plants[0][0]:
        return plants[0][2].copy()
    for i, (t0, t1, pos) in enumerate(plants):
        if t0 <= t <= t1:
            return pos.copy()
        if i + 1 < len(plants) and t1 < t < plants[i + 1][0]:
            n0, n1, npos = plants[i + 1]
            s = (t - t1) / (n0 - t1)
            e = s * s * (3 - 2 * s)
            return pos + (npos - pos) * e + np.array([0, 0, arc * np.sin(np.pi * s) ** 1.2])
    return plants[-1][2].copy()


def carry_staff(prm, opts, t, plants, body_pos, body_yaw, hand=HAND_REST, left_swing=0.55):
    """Add the staff to a gait frame: right hand on the staff at a fixed body point, the butt planted in world space."""
    bw = staff_world(t, plants)
    butt = Rz(-body_yaw) @ (bw - np.asarray(body_pos, float))
    h = hand + np.array([prm["pel"][0], 0.0, prm["pel"][2]])
    d = h - butt
    along = float(np.linalg.norm(d))
    axis = d / along
    p = SK.hold(prm, butt, axis, right=(along, "side"))
    p["armL"] = p["armL"] * np.array([left_swing, 1, 1, 1, 1, 1]) + np.array([0, 0, 0, 0, 0, 0])
    o = dict(opts)
    o["arm_mode"] = ("fk", "ik")
    o["arm_space"] = ("world", "world")
    return p, o


def staff_gait_clip(name, g, desc, kind="loop", **meta):
    if kind == "loop":
        stepsL = GK.make_steps(g, n=4)[0]
        plants = plants_from_steps(stepsL)
        steps = GK.make_steps(g)

        def fn(t):
            prm, opts = GK.gait_params(t, g, steps)
            return carry_staff(prm, opts, t, plants, opts["world"]["pos"], 0.0)
        clip(name, "locomotion", g.T, loop=True, speed=g.v, desc=desc, props=["staff"], **meta)(RK.with_blinks(fn, g.T, 33, every=(1.8, 3.0)))
        return
    raise ValueError(kind)


STAFF_WALK = GK.Gait(T=34 / 30, v=1.20, arm=18.0, lean=2.5, syaw=7.0, gripR="grip_staff")
staff_gait_clip("walk_staff", STAFF_WALK, "Walking with the staff held in the right hand, planted ahead on each left step. In place: timeScale = speed / 1.20.",
                interrupt="any", blend_in=0.2, blend_out=0.2)


def staff_start(name, g, ramp, desc):
    swing = (1 - g.duty) * g.T
    seconds = round((swing + g.T) * 30) / 30.0
    path = PG.Path(lambda t: g.v * smooth(t / ramp), lambda t: 0.0, seconds)
    steps = PG.build_steps(path, g, swing, "L", n_steps=3)
    plants = plants_from_steps(steps["L"])
    plants[0] = (plants[0][0], plants[0][1], np.array([0.09, 0.0, 0.0]) + PLANT_OFF)

    def fn(t):
        prm, opts, info = PG.frame(t, g, path, steps, g.v)
        prm["fR"] = RK.G("grip_staff")
        return carry_staff(prm, opts, t, plants, info["pos"], info["yaw"])
    _record(name, path, seconds)
    clip(name, "transition", seconds, loop=False, root="inplace_path", desc=desc, props=["staff"], next_clip="walk_staff", next_phase=0.0,
         start_pose="stand_staff", end_pose="walk_staff@0.0", interrupt="after_step", blend_in=0.1, blend_out=0.0, speed_curve=True)(RK.with_blinks(fn, seconds, 41))


staff_start("walk_staff_start", STAFF_WALK, 1.2, "Standing with the staff to walking with it: the staff lifts with the left foot, speed ramps to 1.20 m/s. Ends at `walk_staff` phase 0.")


# ---------------------------------------------------------------------------------------------------- idles with the staff
def _idle_staff(t):
    T = 9.0
    ph = t / T
    s1 = np.sin(TAU * ph)
    p = RK.stand(mood=0.1)
    shift = 0.5 * s1
    p["pel"] = np.array([0.012 * shift, 0.0, -0.006 - 0.004 * abs(shift), 0, -1.5 * shift, 2.0 * np.sin(TAU * (ph * 2 + 0.2))])
    p["sp"] = np.array([1.0, 1.0 * shift, -2.0 * np.sin(TAU * (ph * 2 + 0.2))])
    yaw = 28 * np.sin(TAU * (ph + 0.1))
    p["hd"] = np.array([-1.5, 0.5 * shift, yaw * 0.62])
    p["eye"] = np.array([yaw * 0.2, 1.0])
    p["armL"] = RK.ARM_HANG.copy()
    p["armL"][1] += 1.5 * shift
    s = SK.SS(-0.30, 0.12, 0.0, 3.0, -1.0, 0.0, along=1.00, wR=1.0)
    p = SK.apply_state(p, s)
    p["armL_w"] = np.array([0.0])
    p = RK.breathing(p, t, 4.2, 1.0)
    return p, SK.opts_blend()


@clip("idle_staff", "idle", 9.0, loop=True, desc="Standing with the staff planted at his right side, right hand resting on it at hip height; breathing, weight shift, slow look around.",
      props=["staff"], interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="stand_staff", end_pose="stand_staff")
def idle_staff(t):
    return RK.with_blinks(_idle_staff, 9.0, 51)(t)


def _idle_staff_lean(t):
    T = 10.0
    ph = t / T
    s1 = np.sin(TAU * ph)
    p = RK.stand(mood=0.15)
    p["pel"] = np.array([0.0, -0.06, -0.012 + 0.003 * s1, 8.0, 0.0, 0.0])
    p["sp"] = np.array([20.0 + 0.8 * s1, 0.0, 2.0 * np.sin(TAU * ph * 2)])
    p["hd"] = np.array([-14.0 + 1.5 * np.sin(TAU * (ph * 2 + 0.3)), 0.0, 25 * np.sin(TAU * (ph + 0.15))])
    p["eye"] = np.array([6 * np.sin(TAU * (ph * 3)), 0.0])
    p["armL"] = np.array([30.0, -10.0, 0.0, 60.0, 0, 0])
    p["armR"] = np.array([30.0, -10.0, 0.0, 60.0, 0, 0])
    s = SK.SS(-0.02, 0.42, 0.0, -4.0, 0.0, 0.0, along=1.12, wR=1.0, wL=1.0, alongL=1.32)
    p = SK.apply_state(p, s, right_mode="back", left_mode="back")
    p = RK.breathing(p, t, 4.4, 1.0)
    return p, SK.opts_blend()


@clip("idle_staff_lean", "idle", 10.0, loop=True, desc="Leaning forward on the staff planted in front of him, both hands stacked on top; resting, gazing out, slow breathing.",
      props=["staff"], interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="lean_staff", end_pose="lean_staff")
def idle_staff_lean(t):
    return RK.with_blinks(_idle_staff_lean, 10.0, 52)(t)


# ---------------------------------------------------------------------------------------------------- stop / pick up / put down / point / probe
def staff_stop(name, g, desc, t_dec=0.30, dec=1.15, rem=0.42, tail=0.55):
    """Walking with the staff to standing with it planted at his side."""
    T = g.T
    swing = (1 - g.duty) * T
    path = PG.Path(lambda t: g.v * (1 - smooth((t - t_dec) / dec)), lambda t: 0.0, 8.0)
    X_end = -path.at(8.0)[0][1]
    cands = [("L", k * T) for k in range(0, 8)] + [("R", T / 2 + k * T) for k in range(0, 8)]
    lead_side, t_lead = min(cands, key=lambda c: abs((X_end + path.at(c[1])[0][1]) - rem) + (0.0 if c[1] > t_dec else 5.0))
    close_side = "R" if lead_side == "L" else "L"
    t_close = t_lead + T / 2
    seconds = round((t_close + tail) * 30) / 30.0
    lat = {"L": g.x, "R": -g.x}
    toe = {"L": g.toe_out, "R": -g.toe_out}
    steps = PG.build_steps(path, g, 0.0, "L", n_steps=8, steady_start=True)
    for side, t_final, f_final in ((lead_side, t_lead, X_end - 0.025), (close_side, t_close, X_end + 0.020)):
        keep = [st for st in steps[side] if st.t0 < t_final - 1e-6]
        keep.append(ST.Step(t_final, 99.0, lat[side] * 1.05, f_final, toe[side] * 0.3))
        steps[side] = keep
    plants = plants_from_steps([st for st in steps["L"] if st.t1 < 50])
    # final plant: beside the right foot (stand pose), landing before the close step
    final_pos = np.array([-0.30, -(X_end + 0.12), 0.0])
    t_final_land = seconds - 0.40
    plants = [pl for pl in plants if pl[1] < t_final_land - 0.35] + [(t_final_land, 99.0, final_pos)]

    def fn(t):
        prm, opts, info = PG.frame(t, g, path, steps, g.v)
        prm["fR"] = RK.G("grip_staff")
        return carry_staff(prm, opts, t, plants, info["pos"], info["yaw"])
    _record(name, path, seconds)
    clip(name, "transition", seconds, loop=False, root="inplace_path", desc=desc, props=["staff"], start_pose="walk_staff@0.0", end_pose="stand_staff",
         interrupt="none", blend_in=0.1, blend_out=0.25, speed_curve=True)(RK.with_blinks(fn, seconds, 43))


staff_stop("walk_staff_stop", STAFF_WALK, "Walking with the staff to standing: starts at `walk_staff` phase 0, the staff is planted at his side for the final step.")


def _staff_pickup(t):
    """Stand -> bend and pick the staff up from the ground at his right side -> stand with it planted."""
    S0 = SK.SS(-0.32, -0.45, 0.03, 90.0, 0.0, 0.0, along=0.62, wR=0.0)       # lying on the ground, axis pointing forward... (pitch 90 = horizontal, tip forward)
    s_g = SK.SS(-0.32, -0.45, 0.03, 90.0, 0.0, 0.0, along=0.62, wR=1.0)
    s_up = SK.SS(-0.32, -0.30, 0.10, 60.0, 0.0, 0.0, along=0.62, wR=1.0)
    s_h = SK.SS(-0.30, 0.02, 0.0, 14.0, -1.0, 0.0, along=0.90, wR=1.0)
    s_f = SK.SS(-0.30, 0.12, 0.0, 3.0, -1.0, 0.0, along=1.00, wR=1.0)
    st = SK.kv(t, [(0.0, S0), (1.0, S0), (1.25, s_g), (1.8, s_g), (2.3, s_up), (3.0, s_h), (3.5, s_f), (4.0, s_f)])
    stand = RK.stand(mood=0.1)
    crouch = PR.update(stand, pel=[0, 0.10, -0.50, 14, 0, 0], sp=[34, 0, 6], hd=[-18, 0, 8],
                       ftL=RK.FT("L", 0.115, 0.08, RK.ANKLE_Z, 0, 0, 6), ftR=RK.FT("R", -0.115, 0.08, RK.ANKLE_Z, 0, 0, -6))
    crouch["armL"] = np.array([8.0, -14.0, 0, 20, 0, 0])
    mid = PR.update(stand, pel=[0, 0.05, -0.20, 8, 0, 0], sp=[18, 0, 3], hd=[-10, 0, 4])
    mid["armL"] = np.array([6.0, -18.0, 0, 16, 0, 0])
    final = RK.stand(mood=0.15)
    final["armL"] = RK.ARM_HANG.copy()
    p = keys(t, [(0.0, stand), (0.9, stand), (1.25, crouch), (1.8, crouch), (2.4, mid), (3.1, final), (4.0, final)])
    p = SK.apply_state(p, st, right_mode="over" if t < 2.6 else "side")
    # grip on the lying staff: palm down onto it; later the hand turns to the hip grip
    o = SK.opts_blend()
    return p, o


@clip("staff_pickup", "interaction", 4.0, desc="Bends down, picks the staff up from the ground at his right side and plants it beside him (ends in `idle_staff`).",
      props=["staff"], start_pose="stand_staff_on_ground", end_pose="stand_staff", interrupt="none", blend_in=0.2, blend_out=0.3, events=[(1.25, "grip_staff"), (2.3, "staff_leaves_ground")])
def staff_pickup(t):
    return RK.with_blinks(_staff_pickup, 4.0, 61)(t)
