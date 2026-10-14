"""Tier 1: sitting, kneeling, lying, sleeping, waking."""
import numpy as np

import clipkit as CK
import params as PR
import rigkit as RK
from clipkit import clip, keys, smooth
from rigkit import FT, ik_hand, hang_ik

TAU = 2 * np.pi
HZ = RK.HIP_Z
AZ = RK.ANKLE_Z


def S(**kw):
    """stand pose + updates; arms in IK world mode defaults to hanging hands."""
    p = RK.stand()
    p["armL_ik"] = hang_ik("L")
    p["armR_ik"] = hang_ik("R")
    return PR.update(p, **kw) if kw else p


def hands(p, L=None, R=None, grip_L=None, grip_R=None):
    p = PR.copy(p)
    if L is not None:
        p["armL_ik"] = np.asarray(L, float)
    if R is not None:
        p["armR_ik"] = np.asarray(R, float)
    if grip_L:
        p["fL"] = RK.G(grip_L)
    if grip_R:
        p["fR"] = RK.G(grip_R)
    return p


FLAT = (0, 1, 0)


def arms(p, L, R=None):
    p = PR.copy(p)
    p["armL"] = np.array(L, float)
    p["armR"] = np.array(L if R is None else R, float)
    return p


ARM_SITTING = [38.0, -14.0, 0.0, 52.0, 0, 0]
ARM_BEHIND = [-28.0, -6.0, 0.0, 10.0, 0, 0]
ARM_BAL = [24.0, -10.0, 0.0, 36.0, 0, 0]


def palm_down(x, f, z, fd=(0, 1, 0)):
    return ik_hand([x, -f, z], fd, (0, 0, -1))


def palm_in(side, x, f, z):
    """palm facing the body's midline (hand resting on a thigh)."""
    s = 1.0 if side == "L" else -1.0
    return ik_hand([x, -f, z], (0, -1, 0), (-s, 0, 0))


# ---------------------------------------------------------------------------------------------------- posture poses
def pose_sit_ground(knees=0.60, grip="relaxed", hands_on="knees"):
    p = S()
    p = PR.update(p, pel=[0, 0.05, -(HZ - 0.085), -12, 0, 0], sp=[24, 0, 0], hd=[-14, 0, 0],
                  ftL=FT("L", 0.15, knees, AZ + 0.01, -14, -8, 14), ftR=FT("R", -0.15, knees, AZ + 0.01, -14, 8, -14))
    if hands_on == "knees":
        p = hands(p, palm_in("L", 0.16, knees * 0.55, 0.40), palm_in("R", -0.16, knees * 0.55, 0.40))
    p["fL"] = RK.G(grip)
    p["fR"] = RK.G(grip)
    return p


def pose_kneel(hands_on="thighs"):
    p = S()
    p = PR.update(p, pel=[0, 0.02, -(HZ - 0.50), 0, 0, 0], sp=[6, 0, 0], hd=[-6, 0, 0],
                  ftL=FT("L", 0.105, -0.42, 0.10, 160, 0, 0), ftR=FT("R", -0.105, -0.42, 0.10, 160, 0, 0))
    p = hands(p, palm_in("L", 0.14, 0.12, 0.62), palm_in("R", -0.14, 0.12, 0.62))
    return p


def pose_supine(arms_out=0.0):
    p = S()
    p = PR.update(p, pel=[0, 0.0, -(HZ + 0.02 - 0.12), -90, 0, 0], sp=[0, 0, 0], hd=[8, 0, 0],
                  ftL=FT("L", 0.13, 0.95, 0.09, -80, -12, 0), ftR=FT("R", -0.13, 0.95, 0.09, -80, 12, 0))
    p["armL"] = RK.ARM_HANG + np.array([0, 4 + 30 * arms_out, 0, 0, 0, 0])
    p["armR"] = RK.ARM_HANG + np.array([0, 4 + 30 * arms_out, 0, 0, 0, 0])
    p["armL_ik"] = ik_hand([0.27 + 0.12 * arms_out, -0.06, 0.075], (0, -1, 0), (0, 0, -1), 50)
    p["armR_ik"] = ik_hand([-0.27 - 0.12 * arms_out, -0.06, 0.075], (0, -1, 0), (0, 0, -1), -50)
    return p


