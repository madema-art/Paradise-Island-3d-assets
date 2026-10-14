"""Group G: personality and expressive standing actions (laughs, frustration, surprise, thinking, scratching, sighing, yawning...).
Authored as keyposes + oscillations; arms FK or IK (head space) with a per-key IK weight."""
import numpy as np

import gaitkit as GK
import params as PR
import rigkit as RK
import steps as ST
from clipkit import clip, keys, smooth, seg, pulse
from posekit import *      # noqa: F401,F403
import posekit as K

H = "head"

STAND = RK.stand(mood=0.1)
HANG = RK.ARM_HANG


def arms_hang():
    return dict(armL=HANG.copy(), armR=HANG.copy(), wL=0.0, wR=0.0)


def base(m=0.1, **kw):
    p = K.P(RK.stand(mood=m), armL=HANG.copy(), armR=HANG.copy(), wL=0.0, wR=0.0)
    return K.P(p, **kw) if kw else p


def F(**f):
    return f


# ---------------------------------------------------------------------------------------------------- laughs
def _laugh_quiet(t):
    T = 3.4
    a = env(t, 0.2, 0.7, 2.6, 3.4)
    chuck = shake(t, 4.2, 1.0, 0.3, 3.0)
    p = base(0.3)
    p = add(p, sp=[-3.0 * a + 3.0 * chuck * a, 0, 0], hd=[-9 * a - 3 * chuck * a, 7 * a * np.sin(TAU * t / 2.6), 8 * a * np.sin(TAU * (t / 3.4))])
    p["pel"] = p["pel"] + np.array([0, 0, -0.004 * chuck * a, 0, 0, 0])
    p = addf(p, smile_L=0.45 * a, smile_R=0.5 * a, cheek=0.5 * a, squint=0.3 * a, jaw=1.0 + 6.0 * a * (0.5 + 0.5 * chuck))
    p = add(p, armL=[3 * a, 0, 0, 14 * a * (1 + 0.1 * chuck), 0, 0], armR=[3 * a, 0, 0, 14 * a, 0, 0])
    p = RK.breathing(p, t, 2.0, 1.0)
    return p, O()


mk("laugh_quiet", "personality", 3.4, desc="Quiet amused chuckle: shoulders shake softly, eyes crinkle, head tips slightly.",
   interrupt="any", blend_in=0.25, blend_out=0.3, start_pose="stand", end_pose="stand")(_laugh_quiet)


def _laugh_hearty(t):
    T = 4.2
    a = env(t, 0.15, 0.5, 3.4, 4.2)
    s = shake(t, 5.2, 1.0, 0.2, 3.8, 0.2)
    bend = env(t, 0.5, 1.4, 2.4, 3.8)
    p = base(0.5)
    p = add(p, sp=[-12 * a + 30 * bend + 4 * s * a, 0, 5 * np.sin(TAU * t / 2.2) * a], hd=[-26 * a + 5 * s * a, 8 * a * np.sin(TAU * t / 3.0), 0],
            pel=[0, 0.02 * bend, -0.03 * a - 0.02 * s * a, 10 * bend, 0, 0])
    # hand on belly, other hand slaps the thigh / wipes the eye
    belly = v3(-0.06, 0.12, 1.20)
    p = K.P(p, ikR=K.ik(belly, (0.2, -1, -0.2), (0, 1, 0.3)), wR=1.0 * smooth(seg(t, 0.4, 1.0)) * (1 - smooth(seg(t, 3.4, 4.0))), spR_dummy=[0]) if False else p
    p["armR_ik"] = K.ik(v3(-0.10, 0.12, 1.22), (0.35, -1, -0.15), (-0.3, 0.9, 0.3))
    p["armR_w"] = np.array([smooth(seg(t, 0.3, 0.9)) * (1 - smooth(seg(t, 3.3, 3.9)))])
    p["armR"] = HANG + np.array([20 * a, 0, 0, 40 * a, 0, 0])
    p["armL"] = HANG + np.array([14 * a + 6 * s * a, 8 * a, 0, 30 * a, 0, 0])
    p = addf(p, smile_L=0.85 * a, smile_R=0.9 * a, cheek=0.9 * a, squint=0.8 * a, jaw=18 * a * (0.55 + 0.45 * (0.5 + 0.5 * s)), brow_L=0.2 * a, brow_R=0.2 * a)
    p["gR"] = RK.G("relaxed") if False else p["fR"]
    p = RK.breathing(p, t, 1.2, 2.0)
    return p, O(spL="world", spR="chest")


mk("laugh_hearty", "personality", 4.2, desc="Big belly laugh: head thrown back, torso rocking and folding forward, one hand on the belly, wide open mouth.",
   interrupt="any", blend_in=0.25, blend_out=0.35, start_pose="stand", end_pose="stand")(_laugh_hearty)


# ---------------------------------------------------------------------------------------------------- frustration / disappointment
def _frustration(t):
    a = env(t, 0.2, 0.6, 2.2, 3.0)
    sh = shake(t, 3.0, 1.0, 0.5, 2.0)
    p = base(-0.2)
    p = add(p, hd=[-3 * a, 0, 18 * sh], sp=[3 * a, 0, -5 * sh * a], pel=[0, 0, -0.006 * a, 0, 0, 0])
    # fists clenched at the sides, shoulders up, then a hand rakes through the hair
    rake = env(t, 1.7, 2.1, 2.5, 3.0)
    p["armL"] = HANG + np.array([14 * a, 6 * a, 0, 60 * a, 0, 0])
    p["armR"] = HANG + np.array([14 * a, 6 * a, 0, 60 * a, 0, 0])
    p["armR_ik"] = K.ik(v3(-0.02, -0.03, 2.03), (0, 1, 0.1), (0, 0.1, -1))
    p["armR_w"] = np.array([rake])
    p["fL"] = RK.G("fist", a)
    p["fR"] = RK.G("fist", a * (1 - rake) + 0.5 * rake)
    p = addf(p, frown=0.9 * a, furrow=0.9 * a, squint=0.4 * a, jaw=3 * a, brow_L=-0.2 * a, brow_R=-0.2 * a)
    p = RK.breathing(p, t, 1.6, 2.0 * a)
    return p, O(spR="head")


mk("frustration", "personality", 3.0, desc="Tight-jawed frustration: fists clench, shoulders rise, sharp head shake, a hand rakes through the hair.",
   interrupt="any", blend_in=0.2, blend_out=0.3, start_pose="stand", end_pose="stand")(_frustration)


