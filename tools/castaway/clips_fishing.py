"""Group C: fishing with the pole (cast, wait, bite, reel, lift, inspect, celebrate, fail, reset) and spearfishing with the staff."""
import numpy as np

import params as PR
import rigkit as RK
import staffkit as SK
from clipkit import clip, keys, smooth, seg, pulse
from posekit import *      # noqa: F401,F403
import posekit as K
from clips_posture import pose_crouch

HANG = RK.ARM_HANG
WATER = np.array([0.0, -3.5, 0.0])        # where the line lands (world), for gaze


def b(m=0.1, **kw):
    p = K.P(RK.stand(mood=m), armL=HANG.copy(), armR=HANG.copy(), wL=0.0, wR=0.0)
    return K.P(p, **kw) if kw else p


def staffed(p, s, rmode="side", lmode="over"):
    return SK.apply_state(p, s, right_mode=rmode, left_mode=lmode)


def fish_pose(base_kw, s, m=0.0, rmode="side", lmode="over", fk_l=None):
    p = b(m, **base_kw)
    if fk_l is not None:
        p["armL"] = np.array(fk_l, float)
    p = staffed(p, s, rmode, lmode)
    return p


ARM_FK_REST = HANG + np.array([30, 8, 0, 50, 0, 0])


def O2(**kw):
    return SK.opts_blend() | kw


# poses -------------------------------------------------------------------------------------------------
READY = SK.SH(-0.14, 0.26, 1.12, 52, 0, 0, 0.72, 1.22)
WAIT = SK.SH(-0.14, 0.30, 1.08, 74, -2, 0, 0.72, 1.22)


def stance(lean=4.0, hd=6.0, sway=0.0):
    return dict(pel=[0, 0.0, -0.02, 2, 0, 0], sp=[lean, 0, 0], hd=[hd, 0, 0])


def _fish_wait(t):
    T = 12.0
    ph = t / T
    shift = sw(t, T)
    s = READY.copy()
    s = SK.kv(t, [(0.0, WAIT), (3.0, SK.SH(-0.14, 0.30, 1.09, 73, -2, 0, 0.72, 1.22)), (3.4, SK.SH(-0.14, 0.30, 1.09, 71, -2, 1.5, 0.72, 1.22)), (6.0, WAIT),
                 (8.0, SK.SH(-0.15, 0.28, 1.10, 77, -3, -2, 0.72, 1.22)), (9.0, SK.SH(-0.15, 0.28, 1.10, 79, -3, -2, 0.72, 1.22)), (12.0, WAIT)])
    s[3] += 1.2 * np.sin(TAU * t * 0.9) * pulse(t, 8.0, 8.4, 9.8, 10.2)      # tip twitch
    p = b(0.1, **stance(8.0, 8.0))
    p = add(p, pel=[0.012 * shift, 0, 0, 0, -1.0 * shift, 0], sp=[0, 0.8 * shift, 3 * sw(t, T, 0.2)])
    p["look"] = np.array([0.0, -2.6, 0.0, 0.9])
    p["hd"] = p["hd"] + np.array([0, 0, 4 * sw(t, T, 0.3)])
    p = RK.breathing(p, t, 4.2, 1.0)
    p = staffed(p, s)
    return p, SK.opts_blend()


mk("fish_wait_stand", "fishing", 12.0, loop=True, desc="Standing and fishing, pole held two-handed with the tip over the water: patient weight shifts, line checks, small twitches of the tip.",
   props=["staff"], interrupt="any", blend_in=0.4, blend_out=0.4, start_pose="fish_ready", end_pose="fish_ready", staff_use="fishing_pole")(_fish_wait)


