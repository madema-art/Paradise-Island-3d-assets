"""Group F: climbing and scrambling (trees, boulders, rocks), balance, lookouts, plus water locomotion (wade, swim, float, tread).
Vertical climbs are baked in place: the world holds (hands/feet) are locked and the virtual root rises/falls; the climb speed is exported as metadata."""
import numpy as np

import clipkit as CK
import gaitkit as GK
import params as PR
import rigkit as RK
import steps as ST
from clipkit import clip, keys, smooth, seg, pulse
from clips_canoe import anchored, to_local
from kin import Rz
from posekit import *      # noqa: F401,F403
import posekit as K
from clips_posture import pose_crouch, pose_supine

HANG = RK.ARM_HANG
NOGROUND = dict(ground=None)


def b(m=0.1, **kw):
    p = K.P(RK.stand(mood=m), armL=HANG.copy(), armR=HANG.copy(), wL=0.0, wR=0.0)
    return K.P(p, **kw) if kw else p


def OK(**kw):
    return O(stance=(True, True), ground=-10.0, **kw)


# ---------------------------------------------------------------------------------------------------- trunk climbing
TRUNK_F = 0.36            # trunk surface distance in front of the body axis (the body hugs the trunk)
STEP = 0.34
TCLIMB = 2.4
MOVE = 0.30


def limb_world_z(t, phase, z0, direction):
    """World height of a limb hold: held while the body rises, then moved one step up/down in the last MOVE of its cycle."""
    x = t / TCLIMB + phase
    k = np.floor(x)
    u = x - k
    mv = smooth((u - (1.0 - MOVE)) / MOVE)
    return z0 + direction * STEP * (k + mv), (np.sin(np.pi * np.clip((u - (1.0 - MOVE)) / MOVE, 0, 1)) if u > 1.0 - MOVE else 0.0)


def _tree(t, direction):
    v = direction * STEP / TCLIMB
    zb = v * t                                   # virtual root height
    pel_z = RK.HIP_Z - 0.06
    p = b(0.0)
    p["pel_auto"] = np.array([1.0, 0.03, 0.0])
    cyc = (t / TCLIMB) % 1.0
    sway = np.sin(TAU * cyc)
    p = K.P(p, pel=[0.012 * sway, 0.16, -0.06, -6, -2 * sway, 3 * sway], sp=[-10, 3 * sway, -4 * sway], hd=[-14 if direction > 0 else 8, 0, 6 * sway])
    tgt = {}
    for name, phase, z_rel0 in (("R", 0.00, 1.80), ("L", 0.50, 1.80), ("FL", 0.25, 0.55), ("FR", 0.75, 0.55)):
        zw, lift = limb_world_z(t, phase, z_rel0 - (0.0 if direction > 0 else STEP), direction)
        tgt[name] = (zw - zb, lift)
    # hands on the trunk (palms against it), feet flat against it with toes up
    zR, lR = tgt["R"]
    zL, lL = tgt["L"]
    p["armR_ik"] = K.ik(v3(-0.16, TRUNK_F - 0.03 + 0.06 * lR, zR), (0, -0.3, 1), (0, -1, 0.0), 10)
    p["armL_ik"] = K.ik(v3(0.16, TRUNK_F - 0.03 + 0.06 * lL, zL), (0, -0.3, 1), (0, -1, 0.0), -10)
    p["armR_w"] = np.array([1.0])
    p["armL_w"] = np.array([1.0])
    p["fR"] = RK.G("grip_big", 0.9)
    p["fL"] = RK.G("grip_big", 0.9)
    zFL, lFL = tgt["FL"]
    zFR, lFR = tgt["FR"]
    p["ftL"] = np.array([0.12, -(TRUNK_F - 0.10 + 0.07 * lFL), zFL, -62, 0, 8])
    p["ftR"] = np.array([-0.12, -(TRUNK_F - 0.10 + 0.07 * lFR), zFR, -62, 0, -8])
    p = add(p, hd=[0, 0, 0])
    p["look"] = np.array([0.0, -TRUNK_F, 2.6 if direction > 0 else 0.3, 0.6])
    p = addf(p, furrow=0.3, squint=0.2, jaw=2)
    p = RK.breathing(p, t, TCLIMB / 2, 1.5)
    o = OK(world=dict(pos=(0.0, 0.0, zb), yaw=0.0))
    return p, o