def _disappointment(t):
    a = env(t, 0.3, 1.2, 2.4, 3.4)
    p = base(-0.3)
    p = add(p, sp=[12 * a, 0, 0], hd=[14 * a, 2 * a, 10 * np.sin(TAU * t / 3.4) * a], pel=[0, 0, -0.014 * a, 2 * a, 0, 0])
    p["armL"] = HANG + np.array([-3 * a, 4 * a, 0, 6 * a, -12 * a, 0])
    p["armR"] = HANG + np.array([-3 * a, 4 * a, 0, 6 * a, -12 * a, 0])
    p["fL"] = RK.G("relaxed", 0.4)
    p["fR"] = RK.G("relaxed", 0.4)
    p = addf(p, frown=0.5 * a, brow_L=0.35 * a, brow_R=0.2 * a, furrow=0.2 * a, smile_L=-0.1 * a, smile_R=-0.1 * a, lip_low=0.3 * a)
    sigh = env(t, 1.4, 1.9, 2.1, 2.7)
    p = add(p, sp=[-3 * sigh, 0, 0])
    p = addf(p, jaw=5 * sigh)
    p = RK.breathing(p, t, 3.4, 1.0)
    return p, O()


mk("disappointment", "personality", 3.4, desc="Disappointed slump: shoulders and head drop, slow head shake, small sigh, hands hanging limp.",
   interrupt="any", blend_in=0.3, blend_out=0.35, start_pose="stand", end_pose="stand")(_disappointment)


# ---------------------------------------------------------------------------------------------------- surprise / excitement
def _surprise(t):
    a = env(t, 0.05, 0.2, 1.1, 1.8)
    p = base(0.0)
    p = add(p, sp=[-6 * a, 0, 0], hd=[-8 * a, 0, 0], pel=[0, 0.03 * a, 0.0, -3 * a, 0, 0])
    p["armL"] = HANG + np.array([36 * a, 18 * a, 0, 70 * a, 0, 0])
    p["armR"] = HANG + np.array([36 * a, 18 * a, 0, 70 * a, 0, 0])
    p["fL"] = RK.G("open", a)
    p["fR"] = RK.G("open", a)
    p["ftL"] = RK.FT("L", 0.0, -0.03 * a, AZ, 0, 0, 0) if False else p["ftL"]
    p = addf(p, wide=1.0 * a, brow_L=0.9 * a, brow_R=0.9 * a, jaw=10 * a)
    return p, O()


mk("surprise", "personality", 1.8, desc="Startled surprise: weight jerks back, eyes widen, brows shoot up, hands fly open in front of the chest.",
   interrupt="any", blend_in=0.1, blend_out=0.3, start_pose="stand", end_pose="stand")(_surprise)


def _excitement(t):
    T = 2.6
    a = env(t, 0.1, 0.4, 2.2, 2.6)
    hop = np.maximum(0.0, np.sin(TAU * 2.0 * t / T)) ** 0.8 * a
    p = base(0.8)
    p["pel"] = p["pel"] + np.array([0, 0, 0.14 * hop - 0.05 * (1 - hop) * a, 0, 0, 0])
    p = add(p, sp=[-3 * a, 0, 4 * np.sin(TAU * t / 1.3) * a], hd=[-6 * a, 0, 8 * np.sin(TAU * t / 1.3 + 1) * a])
    lift = 0.16 * hop
    p["ftL"] = np.array(p["ftL"]) + np.array([0, 0, lift, 0, 0, 0])
    p["ftR"] = np.array(p["ftR"]) + np.array([0, 0, lift, 0, 0, 0])
    pump = np.sin(TAU * 2.0 * t / T) * a
    p["armL"] = HANG + np.array([50 * a + 14 * pump, 30 * a, 0, 100 * a, 0, 0])
    p["armR"] = HANG + np.array([50 * a - 14 * pump, 30 * a, 0, 100 * a, 0, 0])
    p["fL"] = RK.G("fist", a)
    p["fR"] = RK.G("fist", a)
    p = addf(p, smile_L=0.9 * a, smile_R=0.9 * a, cheek=0.8 * a, brow_L=0.5 * a, brow_R=0.5 * a, jaw=10 * a, wide=0.3 * a)
    return p, O(stance=(hop < 0.02, hop < 0.02))


mk("excitement", "personality", 2.6, desc="Excited little hops with both fists pumping, big grin, head bobbing.",
   interrupt="any", blend_in=0.2, blend_out=0.3, start_pose="stand", end_pose="stand")(_excitement)


# ---------------------------------------------------------------------------------------------------- confusion, scratching, thinking
def _confusion(t):
    a = env(t, 0.3, 0.9, 2.4, 3.2)
    p = base(0.0)
    tilt = np.sin(TAU * t / 3.2)
    p = add(p, hd=[3 * a, 12 * a + 3 * tilt * a, 14 * tilt * a], sp=[0, 3 * a, 5 * tilt * a])
    p["armL"] = HANG + np.array([30 * a, 28 * a, 0, 80 * a, 0, 0])      # open palm up shrug
    p["armR"] = HANG + np.array([4 * a, 4 * a, 0, 14 * a, 0, 0])
    p["fL"] = RK.G("open", 0.8 * a)
    p = addf(p, brow_L=0.1 * a, brow_R=0.85 * a, furrow=0.5 * a, squint=0.2 * a, smile_L=-0.1 * a, smile_R=0.1 * a, pucker=0.15 * a)
    return p, O()


mk("confusion", "personality", 3.2, desc="Puzzled: head tilts and turns, one eyebrow climbs, one hand opens palm-up in a questioning shrug.",
   interrupt="any", blend_in=0.25, blend_out=0.3, start_pose="stand", end_pose="stand")(_confusion)


def _head_scratch(t):
    a = env(t, 0.3, 0.9, 2.5, 3.2)
    scr = shake(t, 3.4, 1.0, 0.9, 2.5, 0.2)
    p = base(0.0)
    p = add(p, hd=[4 * a, 6 * a, -6 * a])
    p["armR_ik"] = K.ik(v3(-0.07, -0.02, 2.00) + np.array([0.012 * scr, 0.012 * scr * 0.6, 0]), (0, 1, 0.25), (0.1, 0.2, -1), 0.0)
    p["armR_w"] = np.array([a])
    p["armR"] = HANG + np.array([40 * a, 20 * a, 0, 110 * a, 0, 0])
    p["armL"] = HANG
    p["fR"] = RK.G("relaxed", 0.5 + 0.4 * (0.5 + 0.5 * scr) * a)
    p = addf(p, squint=0.35 * a, smile_L=0.1 * a, smile_R=0.0, brow_R=0.4 * a)
    return p, O(spR="head")


mk("head_scratch", "personality", 3.2, desc="Scratches the back/top of his head with the right hand while thinking, head tilted.",
   interrupt="any", blend_in=0.25, blend_out=0.3, start_pose="stand", end_pose="stand")(_head_scratch)


