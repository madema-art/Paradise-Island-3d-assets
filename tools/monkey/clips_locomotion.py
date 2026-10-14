"""Ground locomotion + idles: idle, alert_idle, walk, scurry, turn_in_place_L/R, hop."""
import math

from mathutils import Matrix, Vector

import anim_lib as A
from anim_lib import State, V, P, lerp, smooth, seg
from clips_core import *  # noqa: F401,F403
from clips_core import (BALL_Z, FOOT_F, FOOT_X, HAND_F, HAND_X, KNUCKLE_Z, clip, gait_state, keypose_fn, place_foot,
                        place_hand, quad_stance, rest_poles, side_sign, standing_state)

TAU = math.tau


# ---------------------------------------------------------------------------- idles
@clip("idle", 90, loop=True, group="idle", description="Relaxed standing quadruped: breathing, slow look-around, tail sway, ear flicks.")
def idle(phase):
    st = standing_state()
    ph = phase * TAU
    breath = math.sin(2 * ph)
    st.root_loc = V(0.004 * math.sin(ph), 0, 0.0015 * breath)
    st.root_rot = (0.4 * breath, 1.2 * math.sin(ph), 0)
    A.spine_pose(st, s2=(0.6 * breath, 0, 0), s3=(0.9 * breath, 0, 1.5 * math.sin(ph)))
    A.head_look(st, yaw=9 * math.sin(ph) + 4 * math.sin(2 * ph + 1.0), pitch=-5 + 3 * math.sin(2 * ph + 0.3),
                roll=2.0 * math.sin(ph + 1.0))
    A.eyes_look(st, yaw=-5 * math.sin(ph) + 3 * math.sin(3 * ph), pitch=2 * math.sin(2 * ph))
    A.tail_pose(st, curl_up=7 + 2 * math.sin(ph), sway=10 * math.sin(ph + 0.8), wave=4, phase=ph * 1.0)
    flick = max(0.0, math.sin(2 * ph * 1.5 + 2.0)) ** 8
    A.ears(st, flick=6 * flick, back=2 * math.sin(ph))
    return st


@clip("alert_idle", 72, loop=True, group="idle",
      description="Alert stance: chest and head raised, ears forward, quick head snaps left/right, tail lifted.")
def alert_idle(phase):
    st = standing_state()
    ph = phase * TAU
    st.root_loc = V(0.0, 0.0, -0.007 + 0.0015 * math.sin(2 * ph))
    st.root_rot = (-2.5, 0, 0)
    A.spine_pose(st, s1=(-3, 0, 0), s2=(-4, 0, 0), s3=(-4, 0, 0))
    keys = [(0, 0), (0.10, -26), (0.34, -26), (0.42, 22), (0.66, 22), (0.76, -4), (1.0, 0)]
    yaw = 0.0
    for (t0, y0), (t1, y1) in zip(keys[:-1], keys[1:]):
        if t0 <= phase <= t1:
            yaw = lerp(y0, y1, smooth(seg(phase, t0, t1)))
    A.head_look(st, yaw=yaw, pitch=-14 + 3 * math.sin(2 * ph), roll=-0.15 * yaw)
    A.eyes_look(st, yaw=0.25 * yaw)
    A.tail_pose(st, curl_up=18, sway=6 * math.sin(ph), wave=3, phase=ph)
    A.ears(st, flick=2 * math.sin(3 * ph), back=-9)
    return st


# ---------------------------------------------------------------------------- locomotion
WALK = dict(duty=0.64, stride_h=0.19, stride_f=0.19, lift_h=0.022, lift_f=0.026,
            center_h=0.330, center_f=0.072, heel_h=4, toe_h=10, peak_h=8, heel_f=6, toe_f=18, peak_f=14,
            swing_curl=0.30, abd=0.008, bob=0.004, sway=0.006, yaw=1.6, lat=4.0, drop=-0.004,
            offsets=dict(foot_L=0.0, hand_R=0.12, foot_R=0.5, hand_L=0.62),
            head_pitch=-8, head_bob=2.0, tail_up=9, tail_sway=7, tail_wave=5)


