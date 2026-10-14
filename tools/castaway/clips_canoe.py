"""Group D: outrigger canoe: boarding, sitting, paddling, drifting, fishing from the canoe, landing, exiting and hauling it up the beach.
Canoe frame (proxy): hull along Y, bow towards -Y; floor z=0.12, gunwale z=0.40 at x=+-0.38, thwart seat z=0.30.
Anchored clips (board / exit) bake root translation relative to the shore anchor: (0,0,0) at the start/end on land."""
import numpy as np

import params as PR
import rigkit as RK
import staffkit as SK
from clipkit import clip, keys, smooth, seg, pulse
from kin import Rz
from posekit import *      # noqa: F401,F403
import posekit as K
from clips_posture import pose_crouch

HANG = RK.ARM_HANG
SEAT_Z = 0.30


def b(m=0.1, **kw):
    p = K.P(RK.stand(mood=m), armL=HANG.copy(), armR=HANG.copy(), wL=0.0, wR=0.0)
    return K.P(p, **kw) if kw else p


FLOOR = 0.12


def seated(h=SEAT_Z, lean=10.0, m=0.1, f=0.40, spread=0.13, hd=-6.0, yaw=0.0):
    """Seated on the thwart (world height h) with the feet on the hull floor ahead. Everything is in the canoe/root frame: the root is lifted
    by the floor height, so local seat height = h - FLOOR and the feet sit at the normal ankle height."""
    hl = h - FLOOR
    p = K.P(RK.stand(mood=m), pel=[0, 0.12, -(RK.HIP_Z - (hl + 0.075)), 4, 0, yaw], sp=[lean, 0, 0], hd=[hd, 0, 0],
            ftL=FT("L", spread, f, AZ, 0, 0, 10), ftR=FT("R", -spread, f, AZ, 0, 0, -10), armL=HANG.copy(), armR=HANG.copy(), wL=0.0, wR=0.0)
    p["armL_ik"] = K.ik(v3(0.17, 0.30, hl + 0.20), (0, -1, 0), (-1, 0, 0))
    p["armR_ik"] = K.ik(v3(-0.17, 0.30, hl + 0.20), (0, -1, 0), (1, 0, 0))
    p["root"] = np.array([0.0, 0.0, FLOOR, 0.0])
    return p


def paddle_state(tip_x, tip_f, tip_z, pitch, roll=0.0, yaw=0.0, aR=0.55, aL=1.20, wR=1.0, wL=1.0):
    """Paddle state: blade tip (butt) position, shaft tilt, lower (right) and upper (left, T-grip) hand distances from the tip."""
    return SK.SS(tip_x, tip_f, tip_z, pitch, roll, yaw, along=aR, wR=wR, wL=wL, alongL=aL)


def paddle_pose(p, s, rmode="side", lmode="back"):
    return SK.apply_state(p, s, right_mode=rmode, left_mode=lmode, grip="grip_staff", prop="aux")


def O_(**kw):
    return SK.opts_blend() | kw


def anchored(p, root, ftL_w, ftR_w, yaw=None):
    """Convert world foot targets to the root-local frame and set the root key (x, y, z, yaw)."""
    root = np.asarray(root, float)
    p = PR.copy(p)
    p["root"] = root
    p["pel_auto"] = np.array([1.0, 0.03, 0.0])          # let the pelvis drop when a foot is placed too far below the hips
    for sd, w in (("L", ftL_w), ("R", ftR_w)):
        w = np.asarray(w, float)
        loc = Rz(-root[3]) @ (w[:3] - root[:3])
        p[f"ft{sd}"] = np.array([loc[0], loc[1], loc[2], w[3], w[4], w[5] - root[3]])
    return p


def to_local(root, pt):
    root = np.asarray(root, float)
    return Rz(-root[3]) @ (np.asarray(pt, float) - root[:3])


