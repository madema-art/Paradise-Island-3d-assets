"""Group E: wildlife encounters: observing, tracking, stalking, spear thrusts at prey, startle and flight, chases and recoveries."""
import numpy as np

import clipkit as CK
import gaitkit as GK
import params as PR
import pathgait as PG
import rigkit as RK
import staffkit as SK
import steps as ST
from clipkit import clip, keys, smooth, seg, pulse
from clips_transitions import _record
from posekit import *      # noqa: F401,F403
import posekit as K
from clips_posture import pose_crouch
from clips_fishing import spear_body, spear_pose, SP_STANCE

HANG = RK.ARM_HANG


def b(m=0.1, **kw):
    p = K.P(RK.stand(mood=m), armL=HANG.copy(), armR=HANG.copy(), wL=0.0, wR=0.0)
    return K.P(p, **kw) if kw else p


# ---------------------------------------------------------------------------------------------------- observing
def _observe(t):
    T = 10.0
    ph = t / T
    p = b(0.1)
    yaw = 42 * np.sin(TAU * ph) + 8 * np.sin(TAU * ph * 3)
    p = add(p, sp=[3, 0, 0.3 * yaw], hd=[-1, 2 * sw(t, T, 0.3), 0.6 * yaw], pel=[0, 0, -0.01, 0, 0, 0.1 * yaw])
    # a hand shades the eyes during the longer holds
    shade = pulse(t, 2.0, 2.8, 5.5, 6.3)
    p = K.hand_to_head(p, "R", v3(-0.07, 0.14, 1.93), (0.4, -0.7, 0.1), (0.1, 0.1, -1.0), None, w=shade)
    p["armR"] = HANG + np.array([60 * shade, 18 * shade, 0, 100 * shade, 0, 0])
    p["fR"] = RK.G("flat", 0.5 * shade)
    p["eye"] = np.array([0.16 * yaw, -2.0])
    p = addf(p, squint=0.35 * shade + 0.1)
    p = RK.breathing(p, t, 4.2, 1.0)
    return p, O()


mk("observe_animal", "wildlife", 10.0, loop=True, desc="Standing very still watching an animal: slow head and shoulder scan, one hand shading the eyes against the glare.",
   interrupt="any", blend_in=0.4, blend_out=0.4, start_pose="stand", end_pose="stand")(_observe)


def _birdwatch(t):
    T = 9.0
    ph = t / T
    p = b(0.2)
    track = np.sin(TAU * ph)
    up = 0.6 + 0.4 * np.sin(TAU * ph * 2 + 0.5)
    p = add(p, sp=[-5 * up, 0, 10 * track], hd=[-24 * up, 4 * track, 34 * track], pel=[0, 0, 0, -2 * up, 0, 4 * track])
    shade = 0.8
    p = K.hand_to_head(p, "R", v3(-0.06, 0.14, 1.94), (0.4, -0.7, 0.1), (0.1, 0.1, -1.0), None, w=shade)
    p["armR"] = HANG + np.array([60 * shade, 18 * shade, 0, 100 * shade, 0, 0])
    p["fR"] = RK.G("flat", 0.5)
    p["armL"] = HANG + np.array([6, 6, 0, 20, 0, 0])
    p["eye"] = np.array([6 * track, -9 * up])
    p = addf(p, squint=0.4, smile_L=0.15, smile_R=0.1, jaw=2)
    p = RK.breathing(p, t, 4.4, 1.0)
    return p, O()


mk("birdwatch", "wildlife", 9.0, loop=True, desc="Tracks birds flying overhead: head thrown back following the arc of the flock, hand shading the eyes, a delighted half-smile.",
   interrupt="any", blend_in=0.4, blend_out=0.4, start_pose="stand", end_pose="stand")(_birdwatch)