def _contemplation(t):
    T = 6.0
    ph = t / T
    p = base(0.0)
    p = add(p, sp=[4, 0, 0], hd=[-2 + 1.5 * np.sin(TAU * ph), 4 * np.sin(TAU * ph), 18 * np.sin(TAU * (ph + 0.2))],
            pel=[0, 0, -0.006, 0, -1.5, 0])
    p["armR_ik"] = K.ik(v3(-0.03, 0.11, 1.74), (0.2, -0.4, 1), (-0.2, -1.0, 0.1), -20)
    p["armR_w"] = np.array([1.0])
    p["armL_ik"] = K.ik(v3(0.12, 0.12, 1.33), (-1, -0.2, 0.1), (0.1, 0.1, 1), 0)
    p["armL_w"] = np.array([1.0])
    p["fR"] = RK.G("relaxed", 0.8)
    p["fL"] = RK.G("relaxed", 0.8)
    p["eye"] = np.array([10 * np.sin(TAU * ph * 2), -3.0])
    p = RK.breathing(p, t, 4.4, 1.0)
    return p, O(spL="chest", spR="head")


mk("contemplation", "personality", 6.0, loop=True, desc="Thoughtful pose: right hand to the chin, left arm folded across the belly, gaze drifting out to sea.",
   interrupt="any", blend_in=0.4, blend_out=0.4, start_pose="stand_think", end_pose="stand_think")(_contemplation)


def _sigh(t):
    a = env(t, 0.2, 1.1, 1.6, 3.0)
    p = base(-0.1)
    p = add(p, sp=[-5 * a + 7 * smooth(seg(t, 1.5, 2.6)) * (1 - smooth(seg(t, 2.6, 3.4))), 0, 0], hd=[-5 * a + 8 * smooth(seg(t, 1.5, 2.4)) * (1 - smooth(seg(t, 2.4, 3.4))), 0, 0],
            pel=[0, 0, -0.008 * smooth(seg(t, 1.5, 2.4)) * (1 - smooth(seg(t, 2.4, 3.4))), 0, 0, 0])
    p["armL"] = HANG + np.array([0, 6 * a - 8 * smooth(seg(t, 1.5, 2.4)), 0, 0, 0, 0])
    p["armR"] = p["armL"].copy()
    ex = env(t, 1.5, 1.9, 2.3, 2.8)
    p = addf(p, jaw=7 * ex + 3 * a, pucker=0.4 * ex, brow_L=0.3 * a, brow_R=0.3 * a, frown=0.3 * ex)
    return p, O()


mk("sigh", "personality", 3.4, desc="Deep breath in (chest and shoulders rise) and a long audible sigh out with the shoulders sagging.",
   interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="stand", end_pose="stand")(_sigh)


# ---------------------------------------------------------------------------------------------------- yawn / stretch
def _yawn(t):
    a = env(t, 0.3, 1.2, 2.2, 3.4)
    jaw = env(t, 0.6, 1.5, 2.1, 2.9)
    p = base(-0.1)
    p = add(p, sp=[-6 * a, 0, 0], hd=[-14 * jaw, 0, 0], pel=[0, 0, 0.0, 2 * a, 0, 0])
    # right fist rubs/covers the mouth; left arm stretches out a little
    cover = env(t, 0.5, 1.2, 2.6, 3.3)
    p["armR_ik"] = K.ik(v3(-0.03, 0.14, 1.77), (0.1, -0.2, 1), (-0.3, -1, 0.0), -10)
    p["armR_w"] = np.array([cover])
    p["armR"] = HANG + np.array([40 * a, 10 * a, 0, 100 * a, 0, 0])
    p["armL"] = HANG + np.array([20 * a, 36 * a, 0, 14 * a, 0, 0])
    p["fR"] = RK.G("fist", 0.7 * cover)
    p = addf(p, jaw=30 * jaw, squint=0.9 * jaw, brow_L=0.3 * jaw, brow_R=0.3 * jaw, blink_L=0.9 * jaw, blink_R=0.9 * jaw, cheek=0.5 * jaw)
    return p, O(spR="head")


mk("yawn", "personality", 3.4, blinks=False, desc="Big tired yawn: head tips back, jaw wide, eyes squeezed shut, a fist partly covers the mouth, left arm stretches out.",
   interrupt="any", blend_in=0.25, blend_out=0.3, start_pose="stand", end_pose="stand")(_yawn)


def _stretch_stand(t):
    up = env(t, 0.4, 1.6, 3.0, 4.3)
    arch = env(t, 0.8, 1.8, 2.8, 3.8)
    side = np.sin(TAU * (t - 1.0) / 3.0) * env(t, 1.0, 1.6, 2.8, 3.6)
    p = base(0.1)
    p = add(p, sp=[-14 * arch, 6 * side, 0], hd=[-14 * arch, 3 * side, 0], pel=[0, 0.03 * arch, 0.01 * up, -6 * arch, 0, 0])
    p["armL"] = HANG + np.array([160 * up, 18 * up, 0, 6 * up, 10 * up, 0])
    p["armR"] = HANG + np.array([160 * up, 18 * up, 0, 6 * up, 10 * up, 0])
    p["fL"] = RK.G("open", 0.4 * up)
    p["fR"] = RK.G("open", 0.4 * up)
    p["fL"][12] = 0.3 * up
    p = addf(p, jaw=8 * arch, squint=0.6 * arch, smile_L=0.2 * arch, smile_R=0.2 * arch)
    p = RK.breathing(p, t, 2.2, 1.5)
    return p, O()


mk("stretch_standing", "personality", 4.3, desc="Standing full-body stretch: arms reach overhead, back arches, a lean to each side, with a satisfied exhale.",
   interrupt="any", blend_in=0.3, blend_out=0.35, start_pose="stand", end_pose="stand")(_stretch_stand)


# ---------------------------------------------------------------------------------------------------- whistle / hum / shout / talk
def _whistle(t):
    T = 4.0
    a = env(t, 0.2, 0.5, 3.4, 3.9)
    notes = np.sin(TAU * t * 1.5) ** 2
    p = base(0.2)
    p = add(p, hd=[-3 * a + 2 * notes * a, 0, 5 * a * np.sin(TAU * t / 2.0)], sp=[0, 0, 3 * a * np.sin(TAU * t / 2.0)], pel=[0, 0, 0, 0, 3 * a * np.sin(TAU * t / 2.0), 0])
    # hands loosely in front/behind: left in pocket-like hip rest, right swings
    p["armL"] = HANG + np.array([-6 * a, -2 * a, 0, 50 * a, 0, 0])
    p["armR"] = HANG + np.array([4 * a + 6 * np.sin(TAU * t / 2.0) * a, 2 * a, 0, 12 * a, 0, 0])
    p = addf(p, pucker=0.9 * a * (0.6 + 0.4 * notes), jaw=2.5 * a, brow_L=0.15 * a, brow_R=0.25 * a)
    p["eye"] = np.array([6 * np.sin(TAU * t / 4.0), -2.0])
    return p, O()


mk("whistle", "personality", 4.0, desc="Casual whistling: lips pursed, head bobbing to the tune, one hand tucked at the hip, the other swinging.",
   interrupt="any", blend_in=0.25, blend_out=0.3, start_pose="stand", end_pose="stand")(_whistle)