def _fish_prepare(t):
    """Inspect the pole: hold it across the body, slide the left hand along the shaft past each line guide, flex it, then set up to cast."""
    carry = SK.SH(-0.14, 0.26, 1.12, 90, 4, 80, 0.72, 1.22, 1.0, 1.0)
    # staff across the body horizontally: yaw rotates the tip to his left (+x)
    across = SK.SH(-0.16, 0.30, 1.22, 88, 0, 70, 0.72, 1.00, 1.0, 1.0)
    s = SK.kv(t, [(0.0, SK.SH(-0.30, 0.12, 0.95, 3, -1, 0, 1.0, 1.5, 1.0, 0.0)), (0.7, across), (1.4, SK.SH(-0.16, 0.30, 1.22, 88, 0, 70, 0.72, 1.35, 1.0, 1.0)),
                 (2.2, SK.SH(-0.16, 0.30, 1.22, 88, 0, 70, 0.72, 1.70, 1.0, 1.0)), (2.9, SK.SH(-0.16, 0.30, 1.22, 88, 0, 70, 0.72, 1.35, 1.0, 1.0)),
                 (3.6, SK.SH(-0.14, 0.28, 1.15, 70, 0, 20, 0.72, 1.22, 1.0, 1.0)), (4.4, READY), (5.0, READY)])
    p0 = b(0.1)
    look_t = [(0.0, [0, -0.3, 1.1, 0.8]), (0.7, [0.6, -0.4, 1.3, 1.0]), (2.2, [1.4, -0.5, 1.6, 1.0]), (3.6, [0.6, -0.4, 1.3, 1.0]), (4.4, [0, -3.0, 0.4, 0.8]), (5.0, [0, -3.0, 0.4, 0.8])]
    lk = SK.kv(t, [(a, np.array(c)) for a, c in look_t])
    p = add(p0, sp=[6 * smooth(seg(t, 0.2, 0.8)) * (1 - smooth(seg(t, 3.6, 4.4))), 0, 8 * smooth(seg(t, 0.2, 0.8)) * (1 - smooth(seg(t, 3.6, 4.4)))])
    p["look"] = lk
    p = staffed(p, s)
    p = addf(p, squint=0.2 * smooth(seg(t, 0.7, 1.2)), smile_L=0.1, smile_R=0.1)
    return p, SK.opts_blend()


mk("fish_prepare_rod", "fishing", 5.0, desc="Takes the pole in both hands, runs the left hand up the shaft checking the line guides and lashings, flexes it and settles into the ready stance.",
   props=["staff"], interrupt="none", blend_in=0.3, blend_out=0.3, start_pose="stand_staff", end_pose="fish_ready", staff_use="fishing_pole")(_fish_prepare)


def _fish_cast(t):
    back = SK.SH(-0.18, 0.06, 1.60, -22, 0, 0, 0.72, 1.22, 1.0, 0.0)
    fwd = SK.SH(-0.12, 0.44, 1.46, 96, 0, 0, 0.72, 1.22, 1.0, 0.0)
    follow = SK.SH(-0.12, 0.40, 1.30, 70, 0, 0, 0.72, 1.22, 1.0, 0.0)
    settle = WAIT
    s = SK.kv(t, [(0.0, READY), (0.5, READY), (1.0, back), (1.25, back), (1.55, fwd), (1.9, follow), (2.6, SK.SH(-0.13, 0.32, 1.14, 66, -1, 0, 0.72, 1.22, 1.0, 1.0)), (3.2, settle)])
    # left hand leaves the rod during the cast (wL 0) and returns on the settle
    wl = 1.0 - smooth(seg(t, 0.8, 1.0)) + smooth(seg(t, 2.2, 2.8)) * 1.0
    wl = float(np.clip(wl, 0, 1))
    s[8] = wl
    lean = env(t, 0.5, 1.0, 1.25, 1.55) * -12 + env(t, 1.3, 1.6, 1.9, 2.6) * 14
    p = b(0.1, **stance(6.0, 6.0))
    p = add(p, sp=[lean, 0, -10 * env(t, 0.5, 1.0, 1.2, 1.5) + 8 * env(t, 1.4, 1.6, 1.8, 2.4)], pel=[0, 0.05 * env(t, 1.4, 1.6, 1.8, 2.6), -0.03 * env(t, 1.4, 1.6, 1.8, 2.6), 3 * env(t, 1.4, 1.6, 1.8, 2.6), 0, 6 * env(t, 1.4, 1.6, 1.8, 2.6)])
    p["armL"] = HANG + np.array([20 + 10 * env(t, 0.8, 1.0, 1.8, 2.3), 20 * env(t, 0.8, 1.0, 1.8, 2.3), 0, 60, 0, 0])
    p["look"] = np.array([0.0, -2.6 - 1.0 * smooth(seg(t, 1.5, 2.0)), 0.8 - 0.8 * smooth(seg(t, 1.5, 2.2)), 0.9])
    p = staffed(p, s)
    p = addf(p, jaw=3 * env(t, 1.3, 1.5, 1.7, 2.0), squint=0.2)
    return p, SK.opts_blend()