mk("tree_climb_up", "climbing", TCLIMB, loop=True, root="inplace_vertical", climb_speed=STEP / TCLIMB,
   desc="Climbing a leaning palm trunk, hand over hand and foot over foot (0.14 m/s upwards): hugging the trunk with the soles flat against it. In-place; the virtual root rises at climb_speed.",
   props=["palm"], interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="tree_hold", end_pose="tree_hold")(lambda t: _tree(t, +1))
mk("tree_climb_down", "climbing", TCLIMB, loop=True, root="inplace_vertical", climb_speed=-STEP / TCLIMB,
   desc="Climbing back down the trunk feet first, one limb at a time (0.14 m/s downward). In-place; the virtual root descends.",
   props=["palm"], interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="tree_hold", end_pose="tree_hold")(lambda t: _tree(t, -1))


def _tree_rest(t):
    p, o = _tree(0.0, +1)
    T = 6.0
    rest = pulse(t, 0.5, 1.5, 4.5, 5.5)
    p = add(p, sp=[0, 0, 0], hd=[14 * rest, 0, 8 * np.sin(TAU * t / T)])
    p["look"] = np.array([0.0, -TRUNK_F, 1.8, 0.0])
    p = add(p, sp=[4 * rest + 1.2 * np.sin(TAU * t / 3.0), 0, 0], pel=[0, 0.02 * rest, 0, 0, 0, 0])
    p = addf(p, squint=0.4 * rest, jaw=3 * np.sin(TAU * t / 3.0) ** 2)
    return p, o


mk("tree_hold_rest", "climbing", 6.0, loop=True, desc="Resting mid-climb: arms and legs locked around the trunk, forehead dropping towards the bark, deep breaths.",
   props=["palm"], interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="tree_hold", end_pose="tree_hold")(_tree_rest)


def _reach_handhold(t):
    a = env(t, 0.2, 0.9, 1.5, 2.2)
    test = np.sin(TAU * 2.5 * (t - 1.0)) * env(t, 1.1, 1.3, 1.7, 1.9)
    p = b(0.1)
    p = add(p, sp=[-8 * a, 3 * a, 0], hd=[-22 * a, 0, -6 * a], pel=[0.01 * a, 0.03 * a, 0.02 * a, -3 * a, 0, 0])
    p["armR_ik"] = K.ik(v3(-0.18, 0.40, 2.05 + 0.02 * test), (0, -0.3, 1), (0, -1, 0), 10)
    p["armR_w"] = np.array([a])
    p["armR"] = HANG + np.array([150 * a, 10 * a, 0, 20 * a, 0, 0])
    p["fR"] = RK.G("open", 0.8 * (1 - smooth(seg(t, 0.9, 1.3))) * a + RK.G("grip_big", 0.9)[0] * 0)
    p["fR"] = RK.G("grip_big", 1.0 * smooth(seg(t, 1.0, 1.4)) * a + 0.1 * (1 - smooth(seg(t, 1.0, 1.4))))
    p["armL"] = HANG + np.array([12 * a, 12 * a, 0, 24 * a, 0, 0])
    p["ftL"] = np.array(p["ftL"]) + np.array([0, 0, 0, 0, 0, 0])
    p["look"] = np.array([-0.18, -0.4, 2.1, 0.8 * a])
    p = addf(p, furrow=0.3 * a, squint=0.3 * a)
    return p, O()


mk("reach_for_handhold", "climbing", 2.2, desc="Reaches high for a rock or branch, stretching onto his toes, tests the hold with a tug, then commits his weight.",
   interrupt="any", blend_in=0.2, blend_out=0.3, start_pose="stand", end_pose="stand")(_reach_handhold)


