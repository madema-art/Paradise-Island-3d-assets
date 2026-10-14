"""
Animation framework for the monkey rig (bpy).

Conventions (Blender armature space, same as the modelling space):
  * the monkey faces -Y, +X is its left, +Z is up
  * FK rotations are given in degrees about the *rest-frame world axes*, relative to the parent:
      pitch (rx): + = rotate the forward-pointing end DOWN (head down, digit curl, jaw open, tail UP)
      roll  (ry): + = left side down
      yaw   (rz): + = turn towards the monkey's left
  * the whole monkey is posed by one rigid world transform on `root`
  * hands/feet are placed with IK control bones, given as a world head position + a rotation delta
    (degrees, about world axes) applied to the control bone's rest orientation
"""
import math
import os
from collections import defaultdict

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

FPS = 30
SIDES = ("L", "R")
FINGERS = ("index", "middle", "ring", "pinky")


def V(x=0.0, y=0.0, z=0.0):
    return Vector((x, y, z))


def P(x, f, z):
    """Model-space helper: lateral, forward distance, height -> Blender world."""
    return Vector((x, -f, z))


def eul(rx=0.0, ry=0.0, rz=0.0):
    return Euler((math.radians(rx), math.radians(ry), math.radians(rz)), "XYZ").to_matrix()


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def seg(t, a, b):
    """0..1 progress of t inside [a, b]."""
    return max(0.0, min(1.0, (t - a) / (b - a))) if b != a else (1.0 if t >= b else 0.0)


class State:
    """Everything needed to pose one frame."""

    def __init__(self):
        self.root_loc = V()
        self.root_rot = (0.0, 0.0, 0.0)
        self.fk = defaultdict(lambda: [0.0, 0.0, 0.0])  # bone -> [rx, ry, rz]
        self.ctrl = {}                                  # ctrl name -> (head Vector, (rx,ry,rz))
        self.coconut = None                              # (Vector pos, (rx,ry,rz)) in world, or None
        self.pelvis_off = V()                            # world-space translation of the pelvis (and everything above it)

    def rot(self, bone, rx=0.0, ry=0.0, rz=0.0, add=True):
        v = self.fk[bone]
        if add:
            v[0] += rx
            v[1] += ry
            v[2] += rz
        else:
            v[:] = [rx, ry, rz]

    def put(self, name, head, rot=(0.0, 0.0, 0.0)):
        self.ctrl[name] = (Vector(head), tuple(rot))


