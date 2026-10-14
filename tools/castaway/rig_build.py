"""Armature construction for the castaway (bpy) + rest-pose dump used by the numpy kinematics."""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import hdesign  # noqa: E402

UP = Vector((0, 0, 1))
FORWARD = Vector((0, -1, 0))


def roll_vector(d):
    d = Vector(d).normalized()
    return FORWARD if abs(d.dot(UP)) > 0.9 else UP


def build_armature(D, name="CastawayRig"):
    arm = bpy.data.armatures.new(name + "Armature")
    ob = bpy.data.objects.new(name, arm)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.edit_bones
    made = {}
    for bn, b in D.bones.items():
        e = eb.new(bn)
        e.head = Vector(b["head"])
        e.tail = Vector(b["tail"])
        e.align_roll(roll_vector(e.tail - e.head))
        e.use_deform = bool(b["deform"])
        made[bn] = e
    for bn, b in D.bones.items():
        if b["parent"]:
            made[bn].parent = made[b["parent"]]
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in ob.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return ob


def _plain(v):
    if isinstance(v, (tuple, list)):
        return [_plain(x) for x in v]
    if isinstance(v, np.ndarray):
        return v.tolist()
    return v


def dump_rest(rig, path, D=None):
    data = []
    for b in rig.data.bones:
        data.append(dict(name=b.name, parent=b.parent.name if b.parent else None,
                         head=list(b.head_local), tail=list(b.tail_local),
                         matrix=[list(r) for r in b.matrix_local], deform=bool(b.use_deform)))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lm = {k: _plain(v) for k, v in (D.lm.items() if D else [])}
    json.dump(dict(bones=data, landmarks=lm), open(path, "w"))
    print(f"[rest] {len(data)} bones -> {path}")


if __name__ == "__main__":
    bpy.ops.wm.read_factory_settings(use_empty=True)
    D = hdesign.build()
    rig = build_armature(D)
    out = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.path.join(HERE, "rest_pose.json")
    dump_rest(rig, out, D)