mk("fish_cast", "fishing", 3.2, desc="Casting: the pole sweeps back over the shoulder, then whips forward and releases the line; follow-through settles with the tip over the water.",
   props=["staff"], interrupt="none", blend_in=0.25, blend_out=0.3, start_pose="fish_ready", end_pose="fish_wait", staff_use="fishing_pole",
   events=[(1.55, "line_release")])(_fish_cast)


def _fish_bite(t):
    base = WAIT
    s = SK.kv(t, [(0.0, base), (0.3, SK.SH(-0.14, 0.30, 1.08, 84, -2, 0, 0.72, 1.22)), (0.45, SK.SH(-0.14, 0.30, 1.08, 92, -2, 0, 0.72, 1.22)), (0.7, SK.SH(-0.14, 0.30, 1.10, 60, -2, 0, 0.72, 1.22)),
                 (1.1, SK.SH(-0.14, 0.28, 1.18, 56, 0, 0, 0.72, 1.22)), (1.6, SK.SH(-0.14, 0.26, 1.16, 62, 0, 0, 0.72, 1.22))])
    p = b(0.2, **stance(8.0, 8.0))
    pop = env(t, 0.25, 0.4, 0.6, 1.0)
    p = add(p, sp=[-8 * env(t, 0.5, 0.75, 0.9, 1.4)], pel=[0, 0.02 * pop, 0, 0, 0, 0])
    p["look"] = np.array([0.0, -2.6, 0.0, 0.9])
    p = staffed(p, s)
    p = addf(p, wide=0.7 * pop, brow_L=0.7 * pop, brow_R=0.7 * pop, jaw=4 * pop)
    return p, SK.opts_blend()


mk("fish_bite_reaction", "fishing", 1.6, desc="A bite! The tip dips hard, he starts, then strikes: a sharp pull up to set the hook, eyes wide.", props=["staff"], interrupt="none",
   blend_in=0.1, blend_out=0.2, start_pose="fish_wait", end_pose="fish_fight", staff_use="fishing_pole", events=[(0.45, "tip_dip"), (0.7, "set_hook")])(_fish_bite)