def pose_crouch(depth=0.42):
    p = S()
    return PR.update(p, pel=[0, 0.12 * depth / 0.4, -depth, 12 * depth / 0.4, 0, 0], sp=[22 * depth / 0.4, 0, 0], hd=[-18 * depth / 0.4, 0, 0],
                     ftL=FT("L", 0.115, 0.04, AZ, 0, 0, 6), ftR=FT("R", -0.115, 0.04, AZ, 0, 0, -6))


def blendk(p, fk=None, w=0.0, L=None, R=None):
    """Key with FK arms and an optional IK target, blended with weight w (arm_mode 'blend')."""
    p = PR.copy(p)
    if fk is not None:
        p["armL"] = np.array(fk, float)
        p["armR"] = np.array(fk, float)
    if L is not None:
        p["armL_ik"] = np.asarray(L, float)
    if R is not None:
        p["armR_ik"] = np.asarray(R, float)
    p["armL_w"] = np.array([w])
    p["armR_w"] = np.array([w])
    return p


def opts_blend():
    return dict(arm_mode=("blend", "blend"), arm_space=("world", "world"), stance=(True, True))


def opts_ik():
    return dict(arm_mode=("ik", "ik"), arm_space=("world", "world"), stance=(True, True))


def opts_lying():
    return dict(arm_mode=("fk", "fk"), stance=(False, False))


def seq(t, kf, ease="smooth"):
    return keys(t, kf, ease=ease)


# ---------------------------------------------------------------------------------------------------- sit down / idle / up
def _sit_down(t):
    st = blendk(S(), RK.ARM_HANG, 0.0)
    k1 = blendk(pose_crouch(0.30), ARM_BAL, 0.0)
    k2 = blendk(PR.update(pose_crouch(0.58), pel=[0, 0.22, -0.58, 20, 0, 0], sp=[26, 0, 0], hd=[-20, 0, 0]), ARM_BAL, 0.0)
    k3 = blendk(PR.update(pose_sit_ground(0.62), pel=[0, 0.12, -(HZ - 0.12), -2, 0, 0], sp=[20, 0, 0], hd=[-8, 0, 0]), ARM_BAL, 1.0,
                palm_in("L", 0.18, 0.28, 0.46), palm_in("R", -0.18, 0.28, 0.46))
    k4 = blendk(pose_sit_ground(0.62), ARM_SITTING, 1.0)
    return seq(t, [(0.0, st), (0.55, k1), (1.15, k2), (1.75, k3), (2.4, k4)]), opts_blend()


@clip("sit_down", "posture", 2.4, desc="Standing to sitting on the ground: knees bend, weight sinks back, hands reach behind to lower the pelvis, then settle with the hands on the knees (ends in the `sit_idle` pose).",
      start_pose="stand", end_pose="sit_ground", interrupt="none", blend_in=0.2, blend_out=0.25, events=[(1.75, "pelvis_touch_ground")])
def sit_down(t):
    return RK.with_blinks(_sit_down, 2.4, 3)(t)


def _sit_idle(t):
    T = 7.0
    p = pose_sit_ground(0.62)
    ph = t / T
    s = np.sin(TAU * ph)
    p = PR.update(p, sp=[24 + 1.2 * s, 0, 2 * np.sin(TAU * ph * 2)], hd=[-14 - 2 * s, 0, 14 * np.sin(TAU * (ph + 0.2))],
                  eye=[8 * np.sin(TAU * (ph * 2 + 0.3)), 2 * s])
    p = RK.breathing(p, t, 4.0, 1.0)
    return p, opts_ik()


@clip("sit_idle", "posture", 7.0, loop=True, desc="Seated on the ground, knees up, hands resting on the knees: breathing, slow looking around at the sea.",
      start_pose="sit_ground", end_pose="sit_ground", interrupt="any", blend_in=0.3, blend_out=0.3)
def sit_idle(t):
    return RK.with_blinks(_sit_idle, 7.0, 4, every=(3.0, 5.0))(t)