class MonkeyRig:
    def __init__(self, ob):
        self.ob = ob
        self.pose = ob.pose
        self.bones = ob.data.bones
        self.rest = {b.name: b.matrix_local.copy() for b in self.bones}
        self.rest3 = {n: m.to_3x3() for n, m in self.rest.items()}
        self.ik_bones = {f"{n}_{s}" for s in SIDES for n in ("upper_arm", "forearm", "hand", "thigh", "shin", "foot")}
        self.ctrl_names = [b.name for b in self.bones if b.name.startswith(("ik_", "pole_"))]
        self.fk_names = [b.name for b in self.bones
                         if b.use_deform and b.name not in self.ik_bones and b.name != "root"]
        self.stats = {}
        for pb in self.pose.bones:
            pb.rotation_mode = "QUATERNION"

    # ---------------------------------------------------------------- geometry helpers
    def rest_head(self, name):
        return self.bones[name].head_local.copy()

    def rest_tail(self, name):
        return self.bones[name].tail_local.copy()

    def reset(self):
        for pb in self.pose.bones:
            pb.location = (0, 0, 0)
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.scale = (1, 1, 1)
        bpy.context.view_layer.update()

    # ---------------------------------------------------------------- posing
    def apply(self, st):
        pose = self.pose.bones
        W = Matrix.Translation(st.root_loc) @ eul(*st.root_rot).to_4x4()
        pose["root"].matrix = W @ self.rest["root"]
        bpy.context.view_layer.update()
        # FK bones: rotation about rest-frame world axes, relative to the (already posed) parent
        for name in self.fk_names:
            r = st.fk.get(name) if name in st.fk else None
            pb = pose[name]
            if r is None:
                pb.rotation_quaternion = (1, 0, 0, 0)
                pb.location = (0, 0, 0)
                continue
            R3 = self.rest3[name]
            basis = R3.inverted() @ eul(*r) @ R3
            pb.rotation_quaternion = basis.to_quaternion()
        # pelvis translation (world offset -> bone-local basis location)
        pel = pose["pelvis"]
        pel.location = self.rest3["pelvis"].inverted() @ eul(*st.root_rot).inverted() @ st.pelvis_off
        # control bones: world head position + rotation delta on their rest orientation
        bpy.context.view_layer.update()
        # prop bone (coconut): world pose when held/placed, otherwise parked at its rest position
        cb = pose["coconut_attach"]
        if st.coconut is not None:
            pos, rot = st.coconut
            cb.matrix = Matrix.Translation(pos) @ (eul(*rot) @ self.rest3["coconut_attach"]).to_4x4()
        else:
            cb.matrix = W @ self.rest["coconut_attach"]
        for name in self.ctrl_names:
            pb = pose[name]
            if name in st.ctrl:
                head, rot = st.ctrl[name]
                M = Matrix.Translation(head) @ (eul(*rot) @ self.rest3[name]).to_4x4()
                pb.matrix = M
            else:
                # default: ride along with the root at the rest position
                pb.matrix = W @ self.rest[name]
        bpy.context.view_layer.update()

    def reach_error(self, st):
        """Largest distance between an IK target and the wrist/ankle the chain actually reaches (m)."""
        errs = {}
        pose = self.pose.bones
        for side in SIDES:
            for limb, tip, ctrl in (("arm", f"forearm_{side}", f"ik_hand_{side}"),
                                    ("leg", f"shin_{side}", f"ik_foot_{side}")):
                tip_pos = pose[tip].tail
                tgt = pose[ctrl].head
                errs[f"{limb}_{side}"] = (tip_pos - tgt).length
        return errs

    # ---------------------------------------------------------------- keyframes
    def key_state(self, frame, prev_q):
        pose = self.pose.bones
        names = ["root"] + self.fk_names + self.ctrl_names
        for name in names:
            pb = pose[name]
            q = pb.rotation_quaternion.copy()
            pq = prev_q.get(name)
            if pq is not None and q.dot(pq) < 0:
                q.negate()
                pb.rotation_quaternion = q
            prev_q[name] = q.copy()
            pb.keyframe_insert("rotation_quaternion", frame=frame)
            if name in ("root", "pelvis", "coconut_attach") or name in self.ctrl_names:
                pb.keyframe_insert("location", frame=frame)

    def bake(self, clip_name, nframes, fn, loop=True):
        """Sample fn(phase)->State at nframes+1 keys (frame 1..nframes+1); phase 1.0 == phase 0.0 for loops."""
        self.reset()
        act = bpy.data.actions.new(clip_name)
        act.use_fake_user = True
        ad = self.ob.animation_data_create()
        ad.action = act
        prev_q = {}
        worst = defaultdict(float)
        for i in range(nframes + 1):
            st = fn(i / nframes)
            self.apply(st)
            for k, v in self.reach_error(st).items():
                worst[k] = max(worst[k], v)
                if v > 0.006 and os.environ.get("MONKEY_VERBOSE"):
                    print(f"    [miss] {clip_name} frame {i}/{nframes} phase {i / nframes:.2f} {k}: {v * 1000:.0f} mm")
            self.key_state(1 + i, prev_q)
            if st.coconut is not None:
                pass
        ad.action = None
        act["loop"] = bool(loop)
        act["frames"] = nframes
        self.stats[clip_name] = {k: round(v * 1000, 1) for k, v in worst.items()}
        return act