# ---------------------------------------------------------------------------------------------------- boarding / exiting
def _board(t):
    """From the beach beside the hull: grab the gunwale, swing the left leg over the rail, step into the hull and settle facing the bow.
    World frame = shore anchor; the hull centreline is x=0, the rail at x=+-0.38 (z=0.40), the floor z=0.12."""
    root = SK.kv(t, [(0.0, [0.80, 0.0, 0.0, -90]), (0.8, [0.72, 0.0, 0.0, -90]), (1.4, [0.50, 0.0, 0.08, -90]), (2.0, [0.22, 0.0, 0.12, -75]),
                     (2.6, [0.0, 0.0, 0.12, -25]), (3.2, [0.0, 0.0, 0.12, 0])])
    fl = SK.kv(t, [(0.0, [0.80, -0.10, AZ, 0, 0, -90]), (0.8, [0.80, -0.10, AZ, 0, 0, -90]), (1.3, [0.52, -0.10, AZ + 0.50, -10, 0, -90]),
                   (1.7, [0.20, -0.10, AZ + 0.34, -10, 0, -90]), (2.1, [0.10, -0.10, 0.12 + AZ, 0, 0, -60]), (3.2, [0.10, -0.06, 0.12 + AZ, 0, 0, 0])])
    fr = SK.kv(t, [(0.0, [0.80, 0.10, AZ, 0, 0, -90]), (1.7, [0.80, 0.10, AZ, 0, 0, -90]), (2.2, [0.34, 0.10, AZ + 0.50, -10, 0, -90]),
                   (2.7, [-0.10, 0.10, 0.12 + AZ, 0, 0, -30]), (3.2, [-0.10, 0.06, 0.12 + AZ, 0, 0, 0])])
    rt = np.array(root)
    p = b(0.0)
    lean = env(t, 0.3, 1.0, 1.6, 2.4)
    p = add(p, sp=[20 * lean, 0, 0], hd=[-12 * lean, 0, 0], pel=[0, 0, -0.10 * lean, 8 * lean, 0, 0])
    p = anchored(p, rt, fl, fr)
    grip_r = to_local(rt, [0.38, 0.22, 0.43])           # both hands on the near rail while he faces the hull
    grip_l = to_local(rt, [0.38, -0.22, 0.43])
    p["armR_ik"] = K.ik(grip_r, (0, -1, 0), (0, 0, 1), 10)
    p["armL_ik"] = K.ik(grip_l, (0, -1, 0), (0, 0, 1), -10)
    p["armR_w"] = np.array([smooth(seg(t, 0.4, 0.9)) * (1 - smooth(seg(t, 1.2, 1.6)))])
    p["armL_w"] = np.array([smooth(seg(t, 0.6, 1.0)) * (1 - smooth(seg(t, 1.3, 1.7)))])
    p["armR"] = HANG + np.array([20, 10, 0, 30, 0, 0])
    p["armL"] = HANG + np.array([20, 10, 0, 30, 0, 0])
    p["fR"] = RK.G("grip_big", 0.8)
    p["fL"] = RK.G("grip_big", 0.8)
    p["look"] = np.array([0.0, -0.6, 0.4, 0.8])
    return p, O_(stance=(True, True))


mk("canoe_board", "canoe", 3.2, root="anchored", desc="Steps from the beach into the canoe: grips the gunwale, swings a leg over the rail, steps in and turns to face the bow. Root is baked relative to the shore anchor (beside the hull).",
   props=["canoe"], interrupt="none", blend_in=0.2, blend_out=0.3, start_pose="stand_beside_canoe", end_pose="canoe_stand", anchor="shore", events=[(1.3, "foot_over_gunwale"), (2.1, "foot_in_hull")])(_board)


def _sit_settle(t):
    st = b(0.1)
    st["armL_ik"] = RK.hang_ik("L")
    st["armR_ik"] = RK.hang_ik("R")
    mid = K.P(st, pel=[0, 0.05, -0.30, 8, 0, 0], sp=[18, 0, 0], hd=[-8, 0, 0], ftL=FT("L", 0.13, 0.20, 0.12 + AZ, 0, 0, 8), ftR=FT("R", -0.13, 0.20, 0.12 + AZ, 0, 0, -8))
    mid["armL"] = HANG + np.array([20, 10, 0, 40, 0, 0])
    mid["armR"] = mid["armL"].copy()
    seat = seated()
    seat["armL_w"] = np.array([1.0])
    seat["armR_w"] = np.array([1.0])
    st["pel"] = np.array([0, 0, 0, 0, 0, 0.0])
    st["ftL"] = FT("L", 0.10, 0.0, 0.12 + AZ, 0, 0, 0)
    st["ftR"] = FT("R", -0.10, 0.0, 0.12 + AZ, 0, 0, 0)
    mid["pel"] = np.array(mid["pel"]) + np.array([0, 0, 0.0, 0, 0, 0])
    p = seq(t, [(0.0, st), (0.7, mid), (1.5, seat), (2.2, seat)])
    p["root"] = np.array([0.0, 0.0, FLOOR * smooth(seg(t, 0.0, 0.7)), 0.0])
    return p, O_()