def _stand_up(t):
    st = blendk(pose_sit_ground(0.62), ARM_SITTING, 1.0)
    k1 = blendk(PR.update(pose_sit_ground(0.50), pel=[0, 0.04, -(HZ - 0.20), 8, 0, 0], sp=[34, 0, 0], hd=[-20, 0, 0],
                          ftL=FT("L", 0.12, 0.42, AZ, 0, 0, 8), ftR=FT("R", -0.12, 0.42, AZ, 0, 0, -8)), ARM_BAL, 1.0,
                palm_in("L", 0.18, 0.30, 0.42), palm_in("R", -0.18, 0.30, 0.42))
    k2 = blendk(PR.update(pose_crouch(0.50), pel=[0, 0.16, -0.50, 22, 0, 0], sp=[34, 0, 0], hd=[-26, 0, 0],
                          ftL=FT("L", 0.115, 0.10, AZ, 0, 0, 6), ftR=FT("R", -0.115, 0.10, AZ, 0, 0, -6)), ARM_BAL, 0.0)
    k3 = blendk(pose_crouch(0.22), [10, -18, 0, 20, 0, 0], 0.0)
    k4 = blendk(S(), RK.ARM_HANG, 0.0)
    return seq(t, [(0.0, st), (0.50, k1), (1.05, k2), (1.55, k3), (2.1, k4)]), opts_blend()


@clip("stand_up", "posture", 2.1, desc="Sitting on the ground to standing: leans forward, feet pull in, hands push off the ground, rises through a crouch to a relaxed stand.",
      start_pose="sit_ground", end_pose="stand", interrupt="none", blend_in=0.2, blend_out=0.25, events=[(1.05, "hands_leave_ground")])
def stand_up(t):
    return RK.with_blinks(_stand_up, 2.1, 5)(t)


# ---------------------------------------------------------------------------------------------------- kneel
def _kneel_down(t):
    st = S()
    k1 = PR.update(pose_crouch(0.34), pel=[0, 0.08, -0.34, 10, 0, 0])
    k2 = PR.update(pose_crouch(0.50), pel=[0, 0.04, -0.50, 8, 0, 0], ftL=FT("L", 0.105, 0.05, AZ, 0, 0, 4), ftR=FT("R", -0.105, -0.10, AZ + 0.10, 70, 0, -4))
    k3 = pose_kneel()
    return seq(t, [(0.0, st), (0.45, k1), (0.95, k2), (1.5, k3)]), opts_ik()


@clip("kneel_down", "posture", 1.5, desc="Standing to kneeling on both knees (shins on the ground behind, hands settle on the thighs).",
      start_pose="stand", end_pose="kneel", interrupt="none", blend_in=0.2, blend_out=0.2, events=[(1.2, "knees_touch_ground")])
def kneel_down(t):
    return RK.with_blinks(_kneel_down, 1.5, 6)(t)


def _kneel_idle(t):
    T = 6.0
    p = pose_kneel()
    s = np.sin(TAU * t / T)
    p = PR.update(p, sp=[6 + 1.0 * s, 0, 2.0 * np.sin(TAU * t / T * 2)], hd=[-6, 0, 10 * np.sin(TAU * (t / T + 0.1))], pel=[0, 0.02 + 0.004 * s, -(HZ - 0.50) - 0.003 * s, 0, 0, 0])
    p = RK.breathing(p, t, 4.0, 1.0)
    return p, opts_ik()


@clip("kneel_idle", "posture", 6.0, loop=True, desc="Kneeling quietly (both knees down), breathing, small head turns.", start_pose="kneel", end_pose="kneel",
      interrupt="any", blend_in=0.3, blend_out=0.3)
def kneel_idle(t):
    return RK.with_blinks(_kneel_idle, 6.0, 7)(t)


def _kneel_rise(t):
    st = pose_kneel()
    k1 = PR.update(pose_kneel(), pel=[0, -0.08, -(HZ - 0.58), 14, 0, 0], sp=[18, 0, 0], ftL=FT("L", 0.105, 0.30, AZ, 0, 0, 4),
                   armL_ik=ik_hand([0.25, -0.34, 0.60], (0, -1, 0), (-1, 0, 0)))
    k1 = PR.update(k1, ftR=FT("R", -0.105, -0.30, 0.10, 150, 0, 0))
    k2 = PR.update(pose_crouch(0.45), pel=[0, 0.02, -0.46, 20, 0, 0], sp=[26, 0, 0], hd=[-18, 0, 0])
    k3 = S()
    return seq(t, [(0.0, st), (0.55, k1), (1.1, k2), (1.65, k3)]), opts_ik()


@clip("kneel_rise", "posture", 1.65, desc="Rising from kneeling: one foot steps forward, hands push on the knee, stand up straight.", start_pose="kneel", end_pose="stand",
      interrupt="none", blend_in=0.2, blend_out=0.25)
def kneel_rise(t):
    return RK.with_blinks(_kneel_rise, 1.65, 8)(t)