def _hum_sing(t):
    T = 6.0
    ph = t / T
    a = env(t, 0.3, 0.8, 5.2, 6.0)
    beat = np.sin(TAU * t * 1.0)
    vow = 0.5 + 0.5 * np.sin(TAU * t * 2.0)
    p = base(0.35)
    p = add(p, sp=[-3 * a, 3 * a * beat, 5 * a * np.sin(TAU * ph)], hd=[-4 * a + 2 * a * beat, 6 * a * np.sin(TAU * ph * 2), 8 * a * np.sin(TAU * ph)],
            pel=[0.015 * a * beat, 0, -0.004 * a * abs(beat), 0, -3 * a * beat, 2 * a * beat])
    p["armL"] = HANG + np.array([10 * a * beat, 4 * a, 0, 20 * a, 0, 0])
    p["armR"] = HANG + np.array([14 * a * (1 - beat) * 0.5, 4 * a, 0, 40 * a * (0.5 + 0.5 * beat), 0, 0])
    p = addf(p, jaw=8 * a * vow, pucker=0.5 * a * (1 - vow), smile_L=0.3 * a, smile_R=0.3 * a, brow_L=0.2 * a * vow, brow_R=0.2 * a * vow)
    return p, O()


mk("hum_sing", "personality", 6.0, desc="Humming/singing to himself: slow sway, head nodding on the beat, mouth shaping vowels, relaxed arms keeping time.",
   interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="stand", end_pose="stand")(_hum_sing)


def _shout(t):
    a = env(t, 0.15, 0.5, 1.7, 2.2)
    mouthy = np.sin(TAU * 3.0 * t) ** 2
    p = base(0.0)
    p = add(p, sp=[-6 * a, 0, 0], hd=[-8 * a, 0, 6 * a], pel=[0, 0, 0, 3 * a, 0, 0])
    p["armL_ik"] = K.ik(v3(0.07, 0.17, 1.80), (-0.3, -0.7, 0.5), (0.9, 0.0, 0.2))
    p["armR_ik"] = K.ik(v3(-0.07, 0.17, 1.80), (0.3, -0.7, 0.5), (-0.9, 0.0, 0.2))
    p["armL_w"] = np.array([a])
    p["armR_w"] = np.array([a])
    p["armL"] = HANG + np.array([60 * a, 20 * a, 0, 120 * a, 0, 0])
    p["armR"] = HANG + np.array([60 * a, 20 * a, 0, 120 * a, 0, 0])
    p["fL"] = RK.G("flat", a * 0.6)
    p["fR"] = RK.G("flat", a * 0.6)
    p = addf(p, jaw=22 * a * (0.6 + 0.4 * mouthy), brow_L=0.4 * a, brow_R=0.4 * a, squint=0.2 * a, wide=0.2 * a)
    return p, O(spL="head", spR="head")


mk("shout", "personality", 2.2, desc="Shouting across the water: hands cupped around the mouth, head back, wide mouth. (Hands ride on the head.)",
   interrupt="any", blend_in=0.2, blend_out=0.3, start_pose="stand", end_pose="stand")(_shout)


def _talk_to_self(t):
    T = 7.0
    ph = t / T
    p = base(0.15)
    beat = np.sin(TAU * t * 1.6)
    talk = 0.5 + 0.5 * np.sin(TAU * t * 3.4) * np.sin(TAU * t * 0.7 + 1)
    p = add(p, hd=[-2 + 4 * beat * 0.5, 4 * np.sin(TAU * ph * 2), 22 * np.sin(TAU * ph) * np.cos(TAU * ph * 3)], sp=[1, 0, 8 * np.sin(TAU * ph)],
            pel=[0, 0, -0.004, 0, 1.5 * np.sin(TAU * ph * 2), 3 * np.sin(TAU * ph)])
    p["armR"] = HANG + np.array([32 + 18 * beat, 22, 0, 74 + 20 * np.sin(TAU * t * 0.8), 0, 0])
    p["armL"] = HANG + np.array([14 + 6 * np.sin(TAU * t * 0.7), 8, 0, 40 + 10 * np.sin(TAU * t * 1.1), 0, 0])
    p["fR"] = RK.G("relaxed", 0.5 + 0.4 * (0.5 + 0.5 * beat))
    p["fL"] = RK.G("relaxed", 0.6)
    p = addf(p, jaw=6 * talk, brow_L=0.3 * (0.5 + 0.5 * beat), brow_R=0.3 * (0.5 - 0.5 * beat) + 0.1, smile_L=0.1, smile_R=0.1)
    p["eye"] = np.array([12 * np.sin(TAU * ph * 3), -2 + 4 * np.sin(TAU * ph * 5)])
    p = RK.breathing(p, t, 4.0, 1.0)
    return p, O()


mk("talk_to_self", "personality", 7.0, loop=True, desc="Muttering to himself: mouth moving, small explanatory hand gestures, head turning and nodding as if arguing both sides.",
   interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="stand", end_pose="stand")(_talk_to_self)


# ---------------------------------------------------------------------------------------------------- celebrate / embarrassed
def _celebrate(t):
    T = 3.4
    jump = env(t, 0.5, 0.75, 0.95, 1.3) * 0 + np.where((t > 0.55) & (t < 1.25), np.sin(np.pi * (t - 0.55) / 0.7), 0.0)
    crouch = env(t, 0.1, 0.5, 0.52, 0.6)
    a = env(t, 0.5, 0.9, 2.8, 3.4)
    p = base(0.9)
    p["pel"] = np.array([0, 0.0, -0.10 * crouch + 0.35 * jump - 0.02 * a, 8 * crouch, 0, 5 * np.sin(TAU * t / 1.7) * a])
    p = add(p, sp=[12 * crouch - 6 * a, 0, 6 * np.sin(TAU * t / 1.7) * a], hd=[-4 * a, 0, 0])
    for sd in ("L", "R"):
        p[f"ft{sd}"] = np.array(p[f"ft{sd}"]) + np.array([0, 0, 0.30 * jump + 0.0, -20 * jump, 0, 0])
    wave = np.sin(TAU * 2.0 * t) * a
    p["armL"] = HANG + np.array([150 * a * (1 - 0.1 * crouch), 28 * a, 0, 20 * a, 0, 0]) + np.array([0, 6 * wave, 0, 0, 0, 0])
    p["armR"] = HANG + np.array([150 * a, 28 * a, 0, 20 * a, 0, 0]) + np.array([0, -6 * wave, 0, 0, 0, 0])
    p["fL"] = RK.G("fist", a)
    p["fR"] = RK.G("fist", a)
    p = addf(p, smile_L=1.0 * a, smile_R=1.0 * a, cheek=1.0 * a, jaw=16 * a, brow_L=0.5 * a, brow_R=0.5 * a, squint=0.4 * a)
    air = jump > 0.02
    return p, O(stance=(not air, not air))