def _approach_tree(t):
    a = env(t, 0.3, 1.0, 1.9, 2.6)
    p = b(0.2)
    p = add(p, sp=[6 * a, 0, 0], hd=[-26 * a, 0, 8 * a], pel=[0, 0.0, 0, 2 * a, 0, 0])
    p["armR_ik"] = K.ik(v3(-0.14, 0.34, 1.30), (0, -0.3, 1), (0, -1, 0), 10)
    p["armR_w"] = np.array([a])
    p["armR"] = HANG + np.array([60 * a, 6 * a, 0, 40 * a, 0, 0])
    p["fR"] = RK.G("flat", 0.5 * a)
    p["look"] = np.array([0.0, -0.4, 3.2, 0.8 * a])
    p = addf(p, squint=0.3 * a, brow_L=0.4 * a, brow_R=0.4 * a)
    return p, O()


mk("climb_approach_tree", "climbing", 2.6, desc="Stops at a palm trunk, lays a hand on the bark and looks up the length of it, sizing up the climb.", interrupt="any",
   blend_in=0.2, blend_out=0.3, start_pose="stand", end_pose="stand_at_tree")(_approach_tree)


# ---------------------------------------------------------------------------------------------------- boulders and rocks
BOULDER_H = 1.0


def _boulder_up(t):
    root = SK_kv(t, [(0.0, [0, 0.0, 0.0, 0]), (0.6, [0, -0.08, 0.0, 0]), (1.4, [0, -0.22, 0.28, 0]), (2.2, [0, -0.36, 0.64, 0]), (2.8, [0, -0.46, BOULDER_H, 0]), (3.5, [0, -0.50, BOULDER_H, 0])])
    rt = np.array(root)
    fl = SK_kv(t, [(0.0, [0.10, 0.0, AZ, 0, 0, 0]), (1.7, [0.10, 0.0, AZ, 0, 0, 0]), (2.2, [0.14, -0.50, 0.86 + AZ, -10, 0, 10]), (3.2, [0.10, -0.52, BOULDER_H + AZ, 0, 0, 0])])
    fr = SK_kv(t, [(0.0, [-0.10, 0.0, AZ, 0, 0, 0]), (0.8, [-0.10, 0.0, AZ, 0, 0, 0]), (1.3, [-0.12, -0.46, 0.46 + AZ, -20, 0, -10]), (2.4, [-0.12, -0.46, 0.46 + AZ, -20, 0, -10]),
                   (2.9, [-0.12, -0.58, BOULDER_H + AZ, -5, 0, 0]), (3.5, [-0.10, -0.54, BOULDER_H + AZ, 0, 0, 0])])
    p = b(0.0)
    lean = env(t, 0.4, 1.2, 2.4, 3.2)
    p = add(p, sp=[26 * lean, 0, 0], hd=[-22 * lean, 0, 0], pel=[0, 0.0, -0.10 * lean, 8 * lean, 0, 0])
    p = anchored(p, rt, fl, fr)
    top = to_local(rt, [0.0, -0.70, BOULDER_H + 0.05])
    grab = smooth(seg(t, 0.5, 1.0)) * (1 - smooth(seg(t, 2.7, 3.2)))
    p["armR_ik"] = K.ik(to_local(rt, [-0.20, -0.66, BOULDER_H + 0.04]), (0, -1, 0), (0, 0, -1), 10)
    p["armL_ik"] = K.ik(to_local(rt, [0.20, -0.66, BOULDER_H + 0.04]), (0, -1, 0), (0, 0, -1), -10)
    p["armR_w"] = np.array([grab])
    p["armL_w"] = np.array([grab])
    p["armR"] = HANG + np.array([60, 10, 0, 20, 0, 0])
    p["armL"] = HANG + np.array([60, 10, 0, 20, 0, 0])
    p["fR"] = RK.G("grip_big", 0.9)
    p["fL"] = RK.G("grip_big", 0.9)
    p["look"] = np.array([0.0, -0.7, BOULDER_H + 0.3, 0.8])
    p = addf(p, furrow=0.4 * lean, jaw=4 * lean, squint=0.2)
    return p, OK(root_note="anchored")