def _track(t):
    T = 9.0
    ph = t / T
    p = K.P(pose_crouch(0.46), sp=[40, 0, 0], hd=[-26, 0, 0], armL=HANG.copy(), armR=HANG.copy(), wL=0.0, wR=0.0)
    p = RK.face_neutral(p, 0.0)
    p["ftL"] = FT("L", 0.115, 0.04, AZ, 0, 0, 6)
    p["ftR"] = FT("R", -0.115, 0.04, AZ, 0, 0, -6)
    scan = np.sin(TAU * ph)
    touch = pulse(t, 2.0, 2.6, 4.2, 4.8)
    p["armR_ik"] = K.ik(v3(-0.16, 0.42 + 0.10 * scan, 0.04), (0, -1, -0.2), (0, 0, -1), 20)
    p["armR_w"] = np.array([0.4 + 0.6 * touch])
    p["armR"] = HANG + np.array([50, 10, 0, 30, 0, 0])
    p["armL"] = HANG + np.array([20, 14, 0, 70, 0, 0])
    p["fR"] = RK.G("open", 0.5)
    p = add(p, sp=[0, 0, 12 * scan], hd=[0, 0, 22 * scan * np.cos(TAU * ph)], pel=[0, 0.03 * touch, -0.03 * touch, 0, 0, 3 * scan])
    p["look"] = np.array([-0.16, -0.42 - 0.10 * scan, 0.04, 0.9])
    p = addf(p, squint=0.4, furrow=0.3)
    p = RK.breathing(p, t, 4.2, 1.0)
    return p, O(stance=(True, True))


mk("track_animals", "wildlife", 9.0, loop=True, desc="Crouched reading tracks in the sand: scanning the ground, brushing the prints with the fingertips, following the trail with his eyes.",
   interrupt="any", blend_in=0.4, blend_out=0.4, start_pose="crouch", end_pose="crouch")(_track)


def _curious_reaction(t):
    a = env(t, 0.1, 0.4, 1.4, 2.2)
    snap = env(t, 0.0, 0.15, 0.3, 0.6)
    p = b(0.3)
    p = add(p, sp=[-4 * snap + 10 * a, 0, 6 * a], hd=[-6 * snap + 8 * a, 14 * a, 24 * a], pel=[0, 0.05 * a, -0.02 * a, 3 * a, 0, 5 * a])
    p["armL"] = HANG + np.array([14 * a, 4 * a, 0, 30 * a, 0, 0])
    p["armR"] = HANG + np.array([10 * a, 4 * a, 0, 24 * a, 0, 0])
    p["eye"] = np.array([-10 * a, 3 * a])
    p = addf(p, wide=0.5 * snap, brow_L=0.7 * a, brow_R=0.3 * a, squint=0.2 * a, jaw=2 * snap)
    return p, O()


mk("curious_reaction", "wildlife", 2.2, desc="Something rustles: head snaps toward the sound, then he leans in, brows raised, trying to see what it is.",
   interrupt="any", blend_in=0.1, blend_out=0.3, start_pose="stand", end_pose="stand")(_curious_reaction)


def _startled(t):
    a = env(t, 0.05, 0.2, 0.7, 1.4)
    jump = np.sin(np.pi * np.clip((t - 0.05) / 0.4, 0, 1)) * (t < 0.5)
    p = b(0.0)
    p["pel"] = np.array([0, 0.10 * a, 0.10 * jump - 0.05 * smooth(seg(t, 0.45, 0.6)) * (1 - smooth(seg(t, 0.8, 1.4))), -10 * a, 0, 0])
    p = add(p, sp=[-12 * a, 0, 0], hd=[-10 * a, 0, 8 * a], pel=[0, 0, 0, 0, 0, 0])
    p["ftL"] = np.array(p["ftL"]) + np.array([-0.03 * a, 0.14 * a, 0.06 * jump, 0, 0, 0])
    p["ftR"] = np.array(p["ftR"]) + np.array([0.0, 0.18 * a, 0.08 * jump, 0, 0, 0])
    p["armL"] = HANG + np.array([60 * a, 40 * a, 0, 60 * a, 0, 0])
    p["armR"] = HANG + np.array([70 * a, 44 * a, 0, 50 * a, 0, 0])
    p["fL"] = RK.G("open", a)
    p["fR"] = RK.G("open", a)
    p = addf(p, wide=1.0 * a, brow_L=1.0 * a, brow_R=1.0 * a, jaw=18 * a)
    return p, O(stance=(jump < 0.02, jump < 0.02))


