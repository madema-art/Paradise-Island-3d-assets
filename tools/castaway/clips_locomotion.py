"""Tier 1: standing idles, walking and running loops."""
import numpy as np

import clipkit as CK
import gaitkit as GK
import params as PR
import rigkit as RK
import steps as ST
from clipkit import clip, keys, pulse, seg, smooth
from kin import euler

TAU = 2 * np.pi


def _wrap(fn, seconds, seed):
    return RK.with_blinks(fn, seconds, seed)


# ------------------------------------------------------------------------------------------------ idles
def _idle_relaxed(t):
    T = 8.0
    p = RK.stand(mood=0.1)
    s1 = np.sin(TAU * t / T)
    s2 = np.sin(TAU * (t / T * 2 + 0.2))
    # slow weight shift: pelvis drifts over one leg, opposite shoulder drops, knee soft
    shift = 0.5 * s1
    p["pel"] = np.array([0.012 * shift, 0.0, -0.006 - 0.004 * abs(shift), 0, -1.5 * shift, 2.0 * s2])
    p["sp"] = np.array([1.0, 1.2 * shift, -2.0 * s2])
    p["hd"] = np.array([-1.5 + 1.0 * s2, 0.5 * shift, 3.5 * np.sin(TAU * (t / T + 0.15))])
    p["eye"] = np.array([5.0 * np.sin(TAU * (t / T * 2 + 0.6)), 1.0 * s1])
    p["armL"][1] += 1.5 * shift
    p["armR"][1] -= 1.5 * shift
    p["armL"][3] += 2 * s2
    return RK.breathing(p, t, 4.0, 1.0), dict(arm_mode=("fk", "fk"))


@clip("idle_relaxed", "idle", 8.0, loop=True, desc="Relaxed standing idle: breathing, a slow weight shift, small head and eye drift, blinks.",
      interrupt="any", blend_in=0.3, blend_out=0.3)
def idle_relaxed(t):
    return RK.with_blinks(_idle_relaxed, 8.0, 3)(t)


@clip("idle_breathe", "idle", 5.0, loop=True, desc="Quiet standing with slow, deep breathing (contemplative); almost still.",
      interrupt="any", blend_in=0.3, blend_out=0.3)
def idle_breathe(t):
    def f(t):
        p = RK.stand(mood=0.0)
        p["hd"] = np.array([-3.0, 0, 0.0]) + np.array([0.8 * np.sin(TAU * t / 5.0), 0, 0])
        p["pel"][2] = -0.004
        q = RK.breathing(p, t, 5.0, 2.2)
        return q, dict(arm_mode=("fk", "fk"))
    return RK.with_blinks(f, 5.0, 11, every=(2.4, 3.0))(t)


@clip("idle_weight_shift", "idle", 10.0, loop=True, desc="Standing idle that shifts weight from one leg to the other, rolling the hips; one foot re-plants slightly.",
      interrupt="any", blend_in=0.3, blend_out=0.3)
def idle_weight_shift(t):
    def f(t):
        T = 10.0
        p = RK.stand(mood=0.05)
        ph = t / T
        w = np.sin(TAU * ph)                      # -1 weight on the right leg ... +1 on the left leg
        wl = smooth((w + 0.3) / 1.3) if w > -0.3 else 0.0
        p["pel"] = np.array([0.050 * w, 0.0, -0.012 - 0.010 * abs(w), 0, -4.5 * w, 3 * np.sin(TAU * ph * 2)])
        p["sp"] = np.array([1.0, 3.5 * w, -2 * np.sin(TAU * ph * 2)])
        p["hd"] = np.array([-1.0, -2.0 * w, 2.0 * np.sin(TAU * (ph + 0.2))])
        # the unloaded foot rests on its toe a little ahead / to the side
        unl_L = max(0.0, -w)
        unl_R = max(0.0, w)
        for side, unl in (("L", unl_L), ("R", unl_R)):
            sgn = 1.0 if side == "L" else -1.0
            ft = PR.foot_target(side, 0.03 * unl, x=0.100 + sgn * 0.012 * unl, yaw=sgn * 8 * unl, pitch=6 * unl, pivot="ball")
            p[f"ft{side}"] = ft
        p["armL"][1] += 2.0 * w
        p["armR"][1] -= 2.0 * w
        q = RK.breathing(p, t, 4.4, 1.0)
        return q, dict(arm_mode=("fk", "fk"), stance=(True, True))
    return RK.with_blinks(f, 10.0, 5)(t)