mk("celebrate", "personality", 3.4, desc="Triumphant celebration: crouch, leap with both fists overhead, land and punch the air with a roar of joy.",
   interrupt="none", blend_in=0.15, blend_out=0.3, start_pose="stand", end_pose="stand", events=[(0.55, "leave_ground"), (1.25, "land")])(_celebrate)


def _embarrassed(t):
    a = env(t, 0.3, 0.9, 2.6, 3.4)
    rub = shake(t, 3.0, 1.0, 1.0, 2.6, 0.2)
    p = base(0.3)
    p = add(p, sp=[5 * a, 0, -6 * a], hd=[6 * a, -10 * a, -24 * a], pel=[0, 0, -0.01 * a, 0, -3 * a, -5 * a])
    p["armR_ik"] = K.ik(v3(-0.04, 0.10, 1.70) + np.array([0.01 * rub, 0, 0]), (0.1, 0.6, 0.6), (-0.2, 0.3, -0.9), 0)
    p["armR_w"] = np.array([a])
    p["armR"] = HANG + np.array([30 * a, 20 * a, 0, 120 * a, 0, 0])
    p["armL"] = HANG + np.array([-4 * a, 4 * a, 0, 30 * a, 0, 0])
    p["fR"] = RK.G("relaxed", 0.4)
    p["eye"] = np.array([-18 * a, 8 * a])
    p = addf(p, smile_L=0.55 * a, smile_R=0.35 * a, brow_L=0.5 * a, brow_R=0.1 * a, squint=0.2 * a, lip_low=0.3 * a)
    return p, O(spR="head")


mk("embarrassed_recover", "personality", 3.4, desc="Sheepish embarrassment after a blunder: rubs the back of his neck, shy lopsided grin, looks away, shuffles.",
   interrupt="any", blend_in=0.25, blend_out=0.3, start_pose="stand", end_pose="stand")(_embarrassed)


# ---------------------------------------------------------------------------------------------------- dances
REST_L = np.array([0.100, 0.0, AZ, 0, 0, 0])
REST_R = np.array([-0.100, 0.0, AZ, 0, 0, 0])


def _dance_sway(t):
    T = 4.0
    ph = t / T
    s = np.sin(TAU * ph)
    c = np.cos(TAU * ph)
    p = base(0.7)
    p["pel"] = np.array([0.07 * s, 0.0, -0.06 - 0.02 * np.cos(TAU * ph * 2), 0, -9 * s, 8 * c])
    p = add(p, sp=[2, 8 * s, -10 * c], hd=[-3, -5 * s, 6 * c])
    # weight shifts over the foot on the swaying side; the other foot pivots on its toe
    p["ftL"] = REST_L + np.array([0.0, 0, 0.0, 0, 0, 6 * c])
    p["ftR"] = REST_R + np.array([0.0, 0, 0.0, 0, 0, 6 * c])
    p["armL"] = HANG + np.array([70 + 60 * c, 40 + 20 * s, 0, 40 - 20 * c, 0, 0])
    p["armR"] = HANG + np.array([70 - 60 * c, 40 - 20 * s, 0, 40 + 20 * c, 0, 0])
    p["fL"] = RK.G("open", 0.5)
    p["fR"] = RK.G("open", 0.5)
    p = addf(p, smile_L=0.6, smile_R=0.6, cheek=0.4)
    return p, O()


mk("dance_sway", "personality", 4.0, loop=True, desc="Slow flowing sway dance: hips roll side to side with bent knees, arms drifting over the head in opposite waves.",
   interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="stand", end_pose="stand")(_dance_sway)


def _dance_hop(t):
    T = 2.0
    ph = t / T
    s = np.sin(TAU * ph)
    hopL = max(0.0, np.sin(TAU * ph))
    hopR = max(0.0, -np.sin(TAU * ph))
    air = np.sin(np.pi * ((ph * 2) % 1.0))
    p = base(0.8)
    p["pel"] = np.array([0.04 * s, 0.0, -0.04 + 0.09 * air, 0, -5 * s, 6 * s])
    p = add(p, sp=[3, 6 * s, -8 * s], hd=[-4, 0, 6 * s])
    # kick-hop: the free leg swings forward/out while the stance leg bounces
    p["ftL"] = REST_L + np.array([0.0, -0.20 * hopR, 0.0 + 0.04 * air * (hopL > 0) + 0.14 * hopR, -18 * hopR, 0, 0])
    p["ftR"] = REST_R + np.array([0.0, -0.20 * hopL, 0.0 + 0.04 * air * (hopR > 0) + 0.14 * hopL, -18 * hopL, 0, 0])
    p["armL"] = HANG + np.array([30 + 40 * s, 30, 0, 80 + 30 * s, 0, 0])
    p["armR"] = HANG + np.array([30 - 40 * s, 30, 0, 80 - 30 * s, 0, 0])
    p["fL"] = RK.G("fist", 0.5)
    p["fR"] = RK.G("fist", 0.5)
    p = addf(p, smile_L=0.8, smile_R=0.8, cheek=0.6, jaw=6)
    return p, O(stance=(hopR < 0.01, hopL < 0.01))


mk("dance_hop", "personality", 2.0, loop=True, desc="Lively one-legged hop dance: alternates bouncing on each foot with a kick, arms pumping with the beat.",
   interrupt="any", blend_in=0.2, blend_out=0.2, start_pose="stand", end_pose="stand")(_dance_hop)


def _dance_stomp(t):
    T = 2.4
    ph = t / T
    p = base(0.5)
    sL = np.clip(np.sin(TAU * ph * 2) , 0, 1) if ph % 1.0 < 0.5 else 0.0
    stepL = 1.0 if (ph % 1.0) < 0.5 else 0.0
    q = (ph * 2) % 1.0
    lift = np.sin(np.pi * np.clip(q / 0.55, 0, 1)) if q < 0.55 else 0.0
    stamp = smooth(seg(q, 0.5, 0.58)) * (1 - smooth(seg(q, 0.58, 0.9)))
    p["pel"] = np.array([0.045 * (1 if stepL else -1) * 0.6, 0.0, -0.14 - 0.03 * stamp, 6, 0, 0])
    p = add(p, sp=[10, 4 * (1 if stepL else -1), 0], hd=[-8, 0, 0])
    L_up = lift if stepL else 0.0
    R_up = 0.0 if stepL else lift
    p["ftL"] = REST_L + np.array([0.06, -0.04, 0.22 * L_up, 0, 0, 0])
    p["ftR"] = REST_R + np.array([-0.06, -0.04, 0.22 * R_up, 0, 0, 0])
    pulse_a = 0.5 + 0.5 * np.cos(TAU * ph * 2)
    p["armL"] = HANG + np.array([50 + 30 * pulse_a, 6 + 12 * pulse_a, 0, 90 + 20 * pulse_a, 0, 0])
    p["armR"] = HANG + np.array([50 + 30 * pulse_a, 6 + 12 * pulse_a, 0, 90 + 20 * pulse_a, 0, 0])
    p["fL"] = RK.G("fist", 0.7)
    p["fR"] = RK.G("fist", 0.7)
    p = addf(p, smile_L=0.3, smile_R=0.3, brow_L=0.2, brow_R=0.2, furrow=0.3, jaw=3)
    return p, O(stance=(L_up < 0.02, R_up < 0.02))


