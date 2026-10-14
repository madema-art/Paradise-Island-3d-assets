"""
Stage 5: export the animated monkey to GLB (skinned mesh + eyes + all clips as named glTF animations).

  /opt/bpy-venv/bin/python tools/monkey/export_glb.py --blend build/monkey/Monkey_anim.blend --out build/monkey/Monkey.glb
"""
import argparse
import os
import sys

import bpy


def make_nla_tracks(rig):
    ad = rig.animation_data_create()
    ad.action = None
    for tr in list(ad.nla_tracks):
        ad.nla_tracks.remove(tr)
    names = sorted((a.name for a in bpy.data.actions if "frames" in a), key=lambda n: n)
    for name in names:
        act = bpy.data.actions[name]
        track = ad.nla_tracks.new()
        track.name = name
        strip = track.strips.new(name, 1, act)
        strip.name = name
        strip.extrapolation = "NOTHING"
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", default="build/monkey/Monkey_anim.blend")
    ap.add_argument("--out", default="build/monkey/Monkey.glb")
    ap.add_argument("--mode", default="NLA_TRACKS", choices=["NLA_TRACKS", "ACTIONS"])
    ap.add_argument("--no-anim", action="store_true")
    a = ap.parse_args()

    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a.blend))
    rig = bpy.data.objects["MonkeyRig"]
    export_objs = [rig] + [o for o in bpy.data.objects if o.type == "MESH" and o.parent == rig and o.name.startswith("Monkey_")]
    for o in bpy.data.objects:
        o.select_set(False)
    coco = bpy.data.objects.get("Coconut")
    if coco is not None:
        coco.hide_set(True)
    for o in export_objs:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="OBJECT")
    names = make_nla_tracks(rig) if not a.no_anim else []
    bpy.context.scene.frame_set(1)
    kwargs = dict(
        filepath=os.path.abspath(a.out), export_format="GLB", use_selection=True, export_yup=True,
        export_apply=False, export_skins=True, export_def_bones=True, export_influence_nb=4,
        export_animations=not a.no_anim, export_animation_mode=a.mode, export_force_sampling=True,
        export_optimize_animation_size=True, export_anim_single_armature=True, export_frame_step=1,
        export_image_format="AUTO", export_tangents=False, export_morph=False, export_extras=True,
        export_nla_strips=True, export_current_frame=False,
    )
    bpy.ops.export_scene.gltf(**kwargs)
    print(f"[export] {a.out} {os.path.getsize(a.out) / 1e6:.2f} MB  animations={len(names)}")


if __name__ == "__main__":
    main()