@clip("walk", 24, loop=True, group="locomotion", speed_mps=round(0.19 / (0.64 * 24 / 30), 3),
      description="Diagonal-sequence quadrupedal walk. All four contacts move at the same ground speed (0.37 m/s, 0.8 s per cycle), so there is no foot slide when the root moves at that speed: set timeScale = travelSpeed / 0.37.")
def walk(phase):
    return gait_state(phase, WALK)


SCURRY = dict(duty=0.42, stride_h=0.20, stride_f=0.20, lift_h=0.040, lift_f=0.046,
              center_h=0.326, center_f=0.070, heel_h=2, toe_h=16, peak_h=14, heel_f=3, toe_f=26, peak_f=22,
              swing_curl=0.45, abd=0.004, bob=0.014, sway=0.004, yaw=3.0, lat=3.0, drop=0.006, rock=3.5,
              flex=8.0, flex_phase=0.4, offsets=dict(foot_R=0.0, foot_L=0.08, hand_L=0.40, hand_R=0.48),
              head_pitch=-12, head_bob=3.0, tail_up=20, tail_sway=4, tail_wave=7)


@clip("scurry", 12, loop=True, group="locomotion", speed_mps=round(0.20 / (0.42 * 12 / 30), 3),
      description="Fast bounding run with spine flexion, 0.40 s per cycle. Contact points move at 1.19 m/s: set timeScale = travelSpeed / 1.19.")
def scurry(phase):
    return gait_state(phase, SCURRY)


# ---------------------------------------------------------------------------- turn in place
def rz(deg):
    return Matrix.Rotation(math.radians(deg), 3, "Z")


def turn_clip(sign):
    total = 90.0 * sign
    centre = V(0, -0.15, 0)
    # (limb, [(start, end), (start, end)]) staggered diagonal steps
    windows = {
        "foot_L": [(0.04, 0.34), (0.44, 0.74)],
        "hand_R": [(0.10, 0.40), (0.50, 0.80)],
        "foot_R": [(0.20, 0.50), (0.60, 0.90)],
        "hand_L": [(0.26, 0.56), (0.66, 0.96)],
    }

    def psi(t):
        return total * smooth(seg(t, 0.02, 0.98))

    def rest_of(limb, yaw_deg):
        s = limb[-1]
        x = side_sign(s)
        p = P(x * (HAND_X if limb.startswith("hand") else FOOT_X), HAND_F if limb.startswith("hand") else FOOT_F,
              KNUCKLE_Z if limb.startswith("hand") else BALL_Z)
        return centre + rz(yaw_deg) @ (p - centre)

    def fn(phase):
        st = State()
        yaw = psi(phase)
        Rm = rz(yaw)
        st.root_rot = (0, 0, yaw)
        st.root_loc = centre - Rm @ centre
        for limb, wins in windows.items():
            pos = rest_of(limb, 0.0)
            z_lift = 0.0
            pitch = 0.0
            for (t0, t1) in wins:
                land = rest_of(limb, psi(t1))
                if phase >= t1:
                    pos = land
                elif phase > t0:
                    e = smooth(seg(phase, t0, t1))
                    pos = pos.lerp(land, e)
                    z_lift = (0.026 if limb.startswith("foot") else 0.022) * math.sin(math.pi * seg(phase, t0, t1))
                    pitch = 12 * math.sin(math.pi * seg(phase, t0, t1))
                    break
            s = limb[-1]
            pos = pos + V(0, 0, z_lift)
            if limb.startswith("hand"):
                place_hand(st, s, pos, pitch, yaw=yaw)
                A.grip(st, s, 0.3 if z_lift > 0 else 0.0)
            else:
                place_foot(st, s, pos, pitch, yaw=yaw)
        # poles ride the body
        for s in A.SIDES:
            x = side_sign(s)
            st.put(f"pole_elbow_{s}", centre + Rm @ (P(x * 0.080, 0.205, 0.130) - centre))
            st.put(f"pole_knee_{s}", centre + Rm @ (P(x * 0.085, 0.230, 0.120) - centre))
        A.spine_pose(st, s1=(0, 0, 0.22 * yaw * 0.0), s2=(0, 0, 0), s3=(0, 0, 0))
        lead = 0.35 * math.sin(math.pi * seg(phase, 0.0, 0.75))
        A.head_look(st, yaw=(total * 0.28) * lead * (1 if sign > 0 else 1), pitch=-6)
        A.tail_pose(st, curl_up=8, sway=-sign * 14 * math.sin(math.pi * phase), wave=3, phase=phase * TAU)
        return st
    return fn