mk("startled", "wildlife", 1.4, desc="Sudden fright: jumps back with arms flung out, eyes and mouth wide open, then freezes tense.",
   interrupt="any", blend_in=0.05, blend_out=0.25, start_pose="stand", end_pose="stand_tense")(_startled)


# ---------------------------------------------------------------------------------------------------- sneaking / stalking gaits
SNEAK = GK.Gait(T=50 / 30, v=0.55, duty=0.72, x=0.115, toe_out=5.0, bob=0.010, sway=0.030, roll=3.0, pyaw=3.0, syaw=5.0, arm=8.0, elbow0=40.0,
                elbow1=8.0, lean=20.0, z0=-0.20, out=-12.0, head_stab=0.8, foot=ST.Cfg(lift=0.10, toe_pitch=22.0, heel_pitch=3.0, roll_on=0.08, heel_off=0.55))
STALK = GK.Gait(T=56 / 30, v=0.45, duty=0.74, x=0.115, toe_out=5.0, bob=0.008, sway=0.030, roll=3.0, pyaw=3.0, syaw=4.0, arm=4.0, elbow0=60.0,
                elbow1=4.0, lean=24.0, z0=-0.26, out=-10.0, head_stab=0.8, foot=ST.Cfg(lift=0.09, toe_pitch=20.0, heel_pitch=2.0, roll_on=0.08, heel_off=0.55))


def _sneak(t):
    steps = GK.make_steps(SNEAK)
    prm, opts = GK.gait_params(t, SNEAK, steps)
    prm = K.P(prm, wL=0.0, wR=0.0)
    for sd in ("L", "R"):
        if not np.any(prm[f"arm{sd}_ik"]):
            prm[f"arm{sd}_ik"] = RK.hang_ik(sd)
    prm["look"] = np.array([0.0, -3.0, 0.2, 0.7])
    prm = addf(prm, squint=0.3, furrow=0.2)
    o = O(stance=(True, True), world=opts["world"])
    o["arm_mode"] = ("blend", "blend")
    return prm, o


mk("approach_carefully", "wildlife", SNEAK.T, loop=True, root="inplace", speed=SNEAK.v,
   desc="Creeping forward in a low, quiet crouch (0.55 m/s): knees bent, heel-toe placement, arms out for balance, eyes locked on the target. timeScale = speed / 0.55.",
   interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="stand", end_pose="stand")(_sneak)


def _stalk_spear(t):
    steps = GK.make_steps(STALK)
    prm, opts = GK.gait_params(t, STALK, steps)
    s = SK.SH(-0.14, 0.32, 0.70 + 0.03 * np.cos(TAU * t / STALK.T * 2), 112 + 2 * np.sin(TAU * t / STALK.T), 0, 0, 0.95, 1.55, 1.0, 1.0)
    prm = K.P(prm)
    prm["look"] = np.array([0.0, -3.0, 0.0, 0.8])
    prm = SK.apply_state(prm, s, "over", "over")
    prm = addf(prm, squint=0.4, furrow=0.3)
    o = O(stance=(True, True), world=opts["world"])
    return prm, o


mk("stalk_rat", "wildlife", STALK.T, loop=True, speed=STALK.v, props=["staff"], staff_use="spear",
   desc="Stalking prey with the spear held low in both hands (0.45 m/s): deep crouch, slow silent steps, tip trained on the target. timeScale = speed / 0.45.",
   interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="stand", end_pose="spear_ready")(_stalk_spear)