mk("dance_stomp", "personality", 2.4, loop=True, desc="Grounded tribal-style stomp dance: deep knee bend, alternating stamping steps, forearms driving at the chest.",
   interrupt="any", blend_in=0.2, blend_out=0.2, start_pose="stand", end_pose="stand")(_dance_stomp)


def _dance_hula(t):
    T = 4.0
    ph = t / T
    a = TAU * ph
    p = base(0.7)
    p["pel"] = np.array([0.045 * np.cos(a), 0.035 * np.sin(a), -0.07, 5 * np.sin(a), -7 * np.cos(a), 0])
    p = add(p, sp=[-2 * np.sin(a), 6 * np.cos(a), 0], hd=[0, -3 * np.cos(a), 0])
    wv = np.sin(a * 2)
    p["armL"] = HANG + np.array([80, 55 + 10 * np.sin(a * 2 + 1), 0, 60 + 40 * wv, 20 * wv, 0])
    p["armR"] = HANG + np.array([80, 55 + 10 * np.sin(a * 2), 0, 60 - 40 * wv, -20 * wv, 0])
    p["fL"] = RK.G("open", 0.6)
    p["fR"] = RK.G("open", 0.6)
    p = addf(p, smile_L=0.7, smile_R=0.7, cheek=0.5)
    return p, O()


mk("dance_hula", "personality", 4.0, loop=True, desc="Hip-circling island sway with rippling wave hands, knees soft, a broad smile.",
   interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="stand", end_pose="stand")(_dance_hula)


def _dance_twist(t):
    T = 1.6
    a = TAU * t / T
    p = base(0.8)
    p["pel"] = np.array([0.0, 0.0, -0.11, 0, 0, 22 * np.sin(a)])
    p = add(p, sp=[6, 0, -34 * np.sin(a)], hd=[-6, 0, 12 * np.sin(a)])
    p["ftL"] = REST_L + np.array([0, 0, 0, 0, 0, -8 * np.sin(a)])
    p["ftR"] = REST_R + np.array([0, 0, 0, 0, 0, -8 * np.sin(a)])
    p["armL"] = HANG + np.array([60 + 20 * np.sin(a + 1), 20, 0, 100, 0, 0])
    p["armR"] = HANG + np.array([60 - 20 * np.sin(a + 1), 20, 0, 100, 0, 0])
    p["fL"] = RK.G("fist", 0.4)
    p["fR"] = RK.G("fist", 0.4)
    p = addf(p, smile_L=0.8, smile_R=0.8, cheek=0.6, jaw=8)
    return p, O()


mk("dance_twist", "personality", 1.6, loop=True, desc="Twist dance: knees bent, hips and shoulders counter-rotate, elbows pumping.",
   interrupt="any", blend_in=0.2, blend_out=0.2, start_pose="stand", end_pose="stand")(_dance_twist)


# ---------------------------------------------------------------------------------------------------- clap / wave / shrug / nod
def _clap(t):
    T = 3.0
    a = env(t, 0.2, 0.5, 2.5, 3.0)
    c = 0.5 + 0.5 * np.cos(TAU * 3.0 * t)          # 1 = apart, 0 = together
    p = base(0.8)
    p = add(p, sp=[-2 * a, 0, 0], hd=[-3 * a + 3 * np.sin(TAU * 3 * t) * a * 0.3, 0, 0], pel=[0, 0, -0.01 * a * (1 - c), 0, 0, 0])
    sep = 0.05 + 0.16 * c
    p["armL_ik"] = K.ik(v3(sep, 0.30, 1.40), (-0.2, -1, 0.1), (-1, 0, 0), 0)
    p["armR_ik"] = K.ik(v3(-sep, 0.30, 1.40), (0.2, -1, 0.1), (1, 0, 0), 0)
    p["armL_w"] = np.array([a])
    p["armR_w"] = np.array([a])
    p["armL"] = HANG + np.array([50 * a, 10 * a, 0, 80 * a, 0, 0])
    p["armR"] = HANG + np.array([50 * a, 10 * a, 0, 80 * a, 0, 0])
    p["fL"] = RK.G("flat", 0.5 * a)
    p["fR"] = RK.G("flat", 0.5 * a)
    p = addf(p, smile_L=0.8 * a, smile_R=0.8 * a, cheek=0.5 * a, brow_L=0.3 * a, brow_R=0.3 * a)
    return p, O(spL="chest", spR="chest")


mk("clap", "personality", 3.0, desc="Applause: clapping briskly in front of the chest with a delighted grin.",
   interrupt="any", blend_in=0.2, blend_out=0.25, start_pose="stand", end_pose="stand")(_clap)


def _wave(t):
    a = env(t, 0.2, 0.6, 2.6, 3.2)
    w = np.sin(TAU * 2.2 * t) * a
    p = base(0.7)
    p = add(p, hd=[-2 * a, 4 * a, 8 * a], sp=[0, 0, 4 * a], pel=[0, 0, 0, 0, -2 * a, 0])
    p["armR"] = HANG + np.array([120 * a, 26 * a, 0, 70 * a + 8 * w, 6 * a, 20 * w])
    p["armL"] = HANG
    p["fR"] = RK.G("open", 0.8 * a)
    p = addf(p, smile_L=0.8 * a, smile_R=0.8 * a, cheek=0.5 * a, brow_L=0.3 * a, brow_R=0.3 * a)
    return p, O()


mk("wave_hello", "personality", 3.2, desc="Friendly wave hello/goodbye with the right hand raised, fingers open, wrist swinging.",
   interrupt="any", blend_in=0.2, blend_out=0.25, start_pose="stand", end_pose="stand")(_wave)


def _shrug(t):
    a = env(t, 0.2, 0.55, 1.5, 2.2)
    p = base(0.1)
    p = add(p, hd=[0, 10 * a, 0], sp=[0, 0, 0], pel=[0, 0, 0, 0, 0, 0])
    p["armL"] = HANG + np.array([20 * a, 26 * a, 0, 70 * a, 0, 0])
    p["armR"] = HANG + np.array([20 * a, 26 * a, 0, 70 * a, 0, 0])
    p["fL"] = RK.G("open", 0.8 * a)
    p["fR"] = RK.G("open", 0.8 * a)
    p = addf(p, brow_L=0.6 * a, brow_R=0.6 * a, frown=0.4 * a, smile_L=-0.1 * a, smile_R=-0.1 * a, lip_low=0.3 * a)
    return p, O()


mk("shrug", "personality", 2.2, desc="Classic 'who knows?' shrug: shoulders up, palms out and up, brows raised, mouth pulled down.",
   interrupt="any", blend_in=0.15, blend_out=0.25, start_pose="stand", end_pose="stand")(_shrug)


