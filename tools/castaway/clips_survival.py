"""Group B: survival and daily-life interactions (drinking, eating, coconuts, fire, resting, rain, rocks)."""
import numpy as np

import params as PR
import rigkit as RK
from clipkit import clip, keys, smooth, seg, pulse
from posekit import *      # noqa: F401,F403
import posekit as K
from clips_posture import pose_crouch, pose_sit_ground, pose_kneel

HANG = RK.ARM_HANG


def b(m=0.1, **kw):
    p = K.P(RK.stand(mood=m), armL=HANG.copy(), armR=HANG.copy(), wL=0.0, wR=0.0)
    return K.P(p, **kw) if kw else p


def crouch_base(depth=0.5, lean=34.0, hd=-20.0, f=0.04, m=0.1):
    p = pose_crouch(depth)
    p = K.P(p, sp=[lean, 0, 0], hd=[hd, 0, 0], pel=[0, 0.14 * depth / 0.4, -depth, 14 * depth / 0.4, 0, 0],
            ftL=FT("L", 0.115, f, AZ, 0, 0, 6), ftR=FT("R", -0.115, f, AZ, 0, 0, -6), armL=HANG.copy(), armR=HANG.copy(), wL=0.0, wR=0.0)
    return RK.face_neutral(p, m)


def ground_hand(side, x, f, z, fd=(0, -1, 0), pn=(0, 0, 1), twist=0.0):
    return K.ik(v3(x, f, z), fd, pn, twist)


# ---------------------------------------------------------------------------------------------------- drinking
def _drink_cupped(t):
    st = b()
    cr = crouch_base(0.52, 36, -26)
    # key A: hands cupped together dipped in the water in front of him
    dip = K.P(cr, ikL=ground_hand("L", 0.05, 0.40, 0.09, (-0.1, -1, 0.35), (0.1, 0, 1), -10), ikR=ground_hand("R", -0.05, 0.40, 0.09, (0.1, -1, 0.35), (-0.1, 0, 1), 10),
              gL="cup", gR="cup")
    dip["fL"] = RK.G("cup", 1.0)
    dip["fR"] = RK.G("cup", 1.0)
    # key B: hands raised to the mouth, head dipped to meet them
    up = K.P(crouch_base(0.52, 28, -10), gL="cup", gR="cup", hd=[2, 0, 0])
    up = K.hand_to_head(up, "L", v3(0.035, 0.16, 1.745), (-0.1, -0.5, 0.9), (0.1, 0.1, 1.0))
    up = K.hand_to_head(up, "R", v3(-0.035, 0.16, 1.745), (0.1, -0.5, 0.9), (-0.1, 0.1, 1.0))
    drink = K.P(up, hd=[-8, 0, 0], face=dict(jaw=0.0))
    drink = K.P(drink, face=dict(jaw=8.0, pucker=0.4))
    keysl = [(0.0, st), (0.7, cr), (1.3, dip), (1.7, dip), (2.5, up), (3.0, drink), (3.5, drink), (3.9, up), (4.5, dip), (4.8, dip), (5.4, up), (5.9, drink), (6.4, drink), (7.2, cr), (8.0, b(0.3))]
    return seq(t, keysl), O()


mk("drink_cupped_hands", "survival", 8.0, desc="Crouches at the water's edge, scoops water with cupped hands and drinks twice, then rises and wipes his beard.",
   interrupt="none", blend_in=0.2, blend_out=0.3, start_pose="stand", end_pose="stand", contact="hands:water", events=[(1.5, "hands_in_water"), (3.0, "drink"), (5.9, "drink")])(_drink_cupped)