# --------------------------------------------------------------------------- reusable pose pieces
def grip(st, side, amount, thumb=None, spread=0.0):
    """Curl all fingers of a hand (0 = flat, 1 = tight fist-ish grip)."""
    thumb = amount if thumb is None else thumb
    for f in FINGERS:
        for i, (lo, hi) in enumerate(((10, 70), (10, 90), (5, 70))):
            st.rot(f"f_{f}_{i + 1}_{side}", rx=lerp(lo * 0.3, hi, amount) * (1.0 if amount > 0 else 0))
        yaw = {"index": -1, "middle": 0, "ring": 1, "pinky": 2}[f] * spread * (1 if side == "L" else -1)
        st.rot(f"f_{f}_1_{side}", rz=yaw)
    st.rot(f"f_thumb_0_{side}", rx=lerp(0, 18, thumb), rz=(-1 if side == "L" else 1) * lerp(0, 18, thumb))
    st.rot(f"f_thumb_1_{side}", rx=lerp(0, 38, thumb))
    st.rot(f"f_thumb_2_{side}", rx=lerp(0, 45, thumb))


def toe_grip(st, side, amount):
    for f in ("index", "middle", "ring", "pinky"):
        for i, hi in enumerate((55, 65, 50)):
            st.rot(f"t_{f}_{i + 1}_{side}", rx=hi * amount)
    st.rot(f"t_hallux_0_{side}", rx=18 * amount, rz=(-1 if side == "L" else 1) * 10 * amount)
    st.rot(f"t_hallux_1_{side}", rx=40 * amount)
    st.rot(f"t_hallux_2_{side}", rx=40 * amount)


def tail_pose(st, curl_up=0.0, sway=0.0, wave=0.0, phase=0.0, droop=0.0):
    """Tail shape: curl_up raises it progressively along its length, sway = lateral, wave = travelling S-wave."""
    for i in range(1, 11):
        a = i / 10.0
        st.rot(f"tail_{i}", rx=curl_up * (0.6 + 0.6 * a) - droop * a,
               rz=sway * (0.5 + 0.7 * a) + wave * math.sin(phase - a * 2.4))


def head_look(st, yaw=0.0, pitch=0.0, roll=0.0, neck_share=0.55):
    st.rot("neck1", rx=pitch * neck_share * 0.5, rz=yaw * neck_share * 0.5, ry=roll * 0.4)
    st.rot("neck2", rx=pitch * neck_share * 0.5, rz=yaw * neck_share * 0.5, ry=roll * 0.3)
    st.rot("head", rx=pitch * (1 - neck_share), rz=yaw * (1 - neck_share), ry=roll * 0.3)


def eyes_look(st, yaw=0.0, pitch=0.0):
    for s in SIDES:
        st.rot(f"eye_{s}", rx=pitch, rz=yaw)


def ears(st, flick=0.0, back=0.0):
    for s in SIDES:
        sign = 1 if s == "L" else -1
        st.rot(f"ear_{s}", rx=back * 0.3, rz=sign * (flick + back * 0.6))


def spine_pose(st, pelvis=(0, 0, 0), s1=(0, 0, 0), s2=(0, 0, 0), s3=(0, 0, 0)):
    st.rot("pelvis", *pelvis)
    st.rot("spine1", *s1)
    st.rot("spine2", *s2)
    st.rot("spine3", *s3)


def ankle_from_ball(ball, pitch_deg, ankle_off=Vector((0.0, 0.069, 0.0265))):
    """Ankle position when the foot pivots about its ball (forward end) by pitch (toe-down positive)."""
    return ball + eul(pitch_deg, 0, 0) @ ankle_off


def wrist_from_knuckle(knuckle, pitch_deg, wrist_off=Vector((0.0, 0.045, 0.0255))):
    return knuckle + eul(pitch_deg, 0, 0) @ wrist_off