# ---------------------------------------------------------------------------------------------------- lying / sleeping
def _lie_down(t):
    st = S()
    bal = lambda x: hang_ik(x) + np.array([0, -0.18, 0.15, 0, 0, 0, 0, 0, 0, 0])
    k1 = PR.update(pose_crouch(0.34), pel=[0, 0.08, -0.34, 10, 0, 0], armL_ik=bal("L"), armR_ik=bal("R"))
    k2 = hands(PR.update(pose_sit_ground(0.62), pel=[0, 0.10, -(HZ - 0.085), -4, 0, 0], sp=[4, 0, 0], hd=[-4, 0, 0],
                         ftL=FT("L", 0.15, 0.78, AZ + 0.01, -14, -8, 14), ftR=FT("R", -0.15, 0.78, AZ + 0.01, -14, 8, -14)),
               palm_down(0.22, -0.22, 0.04), palm_down(-0.22, -0.22, 0.04))
    k3 = hands(PR.update(pose_sit_ground(0.9), pel=[0, 0.12, -(HZ - 0.10), -34, 0, 0], sp=[-8, 0, 0], hd=[0, 0, 0],
                         ftL=FT("L", 0.13, 0.86, AZ + 0.01, -40, -10, 8), ftR=FT("R", -0.13, 0.86, AZ + 0.01, -40, 10, -8)),
               palm_down(0.22, -0.34, 0.04), palm_down(-0.22, -0.34, 0.04))
    k4 = pose_supine()
    return seq(t, [(0.0, st), (0.55, k1), (1.25, k2), (1.95, k3), (2.8, k4)]), opts_ik()


@clip("lie_down", "posture", 2.8, desc="Standing to lying on the back (head ends toward the character's rear): crouch, sit, recline on the hands, lie flat.",
      start_pose="stand", end_pose="lie_supine", interrupt="none", blend_in=0.2, blend_out=0.3, events=[(1.25, "pelvis_touch_ground"), (2.7, "back_flat")])
def lie_down(t):
    return RK.with_blinks(_lie_down, 2.8, 9)(t)


def _sleep(t):
    T = 6.0
    p = pose_supine(0.15)
    s = np.sin(TAU * t / T)
    p = PR.update(p, sp=[-0.8 * s, 0, 0], hd=[8 + 0.5 * s, 0, 4], pel=[0, 0, -(HZ + 0.02 - 0.12) + 0.002 * s, -90, 0, 0])
    p["armR"] = np.array([-18.0 + 0.8 * s, -40.0, -35.0, 118.0, 0, 0])      # forearm across the chest
    p = RK.fset(p, blink_L=1.0, blink_R=1.0, smile_L=0.02, smile_R=0.0, jaw=3.0 + 1.5 * (0.5 + 0.5 * s), brow_L=0.0, brow_R=0.0)
    return p, opts_lying()


@clip("sleep_loop", "posture", 6.0, loop=True, desc="Sleeping on the back: slow breathing (chest/belly rise, jaw relaxed and slightly open), eyes closed, one arm on the chest.",
      start_pose="lie_supine", end_pose="lie_supine", interrupt="any", blend_in=0.5, blend_out=0.5)
def sleep_loop(t):
    return _sleep(t)


def _fall_asleep(t):
    T = 6.0
    a = pose_supine()
    ph = t / 5.0
    p = PR.copy(a)
    drowsy = smooth(t / 3.5)
    blink = 0.5 + 0.5 * np.sin(TAU * t * 0.7)
    p["armR"] = RK.ARM_HANG + (np.array([-18.0, -40.0, -35.0, 118.0, 0, 0]) - RK.ARM_HANG) * drowsy
    p = PR.update(p, hd=[8 + 4 * drowsy, 0, 6 * drowsy])
    p = RK.fset(p, blink_L=min(1.0, drowsy * 0.8 + 0.2 * blink * (1 - smooth((t - 3.0) / 1.5)) + smooth((t - 3.5) / 1.5)),
                blink_R=min(1.0, drowsy * 0.8 + 0.2 * blink * (1 - smooth((t - 3.0) / 1.5)) + smooth((t - 3.5) / 1.5)),
                jaw=4.0 * smooth((t - 3.0) / 2.0), brow_L=0.3 * (1 - drowsy), brow_R=0.3 * (1 - drowsy), smile_L=0.15, smile_R=0.1)
    p = RK.breathing(p, t, 5.0 - 1.5 * drowsy, 1.0 + 0.4 * drowsy)
    return p, opts_lying()