@clip("idle_look_around", "idle", 9.0, loop=True, desc="Standing and curiously looking around: head and eyes lead, shoulders follow, slow scan left, up, right.",
      interrupt="any", blend_in=0.3, blend_out=0.3)
def idle_look_around(t):
    def f(t):
        T = 9.0
        p = RK.stand(mood=0.15)
        ph = t / T
        yaw = 55 * np.sin(TAU * ph) + 12 * np.sin(TAU * ph * 3)
        pitch = -8 - 12 * np.clip(np.sin(TAU * (ph - 0.1)), 0, 1) + 6 * np.clip(-np.sin(TAU * (ph + 0.3)), 0, 1)
        p["hd"] = np.array([pitch * 0.7, 3 * np.sin(TAU * ph), yaw * 0.62])
        p["sp"] = np.array([1.0, 0, yaw * 0.30])
        p["pel"] = np.array([0, 0, -0.006, 0, 0, yaw * 0.10])
        p["eye"] = np.array([yaw * 0.16 + 9 * np.sin(TAU * (ph * 4)), pitch * 0.3])
        p["face"][PR.FACE_KEYS.index("brow_L")] = 0.25 + 0.2 * max(0, -pitch / 12)
        p["face"][PR.FACE_KEYS.index("brow_R")] = 0.35 + 0.2 * max(0, -pitch / 12)
        q = RK.breathing(p, t, 4.2, 1.0)
        return q, dict(arm_mode=("fk", "fk"))
    return RK.with_blinks(f, 9.0, 8)(t)


# ------------------------------------------------------------------------------------------------ gaits
def gait_clip(name, g, desc, group="locomotion", **meta):
    steps = GK.make_steps(g)

    def fn(t):
        prm, opts = GK.gait_params(t, g, steps)
        return prm, opts
    clip(name, group, g.T, loop=True, speed=g.v, desc=desc, **meta)(RK.with_blinks(fn, g.T, 21, every=(1.8, 3.0)))
    return fn


WALK = GK.Gait(T=32 / 30, v=1.30)
gait_clip("walk", WALK, "Normal walk. In place: set the AnimationAction timeScale = controller speed / 1.30 m/s. Feet are planted in world space.",
          interrupt="any", blend_in=0.2, blend_out=0.2)

BRISK = GK.Gait(T=24 / 30, v=1.90, duty=0.58, bob=0.026, sway=0.018, arm=34.0, elbow0=26.0, elbow1=20.0, lean=4.0, z0=-0.040,
                foot=ST.Cfg(lift=0.15, toe_pitch=36.0, heel_pitch=15.0), pyaw=6.5, syaw=11.0)
gait_clip("walk_brisk", BRISK, "Brisk, purposeful walk with a longer stride and bigger arm swing (1.9 m/s).",
          interrupt="any", blend_in=0.2, blend_out=0.2)

RUN = GK.Gait(T=20 / 30, v=4.3, duty=0.36, x=0.085, bob=0.060, z0=-0.075, sway=0.018, roll=2.5, pyaw=7.0, syaw=13.0, arm=42.0, elbow0=78.0,
              elbow1=14.0, lean=9.0, out=-17.0, run=True, gripL="fist", gripR="fist", toe_out=3.0,
              foot=ST.Cfg(lift=0.26, toe_pitch=48.0, heel_pitch=5.0, roll_on=0.10, heel_off=0.30, toe_clear=4.0, lift_peak=0.50))
gait_clip("run", RUN, "Lanky long-striding run with flight phase (4.3 m/s): strong arm drive, forward lean, loose hands.",
          interrupt="any", blend_in=0.15, blend_out=0.2)