def _fish_reel(t):
    T = 2.0
    ph = t / T
    s0 = SK.SH(-0.14, 0.26, 1.18, 58, -1, 0, 0.72, 1.22, 1.0, 0.0)
    # strain: the tip nods with each pull; the left hand pulls the line down/back in a loop (hand-reel)
    pull = 0.5 - 0.5 * np.cos(TAU * ph)
    s = s0.copy()
    s[3] += -8 * pull + 2 * np.sin(TAU * ph * 3)
    s[:3] = s[:3] + np.array([0, 0.03 * pull, 0.0])
    p = b(0.0, **stance(10.0, 6.0))
    p = add(p, sp=[-5 * pull, 0, 3 * np.sin(TAU * ph)], pel=[0.01 * np.sin(TAU * ph), 0.02 * pull, -0.02 - 0.02 * pull, 4 * pull, 0, 0])
    rx = 0.04 + 0.05 * np.cos(TAU * ph)
    p["armL_ik"] = K.ik(v3(0.10, 0.38 - 0.18 * pull, 1.34 - 0.18 * pull), (-0.1, -1, 0.0), (0.2, 0, 1), -10)
    p["armL"] = HANG + np.array([50, 10, 0, 60, 0, 0])
    p["armR_w"] = np.array([1.0])
    p = staffed(p, s)
    p["armL_w"] = np.array([1.0])
    p["fL"] = RK.G("grip_thin", 0.9 * (1 - pull) + 0.4 * pull)
    p["look"] = np.array([0.0, -2.4, 0.0, 0.9])
    p = addf(p, furrow=0.4, squint=0.3, jaw=3)
    p = RK.breathing(p, t, 1.6, 1.4)
    return p, SK.opts_blend()


mk("fish_reel_in", "fishing", 2.0, loop=True, desc="Reeling in a fish: tip held high bowed under strain, left hand hauls the line hand-over-hand, body leaning back with each pull.",
   props=["staff"], interrupt="any", blend_in=0.2, blend_out=0.3, start_pose="fish_fight", end_pose="fish_fight", staff_use="fishing_pole")(_fish_reel)


def _fish_lift(t):
    s = SK.kv(t, [(0.0, SK.SH(-0.14, 0.26, 1.18, 58, -1, 0, 0.72, 1.22, 1.0, 0.0)), (0.5, SK.SH(-0.14, 0.20, 1.35, 30, 0, 0, 0.72, 1.22, 1.0, 0.0)),
                  (1.1, SK.SH(-0.16, 0.12, 1.50, 5, 0, 0, 0.72, 1.22, 1.0, 0.0)), (1.8, SK.SH(-0.18, 0.18, 1.32, 20, 0, 0, 0.72, 1.22, 1.0, 0.0)), (2.6, SK.SH(-0.18, 0.18, 1.32, 20, 0, 0, 0.72, 1.22, 1.0, 0.0))])
    s[8] = 0.0
    p = b(0.2, **stance(4.0, 4.0))
    lift = env(t, 0.2, 1.0, 1.4, 2.0)
    p = add(p, sp=[-12 * lift, 0, 0], pel=[0, 0.03 * lift, 0, -4 * lift, 0, 0], hd=[-4 * lift, 0, 0])
    grab = env(t, 1.0, 1.4, 2.5, 2.6)
    p["armL_ik"] = K.ik(v3(0.14, 0.52, 1.30), (-0.1, -1, 0.0), (0.2, 0, 1), -10)
    p["armL_w"] = np.array([smooth(seg(t, 1.0, 1.5))])
    p["armL"] = HANG + np.array([40, 10, 0, 50, 0, 0])
    p["fL"] = RK.G("grip_thin", 0.9 * grab)
    p["look"] = np.array([0.1, -0.7, 1.0, 0.9])
    p = staffed(p, s)
    p["armL_w"] = np.array([smooth(seg(t, 1.0, 1.5))])
    p = addf(p, smile_L=0.4 * grab, smile_R=0.4 * grab, brow_L=0.4 * grab, brow_R=0.4 * grab)
    return p, SK.opts_blend()


mk("fish_lift_catch", "fishing", 2.6, desc="Swings the pole up and back to land the fish, catches the line with the left hand and holds the catch out in front.",
   props=["staff", "fish"], interrupt="none", blend_in=0.2, blend_out=0.3, start_pose="fish_fight", end_pose="fish_hold_catch", staff_use="fishing_pole", events=[(1.0, "fish_leaves_water"), (1.4, "catch_in_hand")])(_fish_lift)


