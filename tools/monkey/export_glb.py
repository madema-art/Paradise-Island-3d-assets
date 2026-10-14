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


def lite_textures(tmp):
    """Swap the body textures for 1024px versions (ORM 512px) for the lite/LOD builds."""
    from PIL import Image
    os.makedirs(tmp, exist_ok=True)
    plan = {"monkey_albedo": (1024, "JPEG", 90), "monkey_normal": (1024, "JPEG", 92), "monkey_orm": (512, "PNG", 0)}
    for img in bpy.data.images:
        base = os.path.splitext(img.name)[0]
        if base not in plan:
            continue
        size, fmt, q = plan[base]
        src = bpy.path.abspath(img.filepath)
        im = Image.open(src).convert("RGB").resize((size, size), Image.LANCZOS)
        out = os.path.join(tmp, f"{base}_lite.{'jpg' if fmt == 'JPEG' else 'png'}")
        im.save(out, fmt, **({"quality": q, "subsampling": 0, "optimize": True} if fmt == "JPEG" else {"optimize": True}))
        img.filepath = out
        img.reload()
        print(f"[lite] {base}: {size}px -> {os.path.getsize(out) / 1024:.0f} KB")


def make_lod1(ratio):
    body = bpy.data.objects["Monkey_Body"]
    before = len(body.data.polygons)
    bpy.context.view_layer.objects.active = body
    mod = body.modifiers.new("LOD", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = ratio
    mod.use_collapse_triangulate = True
    bpy.ops.object.modifier_move_to_index(modifier="LOD", index=0)
    bpy.ops.object.modifier_apply(modifier="LOD")
    print(f"[lod1] body {before} -> {len(body.data.polygons)} tris")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", default="build/monkey/Monkey_anim.blend")
    ap.add_argument("--out", default="build/monkey/Monkey.glb")
    ap.add_argument("--mode", default="NLA_TRACKS", choices=["NLA_TRACKS", "ACTIONS"])
    ap.add_argument("--no-anim", action="store_true")
    ap.add_argument("--lite", action="store_true", help="1024px textures")
    ap.add_argument("--lod1", action="store_true", help="decimated mesh, no animations, no eyelids")
    ap.add_argument("--lod1-ratio", type=float, default=0.27)
    a = ap.parse_args()

    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a.blend))
    rig = bpy.data.objects["MonkeyRig"]
    if a.lite or a.lod1:
        lite_textures(os.path.join(os.path.dirname(os.path.abspath(a.out)), "_lite_tex"))
    if a.lod1:
        make_lod1(a.lod1_ratio)
        a.no_anim = True
    export_objs = [rig] + [o for o in bpy.data.objects if o.type == "MESH" and o.parent == rig and o.name.startswith("Monkey_")
                           and not (a.lod1 and "Lid" in o.name)]
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