def _wipe_mouth(t):
    a = env(t, 0.1, 0.4, 1.0, 1.5)
    wipe = np.sin(TAU * 2.2 * (t - 0.3)) * env(t, 0.3, 0.45, 0.95, 1.1)
    p = b(0.1)
    p = K.hand_to_head(p, "R", v3(-0.03 + 0.03 * wipe, 0.12, 1.77), (0.0, -0.6, 0.9), (-0.4, -0.2, -0.9), None, w=a)
    p["armR"] = HANG + np.array([50 * a, 14 * a, 0, 120 * a, 0, 0])
    p = add(p, hd=[6 * a, 4 * wipe, 0])
    p["fR"] = RK.G("flat", 0.5 * a)
    p = addf(p, squint=0.2 * a)
    return p, O()


mk("wipe_mouth", "survival", 1.5, desc="Wipes the mouth and beard with the back of the right hand after drinking or eating.", interrupt="any",
   blend_in=0.15, blend_out=0.2, start_pose="stand", end_pose="stand")(_wipe_mouth)


# ---------------------------------------------------------------------------------------------------- coconut
def _coconut_pickup(t):
    st = b()
    cr = crouch_base(0.55, 36, -24)
    reach = K.P(cr, ikR=ground_hand("R", -0.12, 0.30, 0.10, (0, -1, -0.3), (0, 0, -1), 20), gR="grip_big")
    reach["fR"] = RK.G("open", 0.6)
    grab = K.P(reach, gR="grip_big")
    grab["fR"] = RK.G("grip_big", 1.0)
    mid = K.P(crouch_base(0.3, 24, -12), ikR=ground_hand("R", -0.20, 0.25, 0.62, (0, -1, 0.1), (0.2, 0, 1), 20), wR=1.0)
    mid["fR"] = RK.G("grip_big", 1.0)
    top = K.P(b(0.3, hd=[10, 0, 8]), ikR=K.ik(v3(-0.20, 0.34, 1.28), (0.1, -1, 0.3), (0.3, 0, 1), 20), wR=1.0)
    top["fR"] = RK.G("grip_big", 1.0)
    top["armL"] = HANG + np.array([20, 10, 0, 40, 0, 0])
    return seq(t, [(0.0, st), (0.8, cr), (1.4, reach), (1.8, grab), (2.4, mid), (3.2, top), (3.8, top)]), O()


mk("coconut_pickup", "survival", 3.8, desc="Crouches, picks a coconut up off the sand in his right hand and rises, holding it out to inspect it.",
   props=["coconut"], interrupt="none", blend_in=0.2, blend_out=0.3, start_pose="stand", end_pose="stand_hold_right", events=[(1.8, "attach_coconut_R")],
   attach=[dict(prop="coconut", bone="attach_hand_R", from_event="attach_coconut_R")])(_coconut_pickup)


def _coconut_crack(t):
    """Holds the coconut in the left hand and strikes it with the right fist/rock three times, then it splits and he pulls it apart."""
    p0 = b(0.0)
    hold = K.P(b(0.1, sp=[16, 0, 0], hd=[12, 0, 0], pel=[0, 0.02, -0.02, 4, 0, 0]), ikL=K.ik(v3(0.14, 0.34, 1.20), (-0.1, -1, 0.2), (0.4, 0, 1), -10), wL=1.0,
               ikR=K.ik(v3(-0.20, 0.30, 1.46), (0.1, -0.5, 0.9), (0.2, 0, 1), 0), wR=1.0)
    hold["fL"] = RK.G("grip_big", 1.0)
    hold["fR"] = RK.G("fist", 1.0)
    hit = K.P(hold, ikR=K.ik(v3(-0.04, 0.33, 1.24), (0.1, -0.5, 0.5), (0.2, 0, 1), 0), sp=[24, 0, 0], hd=[16, 0, 0])
    hit["fR"] = RK.G("fist", 1.0)
    split = K.P(hold, ikL=K.ik(v3(0.22, 0.30, 1.22), (-0.2, -1, 0.1), (0.3, 0, 1), -10), ikR=K.ik(v3(-0.06, 0.30, 1.22), (0.2, -1, 0.1), (-0.3, 0, 1), 10))
    split["fR"] = RK.G("grip_big", 0.9)
    split = addf(split, smile_L=0.4, smile_R=0.4)
    kf = [(0.0, p0), (0.6, hold), (1.0, hold), (1.2, hit), (1.35, hold), (1.75, hold), (1.95, hit), (2.1, hold), (2.5, hold), (2.7, hit), (2.85, hold), (3.4, split), (4.2, split)]
    return seq(t, kf), O()