# ---------------------------------------------------------------------------------------------------- after the catch
def _fish_inspect(t):
    T = 5.0
    a = env(t, 0.3, 0.9, 4.1, 4.8)
    turn = sw(t, 2.5)
    p = b(0.3, **stance(10.0, 12.0))
    p = add(p, hd=[10 * a, 6 * turn * a, 10 * turn * a], sp=[4 * a, 0, 4 * turn * a])
    # fish held in both hands in front of the chest, turned over to look at both sides
    p["armR_ik"] = K.ik(v3(-0.10, 0.36, 1.40 + 0.03 * turn), (0.2, -1, 0.1), (0.4, 0.2, 1), -20)
    p["armL_ik"] = K.ik(v3(0.12, 0.36, 1.40 - 0.03 * turn), (-0.2, -1, 0.1), (-0.4, 0.2, 1), 20)
    p["armR_w"] = np.array([a])
    p["armL_w"] = np.array([a])
    p["armR"] = HANG + np.array([50 * a, 10, 0, 80 * a, 0, 0])
    p["armL"] = HANG + np.array([50 * a, 10, 0, 80 * a, 0, 0])
    p["fR"] = RK.G("grip_big", 0.7 * a)
    p["fL"] = RK.G("grip_big", 0.7 * a)
    p["look"] = np.array([0.0, -0.36, 1.4, 0.9 * a])
    p = addf(p, smile_L=0.4 * a, smile_R=0.35 * a, brow_L=0.4 * a, brow_R=0.2 * a, squint=0.2 * a)
    p = RK.breathing(p, t, 4.0, 1.0)
    return p, O(spL="world", spR="world")


mk("fish_inspect_catch", "fishing", 5.0, desc="Holds the freshly caught fish in both hands, turns it over to size it up, pleased half-smile and a raised brow.",
   props=["fish"], interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="stand", end_pose="stand",
   attach=[dict(prop="fish", bone="attach_hand_R", from_t=0.0)])(_fish_inspect)


def _fish_celebrate(t):
    a = env(t, 0.2, 0.6, 2.6, 3.2)
    hop = np.maximum(0, np.sin(TAU * 1.5 * (t - 0.4))) * env(t, 0.4, 0.5, 2.2, 2.6)
    p = b(0.9)
    p["pel"] = np.array([0, 0, 0.12 * hop - 0.02 * a, 0, 0, 4 * np.sin(TAU * t / 1.4) * a])
    for sd in ("L", "R"):
        p[f"ft{sd}"] = np.array(p[f"ft{sd}"]) + np.array([0, 0, 0.12 * hop, 0, 0, 0])
    p = add(p, sp=[-6 * a, 0, 6 * np.sin(TAU * t / 1.4) * a], hd=[-10 * a, 0, 10 * np.sin(TAU * t / 1.4 + 1) * a])
    # fish held high in the right hand, left fist pumping
    p["armR"] = HANG + np.array([130 * a, 20 * a, 0, 40 * a, 0, 0])
    p["armL"] = HANG + np.array([60 * a + 14 * np.sin(TAU * 1.5 * t), 30 * a, 0, 100 * a, 0, 0])
    p["fR"] = RK.G("grip_big", a)
    p["fL"] = RK.G("fist", a)
    p = addf(p, smile_L=1.0 * a, smile_R=1.0 * a, cheek=1.0 * a, jaw=18 * a, brow_L=0.6 * a, brow_R=0.6 * a, squint=0.4 * a)
    return p, O(stance=(hop < 0.02, hop < 0.02))


mk("fish_celebrate", "fishing", 3.2, desc="Holds the fish overhead and whoops with joy, bouncing on his toes with the free fist pumping.", props=["fish"],
   interrupt="any", blend_in=0.2, blend_out=0.3, start_pose="stand", end_pose="stand", attach=[dict(prop="fish", bone="attach_hand_R", from_t=0.0)])(_fish_celebrate)