def SK_kv(t, kf):
    import staffkit as SK
    return SK.kv(t, kf)


mk("climb_onto_boulder", "climbing", 3.5, root="anchored", desc="Hauls himself onto a 1 m boulder: hands on the lip, one foot on a ledge, a knee up onto the top and a push to stand. Root baked relative to the anchor at the foot of the rock.",
   props=["boulder"], interrupt="none", blend_in=0.2, blend_out=0.3, start_pose="stand_at_boulder", end_pose="stand_on_boulder", anchor="boulder_base", events=[(0.5, "hands_on_lip"), (2.3, "knee_on_top")])(_boulder_up)


def _boulder_down(t):
    p, o = _boulder_up(3.5 - t)
    return p, o


mk("climb_down_boulder", "climbing", 3.5, root="anchored", desc="Lowers himself off the 1 m boulder facing it (the climb played in reverse): lies on the edge, feels for the ledge, drops to the ground.",
   props=["boulder"], interrupt="none", blend_in=0.2, blend_out=0.3, start_pose="stand_on_boulder", end_pose="stand_at_boulder", anchor="boulder_base")(_boulder_down)


def _step_down_rock(t):
    H = 0.5
    root = SK_kv(t, [(0.0, [0, 0.0, H, 0]), (0.35, [0, -0.05, H, 0]), (0.75, [0, -0.28, H - 0.18, 0]), (1.05, [0, -0.42, 0.04, 0]), (1.25, [0, -0.44, -0.02, 0]), (1.7, [0, -0.46, 0.0, 0])])
    rt = np.array(root)
    fl = SK_kv(t, [(0.0, [0.10, 0.0, H + AZ, 0, 0, 0]), (0.35, [0.10, 0.0, H + AZ, 0, 0, 0]), (0.9, [0.10, -0.55, AZ + 0.04, 12, 0, 0]), (1.7, [0.10, -0.55, AZ, 0, 0, 0])])
    fr = SK_kv(t, [(0.0, [-0.10, 0.0, H + AZ, 0, 0, 0]), (0.85, [-0.10, 0.0, H + AZ, 0, 0, 0]), (1.25, [-0.10, -0.38, AZ + 0.05, 8, 0, 0]), (1.7, [-0.10, -0.38, AZ, 0, 0, 0])])
    p = b(0.1)
    lean = env(t, 0.2, 0.6, 0.9, 1.4)
    land = env(t, 0.9, 1.1, 1.2, 1.6)
    p = add(p, sp=[8 * lean - 6 * land, 0, 0], pel=[0, 0, -0.04 * land, 4 * lean, 0, 0], hd=[-4 * lean, 0, 0])
    p = anchored(p, rt, fl, fr)
    p["armL"] = HANG + np.array([-10 + 40 * land, 22 * land, 0, 10 + 20 * land, 0, 0])
    p["armR"] = HANG + np.array([-10 + 40 * land, 22 * land, 0, 10 + 20 * land, 0, 0])
    return p, OK()


mk("step_down_rock", "climbing", 1.7, root="anchored", desc="Steps down off a 0.5 m rock: a controlled reach with the left foot, weight transfer, soft landing with the knees and arms out for balance.",
   props=["rock"], interrupt="none", blend_in=0.15, blend_out=0.25, start_pose="stand_on_rock", end_pose="stand", anchor="rock_base", events=[(1.05, "foot_lands")])(_step_down_rock)


# ---------------------------------------------------------------------------------------------------- scrambling / balance / lookout
CLAMBER = GK.Gait(T=58 / 30, v=0.45, duty=0.72, x=0.12, toe_out=8.0, bob=0.015, sway=0.04, roll=4.0, pyaw=5.0, syaw=10.0, arm=0.0, elbow0=20.0, elbow1=0.0,
                  lean=34.0, z0=-0.26, out=-8.0, head_stab=0.5, foot=ST.Cfg(lift=0.22, toe_pitch=30.0, heel_pitch=2.0, roll_on=0.08, heel_off=0.50))


