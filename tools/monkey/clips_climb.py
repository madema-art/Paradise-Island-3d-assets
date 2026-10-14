"""Climbing + branch locomotion.

Climb frame (world): a vertical trunk of radius 0.12 m centred on x=0, y=-0.12 (its surface touches y=0 at x=0), so the
monkey is on the +Y side with its belly facing -Y. The root bone carries the body tilt (-80 deg about X), so in the
game the monkey simply faces the trunk and the clip pitches it up onto it.
Climb clips are in place: contact points slide *down* the trunk relative to the body at `speed_mps`.
"""
import math

from mathutils import Matrix, Vector

import anim_lib as A
from anim_lib import State, V, P, eul, lerp, smooth, seg
from clips_core import (BALL_Z, CLIPS, FOOT_F, FOOT_X, HAND_F, HAND_X, KNUCKLE_Z, clip, foot_cycle, gait_state,
                        keypose_fn, lerp_state, place_foot, place_hand, quad_stance, rest_poles, side_sign,
                        standing_state)

TAU = math.tau
TRUNK_R = 0.12
TILT = -80.0
ROOT_Y = -0.1326          # puts the belly ~1 cm off the bark
ROOT_Z = 0.26
SHOULDER = Vector((0, -0.268, 0.242))
HIP = Vector((0, -0.012, 0.214))


def trunk_y(x):
    return -TRUNK_R + math.sqrt(max(TRUNK_R ** 2 - x * x, 0.0))


def root_world(st):
    return Matrix.Translation(st.root_loc) @ eul(*st.root_rot).to_4x4()


def climb_state(phase, direction=1.0, g=None):
    """direction +1 climbs up (contacts slide down), -1 backs down (contacts slide up)."""
    g = g or CLIMB
    st = State()
    ph = phase * TAU
    st.root_rot = (TILT + 1.6 * math.sin(2 * ph), 1.3 * math.sin(ph), 2.4 * math.sin(ph + 0.3))
    st.root_loc = V(0.007 * math.sin(ph), ROOT_Y + 0.004 * math.cos(2 * ph), ROOT_Z + 0.003 * math.cos(2 * ph + 0.5))
    W = root_world(st)
    offs = g["offsets"]
    for s in A.SIDES:
        x = side_sign(s)
        sh = W @ Vector((x * 0.062, SHOULDER.y, SHOULDER.z))
        hp = W @ Vector((x * 0.046, HIP.y, HIP.z))
        # hand
        f, h, stance, u = foot_cycle(phase - offs[f"hand_{s}"], g["duty"], g["stride"], g["lift"])
        zf = f * direction
        hx = x * 0.056
        wrist = V(hx, trunk_y(hx) + 0.030 + (0 if stance else h * 0.8), sh.z + g["hand_c"] + zf + (0 if stance else 0.0))
        st.put(f"ik_hand_{s}", wrist, (-90, x * 9, 0))
        A.grip(st, s, g["grip"] if stance else lerp(0.30, 0.04, smooth(u)), spread=0.0)
        # foot
        f, h, stance, u = foot_cycle(phase - offs[f"foot_{s}"], g["duty"], g["stride"], g["lift"])
        zf = f * direction
        fx = x * 0.088
        ankle = V(fx, trunk_y(fx) + 0.034 + (0 if stance else h * 0.8), hp.z + g["foot_c"] + zf)
        st.put(f"ik_foot_{s}", ankle, (-78, x * 30, 0))
        A.toe_grip(st, s, g["grip"] if stance else lerp(0.35, 0.05, smooth(u)))
        st.put(f"pole_elbow_{s}", sh + V(x * 0.10, 0.13, -0.04))
        st.put(f"pole_knee_{s}", hp + V(x * 0.14, 0.04, 0.0))
    A.spine_pose(st, pelvis=(0, 0, 3.5 * math.sin(ph)), s1=(0, 0, 4 * math.sin(ph + 0.3)), s2=(-2, 0, 4 * math.sin(ph + 0.6)),
                 s3=(-2, 0, 3 * math.sin(ph + 0.9)))
    A.head_look(st, yaw=-5 * math.sin(ph + 0.8), pitch=-9 if direction > 0 else -3 + 5 * math.sin(ph),
                roll=0.0)
    A.tail_pose(st, curl_up=14, sway=12 * math.sin(ph + 1.0), wave=6, phase=ph)
    A.ears(st, back=6)
    return st