mk("canoe_sit_down", "canoe", 2.2, root="anchored", desc="Lowers himself onto the thwart seat and settles, hands coming to rest on the thighs (hull floor 0.12 m, seat 0.30 m).", props=["canoe"],
   interrupt="none", blend_in=0.2, blend_out=0.3, start_pose="canoe_stand", end_pose="canoe_seated", anchor="canoe", events=[(1.2, "pelvis_on_seat")])(_sit_settle)


def _canoe_sit_idle(t):
    T = 9.0
    ph = t / T
    p = seated(SEAT_Z, 12.0, 0.15)
    p["armL_w"] = np.array([1.0])
    p["armR_w"] = np.array([0.0])
    # the right hand trails in the water over the side, the left rests on the thigh
    trail = 0.5 + 0.5 * sw(t, 5.0)
    p["armR"] = HANG + np.array([20, 30, 0, 20, 0, 0])
    p["armR_ik"] = K.ik(v3(-0.40, 0.10, 0.02), (0, -1, -0.2), (0.4, 0, 1), 10)
    p["armR_w"] = np.array([0.5 + 0.5 * sw(t, T) * 0 + 0.0])
    p = add(p, sp=[1.5 * sw(t, 4.2) + 4 * sw(t, T), 3 * sw(t, T, 0.25), 3 * sw(t, T)], hd=[2 * sw(t, T, 0.3), 3 * sw(t, T), 36 * sw(t, T, 0.1) * np.cos(TAU * ph * 2)],
            pel=[0, 0, 0, 0, 1.2 * sw(t, 3.4), 0])
    p["eye"] = np.array([8 * sw(t, T / 2), 2 * sw(t, T / 3)])
    p = RK.breathing(p, t, 4.2, 1.0)
    return p, O_()


mk("canoe_sit_idle", "canoe", 9.0, loop=True, desc="Seated in the canoe on the thwart, letting the right hand trail in the water, gazing around the lagoon, swaying gently with the hull.",
   props=["canoe"], interrupt="any", blend_in=0.4, blend_out=0.4, start_pose="canoe_seated", end_pose="canoe_seated", anchor="canoe")(_canoe_sit_idle)


def stroke_curve(ph):
    """Paddle stroke: 0..1 phase -> (tip forward f, tip height z, effort). Catch ahead, power phase back, recovery lifted."""
    if ph < 0.55:                                    # power phase: blade in the water drawn back
        u = ph / 0.55
        return 0.62 - 0.92 * u, -0.10 + 0.02 * np.sin(np.pi * u), 1.0
    u = (ph - 0.55) / 0.45                           # recovery: blade out of the water swung forward
    return -0.30 + 0.92 * smooth(u), -0.10 + 0.34 * np.sin(np.pi * u), 0.0


def _paddle(t, T=2.4, side=+1, strong=1.0):
    ph = (t / T) % 1.0
    f, z, eff = stroke_curve(ph)
    sx = -0.62 * side                                # blade distance out from the centreline (side=+1: right side of the canoe)
    s = paddle_state(sx, f, z, 0.0, 0.0, 0.0)
    # shaft leans outward at the blade: build the axis from the blade tip and the top hand: top hand over the centreline, level with the chin
    top = np.array([-0.05 * side, -(f * 0.45 + 0.30), 0.84 + 0.06 * eff])
    tip = np.array([sx, -f, z])
    d = top - tip
    ln = np.linalg.norm(d)
    ax = d / ln
    pitch, roll = SK.tilt_from(ax)
    low, top_a = 0.62, min(ln, 1.20)
    if side > 0:      # blade on his right: the right hand is the lower hand, the left hand holds the T-grip end
        s = SK.SS(sx, f, z, pitch, roll, 0.0, along=low, wR=1.0, wL=1.0, alongL=top_a)
    else:             # blade on his left: roles swap
        s = SK.SS(sx, f, z, pitch, roll, 0.0, along=top_a, wR=1.0, wL=1.0, alongL=low)
    p = seated(SEAT_Z, 14.0 + 10 * (0.5 - 0.5 * np.cos(TAU * ph)) * strong, 0.0)
    p = add(p, sp=[-12 * eff * strong, 5 * side * eff, 8 * side * (0.5 - eff)], hd=[2 * eff, 0, -4 * side], pel=[0, 0, 0, 0, 0, 0])
    p["armL_w"] = np.array([1.0])
    p = paddle_pose(p, s, "side" if side > 0 else "back", "back" if side > 0 else "side")
    p["look"] = np.array([0.0, -4.0, 0.2, 0.7])
    p = addf(p, furrow=0.2 * eff, jaw=2 * eff)
    p = RK.breathing(p, t, T / 2, 1.5 * strong)
    return p, O_()