def _nod_yes(t):
    a = env(t, 0.1, 0.3, 1.6, 2.0)
    p = base(0.3)
    p = add(p, hd=[10 * np.sin(TAU * 2 * t) * a, 0, 0], sp=[2 * np.sin(TAU * 2 * t - 0.6) * a, 0, 0])
    p = addf(p, smile_L=0.4 * a, smile_R=0.4 * a)
    return p, O()


mk("nod_yes", "personality", 2.0, desc="Agreeing nod, two clear head nods with a small smile.", interrupt="any", blend_in=0.15, blend_out=0.2,
   start_pose="stand", end_pose="stand")(_nod_yes)


def _shake_no(t):
    a = env(t, 0.1, 0.3, 1.6, 2.0)
    p = base(0.0)
    p = add(p, hd=[3 * a, 0, 24 * np.sin(TAU * 2 * t) * a], sp=[0, 0, 6 * np.sin(TAU * 2 * t - 0.5) * a])
    p = addf(p, frown=0.4 * a, lip_low=0.4 * a, brow_L=0.2 * a, brow_R=0.2 * a)
    return p, O()


mk("shake_no", "personality", 2.0, desc="Disagreeing head shake, lips pressed down.", interrupt="any", blend_in=0.15, blend_out=0.2,
   start_pose="stand", end_pose="stand")(_shake_no)


# ---------------------------------------------------------------------------------------------------- curious looks
def _curious_look(t):
    T = 4.4
    a = env(t, 0.3, 1.0, 3.4, 4.4)
    tilt = np.sin(TAU * t / T * 1.5)
    p = base(0.3)
    p = add(p, sp=[14 * a, 0, 8 * a], hd=[8 * a, 14 * a + 4 * tilt * a, 20 * a], pel=[0, 0.06 * a, -0.02 * a, 4 * a, 0, 6 * a])
    p["armL"] = HANG + np.array([12 * a, 4 * a, 0, 30 * a, 0, 0])
    p["armR"] = HANG + np.array([6 * a, 4 * a, 0, 20 * a, 0, 0])
    p["eye"] = np.array([-8 * a, 8 * a])
    p = addf(p, brow_L=0.55 * a, brow_R=0.2 * a, squint=0.3 * a, pucker=0.1 * a)
    return p, O()


mk("look_curious", "personality", 4.4, desc="Curious peering: leans in with a tilted head, one brow up, eyes narrowed, hands hanging loose.",
   interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="stand", end_pose="stand")(_curious_look)


def _look_up_sky(t):
    a = env(t, 0.4, 1.3, 4.0, 5.0)
    p = base(0.2)
    p = add(p, sp=[-6 * a, 0, 4 * np.sin(TAU * t / 5.0) * a], hd=[-26 * a, 0, 12 * np.sin(TAU * t / 5.0) * a], pel=[0, 0, 0, -2 * a, 0, 0])
    p["armL"] = HANG + np.array([-4 * a, 4 * a, 0, 6 * a, 0, 0])
    p["armR_ik"] = K.ik(v3(-0.06, -0.04, 1.97), (0.3, -0.5, 0.2), (0, -0.5, -1))      # shading the eyes with the flat hand
    p["armR_w"] = np.array([0.0])
    p["eye"] = np.array([0.0, -10 * a])
    p = addf(p, squint=0.5 * a, brow_L=0.3 * a, brow_R=0.3 * a, jaw=2 * a)
    return p, O()


mk("look_up_sky", "personality", 5.0, desc="Tips his head far back to look up at the sky or the treetops, squinting; a slow turn as something passes.",
   interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="stand", end_pose="stand")(_look_up_sky)


# ---------------------------------------------------------------------------------------------------- lounging and play
def _lounge_sit_back(t):
    T = 12.0
    ph = t / T
    from clips_posture import pose_sit_ground
    p = pose_sit_ground(0.62)
    p = K.P(p, sp=[-14, 0, 0], hd=[2, 0, 0], pel=[0, 0.12, -(RK.HIP_Z - 0.085) - 0.0, -26, 0, 0], armL=HANG.copy(), armR=HANG.copy(), wL=0.0, wR=0.0)
    p = RK.face_neutral(p, 0.4)
    p["armL"] = np.array([-26.0, 16.0, 0.0, 4.0, 0, 0])
    p["armR"] = np.array([-26.0, 16.0, 0.0, 4.0, 0, 0])
    p["fL"] = RK.G("open", 0.3)
    p["fR"] = RK.G("open", 0.3)
    p["ftL"] = FT("L", 0.15, 0.86, AZ + 0.01, -14, -8, 14)
    p["ftR"] = FT("R", -0.15, 0.86, AZ + 0.01, -14, 8, -14)
    p = add(p, sp=[1.4 * sw(t, 4.4), 0, 2 * sw(t, T)], hd=[-3 * np.maximum(0, sw(t, T, 0.25)), 2 * sw(t, T), 14 * sw(t, T, 0.1)])
    p["ftR"] = np.array(p["ftR"]) + np.array([0, 0, 0.02 * np.maximum(0, sw(t, 3.0)), 0, 0, 0])
    p = addf(p, smile_L=0.3, smile_R=0.25, squint=0.15, blink_L=0.0)
    p = RK.breathing(p, t, 4.4, 1.0)
    return p, O(stance=(True, True))


mk("lounge_sit_back", "personality", 12.0, loop=True, desc="Lounging on the sand propped back on both hands, legs stretched out, face tilted to the sun with a contented half smile.",
   interrupt="any", blend_in=0.5, blend_out=0.5, start_pose="sit_back", end_pose="sit_back")(_lounge_sit_back)


def _lounge_recline(t):
    T = 14.0
    ph = t / T
    from clips_posture import pose_sit_ground
    p = pose_sit_ground(0.62)
    p = K.P(p, sp=[-6, -10, 0], hd=[0, 8, 10], pel=[0, 0.14, -(RK.HIP_Z - 0.085), -28, -14, 0], armL=HANG.copy(), armR=HANG.copy(), wL=0.0, wR=0.0)
    p = RK.face_neutral(p, 0.5)
    # propped on the left elbow, right knee drawn up with the right hand resting on it
    p["armL"] = np.array([-26.0, 24.0, 0.0, 70.0, 0, 0])
    p["armR_ik"] = K.ik(v3(-0.14, 0.40, 0.58), (0, -1, 0.1), (0.6, 0, 0.8), 10)
    p["armR_w"] = np.array([1.0])
    p["ftL"] = FT("L", 0.15, 0.84, AZ + 0.01, -14, -8, 14)
    p["ftR"] = FT("R", -0.17, 0.38, AZ, -10, 10, -10)
    p["fL"] = RK.G("relaxed", 0.6)
    p["fR"] = RK.G("relaxed", 0.8)
    p = add(p, sp=[1.2 * sw(t, 4.4), 0, 0], hd=[0, 2 * sw(t, T), 18 * sw(t, T, 0.2)])
    p["eye"] = np.array([8 * sw(t, T / 2), 2 * sw(t, T / 3)])
    p = addf(p, smile_L=0.2, smile_R=0.2)
    p = RK.breathing(p, t, 4.4, 1.0)
    return p, O(stance=(True, True))