mk("coconut_crack", "survival", 4.2, desc="Cracks a coconut with three sharp blows against a rock (held in the right fist), then pulls the shell apart with both hands.",
   props=["coconut", "rock"], interrupt="none", blend_in=0.2, blend_out=0.3, start_pose="stand", end_pose="stand_hold_both", events=[(1.2, "strike"), (1.95, "strike"), (2.7, "strike_split"), (3.4, "split_apart")],
   attach=[dict(prop="coconut", bone="attach_hand_L", from_t=0.0)])(_coconut_crack)


def _coconut_drink(t):
    a = env(t, 0.2, 0.9, 3.6, 4.4)
    tip = env(t, 1.0, 1.6, 3.2, 3.8)
    p = b(0.1)
    p = add(p, sp=[-6 * tip, 0, 0], hd=[-20 * tip, 0, 0], pel=[0, 0, 0, -2 * tip, 0, 0])
    p = K.hand_to_head(p, "R", v3(-0.085, 0.13, 1.74), (0.3, -0.6, 0.5), (0.7, -0.1, 0.6), -150.0, w=a)
    p = K.hand_to_head(p, "L", v3(0.085, 0.13, 1.78), (-0.3, -0.5, 0.5), (-0.7, 0.0, 0.7), 150.0, w=a)
    p["armR"] = HANG + np.array([50 * a, 10 * a, 0, 100 * a, 0, 0])
    p["armL"] = HANG + np.array([60 * a, 10 * a, 0, 120 * a, 0, 0])
    p["fR"] = RK.G("grip_big", a)
    p["fL"] = RK.G("grip_big", a)
    gulp = shake(t, 1.6, 1.0, 1.4, 3.4, 0.2)
    p = addf(p, jaw=6 * tip, squint=0.4 * tip, smile_L=0.2 * tip, smile_R=0.2 * tip, cheek=0.3 * tip)
    p = add(p, sp=[0.6 * gulp, 0, 0])
    return p, O()


mk("coconut_drink", "survival", 4.4, desc="Raises the opened coconut to his mouth with both hands, tips his head back and drinks, then lowers it with a satisfied face.",
   props=["coconut"], interrupt="any", blend_in=0.2, blend_out=0.3, start_pose="stand_hold_both", end_pose="stand_hold_both")(_coconut_drink)


# ---------------------------------------------------------------------------------------------------- eating
def _eat(t):
    T = 6.0
    ph = t / T
    cyc3 = (t / 2.0) % 1.0
    to_mouth = smooth(seg(cyc3, 0.0, 0.3)) * (1 - smooth(seg(cyc3, 0.55, 0.85)))
    chew = np.sin(TAU * 3.0 * t) * 0.5 + 0.5
    p = b(0.2)
    p = add(p, hd=[3 + 4 * to_mouth, 4 * np.sin(TAU * ph), 6 * np.sin(TAU * ph)], sp=[3, 0, 0])
    p = K.hand_to_head(p, "R", v3(-0.03, 0.10, 1.775), (0.1, -0.5, 0.85), (-0.5, -0.1, -0.85), None, w=to_mouth)
    p["armR"] = HANG + np.array([30 + 20 * to_mouth, 10, 0, 40 + 80 * to_mouth, 0, 0])
    p["armL_ik"] = K.ik(v3(0.12, 0.28, 1.15), (-0.1, -1, 0.1), (0.1, 0, 1), -10)
    p["armL_w"] = np.array([0.0])
    p["armL"] = HANG + np.array([34, 10, 0, 70, 0, 0])
    p["fR"] = RK.G("pinch", 0.8)
    p["fL"] = RK.G("cup", 0.7)
    chewing = (1.0 - to_mouth)
    p = addf(p, jaw=1.0 + 4.5 * chew * (0.3 + 0.7 * chewing), cheek=0.3 * chewing, smile_L=0.1, smile_R=0.1, squint=0.1)
    p = RK.breathing(p, t, 4.0, 1.0)
    return p, O()