def _clamber(t):
    steps = GK.make_steps(CLAMBER)
    prm, opts = GK.gait_params(t, CLAMBER, steps)
    prm = K.P(prm, wL=0.0, wR=0.0)
    ph = (t / CLAMBER.T) % 1.0
    c = np.cos(TAU * ph)
    # hands scramble on the rock alternately: reach forward-down, then push back
    for sd, ofs, sgn in (("L", 0.0, 1.0), ("R", 0.5, -1.0)):
        q = (ph + ofs) % 1.0
        reach = np.sin(np.pi * q) ** 1.2
        prm[f"arm{sd}_ik"] = K.ik(v3(sgn * 0.20, 0.30 + 0.30 * reach, 0.62 - 0.12 * reach + 0.10 * (1 - reach)), (0, -1, -0.2), (0, 0, -1), sgn * 10)
        prm[f"arm{sd}_w"] = np.array([0.9])
        prm[f"f{sd}"] = RK.G("open", 0.6 + 0.3 * reach)
    prm["look"] = np.array([0.0, -2.0, 0.9, 0.6])
    prm = addf(prm, furrow=0.3, squint=0.3, jaw=3)
    o = O(stance=(True, True), world=opts["world"])
    return prm, o


mk("clamber_rocks", "climbing", CLAMBER.T, loop=True, speed=CLAMBER.v, desc="Scrambling up a jumble of rocks on all fours-ish: deep forward lean, hands slapping onto holds alternately with the opposite foot stepping up (0.45 m/s).",
   interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="stand", end_pose="stand")(_clamber)


def _balance(t):
    T = 4.0
    ph = t / T
    wob = np.sin(TAU * ph * 2) * 0.6 + np.sin(TAU * ph * 3 + 1) * 0.4
    p = b(0.0)
    p["pel"] = np.array([-0.045 + 0.012 * wob, 0.0, -0.05, 0, 3 * wob, 0])
    p["ftL"] = np.array([0.10, 0.0, AZ + 0.02, 0, 0, 0])
    p["ftR"] = np.array([-0.16 + 0.04 * wob, 0.14 + 0.06 * np.sin(TAU * ph), AZ + 0.20 + 0.04 * wob, 14, 0, -10])
    p = add(p, sp=[3, -6 * wob, 5 * wob], hd=[-4, 3 * wob, 0])
    p["armL"] = HANG + np.array([14 * wob, 66 - 8 * wob, 0, 14, 0, 0])
    p["armR"] = HANG + np.array([-10 * wob, 70 + 8 * wob, 0, 14, 0, 0])
    p["fL"] = RK.G("open", 0.5)
    p["fR"] = RK.G("open", 0.5)
    p["look"] = np.array([0.0, -2.0, 0.0, 0.6])
    p = addf(p, furrow=0.3, squint=0.2, jaw=3)
    return p, O(stance=(True, False))


mk("balance_uneven", "climbing", 4.0, loop=True, desc="Balancing on one foot on unstable ground: arms out and wobbling, torso counter-swaying, free foot hovering for a recovery step.",
   interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="stand", end_pose="stand")(_balance)


def _lookout(t):
    T = 10.0
    ph = t / T
    p = b(0.3)
    p["ftL"] = FT("L", 0.19, 0.04, AZ, 0, 0, 14)
    p["ftR"] = FT("R", -0.19, -0.06, AZ, 0, 0, -12)
    scan = np.sin(TAU * ph)
    p = add(p, sp=[4, 0, 14 * scan], hd=[-4 + 2 * np.sin(TAU * ph * 2), 0, 40 * scan * np.cos(TAU * ph * 0.5)], pel=[0, 0, -0.02, 0, 0, 4 * scan])
    p["armL_ik"] = K.ik(v3(0.22, 0.05, 1.06), (0.2, -1, -0.2), (-0.6, 0.2, 0.8), 10)
    p["armL_w"] = np.array([1.0])
    shade = pulse(t, 1.5, 2.3, 6.5, 7.5)
    p = K.hand_to_head(p, "R", v3(-0.07, 0.14, 1.93), (0.4, -0.7, 0.1), (0.1, 0.1, -1.0), None, w=shade)
    p["armR"] = HANG + np.array([60 * shade, 18 * shade, 0, 100 * shade, 0, 0])
    p["eye"] = np.array([0.1 * scan * 20, -2.0])
    p = addf(p, squint=0.4 * shade + 0.1, smile_L=0.2, smile_R=0.15)
    p = RK.breathing(p, t, 4.2, 1.0)
    return p, O(stance=(True, True))