@clip("fall_asleep", "posture", 5.0, desc="Lying on the back, drifting off: eyelids droop and close, one arm settles on the chest, jaw softens, breathing slows into the `sleep_loop` pose.",
      start_pose="lie_supine", end_pose="lie_supine", interrupt="none", blend_in=0.3, blend_out=0.5)
def fall_asleep(t):
    return _fall_asleep(t)


def _wake(t):
    sleep = _sleep(0.0)[0]
    awake = pose_supine(0.4)
    k = smooth((t - 0.8) / 1.0)
    p = PR.mix(sleep, awake, k)
    p = PR.update(p, hd=[8 + 10 * np.sin(np.pi * smooth(t / 1.2)) * 0.5, 0, 12 * np.sin(TAU * t / 1.6) * (1 - k)])
    open_ = smooth((t - 0.5) / 0.9)
    blink = max(0.0, 1.0 - open_) + 0.9 * np.clip(np.sin(TAU * (t - 1.4) * 1.2), 0, 1) * (t > 1.4) * (t < 2.0)
    p = RK.fset(p, blink_L=min(1.0, blink), blink_R=min(1.0, blink), jaw=8.0 * np.sin(np.pi * smooth(t / 1.5)), furrow=0.5 * (1 - open_), brow_L=0.4 * open_, brow_R=0.4 * open_,
                squint=0.5 * (1 - open_))
    return p, opts_lying()


@clip("wake_up", "posture", 2.2, desc="Waking on the back: groans, jaw works, eyes screw up then open, blinks, looks around; ends awake and lying down.",
      start_pose="lie_supine", end_pose="lie_supine", interrupt="none", blend_in=0.3, blend_out=0.3, events=[(0.9, "eyes_open")])
def wake_up(t):
    return _wake(t)


def _stretch_after_sleep(t):
    lie = pose_supine(0.4)
    k1 = hands(PR.update(pose_sit_ground(0.9), pel=[0, 0.12, -(HZ - 0.10), -34, 0, 0], sp=[-8, 0, 0], hd=[0, 0, 0],
                         ftL=FT("L", 0.13, 0.86, AZ + 0.01, -40, -10, 8), ftR=FT("R", -0.13, 0.86, AZ + 0.01, -40, 10, -8)),
               palm_down(0.22, -0.34, 0.04), palm_down(-0.22, -0.34, 0.04))
    k2 = hands(PR.update(pose_sit_ground(0.84), pel=[0, 0.06, -(HZ - 0.085), -6, 0, 0], sp=[8, 0, 0], hd=[0, 0, 0],
                         ftL=FT("L", 0.15, 0.84, AZ + 0.01, -14, -8, 14), ftR=FT("R", -0.15, 0.84, AZ + 0.01, -14, 8, -14)),
               palm_down(0.22, -0.16, 0.04), palm_down(-0.22, -0.16, 0.04))
    k3 = hands(PR.update(k2, sp=[-12, 0, 0], hd=[-26, 0, 0]), ik_hand([0.19, 0.0, 1.30], (0, 0.15, 1), (-1, 0, 0)), ik_hand([-0.19, 0.0, 1.30], (0, 0.15, 1), (1, 0, 0)))
    k3 = RK.fset(k3, jaw=24.0, squint=0.9, blink_L=0.9, blink_R=0.9, furrow=0.4)
    k3 = PR.update(k3, fL=RK.G("open", 1.0, 6), fR=RK.G("open", 1.0, 6))
    k4 = hands(PR.update(k2, sp=[16, 0, 8], hd=[-8, 0, -10]), palm_in("L", 0.18, 0.30, 0.44), palm_in("R", -0.18, 0.28, 0.44))
    k4 = RK.fset(k4, smile_L=0.4, smile_R=0.4, jaw=4.0)
    k4 = PR.update(k4, fL=RK.G("relaxed"), fR=RK.G("relaxed"))
    return seq(t, [(0.0, lie), (0.9, k1), (1.6, k2), (2.6, k3), (3.6, k3), (4.4, k4)]), opts_ik()


@clip("stretch_after_sleep", "posture", 4.4, desc="Sitting up from lying down, then a big yawning stretch with both arms overhead and a satisfied settle (ends in a seated pose).",
      start_pose="lie_supine", end_pose="sit_ground", interrupt="none", blend_in=0.3, blend_out=0.3, events=[(2.6, "yawn_peak")])
def stretch_after_sleep(t):
    return RK.with_blinks(_stretch_after_sleep, 4.4, 12)(t)