mk("eat_food", "survival", 6.0, loop=True, desc="Eating a piece of fruit/fish held in the right hand: bite, chew with cheeks working, next bite; left hand cups below.",
   props=["food"], interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="stand", end_pose="stand",
   attach=[dict(prop="food", bone="attach_hand_R", from_t=0.0)])(_eat)


# ---------------------------------------------------------------------------------------------------- seats
def seat_base(h=0.50, lean=8.0, m=0.1, spread=0.115, f=0.44):
    """Seated on a rock/log with its top at height h, feet flat on the ground, hands on the thighs."""
    p = K.P(RK.stand(mood=m), pel=[0, 0.14, -(RK.HIP_Z - (h + 0.075)), 4, 0, 0], sp=[lean, 0, 0], hd=[-6, 0, 0],
            ftL=FT("L", spread, f, AZ, 0, 0, 8), ftR=FT("R", -spread, f, AZ, 0, 0, -8), armL=HANG.copy(), armR=HANG.copy(), wL=0.0, wR=0.0)
    p["armL_ik"] = K.ik(v3(0.17, 0.30, h + 0.20), (0, -1, 0), (-1, 0, 0))
    p["armR_ik"] = K.ik(v3(-0.17, 0.30, h + 0.20), (0, -1, 0), (1, 0, 0))
    return p


def ground_sit(knees=0.40, lean=14.0, m=0.1, hd=-8.0):
    p = pose_sit_ground(knees)
    p = K.P(p, sp=[lean, 0, 0], hd=[hd, 0, 0], armL=HANG.copy(), armR=HANG.copy(), wL=0.0, wR=0.0)
    return RK.face_neutral(p, m)


def _rest_on_rock(t):
    T = 10.0
    ph = t / T
    p = seat_base(0.5, 10.0, 0.15)
    p["armL_w"] = np.array([1.0])
    p["armR_w"] = np.array([1.0])
    p = add(p, sp=[1.5 * sw(t, 4.2), 0, 3 * sw(t, T)], hd=[2 * sw(t, T, 0.3), 3 * sw(t, T), 26 * sw(t, T, 0.1) * np.cos(TAU * ph * 2)],
            pel=[0, 0, 0, 0, 0, 2 * sw(t, T)])
    p["eye"] = np.array([6 * sw(t, T / 2), 2 * sw(t, T / 3)])
    p = RK.breathing(p, t, 4.2, 1.0)
    return p, O(stance=(True, True))


mk("rest_on_rock", "survival", 10.0, loop=True, desc="Sitting on a rock or log (seat height 0.50 m), forearms resting on the thighs, gazing slowly around; breathing and small posture shifts.",
   interrupt="any", blend_in=0.4, blend_out=0.4, start_pose="seated_50", end_pose="seated_50", seat_height=0.5)(_rest_on_rock)


def _sit_on_rock(t):
    """Stand -> turn and sit down on a 0.50 m seat behind/under him."""
    st = b(0.1)
    sd = K.P(st, pel=[0, 0.08, -0.22, 8, 0, 0], sp=[16, 0, 0], hd=[-8, 0, 0], ftL=FT("L", 0.115, 0.10, AZ, 0, 0, 6), ftR=FT("R", -0.115, 0.10, AZ, 0, 0, -6))
    sd["armL"] = HANG + np.array([20, 4, 0, 40, 0, 0])
    sd["armR"] = sd["armL"].copy()
    seat = seat_base(0.5, 10.0, 0.15)
    seat["armL_w"] = np.array([1.0])
    seat["armR_w"] = np.array([1.0])
    return seq(t, [(0.0, st), (0.6, sd), (1.4, seat), (1.8, seat)]), O()