# stride 0.17 m, duty .62 over 0.8 s -> contact speed 0.343 m/s
CLIMB = dict(duty=0.62, stride=0.17, lift=0.035, hand_c=0.055, foot_c=-0.085, grip=0.85,
             offsets=dict(hand_L=0.0, foot_R=0.06, hand_R=0.5, foot_L=0.56))
CLIMB_FRAMES = 24
CLIMB_SPEED = round(CLIMB["stride"] / (CLIMB["duty"] * CLIMB_FRAMES / 30), 3)


@clip("climb_up", CLIMB_FRAMES, loop=True, group="climbing", speed_mps=CLIMB_SPEED, trunk_side="front (-Y)",
      description=f"Diagonal-couplet climb up a vertical trunk (radius 0.12 m). Contacts slide down the bark at {CLIMB_SPEED} m/s: "
                  f"move the root up the trunk at that speed (timeScale = climbSpeed / {CLIMB_SPEED}).")
def climb_up(phase):
    return climb_state(phase, 1.0)


CLIMB_DOWN = dict(CLIMB, offsets=dict(foot_L=0.0, hand_R=0.08, foot_R=0.5, hand_L=0.58), stride=0.15, duty=0.66, lift=0.03, grip=0.9)
CLIMB_DOWN_FRAMES = 28
CLIMB_DOWN_SPEED = round(CLIMB_DOWN["stride"] / (CLIMB_DOWN["duty"] * CLIMB_DOWN_FRAMES / 30), 3)


@clip("climb_down", CLIMB_DOWN_FRAMES, loop=True, group="climbing", speed_mps=-CLIMB_DOWN_SPEED, trunk_side="front (-Y)",
      description=f"Backing down a vertical trunk (feet lead, head up, glancing over the shoulder). Contacts slide up at "
                  f"{CLIMB_DOWN_SPEED} m/s: move the root DOWN at that speed.")
def climb_down(phase):
    st = climb_state(phase, -1.0, CLIMB_DOWN)
    return st


@clip("climb_hang_idle", 72, loop=True, group="climbing", trunk_side="front (-Y)",
      description="Resting on the trunk: all four limbs gripping, breathing, tail sway, looking around.")
def climb_hang_idle(phase):
    st = climb_state(0.12, 1.0)
    ph = phase * TAU
    breath = math.sin(2 * ph)
    st.root_loc = st.root_loc + V(0.002 * math.sin(ph), 0, 0.0015 * breath)
    st.rot("spine3", rx=1.0 * breath)
    A.head_look(st, yaw=14 * math.sin(ph), pitch=-14 + 8 * math.sin(ph + 1.0))
    A.tail_pose(st, curl_up=12, sway=14 * math.sin(ph + 0.5), wave=5, phase=ph)
    return st


# ---------------------------------------------------------------------------- transitions
def ground_quad(y0, z0=0.0, bob=0.0):
    st = State()
    st.root_loc = V(0, y0, z0)
    for s in A.SIDES:
        x = side_sign(s)
        place_hand(st, s, P(x * HAND_X, HAND_F, KNUCKLE_Z) + V(0, y0, 0))
        place_foot(st, s, P(x * FOOT_X, FOOT_F, BALL_Z) + V(0, y0, 0))
        st.put(f"pole_elbow_{s}", P(x * 0.080, 0.205, 0.130) + V(0, y0, z0))
        st.put(f"pole_knee_{s}", P(x * 0.085, 0.230, 0.120) + V(0, y0, z0))
    A.tail_pose(st, curl_up=6)
    A.head_look(st, pitch=-8)
    return st