mk("canoe_paddle", "canoe", 2.4, loop=True, desc="Seated paddling on the right side: reach forward, plant the blade, a long draw back with torso rotation, lift and recover.",
   props=["canoe", "paddle"], interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="canoe_seated", end_pose="canoe_seated", anchor="canoe", paddle_side="right", speed=1.0)(lambda t: _paddle(t, 2.4, +1, 1.0))
mk("canoe_paddle_left", "canoe", 2.4, loop=True, desc="Seated paddling on the left side (mirror of `canoe_paddle`).",
   props=["canoe", "paddle"], interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="canoe_seated", end_pose="canoe_seated", anchor="canoe", paddle_side="left")(lambda t: _paddle(t, 2.4, -1, 1.0))
mk("canoe_paddle_hard", "canoe", 1.6, loop=True, desc="Fast, powerful paddling (right side) for returning to shore or racing: short cycle, deeper lean.",
   props=["canoe", "paddle"], interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="canoe_seated", end_pose="canoe_seated", anchor="canoe", paddle_side="right")(lambda t: _paddle(t, 1.6, +1, 1.6))


def _drift(t):
    T = 8.0
    ph = t / T
    p = seated(SEAT_Z, 8.0, 0.15)
    # paddle laid across the lap, both hands resting on it; looking around
    s = SK.SS(-0.55, 0.15, 0.36, 90, 0, 90, along=0.45, wR=1.0, wL=1.0, alongL=0.95)
    s[3] = 90.0
    p = add(p, sp=[2 * sw(t, 4.2), 0, 4 * sw(t, T)], hd=[-2 + 3 * sw(t, T, 0.3), 3 * sw(t, T), 40 * sw(t, T, 0.1) * np.cos(TAU * ph * 2)])
    p = paddle_pose(p, s, "over", "over")
    p = RK.breathing(p, t, 4.2, 1.0)
    return p, O_()


mk("canoe_drift", "canoe", 8.0, loop=True, desc="Drifting: paddle laid across the knees, both hands resting on it, slowly scanning the water and shore.",
   props=["canoe", "paddle"], interrupt="any", blend_in=0.4, blend_out=0.4, start_pose="canoe_seated", end_pose="canoe_seated", anchor="canoe")(_drift)


def _canoe_fish(t):
    T = 10.0
    s = SK.kv(t, [(0.0, SK.SH(-0.20, 0.20, 0.62, 70, -12, 20, 0.72, 1.08)), (4.0, SK.SH(-0.20, 0.22, 0.62, 74, -12, 20, 0.72, 1.08)), (6.0, SK.SH(-0.20, 0.22, 0.62, 72, -12, 22, 0.72, 1.08)),
                  (10.0, SK.SH(-0.20, 0.20, 0.62, 70, -12, 20, 0.72, 1.08))])
    p = seated(SEAT_Z, 8.0, 0.1)
    p = add(p, sp=[0, 1.5 * sw(t, T), 3 * sw(t, T, 0.2)], hd=[6 + 2 * sw(t, T, 0.4), 0, 8 * sw(t, T, 0.1)])
    p["look"] = np.array([-0.6, -2.4, 0.0, 0.9])
    p = SK.apply_state(p, s, "side", "over")
    p = RK.breathing(p, t, 4.2, 1.0)
    return p, O_()


mk("canoe_fish_seated", "canoe", 10.0, loop=True, desc="Fishing from the seated position: pole held in both hands out over the side, patient, tiny tip twitches.",
   props=["canoe", "staff"], interrupt="any", blend_in=0.4, blend_out=0.4, start_pose="canoe_seated", end_pose="canoe_seated", anchor="canoe", staff_use="fishing_pole")(_canoe_fish)