def _fish_fail(t):
    s = SK.kv(t, [(0.0, SK.SH(-0.14, 0.26, 1.18, 58, -1, 0, 0.72, 1.22, 1.0, 0.0)), (0.4, SK.SH(-0.14, 0.26, 1.18, 40, 0, 0, 0.72, 1.22, 1.0, 0.0)),
                  (0.9, SK.SH(-0.14, 0.30, 1.10, 82, 0, 0, 0.72, 1.22, 1.0, 0.0)), (1.6, SK.SH(-0.14, 0.32, 1.05, 100, 0, 0, 0.72, 1.22, 1.0, 0.0)), (3.2, SK.SH(-0.16, 0.25, 0.95, 70, 0, 0, 0.72, 1.22, 1.0, 0.0))])
    s[8] = 0.0
    p = b(-0.2, **stance(8.0, 8.0))
    sag = env(t, 0.6, 1.4, 2.4, 3.2)
    p = add(p, sp=[-6 * env(t, 0.1, 0.3, 0.45, 0.8) + 8 * sag, 0, 0], hd=[-6 * env(t, 0.1, 0.3, 0.45, 0.8) + 12 * sag, 0, 14 * np.sin(TAU * (t - 1.2) / 1.2) * env(t, 1.0, 1.3, 2.3, 2.8)],
            pel=[0, 0, -0.02 * sag, 0, 0, 0])
    p["armL"] = HANG + np.array([20, 10, 0, 40, 0, 0])
    p["look"] = np.array([0.0, -2.6, 0.0, 0.7 * (1 - sag)])
    p = staffed(p, s)
    p = addf(p, frown=0.5 * sag, brow_L=0.4 * sag, brow_R=0.2 * sag, lip_low=0.3 * sag, wide=0.4 * env(t, 0.1, 0.3, 0.5, 0.8))
    return p, SK.opts_blend()


mk("fish_fail", "fishing", 3.2, desc="The fish slips the hook: the pole whips up as the line goes slack, then the tip sags and he exhales and shakes his head.",
   props=["staff"], interrupt="none", blend_in=0.2, blend_out=0.3, start_pose="fish_fight", end_pose="fish_slack", staff_use="fishing_pole", events=[(0.4, "line_goes_slack")])(_fish_fail)


def _fish_reset(t):
    s = SK.kv(t, [(0.0, SK.SH(-0.16, 0.25, 0.95, 70, 0, 0, 0.72, 1.22, 1.0, 0.0)), (0.8, SK.SH(-0.16, 0.25, 1.00, 62, 0, 0, 0.72, 1.22, 1.0, 0.0)),
                  (2.2, SK.SH(-0.16, 0.25, 1.00, 62, 0, 0, 0.72, 1.22, 1.0, 0.0)), (3.4, READY)])
    s[8] = 0.0
    p = b(0.0, **stance(10.0, 12.0))
    hand = env(t, 0.6, 1.0, 2.2, 2.7)
    wind = np.sin(TAU * 2.5 * t) * hand
    p["armL_ik"] = K.ik(v3(0.10, 0.34, 1.22 + 0.04 * wind), (-0.1, -1, 0.1), (0.1, 0, 1), -10)
    p["armL"] = HANG + np.array([40, 10, 0, 70, 0, 0])
    p = add(p, hd=[8 * hand, 0, -4 * hand])
    p["look"] = np.array([0.1, -0.4, 1.0, 0.9 * hand])
    p = staffed(p, s)
    p["armL_w"] = np.array([hand + (1 - hand) * (1.0 if t > 2.9 else 0.0)])
    p["fL"] = RK.G("pinch", 0.8 * hand)
    p = addf(p, squint=0.2 * hand, smile_L=0.1, smile_R=0.1)
    return p, SK.opts_blend()


mk("fish_reset", "fishing", 3.4, desc="Reels the slack line in by hand, checks the hook, re-baits and returns to the ready stance.", props=["staff"], interrupt="none",
   blend_in=0.3, blend_out=0.3, start_pose="fish_slack", end_pose="fish_ready", staff_use="fishing_pole")(_fish_reset)