mk("sit_on_rock", "survival", 1.8, desc="From standing, lowers himself onto a rock or log seat (0.50 m): knees bend, hands settle on the thighs.", interrupt="none",
   blend_in=0.2, blend_out=0.25, start_pose="stand", end_pose="seated_50", seat_height=0.5, events=[(1.2, "pelvis_touch_seat")])(_sit_on_rock)


def _rise_from_rock(t):
    seat = seat_base(0.5, 10.0, 0.15)
    seat["armL_w"] = np.array([1.0])
    seat["armR_w"] = np.array([1.0])
    lean = K.P(seat, pel=[0, 0.10, -0.40, 14, 0, 0], sp=[26, 0, 0], hd=[-14, 0, 0])
    lean["armL_w"] = np.array([0.0])
    lean["armR_w"] = np.array([0.0])
    lean["armL"] = HANG + np.array([30, 8, 0, 60, 0, 0])
    lean["armR"] = lean["armL"].copy()
    up = b(0.1)
    return seq(t, [(0.0, seat), (0.4, lean), (1.0, K.P(lean, pel=[0, 0.06, -0.18, 8, 0, 0])), (1.5, up), (1.7, up)]), O()


mk("rise_from_rock", "survival", 1.7, desc="Leans forward, pushes off the thighs and stands up from a 0.50 m rock/log seat.", interrupt="none", blend_in=0.2, blend_out=0.25,
   start_pose="seated_50", end_pose="stand", seat_height=0.5)(_rise_from_rock)


# ---------------------------------------------------------------------------------------------------- fire
FIRE = np.array([0.0, -0.80, 0.25])          # fire position in front of him (world)


def kneel_base(m=0.1, lean=10.0):
    p = pose_kneel()
    p = K.P(p, sp=[lean, 0, 0], hd=[-10, 0, 0], armL=HANG.copy(), armR=HANG.copy(), wL=0.0, wR=0.0)
    return RK.face_neutral(p, m)


def _tend_fire(t):
    T = 8.0
    ph = t / T
    p = kneel_base(0.0, 14.0)
    # feed a stick: right hand reaches towards the fire and back, left hand steadies on the thigh; blow occasionally
    feed = pulse(t, 1.0, 1.8, 2.2, 3.0) + pulse(t, 5.5, 6.2, 6.6, 7.3)
    blow = pulse(t, 3.4, 3.8, 4.8, 5.2)
    fpt = v3(-0.12, 0.62, 0.30 + 0.12 * feed)
    p["armR_ik"] = K.ik(fpt, (0, -1, -0.2), (0.2, 0, 1), 20)
    p["armR_w"] = np.array([0.0 + 1.0 * np.clip(feed + 0.35, 0, 1)])
    p["armR"] = HANG + np.array([30, 10, 0, 40, 0, 0])
    p["armL"] = HANG + np.array([20, 6, 0, 56, 0, 0])
    p["fR"] = RK.G("grip_thin", 0.8 * feed)
    p = add(p, sp=[10 * blow - 3 * feed, 0, 0], hd=[14 * blow + 6 * feed, 0, 0], pel=[0, 0.05 * blow, 0, 6 * blow, 0, 0])
    p = addf(p, pucker=0.8 * blow, jaw=2 * blow, squint=0.4 * blow + 0.3, brow_L=-0.1, brow_R=-0.1)
    p["look"] = np.array([FIRE[0], FIRE[1], FIRE[2], 0.9])
    p = RK.breathing(p, t, 4.0, 1.0)
    return p, O(stance=(False, False))