def _canoe_reel(t):
    T = 2.0
    ph = t / T
    pull = 0.5 - 0.5 * np.cos(TAU * ph)
    s = SK.SH(-0.20, 0.20, 0.66, 58 - 8 * pull, -12, 20, 0.72, 1.08, 1.0, 0.0)
    p = seated(SEAT_Z, 12.0, 0.0)
    p = add(p, sp=[-6 * pull, 0, 3 * sw(t, T)], hd=[4, 0, 6 * sw(t, T)], pel=[0, 0.01 * pull, 0, 0, 0, 0])
    p["armL_ik"] = K.ik(v3(0.10, 0.36 - 0.16 * pull, 0.62 - 0.14 * pull), (-0.1, -1, 0.0), (0.2, 0, 1), -10)
    p["armL"] = HANG + np.array([50, 10, 0, 60, 0, 0])
    p = SK.apply_state(p, s, "side", "over")
    p["armL_w"] = np.array([1.0])
    p["fL"] = RK.G("grip_thin", 0.9 * (1 - pull) + 0.4 * pull)
    p["look"] = np.array([-0.6, -2.0, 0.0, 0.9])
    p = addf(p, furrow=0.4, squint=0.3, jaw=3)
    return p, O_()


mk("canoe_reel_in", "canoe", 2.0, loop=True, desc="Reeling in a fish from the canoe: rod tip high and bowed, left hand hauling line, torso rocking with each pull.",
   props=["canoe", "staff"], interrupt="any", blend_in=0.2, blend_out=0.3, start_pose="canoe_seated", end_pose="canoe_seated", anchor="canoe", staff_use="fishing_pole")(_canoe_reel)


def _exit(t):
    """Boarding played backwards (stepping out over the same rail): the anchor and the foot placements are the mirror in time."""
    p, o = _board(3.2 - t)
    return p, o


mk("canoe_exit", "canoe", 3.0, root="anchored", desc="Climbs out of the canoe onto the beach: stands, turns, steps a leg over the gunwale and walks clear. Root baked relative to the shore anchor.",
   props=["canoe"], interrupt="none", blend_in=0.2, blend_out=0.3, start_pose="canoe_stand", end_pose="stand_beside_canoe", anchor="shore")(_exit)


def _pull_canoe(t):
    T = 2.4
    ph = (t / T) % 1.0
    pull = np.maximum(0, np.sin(TAU * ph * 1.0)) ** 0.8
    p = b(0.0)
    p = add(p, sp=[-10 * pull + 6, 0, 0], hd=[-4 * pull + 6, 0, 0], pel=[0, 0.12 * pull, -0.16 - 0.04 * pull, -6 * pull + 8, 0, 0])
    p["ftL"] = FT("L", 0.15, -0.24, AZ, 0, 0, 8)
    p["ftR"] = FT("R", -0.15, 0.22, AZ, 0, 0, -8)
    # rope held in both hands out in front; hands alternate, then both pull
    rope_f = 0.55 - 0.30 * pull
    p["armL_ik"] = K.ik(v3(0.10, rope_f, 1.12), (-0.1, -1, 0.1), (0.3, 0, 1), -10)
    p["armR_ik"] = K.ik(v3(-0.10, rope_f + 0.12, 1.14), (0.1, -1, 0.1), (-0.3, 0, 1), 10)
    p["armL_w"] = np.array([1.0])
    p["armR_w"] = np.array([1.0])
    p["fL"] = RK.G("grip_thin", 1.0)
    p["fR"] = RK.G("grip_thin", 1.0)
    p["look"] = np.array([0.0, -2.0, 0.6, 0.6])
    p = addf(p, furrow=0.5 * pull, jaw=4 * pull, squint=0.3 * pull)
    p = RK.breathing(p, t, T / 2, 1.8)
    return p, O_()


mk("canoe_pull_on_land", "canoe", 2.4, loop=True, desc="Hauling the canoe up the beach by its bow rope: wide braced stance, leaning back and heaving, hand over hand.",
   props=["canoe", "rope"], interrupt="any", blend_in=0.3, blend_out=0.3, start_pose="stand", end_pose="stand")(_pull_canoe)