for _sign, _nm in ((1, "L"), (-1, "R")):
    CLIPS[f"turn_in_place_{_nm}"] = dict(
        frames=24, loop=False, fn=turn_clip(_sign),
        meta=dict(group="locomotion", yaw_deg=90 * _sign,
                  description=f"90 degree pivot to the {'left' if _sign > 0 else 'right'} with staggered diagonal steps. "
                              f"Root yaw ({90 * _sign:+d} deg) is baked into the root bone: apply it to the character heading when the clip ends."))


# ---------------------------------------------------------------------------- hop
def hop_pose(y, z, hand_f, hand_z, foot_f, foot_z, pitch=0.0, spine=(0, 0, 0), tail=8.0, head=-6.0, hand_pitch=0.0,
             foot_pitch=0.0, curl=0.0):
    """Pose with the whole body moved by root offset y (forward distance) and z (height)."""
    st = State()
    st.root_loc = V(0, -y, z)
    st.root_rot = (pitch, 0, 0)
    for s in A.SIDES:
        x = side_sign(s)
        place_hand(st, s, P(x * HAND_X, hand_f, hand_z), hand_pitch)
        place_foot(st, s, P(x * FOOT_X, foot_f, foot_z), foot_pitch)
        A.grip(st, s, curl)
        A.toe_grip(st, s, curl * 0.6)
        st.put(f"pole_elbow_{s}", P(x * 0.080, 0.205 + y, 0.130 + z))
        st.put(f"pole_knee_{s}", P(x * 0.085, 0.230 + y, 0.120 + z))
    A.spine_pose(st, pelvis=(spine[0] * 0.5, 0, 0), s1=(spine[0], 0, 0), s2=(spine[1], 0, 0), s3=(spine[2], 0, 0))
    A.head_look(st, pitch=head)
    A.tail_pose(st, curl_up=tail)
    return st


@clip("hop", 24, loop=False, group="locomotion", travel_m=0.20,
      description="Short bounding hop: crouch, launch, flight, hands-first landing. Root travel of 0.20 m forward is baked into the clip.")
def hop(phase):
    H, Fo, KZ, BZ = HAND_F, FOOT_F, KNUCKLE_Z, BALL_Z
    # hop_pose(y_travel, z_height, hand world f, hand z, foot world f, foot z, ...)  (f values are world coordinates)
    keys = [
        (0.00, hop_pose(0.00, 0.000, H, KZ, Fo, BZ)),
        (0.22, hop_pose(0.00, -0.030, H - 0.01, KZ, Fo - 0.01, BZ, pitch=3, spine=(9, 8, 6), head=-14, tail=0)),
        (0.38, hop_pose(0.05, 0.045, H + 0.060, 0.115, Fo + 0.00, 0.040, pitch=-8, spine=(-5, -6, -6), head=-20,
                        hand_pitch=-20, foot_pitch=25, tail=12, curl=0.3)),
        (0.54, hop_pose(0.13, 0.085, H + 0.170, 0.175, Fo + 0.13, 0.050, pitch=-6, spine=(-6, -4, -3), head=-12,
                        hand_pitch=-35, foot_pitch=30, tail=22, curl=0.35)),
        (0.70, hop_pose(0.19, 0.020, H + 0.225, KZ, Fo + 0.17, 0.040, pitch=4, spine=(4, 3, 2), head=-8,
                        hand_pitch=-6, foot_pitch=20, tail=12)),
        (0.84, hop_pose(0.20, -0.012, H + 0.235, KZ, Fo + 0.215, BZ, pitch=3, spine=(6, 5, 4), head=-10, tail=6)),
        (1.00, hop_pose(0.20, 0.000, H + 0.200, KZ, Fo + 0.200, BZ)),
    ]
    return keypose_fn(keys)(phase)