# ---------------------------------------------------------------------------------------------------- spearfishing (staff as a spear)
def spear_body(depth=0.20, lean=22.0, hd=-16.0, f=0.30, wide=0.17):
    p = b(0.0)
    return K.P(p, pel=[0, 0.10, -depth, 10, 0, -4], sp=[lean, 0, 6], hd=[hd, 0, -4],
               ftL=FT("L", wide, f, AZ, 0, 0, 12), ftR=FT("R", -wide, -0.12, AZ, 0, 0, -10))


SP_STANCE = SK.SH(-0.17, 0.30, 1.00, 118, 0, 0, 0.95, 1.55, 1.0, 1.0)
SP_AIM = SK.SH(-0.16, 0.20, 1.20, 140, 0, -2, 0.95, 1.55, 1.0, 1.0)
SP_THRUST = SK.SH(-0.17, 0.58, 0.82, 148, 0, 0, 0.95, 1.55, 1.0, 1.0)


def spear_pose(body, s):
    return SK.apply_state(body, s, right_mode="over", left_mode="over")


def _spear_stance(t):
    T = 6.0
    s = SP_STANCE.copy()
    s[3] += 3 * sw(t, T) + 1.0 * sw(t, 1.7)
    s[:3] = s[:3] + np.array([0.01 * sw(t, T, 0.2), 0.0, 0.01 * sw(t, 2.0)])
    p = spear_body(0.20 + 0.004 * sw(t, 2.0), 22 + 2 * sw(t, T), -16)
    p = add(p, hd=[0, 0, 12 * sw(t, T, 0.25)], sp=[0, 0, -5 * sw(t, T, 0.25)])
    p["look"] = np.array([0.0, -0.8, 0.0, 0.9])
    p = spear_pose(p, s)
    p = RK.breathing(p, t, 3.8, 0.8)
    p = addf(p, squint=0.3, furrow=0.2)
    return p, SK.opts_blend()


mk("spear_stance_idle", "fishing", 6.0, loop=True, desc="Spearfishing stance: knees bent, wide split stance, spear held two-handed pointing down at the water, scanning for fish.",
   props=["staff"], interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="spear_ready", end_pose="spear_ready", staff_use="spear")(_spear_stance)


def _spear_aim(t):
    s = SK.kv(t, [(0.0, SP_STANCE), (0.7, SP_AIM), (1.4, SP_AIM)])
    a = smooth(seg(t, 0.0, 0.7))
    p = spear_body(0.20 + 0.06 * a, 22 + 10 * a, -16 - 6 * a)
    p["look"] = np.array([0.0, -1.1, 0.0, 1.0])
    p = spear_pose(p, s)
    p = addf(p, squint=0.5 * a, furrow=0.5 * a)
    return p, SK.opts_blend()


mk("spear_aim", "fishing", 1.4, desc="Spots a fish: sinks lower, draws the spear back and locks the tip onto it, eyes narrowed, breath held.", props=["staff"],
   interrupt="none", blend_in=0.2, blend_out=0.2, start_pose="spear_ready", end_pose="spear_aimed", staff_use="spear")(_spear_aim)


def _spear_thrust(t):
    s = SK.kv(t, [(0.0, SP_AIM), (0.14, SK.SH(-0.16, 0.30, 1.14, 142, 0, 0, 0.95, 1.55, 1.0, 1.0)), (0.30, SP_THRUST), (0.9, SP_THRUST), (1.4, SP_THRUST)])
    a = smooth(seg(t, 0.1, 0.3))
    p = spear_body(0.26 + 0.12 * a, 32 + 14 * a, -22 - 4 * a, f=0.30 + 0.06 * a)
    p["look"] = np.array([0.0, -1.3, 0.0, 1.0])
    p = spear_pose(p, s)
    p = addf(p, jaw=6 * a, squint=0.5)
    return p, SK.opts_blend()