mk("lounge_recline", "personality", 14.0, loop=True, desc="Reclining on one elbow in the shade, one knee drawn up with a hand draped over it, idly watching the waves.",
   interrupt="any", blend_in=0.5, blend_out=0.5, start_pose="sit_back", end_pose="sit_back")(_lounge_recline)


def _play_toss_catch(t):
    T = 3.2
    ph = (t / T) % 1.0
    toss = pulse(ph, 0.08, 0.2, 0.22, 0.32)
    catch = pulse(ph, 0.62, 0.72, 0.8, 1.0)
    p = base(0.7)
    p = add(p, sp=[-4 * toss + 4 * catch, 0, 0], hd=[-14 * smooth(seg(ph, 0.1, 0.35)) * (1 - smooth(seg(ph, 0.6, 0.7))), 0, 0], pel=[0, 0, -0.01 * catch - 0.02 * toss, 0, 0, 0])
    up = smooth(seg(ph, 0.1, 0.22)) * (1 - smooth(seg(ph, 0.3, 0.6)))
    p["armR"] = HANG + np.array([50 + 100 * toss - 20 * catch, 16, 0, 80 - 60 * toss + 10 * catch, 0, 0])
    p["armL"] = HANG + np.array([24 + 60 * catch, 10 + 10 * catch, 0, 40 + 50 * catch, 0, 0])
    p["fR"] = RK.G("grip_big", 0.9 * (1 - toss))
    p["fL"] = RK.G("open", 0.3 + 0.5 * catch)
    p["look"] = np.array([0.0, -0.3 - 0.0, 1.9 + 2.0 * up, 0.9])
    p = addf(p, smile_L=0.6, smile_R=0.6, jaw=3 * catch, brow_L=0.3 * up, brow_R=0.3 * up)
    return p, O()


mk("play_toss_catch", "personality", 3.2, loop=True, desc="Playfully tossing a coconut up with the right hand and catching it with both, eyes following its arc.", props=["coconut"],
   interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="stand", end_pose="stand")(_play_toss_catch)


def _play_kick_sand(t):
    T = 3.0
    k = pulse(t, 0.5, 0.9, 1.0, 1.5)
    swing = np.sin(np.pi * np.clip((t - 0.7) / 0.5, 0, 1)) * (t > 0.7) * (t < 1.2)
    a = env(t, 0.2, 0.6, 2.2, 2.9)
    p = base(0.4)
    p["pel"] = np.array([-0.04 * a, 0, -0.02 * a, 0, 3 * a, 0])
    p = add(p, sp=[6 * a, 0, 6 * a], hd=[14 * a, 0, -10 * a])
    p["ftL"] = np.array([0.10, 0.0, AZ, 0, 0, 0])
    p["ftR"] = np.array([-0.10, -0.40 * swing * 1.0 + 0.10 * a, AZ + 0.12 * swing + 0.04 * k, -28 * swing, 0, -8 * a])
    p["armL"] = HANG + np.array([10 * a, 30 * a, 0, 20 * a, 0, 0])
    p["armR"] = HANG + np.array([-8 * a, 26 * a, 0, 14 * a, 0, 0])
    p["look"] = np.array([-0.2, -0.6, 0.0, 0.8 * a])
    p = addf(p, smile_L=0.4 * a, smile_R=0.25 * a, lip_low=0.1 * a)
    return p, O(stance=(True, False))


mk("play_kick_sand", "personality", 3.0, desc="Kicking sand idly while he thinks: the right foot scuffs forward, sand flies, hands loose, a lopsided smile.",
   interrupt="any", blend_in=0.2, blend_out=0.3, start_pose="stand", end_pose="stand")(_play_kick_sand)


def _play_flex(t):
    a = env(t, 0.3, 0.9, 3.0, 3.8)
    p = base(0.7)
    pose = smooth(seg(t, 0.8, 1.2)) * (1 - smooth(seg(t, 2.0, 2.3))) 
    pose2 = smooth(seg(t, 2.1, 2.5)) * (1 - smooth(seg(t, 3.2, 3.6)))
    p = add(p, sp=[-3 * a, 0, 6 * (pose - pose2)], hd=[-6 * a, 0, -10 * (pose - pose2)], pel=[0, 0, -0.02 * a, 0, 0, 6 * (pose - pose2)])
    p["armL"] = HANG + np.array([30 * pose + 20 * pose2 + 10 * a, 70 * pose + 50 * pose2 + 10 * a, 0, 120 * pose + 130 * pose2, 0, 0])
    p["armR"] = HANG + np.array([30 * pose + 20 * pose2 + 10 * a, 70 * pose + 50 * pose2 + 10 * a, 0, 120 * pose + 130 * pose2, 0, 0])
    p["fL"] = RK.G("fist", pose + pose2)
    p["fR"] = RK.G("fist", pose + pose2)
    p = addf(p, smile_L=0.8 * a, smile_R=0.6 * a, brow_L=0.5 * a, brow_R=0.2 * a, jaw=2 * a)
    return p, O()


mk("play_flex_pose", "personality", 4.0, desc="Mock bodybuilder poses on the beach: a double-biceps flex, then a side pose, with a ridiculous grin.",
   interrupt="any", blend_in=0.2, blend_out=0.3, start_pose="stand", end_pose="stand")(_play_flex)


SKIP = GK.Gait(T=26 / 30, v=1.8, duty=0.40, x=0.09, bob=0.07, z0=-0.03, sway=0.02, roll=2.0, pyaw=5.0, syaw=8.0, arm=30.0, elbow0=40.0, elbow1=20.0, lean=3.0,
               out=-16.0, run=True, toe_out=3.0, foot=ST.Cfg(lift=0.20, toe_pitch=40.0, heel_pitch=4.0, roll_on=0.08, heel_off=0.30, toe_clear=4.0))


def _skip(t):
    steps = GK.make_steps(SKIP)
    prm, opts = GK.gait_params(t, SKIP, steps)
    prm = K.P(prm, wL=0.0, wR=0.0)
    prm = addf(prm, smile_L=0.8, smile_R=0.8, cheek=0.6, jaw=8)
    prm["hd"] = prm["hd"] + np.array([-4, 4 * np.sin(TAU * t / SKIP.T), 0])
    o = O(stance=(True, True), world=opts["world"])
    return prm, o


mk("play_skip", "personality", SKIP.T, loop=True, speed=SKIP.v, desc="Light-hearted skipping along the beach (1.8 m/s): bouncy gait, arms swinging loosely, big grin. timeScale = speed / 1.8.",
   interrupt="any", blend_in=0.2, blend_out=0.2, start_pose="stand", end_pose="stand")(_skip)