mk("tend_fire", "survival", 8.0, loop=True, desc="Kneeling at the fire: feeds a stick into the flames, leans in and blows on the embers, eyes squinting against the heat.",
   props=["firewood"], interrupt="any", blend_in=0.4, blend_out=0.4, start_pose="kneel", end_pose="kneel", fire_pos=[0, -0.8, 0.25])(_tend_fire)


def _turn_fish(t):
    T = 6.0
    rot = TAU * t / 3.0                       # skewer turned by the wrist
    p = kneel_base(0.1, 12.0)
    p["armR_ik"] = K.ik(v3(-0.16, 0.42, 0.34), (0.1, -1, 0.2), (0.0, 0.5, 1.0), 10 * np.sin(rot))
    p["armL_ik"] = K.ik(v3(0.12, 0.32, 0.30), (-0.1, -1, 0.2), (0.0, 0.5, 1.0), -10)
    p["armR_w"] = np.array([1.0])
    p["armL_w"] = np.array([1.0])
    p["fR"] = RK.G("grip_thin", 0.9)
    p["fL"] = RK.G("grip_thin", 0.8)
    p["fR"][12] = 0.0
    p = add(p, sp=[2 * np.sin(rot / 2), 0, 0], hd=[2 * np.sin(rot), 0, 0])
    p = addf(p, squint=0.4, smile_L=0.1, smile_R=0.1)
    p["look"] = np.array([FIRE[0], FIRE[1], 0.35, 0.9])
    p = RK.breathing(p, t, 4.0, 0.8)
    return p, O(stance=(False, False))


mk("turn_fish_on_fire", "survival", 6.0, loop=True, desc="Kneeling by the fire, turning a fish on a skewer over the flames with both hands, rolling the wrist and watching it cook.",
   props=["fish", "skewer"], interrupt="any", blend_in=0.4, blend_out=0.4, start_pose="kneel", end_pose="kneel",
   attach=[dict(prop="fish", bone="attach_hand_R", from_t=0.0)])(_turn_fish)


def _rest_by_fire(t):
    T = 10.0
    ph = t / T
    p = ground_sit(0.40, 18.0, 0.0, -10.0)
    p["armL_ik"] = K.ik(v3(0.08, 0.33, 0.50), (-0.6, -0.4, 0.3), (0.2, 0.2, 1), -10)
    p["armR_ik"] = K.ik(v3(-0.08, 0.33, 0.50), (0.6, -0.4, 0.3), (-0.2, 0.2, 1), 10)
    p["armL_w"] = np.array([1.0])
    p["armR_w"] = np.array([1.0])
    p = add(p, sp=[1.4 * sw(t, 4.5), 0, 2 * sw(t, T)], hd=[1.5 * sw(t, T), 2 * sw(t, T, 0.4), 6 * sw(t, T, 0.2)])
    p["look"] = np.array([FIRE[0], FIRE[1] - 0.2, 0.3, 0.9])
    p["eye"] = p["eye"] + np.array([0, 0.0])
    p = addf(p, squint=0.25, smile_L=0.12, smile_R=0.08)
    p = RK.breathing(p, t, 4.4, 1.0)
    return p, O()


mk("rest_by_fire", "survival", 10.0, loop=True, desc="Sitting on the ground hugging his knees, staring into the fire; slow breathing, drowsy blinks, firelight squint.",
   interrupt="any", blend_in=0.5, blend_out=0.5, start_pose="sit_knees_up", end_pose="sit_knees_up", fire_pos=[0, -0.8, 0.25])(_rest_by_fire)