def trunk_pose(root_y, root_z, tilt, hand_z, foot_y, foot_z, grip=0.8, foot_pitch=-70, head=-20, tail=10, spine=(0, 0, 0)):
    """Mid-transition pose: body tilted by `tilt`, hands on the bark at wrist height hand_z, feet at (foot_y, foot_z)."""
    st = State()
    st.root_rot = (tilt, 0, 0)
    st.root_loc = V(0, root_y, root_z)
    W = root_world(st)
    for s in A.SIDES:
        x = side_sign(s)
        hx, fx = x * 0.056, x * 0.088
        st.put(f"ik_hand_{s}", V(hx, trunk_y(hx) + 0.030, hand_z), (-90 if tilt < -45 else tilt * 1.6 - 10, x * 9, 0))
        st.put(f"ik_foot_{s}", V(fx, foot_y, foot_z), (foot_pitch, x * 25 if foot_pitch < -45 else 0, 0))
        A.grip(st, s, grip)
        A.toe_grip(st, s, grip * (1.0 if foot_pitch < -45 else 0.2))
        sh = W @ Vector((x * 0.062, SHOULDER.y, SHOULDER.z))
        hp = W @ Vector((x * 0.046, HIP.y, HIP.z))
        st.put(f"pole_elbow_{s}", sh + V(x * 0.10, 0.12, -0.04))
        st.put(f"pole_knee_{s}", hp + V(x * 0.13, 0.05, 0.02))
    A.spine_pose(st, s1=(spine[0], 0, 0), s2=(spine[1], 0, 0), s3=(spine[2], 0, 0))
    A.head_look(st, pitch=head)
    A.tail_pose(st, curl_up=tail)
    return st


@clip("climb_start", 36, loop=False, group="climbing", trunk_side="front (-Y)",
      description="Ground to trunk: the monkey stands facing the bark with its root 0.52 m from the trunk surface (root y = +0.52, nose 5 cm off the bark), "
                  "rears up, grabs the trunk, hops its feet up, and lands in the first frame of climb_up (root y = -0.13, z = 0.26).")
def climb_start(phase):
    def feet_up(st, lift):
        for s in A.SIDES:
            h, r = st.ctrl[f"ik_foot_{s}"]
            st.ctrl[f"ik_foot_{s}"] = (h + V(0, 0, lift), r)
        return st
    k_hop = trunk_pose(0.12, 0.10, -50, 0.33, 0.20, 0.07, grip=0.75, foot_pitch=-10, head=-14, tail=16, spine=(-2, -3, -3))
    keys = [
        (0.00, ground_quad(0.52)),
        (0.14, ground_quad(0.50, 0.0)),
        (0.38, trunk_pose(0.25, 0.06, -34, 0.24, 0.45, 0.034, grip=0.55, foot_pitch=0, head=-14, tail=14, spine=(-3, -4, -4))),
        (0.58, feet_up(k_hop, 0.045)),
        (0.78, trunk_pose(-0.04, 0.17, -66, 0.43, 0.06, 0.12, grip=0.8, foot_pitch=-40, head=-12, tail=16, spine=(-2, -3, -3))),
        (1.00, climb_state(0.0, 1.0)),
    ]
    return keypose_fn(keys)(phase)


@clip("climb_dismount", 33, loop=False, group="climbing", trunk_side="front (-Y)",
      description="Trunk to ground: exact time-reverse of climb_start (ends standing 0.36 m from the trunk, facing it).")
def climb_dismount(phase):
    return climb_start(1.0 - phase)


# ---------------------------------------------------------------------------- branch locomotion
BRANCH = dict(duty=0.70, stride_h=0.15, stride_f=0.15, lift_h=0.020, lift_f=0.022,
              center_h=0.330, center_f=0.074, heel_h=2, toe_h=8, peak_h=6, heel_f=3, toe_f=10, peak_f=8,
              swing_curl=0.45, abd=0.0, bob=0.003, sway=0.004, yaw=1.0, lat=3.0, drop=-0.010, roll=2.0, hand_x=0.026, foot_x=0.026,
              stance_curl_h=0.62, stance_curl_f=0.55,
              offsets=dict(foot_L=0.0, hand_R=0.14, foot_R=0.5, hand_L=0.64),
              head_pitch=-10, head_bob=1.5, tail_up=-4, tail_sway=22, tail_wave=9)


@clip("branch_walk", 30, loop=True, group="locomotion", speed_mps=round(0.15 / (0.70 * 1.0), 3),
      description="Quadrupedal walk along a ~4 cm horizontal branch (feet/hands in a narrow line, gripping, tail used for balance). "
                  "Contact speed 0.21 m/s at 1.0 s per cycle. Root origin sits on the top of the branch.")
def branch_walk(phase):
    st = gait_state(phase, BRANCH)
    return st
