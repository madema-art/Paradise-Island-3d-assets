"""
Contact sheets for the baked clips (Workbench, textured, software GL friendly).

  /opt/bpy-venv/bin/python tools/monkey/render_sheets.py --blend build/monkey/Monkey_anim.blend \
        --clips walk,idle --out build/monkey/sheets [--views side,front] [--cols 6]
"""
import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

import render_utils as R  # noqa: E402

VIEWS = {  # name -> (camera offset from focus, lens)
    "side": (Vector((1.15, 0.0, 0.05)), 50),
    "front": (Vector((0.0, -1.2, 0.15)), 50),
    "three_q": (Vector((0.85, -0.85, 0.30)), 50),
    "top": (Vector((0.0, 0.0, 1.8)), 50),
    "side_far": (Vector((2.3, 0.0, 0.05)), 48),
}


def setup(size):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x, sc.render.resolution_y = size
    sh = sc.display.shading
    sh.light, sh.color_type = "STUDIO", "TEXTURE"
    sh.show_cavity = False
    sh.show_shadows = True
    sh.shadow_intensity = 0.35
    sc.view_settings.view_transform = "Standard"
    w = bpy.data.worlds.new("sheetworld")
    w.color = (0.74, 0.80, 0.86)
    sc.world = w
    # ground slab so contact reads
    bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, -0.0005))
    g = bpy.context.active_object
    m = bpy.data.materials.new("g")
    m.diffuse_color = (0.42, 0.50, 0.34, 1)
    g.data.materials.append(m)
    g.name = "SheetGround"
    return sc


def clone_partner(rig, action):
    """Second monkey 0.60 m in front, rotated 180 degrees, playing `action` (for paired clips)."""
    import math as _m
    new = rig.copy()
    new.data = rig.data.copy()
    bpy.context.scene.collection.objects.link(new)
    for pb in new.pose.bones:
        for c in pb.constraints:
            if getattr(c, "target", None) == rig:
                c.target = new
            if getattr(c, "pole_target", None) == rig:
                c.pole_target = new
    for ch in rig.children:
        if ch.type != "MESH" or ch.name == "Coconut":
            continue
        cc = ch.copy()
        cc.parent = new
        bpy.context.scene.collection.objects.link(cc)
        for m in cc.modifiers:
            if m.type == "ARMATURE":
                m.object = new
    off = action.get("partner_root_offset") or [0.0, -1.08, 0.0]
    off = bpy.data.actions[action.get("partner_of", action.name)].get("partner_root_offset", [0.0, -1.08, 0.0])
    new.location = tuple(off)
    new.rotation_euler = (0, 0, _m.pi)
    new.animation_data_create().action = action
    return new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", default="build/monkey/Monkey_anim.blend")
    ap.add_argument("--clips", required=True)
    ap.add_argument("--out", default="build/monkey/sheets")
    ap.add_argument("--views", default="side,front")
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--size", default="420x330")
    ap.add_argument("--focus", default=None, help="x,y,z of the camera focus")
    ap.add_argument("--ground", type=int, default=1)
    ap.add_argument("--trunk", type=int, default=0)
    a = ap.parse_args()
    w, h = [int(v) for v in a.size.split("x")]
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a.blend))
    sc = setup((w, h))
    if not a.ground:
        bpy.data.objects["SheetGround"].hide_render = True
    if a.trunk:
        bpy.ops.mesh.primitive_cylinder_add(radius=0.12, depth=3.0, location=(0, -0.12, 1.3), vertices=48)
        t = bpy.context.active_object
        t.name = "SheetTrunk"
        m = bpy.data.materials.new("trunk")
        m.diffuse_color = (0.30, 0.20, 0.12, 1)
        t.data.materials.append(m)
    rig = bpy.data.objects["MonkeyRig"]
    cam = R.make_camera()
    os.makedirs(a.out, exist_ok=True)
    focus = Vector([float(v) for v in a.focus.split(",")]) if a.focus else Vector((0, -0.12, 0.20))
    for name in a.clips.split(","):
        act = bpy.data.actions.get(name)
        if act is None:
            print("missing clip", name)
            continue
        rig.animation_data_create().action = act
        partner_objs = [o for o in bpy.data.objects if o.get("is_partner")]
        for o in partner_objs:
            o.hide_render = True
        if act.get("partner_clip") and bpy.data.actions.get(act["partner_clip"]):
            if not partner_objs:
                p = clone_partner(rig, bpy.data.actions[act["partner_clip"]])
                p["is_partner"] = True
                for ch in bpy.data.objects:
                    if ch.parent == p:
                        ch["is_partner"] = True
                partner_objs = [o for o in bpy.data.objects if o.get("is_partner")]
            for o in partner_objs:
                o.hide_render = False
        coco = bpy.data.objects.get("Coconut")
        if coco is not None:
            coco.hide_render = "coconut" not in name
        n = int(act.get("frames", 24))
        rows = []
        for view in a.views.split(","):
            off, lens = VIEWS[view]
            cam.data.lens = lens
            row = []
            for i in range(a.cols):
                ph = i / a.cols
                frame = 1 + int(round(ph * n))
                sc.frame_set(frame)
                R.aim(cam, focus + off, focus)
                path = os.path.join(a.out, f"_t.png")
                R.render(path)
                im = Image.open(path).convert("RGB")
                ImageDraw.Draw(im).text((6, 4), f"{name} {view} {ph:.2f}", fill=(255, 255, 255))
                row.append(im)
            rows.append(row)
        sheet = Image.new("RGB", (w * a.cols, h * len(rows)))
        for r, row in enumerate(rows):
            for c, im in enumerate(row):
                sheet.paste(im, (c * w, r * h))
        out = os.path.join(a.out, f"sheet_{name}.png")
        sheet.save(out)
        print("[sheet]", out)
    if os.path.exists(os.path.join(a.out, "_t.png")):
        os.remove(os.path.join(a.out, "_t.png"))


if __name__ == "__main__":
    main()
