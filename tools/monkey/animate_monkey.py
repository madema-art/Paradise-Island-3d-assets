"""
Stage 4: bake the clip library into Blender actions.

  /opt/bpy-venv/bin/python tools/monkey/animate_monkey.py --blend build/monkey/Monkey_rig.blend \
        --out build/monkey/Monkey_anim.blend [--only walk,idle] [--groups locomotion]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402

import anim_lib as A  # noqa: E402
from anim_lib import blink_amount  # noqa: E402
import clips_core  # noqa: E402
import clips_locomotion  # noqa: E402,F401

OPTIONAL = ("clips_climb", "clips_behavior", "clips_coconut")
for _m in OPTIONAL:
    try:
        __import__(_m)
    except ModuleNotFoundError as exc:
        if exc.name != _m:
            raise


def with_blinks(name, frames, fn, loop):
    """Add natural blinks to every non-static clip (two per ~3 s), unless the clip already drives the lids."""
    if frames <= 2:
        return fn
    seconds = frames / A.FPS
    n = max(1, int(round(seconds / 1.9)))
    seed = sum(ord(c) for c in name)
    events = [((i + 0.35 + 0.17 * ((seed * (i + 3)) % 5) / 5.0) / n) % 1.0 for i in range(n)]
    width = min(0.45, 0.22 / seconds)

    def wrapped(phase):
        st = fn(phase)
        if "lid_up_L" in st.fk and any(abs(v) > 1e-6 for v in st.fk["lid_up_L"]):
            return st                      # the clip sets its own eyelids (e.g. wide-eyed startle)
        a = blink_amount(phase, events, width)
        if a > 0:
            A.eye_state(st, close=a)
        return st
    return wrapped


def attach_coconut(rig_ob, path):
    from mathutils import Matrix
    if not os.path.exists(path):
        print("[warn] no coconut blend at", path)
        return None
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = ["Coconut"]
    ob = dst.objects[0]
    bpy.context.scene.collection.objects.link(ob)
    bone = rig_ob.data.bones["coconut_attach"]
    ob.parent = rig_ob
    ob.parent_type = "BONE"
    ob.parent_bone = "coconut_attach"
    ob.matrix_parent_inverse = Matrix.Translation((0, -bone.length, 0))
    return ob


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", default="build/monkey/Monkey_rig.blend")
    ap.add_argument("--out", default="build/monkey/Monkey_anim.blend")
    ap.add_argument("--only", default=None)
    ap.add_argument("--groups", default=None)
    ap.add_argument("--report", default=None)
    ap.add_argument("--coconut", default="build/monkey/coconut/Coconut.blend")
    a = ap.parse_args()

    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a.blend))
    rig = A.MonkeyRig(bpy.data.objects["MonkeyRig"])
    clips_core.RIG = rig
    attach_coconut(rig.ob, os.path.abspath(a.coconut))
    wanted = set(a.only.split(",")) if a.only else None
    groups = set(a.groups.split(",")) if a.groups else None
    report = {}
    for name, c in clips_core.CLIPS.items():
        if wanted and name not in wanted:
            continue
        if groups and c["meta"].get("group") not in groups:
            continue
        clips_core.CLAMP_MAX["mm"] = 0.0
        act = rig.bake(name, c["frames"], with_blinks(name, c["frames"], c["fn"], c["loop"]), loop=c["loop"])
        clamp_mm = round(clips_core.CLAMP_MAX["mm"], 1)
        for k, v in c["meta"].items():
            act[k] = v
        report[name] = dict(frames=c["frames"], seconds=round(c["frames"] / A.FPS, 3), loop=c["loop"],
                            reach_error_mm=rig.stats[name], clamp_shift_mm=clamp_mm, uses_coconut=bool(act.get("uses_coconut", False)), **{k: v for k, v in c["meta"].items()})
        worst = max(rig.stats[name].values())
        print(f"[clip] {name:28s} {c['frames']:3d}f loop={c['loop']!s:5s} max IK miss {worst:5.1f} mm  clamp shift {clamp_mm:5.1f} mm")
    rig.reset()
    rig.ob.animation_data_create().action = None
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.out))
    rp = a.report or os.path.splitext(os.path.abspath(a.out))[0] + "_clips.json"
    with open(rp, "w") as f:
        json.dump(report, f, indent=2)
    print(f"[done] {a.out}  clips={len(report)}")


if __name__ == "__main__":
    main()