def _spear_ground(t):
    s = SK.kv(t, [(0.0, SK.SH(-0.14, 0.32, 0.72, 112, 0, 0, 0.95, 1.55)), (0.35, SK.SH(-0.14, 0.26, 0.92, 128, 0, 0, 0.95, 1.55)), (0.50, SK.SH(-0.15, 0.50, 0.50, 138, 0, 0, 0.95, 1.55)), (0.9, SK.SH(-0.15, 0.50, 0.50, 138, 0, 0, 0.95, 1.55)), (1.3, SK.SH(-0.15, 0.50, 0.50, 138, 0, 0, 0.95, 1.55))])
    a = smooth(seg(t, 0.25, 0.5))
    p = K.P(pose_crouch(0.30 + 0.12 * a), sp=[28 + 14 * a, 0, 0], hd=[-18, 0, 0], armL=HANG.copy(), armR=HANG.copy(), wL=0.0, wR=0.0,
            ftL=FT("L", 0.15, 0.30 + 0.10 * a, AZ, 0, 0, 10), ftR=FT("R", -0.15, -0.10, AZ, 0, 0, -8))
    p["look"] = np.array([0.0, -0.9, 0.0, 1.0])
    p = SK.apply_state(p, s, "over", "over")
    p = addf(p, jaw=6 * a, squint=0.5)
    return p, SK.opts_blend()


mk("spear_thrust_ground", "wildlife", 1.3, props=["staff"], staff_use="spear", desc="Lunging spear stab downward at small ground prey (rat/crab): the back foot drives, the tip drives into the sand.",
   interrupt="none", blend_in=0.1, blend_out=0.1, start_pose="spear_ready", end_pose="spear_stuck", events=[(0.5, "spear_hits_ground")])(_spear_ground)


def _spear_ground_recover(t):
    s = SK.kv(t, [(0.0, SK.SH(-0.15, 0.50, 0.50, 138, 0, 0, 0.95, 1.55)), (0.6, SK.SH(-0.15, 0.40, 0.70, 120, 0, 0, 0.95, 1.55)), (1.4, SK.SH(-0.18, 0.20, 0.90, 80, 0, 0, 0.95, 1.55, 1.0, 0.0)), (2.2, SK.SH(-0.20, 0.14, 0.95, 20, -2, 0, 1.0, 1.5, 1.0, 0.0))])
    a = smooth(seg(t, 0.4, 1.8))
    p = K.P(pose_crouch(0.42 - 0.38 * a), sp=[42 - 40 * a, 0, 0], hd=[-18 + 14 * a, 0, 14 * np.sin(TAU * (t - 1.0) / 1.0) * env(t, 0.9, 1.1, 1.8, 2.1)], armL=HANG.copy(), armR=HANG.copy(), wL=0.0, wR=0.0,
            ftL=FT("L", 0.15 - 0.04 * a, 0.40 - 0.40 * a, AZ, 0, 0, 10 - 8 * a), ftR=FT("R", -0.15 + 0.05 * a, -0.10 + 0.10 * a, AZ, 0, 0, -8 + 6 * a))
    p["armL"] = HANG + np.array([20, 10, 0, 40, 0, 0])
    p = SK.apply_state(p, s, "over", "over")
    p = addf(p, frown=0.4 * env(t, 0.8, 1.2, 1.8, 2.2), lip_low=0.3 * env(t, 0.8, 1.2, 1.8, 2.2), brow_L=0.3 * a, brow_R=0.1 * a)
    return p, SK.opts_blend()


mk("spear_ground_recover", "wildlife", 2.2, props=["staff"], staff_use="spear", desc="Missed the quarry: pulls the spear from the sand, rises, shakes his head and plants the staff at his side.",
   interrupt="none", blend_in=0.1, blend_out=0.3, start_pose="spear_stuck", end_pose="stand_staff")(_spear_ground_recover)