mk("high_lookout", "climbing", 10.0, loop=True, desc="Standing tall on a high perch, feet planted wide against the wind, one fist on the hip, the other hand shading his eyes while he scans the horizon.",
   interrupt="any", blend_in=0.4, blend_out=0.4, start_pose="stand_wide", end_pose="stand_wide")(_lookout)


def _look_down(t):
    a = env(t, 0.3, 1.2, 2.4, 3.4)
    gulp = np.sin(TAU * 1.6 * t) * 0.3
    p = b(0.0)
    p["ftL"] = FT("L", 0.15, 0.06, AZ, 0, 0, 10)
    p["ftR"] = FT("R", -0.15, -0.14, AZ, 0, 0, -8)
    p = add(p, sp=[26 * a, 0, 4 * a], hd=[28 * a, 0, -6 * a], pel=[0, 0.08 * a, -0.14 * a, 8 * a, 0, 0])
    p["armL_ik"] = K.ik(v3(0.14, 0.34, 0.74), (-0.1, -1, 0.0), (-0.7, 0, 0.7), -10)
    p["armL_w"] = np.array([a])
    p["armR"] = HANG + np.array([30 * a, 40 * a, 0, 40 * a, 0, 0])
    p["fL"] = RK.G("grip_big", 0.8 * a)
    p["look"] = np.array([0.1, -1.4, -3.0, a])
    p = addf(p, wide=0.5 * a, brow_L=0.6 * a, brow_R=0.6 * a, jaw=3 * a, frown=0.2 * a)
    p = add(p, sp=[gulp * a, 0, 0])
    return p, O(stance=(True, True))


mk("look_down_from_height", "climbing", 3.4, desc="Peers over the edge of a high drop: leans forward from a braced stance, hand pressed on the knee, eyes wide, a nervous swallow.",
   interrupt="any", blend_in=0.2, blend_out=0.3, start_pose="stand_wide", end_pose="stand_wide")(_look_down)


# ---------------------------------------------------------------------------------------------------- water
WADE = GK.Gait(T=44 / 30, v=0.95, duty=0.64, x=0.105, toe_out=6.0, bob=0.020, sway=0.030, roll=3.0, pyaw=4.0, syaw=6.0, arm=10.0, elbow0=20.0, elbow1=8.0,
               lean=6.0, z0=-0.05, out=-30.0, head_stab=0.8, foot=ST.Cfg(lift=0.36, toe_pitch=24.0, heel_pitch=6.0, roll_on=0.10, heel_off=0.55, toe_clear=12.0, lift_peak=0.45))


def _wade(t):
    steps = GK.make_steps(WADE)
    prm, opts = GK.gait_params(t, WADE, steps)
    prm = K.P(prm, wL=0.0, wR=0.0)
    ph = (t / WADE.T) % 1.0
    c = np.cos(TAU * ph)
    prm["armL"] = HANG + np.array([-10 * c + 4, 30, 0, 22, 0, 0])
    prm["armR"] = HANG + np.array([10 * c + 4, 30, 0, 22, 0, 0])
    prm["fL"] = RK.G("open", 0.4)
    prm["fR"] = RK.G("open", 0.4)
    prm["look"] = np.array([0.0, -4.0, 0.6, 0.5])
    o = O(stance=(True, True), world=opts["world"])
    return prm, o


mk("wade", "water", WADE.T, loop=True, speed=WADE.v, desc="Wading through knee-deep water (0.95 m/s): high lifted knees, arms held out and low for balance, slower rhythm. timeScale = speed / 0.95.",
   interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="stand", end_pose="stand")(_wade)