def _prepare_food(t):
    T = 6.0
    ph = t / T
    beat = np.sin(TAU * 2.0 * t)
    cut = np.maximum(0, np.sin(TAU * 2.0 * t))
    p = ground_sit(0.45, 24.0, 0.1, -16.0)
    p["armL_ik"] = K.ik(v3(0.12, 0.40, 0.14), (-0.1, -1, 0), (0, 0, 1), -10)
    p["armR_ik"] = K.ik(v3(-0.10, 0.34, 0.20 + 0.16 * cut), (0.1, -1, -0.2), (0, 0, 1), 10)
    p["armL_w"] = np.array([1.0])
    p["armR_w"] = np.array([1.0])
    p["fL"] = RK.G("flat", 0.4)
    p["fR"] = RK.G("grip_thin", 0.9)
    p = add(p, sp=[2 * cut, 0, 0], hd=[2 * cut, 0, 0])
    p["look"] = np.array([0, -0.38, 0.12, 1.0])
    p = addf(p, squint=0.2, smile_L=0.1, smile_R=0.1)
    p = RK.breathing(p, t, 4.2, 0.8)
    return p, O()


mk("prepare_food", "survival", 6.0, loop=True, desc="Sitting on the ground preparing food on a flat stone: left hand holds the item, right hand chops/pounds with a rhythmic beat.",
   props=["knife_stone", "food"], interrupt="any", blend_in=0.4, blend_out=0.4, start_pose="sit_ground", end_pose="sit_ground")(_prepare_food)


# ---------------------------------------------------------------------------------------------------- rain
def _shelter_rain(t):
    T = 3.0
    ph = t / T
    p = b(-0.1)
    p = add(p, sp=[16, 0, 0], hd=[10, 0, 0], pel=[0, 0.04, -0.04, 6, 0, 0])
    shiver = np.sin(TAU * 5.0 * t)
    p["armR"] = HANG + np.array([140, 18, 0, 70, 0, 0])
    p["armL"] = HANG + np.array([50, 10, 0, 130, 0, 0])
    p["fR"] = RK.G("flat", 0.7)
    p["fL"] = RK.G("fist", 0.5)
    p = add(p, sp=[0.6 * shiver, 0, 0])
    p = addf(p, squint=0.5, frown=0.2, furrow=0.2)
    p = RK.breathing(p, t, 2.0, 1.3)
    return p, O()


mk("shelter_from_rain", "survival", 3.0, loop=True, desc="Hunched against the rain: shoulders up, one arm raised overhead as a makeshift roof, the other clutched to the chest, squinting.",
   interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="stand", end_pose="stand")(_shelter_rain)


def _sit_watch_rain(t):
    T = 8.0
    ph = t / T
    p = ground_sit(0.45, 16.0, 0.0, -6.0)
    palm = pulse(t, 1.0, 2.0, 5.0, 6.2)
    p["armL_ik"] = K.ik(v3(0.12, 0.34, 0.50), (-0.2, -1, 0.1), (0.1, 0.1, 1), -10)
    p["armL_w"] = np.array([1.0])
    p["armR"] = HANG + np.array([46 * palm + 10, 16 * palm + 6, 0, 36 * palm + 30, 0, 0])
    p["armR_ik"] = K.ik(v3(-0.24, 0.30, 0.60), (0, -1, 0), (0, 0, 1))
    p["armR_w"] = np.array([0.0])
    p["fR"] = RK.G("open", 0.7 * palm)
    up = pulse(t, 2.0, 3.0, 4.2, 5.0)
    p = add(p, sp=[0.8 * sw(t, 4.4), 0, 0], hd=[-24 * up + 3 * sw(t, T), 0, 14 * sw(t, T)])
    p["eye"] = np.array([0, -6 * up])
    p = addf(p, squint=0.3 * up + 0.1, smile_L=0.15, smile_R=0.1)
    p = RK.breathing(p, t, 4.4, 1.0)
    return p, O()


mk("sit_watching_rain", "survival", 8.0, loop=True, desc="Sitting under shelter watching the rain: holds a palm out to catch drops, tips his head up toward the sky, relaxed breathing.",
   interrupt="any", blend_in=0.5, blend_out=0.5, start_pose="sit_knees_up", end_pose="sit_knees_up")(_sit_watch_rain)