# ---------------------------------------------------------------------------------------------------- flight and chase
SPRINT = GK.Gait(T=17 / 30, v=5.4, duty=0.32, x=0.085, bob=0.075, z0=-0.085, sway=0.016, roll=2.5, pyaw=8.0, syaw=15.0, arm=48.0, elbow0=84.0,
                 elbow1=12.0, lean=13.0, out=-15.0, run=True, gripL="fist", gripR="fist", toe_out=2.0,
                 foot=ST.Cfg(lift=0.30, toe_pitch=52.0, heel_pitch=3.0, roll_on=0.08, heel_off=0.25, toe_clear=3.0, lift_peak=0.5))


def gait_variant(name, g, mod, desc, **meta):
    steps = GK.make_steps(g)

    def fn(t):
        prm, opts = GK.gait_params(t, g, steps)
        prm = K.P(prm, wL=0.0, wR=0.0)
        prm, opts = mod(t, prm, opts)
        o = O(stance=(True, True), world=opts["world"])
        return prm, o
    mk(name, "wildlife", g.T, loop=True, speed=g.v, desc=desc, **meta)(fn)


def _sprint_mod(t, p, o):
    p = addf(p, wide=0.4, jaw=8, furrow=0.4)
    p["look"] = np.array([0.0, -6.0, 0.8, 0.6])
    return p, o


gait_variant("sprint_away", SPRINT, _sprint_mod, "All-out panicked sprint (5.4 m/s): maximum lean, flailing arms, wide eyes. timeScale = speed / 5.4.",
             interrupt="any", blend_in=0.1, blend_out=0.2, start_pose="stand", end_pose="stand")


def _look_back_mod(t, p, o):
    ph = (t / SPRINT.T) % 1.0
    p = add(p, sp=[0, 0, 40], hd=[-2, 0, 52], pel=[0, 0, 0, 0, 0, 6])
    p["eye"] = np.array([14.0, 0.0])
    p = addf(p, wide=0.7, jaw=10, brow_L=0.7, brow_R=0.7)
    return p, o


gait_variant("run_look_back", SPRINT, _look_back_mod, "Fleeing at a sprint while glancing back over the left shoulder at what is chasing him: torso and head twisted ~90 degrees, eyes wide.",
             interrupt="any", blend_in=0.2, blend_out=0.2, start_pose="sprint_away", end_pose="sprint_away")

CHASE = GK.Gait(T=21 / 30, v=3.9, duty=0.38, x=0.088, bob=0.055, z0=-0.075, sway=0.018, roll=2.5, pyaw=6.0, syaw=12.0, arm=20.0, elbow0=60.0,
                elbow1=12.0, lean=11.0, out=-14.0, run=True, toe_out=3.0,
                foot=ST.Cfg(lift=0.24, toe_pitch=46.0, heel_pitch=5.0, roll_on=0.10, heel_off=0.30, toe_clear=4.0, lift_peak=0.5))


def _chase_mod(t, p, o):
    ph = (t / CHASE.T) % 1.0
    c = np.cos(TAU * ph)
    # arms reach forward and swipe (grabbing at the monkey ahead)
    p["armL"] = HANG + np.array([70 + 22 * c, 8, 0, 20 + 14 * (0.5 - 0.5 * c), 0, 0])
    p["armR"] = HANG + np.array([70 - 22 * c, 8, 0, 20 + 14 * (0.5 + 0.5 * c), 0, 0])
    p["fL"] = RK.G("open", 0.7)
    p["fR"] = RK.G("open", 0.7)
    p["look"] = np.array([0.0, -6.0, 0.9, 0.9])
    p = addf(p, smile_L=0.5, smile_R=0.5, jaw=14, cheek=0.4, brow_L=0.4, brow_R=0.4)
    return p, o


gait_variant("chase_monkey", CHASE, _chase_mod, "Running after a monkey that has stolen something: arms reaching and grabbing, jaw open shouting, half grimace half grin (3.9 m/s).",
             interrupt="any", blend_in=0.15, blend_out=0.2, start_pose="stand", end_pose="stand")