def prone_base(m=0.1):
    """Prone, floating at the surface: the body pitched 90 degrees forward about the hips and lowered to the water line."""
    p = b(m)
    p["pel"] = np.array([0, 0.0, -(RK.HIP_Z - 0.10), 90, 0, 0])
    p["sp"] = np.array([-10.0, 0, 0])
    p["hd"] = np.array([-30.0, 0, 0])
    return p


def _swim_crawl(t):
    T = 1.6
    ph = t / T
    p = prone_base(0.0)
    roll = 14 * np.sin(TAU * ph)
    p["pel"] = p["pel"] + np.array([0, 0, 0.0, 0, roll, 0])
    p["sp"] = p["sp"] + np.array([0, -roll * 0.4, 0])
    for sd, off in (("L", 0.0), ("R", 0.5)):
        q = (ph + off) % 1.0
        if q < 0.5:                                  # recovery: arm swings over the water, elbow high
            u = q / 0.5
            fwd = -20 + 190 * smooth(u)
            out = 30 + 25 * np.sin(np.pi * u)
            elb = 70 * np.sin(np.pi * u)
        else:                                        # pull: arm drawn back under the body
            u = (q - 0.5) / 0.5
            fwd = 170 - 190 * smooth(u)
            out = 10 + 15 * np.sin(np.pi * u)
            elb = 45 * np.sin(np.pi * u)
        p[f"arm{sd}"] = np.array([fwd, out, 0.0, elb, 0, 0])
        p[f"f{sd}"] = RK.G("flat", 0.7)
    # flutter kick
    for sd, off in (("L", 0.0), ("R", 0.25)):
        s = 1.0 if sd == "L" else -1.0
        kz = 0.13 * np.sin(TAU * ph * 3 + (0 if sd == "L" else np.pi))
        p[f"ft{sd}"] = np.array([s * 0.09, 0.90, 0.10 + kz, 30, 0, 0])
    # breathing: head turns to the side every second stroke
    br = pulse(t % T, 0.5, 0.7, 0.9, 1.1) if False else 0.5 * (1 + np.sin(TAU * ph - 1.2)) ** 3
    p = add(p, hd=[0, 0, 0], sp=[0, 0, 0])
    p["hd"] = p["hd"] + np.array([20 * br, 10 * br, 55 * br * (1 if True else 0)])
    p = addf(p, pucker=0.3 * br, jaw=8 * br)
    return p, O(stance=(False, False), ground=-10.0)


mk("swim_crawl", "water", 1.6, loop=True, desc="Front crawl at the surface: alternating overarm strokes, flutter kick, body roll with a breath to the side on every other stroke.",
   interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="swim_prone", end_pose="swim_prone", swim_height=0.0)(_swim_crawl)


def _swim_breast(t):
    T = 2.6
    ph = t / T
    p = prone_base(0.1)
    if ph < 0.35:                                   # pull: hands sweep out and back
        u = ph / 0.35
        out = 20 + 50 * np.sin(np.pi * u * 0.8)
        fwd = 165 - 70 * u
    elif ph < 0.60:                                 # recover: hands come together under the chin
        u = (ph - 0.35) / 0.25
        out = 40 - 30 * u
        fwd = 95 + 20 * u
    else:                                           # glide: arms stretched forward
        u = (ph - 0.60) / 0.40
        out = 10
        fwd = 115 + 55 * smooth(u)
    for sd in ("L", "R"):
        p[f"arm{sd}"] = np.array([fwd, out, 0.0, 30 if ph < 0.6 else 4, 0, 0])
        p[f"f{sd}"] = RK.G("flat", 0.7)
    # frog kick: knees draw up and the feet sweep out and round
    k = 0.5 + 0.5 * np.sin(TAU * ph - 1.6)
    for sd in ("L", "R"):
        s = 1.0 if sd == "L" else -1.0
        p[f"ft{sd}"] = np.array([s * (0.10 + 0.22 * np.sin(np.pi * np.clip((ph - 0.3) / 0.4, 0, 1))), 0.95 - 0.40 * np.sin(np.pi * np.clip((ph - 0.25) / 0.45, 0, 1)),
                                 0.10 + 0.05 * k, 20, 0, 0])
    lift = pulse(ph, 0.2, 0.35, 0.55, 0.65)
    p["hd"] = p["hd"] + np.array([30 * lift, 0, 0])
    p["sp"] = p["sp"] + np.array([10 * lift, 0, 0])
    return p, O(stance=(False, False), ground=-10.0)