mk("spear_thrust", "fishing", 1.4, desc="Explosive spear thrust into the water: back leg drives, torso lunges forward, both arms extend and the tip plunges.", props=["staff"],
   interrupt="none", blend_in=0.1, blend_out=0.1, start_pose="spear_aimed", end_pose="spear_in_water", staff_use="spear", events=[(0.3, "spear_hits_water")])(_spear_thrust)


def _spear_recover_miss(t):
    s = SK.kv(t, [(0.0, SP_THRUST), (0.7, SK.SH(-0.17, 0.30, 1.05, 125, 0, 0, 0.95, 1.55, 1.0, 1.0)), (1.5, SK.SH(-0.17, 0.26, 1.00, 100, 0, 0, 0.95, 1.55, 1.0, 1.0)), (2.4, SK.SH(-0.20, 0.20, 0.90, 70, 0, 0, 0.95, 1.55, 1.0, 0.0))])
    a = env(t, 0.5, 1.3, 2.0, 2.4)
    p = spear_body(0.36 - 0.14 * smooth(seg(t, 0.6, 1.4)), 46 - 28 * smooth(seg(t, 0.6, 1.6)), -26 + 10 * smooth(seg(t, 0.6, 1.6)))
    p = add(p, hd=[10 * a, 0, 16 * np.sin(TAU * (t - 1.2) / 1.0) * env(t, 1.1, 1.3, 2.0, 2.3)])
    p["look"] = np.array([0.0, -1.2, 0.0, 0.6 * (1 - a)])
    p = spear_pose(p, s)
    p["armL_w"] = np.array([1.0 - smooth(seg(t, 1.6, 2.2))])
    p = addf(p, frown=0.5 * a, brow_L=0.3 * a, brow_R=0.1 * a, lip_low=0.3 * a)
    return p, SK.opts_blend()


mk("spear_recover_miss", "fishing", 2.4, desc="The fish darts away: pulls the spear out of the water, straightens up and shakes his head with a rueful grimace.", props=["staff"],
   interrupt="none", blend_in=0.15, blend_out=0.3, start_pose="spear_in_water", end_pose="stand_staff", staff_use="spear")(_spear_recover_miss)


def _spear_catch(t):
    s = SK.kv(t, [(0.0, SP_THRUST), (0.5, SK.SH(-0.17, 0.46, 0.96, 130, 0, 0, 0.95, 1.55, 1.0, 1.0)), (1.4, SK.SH(-0.18, 0.30, 1.30, 90, 0, 0, 0.95, 1.55, 1.0, 1.0)),
                  (2.2, SK.SH(-0.18, 0.28, 1.52, 56, 0, 0, 0.95, 1.55, 1.0, 1.0)), (3.0, SK.SH(-0.18, 0.28, 1.52, 56, 0, 0, 0.95, 1.55, 1.0, 1.0))])
    a = smooth(seg(t, 0.4, 2.2))
    p = spear_body(0.38 - 0.34 * a, 46 - 40 * a, -24 + 22 * a, f=0.36 - 0.30 * a)
    p["look"] = np.array([0.0, -0.9, 1.5, 0.8 * a])
    p = spear_pose(p, s)
    p = addf(p, smile_L=0.9 * a, smile_R=0.9 * a, cheek=0.7 * a, brow_L=0.5 * a, brow_R=0.5 * a, jaw=10 * a)
    return p, SK.opts_blend()


mk("spear_catch_lift", "fishing", 3.0, desc="Impaled a fish! Hauls the spear up out of the water with the fish wriggling on the tip and holds it up with a triumphant grin.",
   props=["staff", "fish"], interrupt="none", blend_in=0.15, blend_out=0.3, start_pose="spear_in_water", end_pose="stand_spear_up", staff_use="spear",
   events=[(0.5, "fish_on_spear")])(_spear_catch)