# ---------------------------------------------------------------------------------------------------- recovery
def _catch_breath(t):
    T = 4.4
    ph = t / T
    pant = np.sin(TAU * t / 1.1)
    p = K.P(pose_crouch(0.16), armL=HANG.copy(), armR=HANG.copy(), wL=0.0, wR=0.0, sp=[38, 0, 0], hd=[-4, 0, 0])
    p["ftL"] = FT("L", 0.13, 0.05, AZ, 0, 0, 8)
    p["ftR"] = FT("R", -0.13, 0.05, AZ, 0, 0, -8)
    # hands braced on the knees
    p["armL_ik"] = K.ik(v3(0.15, 0.36, 0.64), (-0.1, -1, 0.0), (-0.7, 0, 0.7), -10)
    p["armR_ik"] = K.ik(v3(-0.15, 0.36, 0.64), (0.1, -1, 0.0), (0.7, 0, 0.7), 10)
    p["armL_w"] = np.array([1.0])
    p["armR_w"] = np.array([1.0])
    p["fL"] = RK.G("grip_big", 0.7)
    p["fR"] = RK.G("grip_big", 0.7)
    p = add(p, sp=[3.0 * pant, 0, 0], hd=[-3 * pant + 4 * np.sin(TAU * ph), 0, 8 * np.sin(TAU * ph)], pel=[0, 0, 0.012 * pant, 0, 0, 0])
    p = addf(p, jaw=8 + 6 * (0.5 + 0.5 * pant), furrow=0.2, squint=0.3)
    return p, O(stance=(True, True))


mk("catch_breath", "wildlife", 4.4, loop=True, desc="Bent over with hands on knees, heaving for breath after the run: heavy panting, shoulders rising, head hanging.",
   interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="bent_hands_on_knees", end_pose="bent_hands_on_knees")(_catch_breath)


def _laugh_after_chase(t):
    T = 4.6
    a = env(t, 0.2, 0.7, 3.6, 4.6)
    s = shake(t, 4.6, 1.0, 0.3, 4.0, 0.2)
    p = K.P(pose_crouch(0.16), armL=HANG.copy(), armR=HANG.copy(), wL=0.0, wR=0.0, sp=[30, 0, 0], hd=[-4, 0, 0])
    st = b(0.9)
    p = seq_blend(t, st, p)
    p["ftL"] = FT("L", 0.13, 0.05, AZ, 0, 0, 8)
    p["ftR"] = FT("R", -0.13, 0.05, AZ, 0, 0, -8)
    p["armL_ik"] = K.ik(v3(0.15, 0.36, 0.64), (-0.1, -1, 0.0), (-0.7, 0, 0.7), -10)
    p["armR_ik"] = K.ik(v3(-0.15, 0.36, 0.64), (0.1, -1, 0.0), (0.7, 0, 0.7), 10)
    p["armL_w"] = np.array([smooth(seg(t, 0.2, 0.9))])
    p["armR_w"] = np.array([smooth(seg(t, 0.2, 0.9))])
    p = add(p, sp=[5 * s * a, 0, 0], hd=[-6 * a + 4 * s * a, 4 * a * np.sin(TAU * t / 2.2), 0], pel=[0, 0, 0.012 * s * a, 0, 0, 0])
    p = addf(p, smile_L=0.9 * a, smile_R=0.95 * a, cheek=0.9 * a, squint=0.8 * a, jaw=16 * a * (0.6 + 0.4 * (0.5 + 0.5 * s)))
    return p, O(stance=(True, True))


def seq_blend(t, a, bpose):
    w = smooth(seg(t, 0.0, 0.6))
    return PR.mix(a, bpose, w)


mk("laugh_after_chase", "wildlife", 4.6, desc="Collapses into helpless laughter after the chase: hands on knees, back heaving, tears of mirth.",
   interrupt="any", blend_in=0.2, blend_out=0.3, start_pose="bent_hands_on_knees", end_pose="bent_hands_on_knees")(_laugh_after_chase)