mk("swim_breaststroke", "water", 2.6, loop=True, desc="Relaxed breaststroke: pull, breathe with the head up, frog kick and a long glide with the arms stretched forward.",
   interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="swim_prone", end_pose="swim_prone", swim_height=0.0)(_swim_breast)


def _float_back(t):
    T = 8.0
    ph = t / T
    p = pose_supine(1.0)
    p = K.P(p, armL=p["armL"], armR=p["armR"], wL=0.0, wR=0.0)
    sc = np.sin(TAU * t / 2.0)
    p["armL"] = HANG + np.array([0, 60 + 4 * sc, 0, 8, 0, 0])
    p["armR"] = HANG + np.array([0, 60 - 4 * sc, 0, 8, 0, 0])
    p["armL"][0] = -4
    p["armR"][0] = -4
    bob = 0.012 * np.sin(TAU * ph)
    p["pel"] = np.array(p["pel"]) + np.array([0, 0, bob, 0, 0, 0])
    p["hd"] = np.array(p["hd"]) + np.array([-4, 0, 6 * np.sin(TAU * ph)])
    p["fL"] = RK.G("open", 0.4)
    p["fR"] = RK.G("open", 0.4)
    p = addf(p, smile_L=0.3, smile_R=0.3)
    p = RK.breathing(p, t, 4.0, 1.5)
    return p, dict(arm_mode=("fk", "fk"), stance=(False, False), ground=-10.0)


mk("float_on_back", "water", 8.0, loop=True, desc="Floating on his back at the surface, arms spread and sculling gently, slow deep breaths, eyes closed against the sun.",
   interrupt="any", blend_in=0.4, blend_out=0.4, start_pose="swim_supine", end_pose="swim_supine", swim_height=0.0)(_float_back)


def _tread(t):
    T = 3.0
    ph = t / T
    p = b(0.0)
    p["root"] = np.array([0.0, 0.0, -0.55, 0.0])
    # eggbeater legs: the feet circle alternately below the pelvis
    for sd, off in (("L", 0.0), ("R", 0.5)):
        s = 1.0 if sd == "L" else -1.0
        a = TAU * (ph + off)
        p[f"ft{sd}"] = np.array([s * (0.16 + 0.07 * np.cos(a)), 0.10 * np.sin(a) - 0.05, 0.28 + 0.07 * np.sin(a) - 0.0, -10, 0, 0])
    # arms scull at the sides
    sc = np.sin(TAU * ph * 2)
    p["armL"] = HANG + np.array([20, 44 + 8 * sc, 0, 50 + 10 * np.cos(TAU * ph * 2), 0, 0])
    p["armR"] = HANG + np.array([20, 44 - 8 * sc, 0, 50 - 10 * np.cos(TAU * ph * 2), 0, 0])
    p["fL"] = RK.G("flat", 0.6)
    p["fR"] = RK.G("flat", 0.6)
    p = add(p, sp=[0, 0.8 * sc, 0], hd=[0, 1.5 * sc, 4 * np.sin(TAU * ph)], pel=[0, 0, 0.01 * np.sin(TAU * ph * 2), 0, 0, 0])
    p["look"] = np.array([0.0, -4.0, 0.0, 0.4])
    p = addf(p, jaw=2, squint=0.2, smile_L=0.1, smile_R=0.1)
    return p, O(stance=(False, False), ground=-10.0)


mk("tread_water", "water", 3.0, loop=True, desc="Treading water upright with the root sunk 0.55 m: eggbeater leg circles, hands sculling at the sides, chin just above the surface.",
   interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="tread", end_pose="tread", swim_height=-0.55)(_tread)
