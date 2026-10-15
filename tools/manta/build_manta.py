"""
Build the giant manta ray: mesh, materials, rig, skin, ten animation clips. Saves the .blend and exports the .glb.

  /opt/bpy-venv/bin/python tools/manta/build_manta.py -- --out assets/manta
  blender -b --factory-startup -P tools/manta/build_manta.py -- --out assets/manta

Conventions: Z up, +X forward (head), +Y the right wing tip. Metres. Origin at the disc centre on the midline.
glTF export converts to Y-up. Animation is in place: the game owns heading, speed and depth (see manta_behavior.json).
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import clips  # noqa: E402
import design  # noqa: E402
import textures  # noqa: E402

FPS = 30


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="assets/manta")
    return ap.parse_args(argv)


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.render.fps_base = 1.0
    scene.frame_start = 0


def make_material(name, color, roughness, tex_path=None, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if tex_path:
        img = bpy.data.images.load(tex_path, check_existing=True)
        img.pack()
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = img
        mat.node_tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    return mat


def uv_for(x, y):
    return ((x + 2.0) / 4.5, (y + 3.2) / 6.4)


def make_mesh(tex_paths):
    verts, faces, mats = design.merged_mesh()
    me = bpy.data.meshes.new("Manta")
    me.from_pydata([tuple(map(float, v)) for v in verts], [], faces)
    me.update(calc_edges=True)

    materials = {
        "dorsal": make_material("MantaDorsal", None, 0.55, tex_paths["dorsal"]),
        "ventral": make_material("MantaVentral", None, 0.60, tex_paths["ventral"]),
        "mouth": make_material("MantaMouth", (0.05, 0.05, 0.06), 0.80),
        "gill": make_material("MantaGill", (0.10, 0.10, 0.11), 0.70),
        "eye": make_material("MantaEye", (0.01, 0.01, 0.01), 0.18),
        "tail": make_material("MantaTail", (0.12, 0.18, 0.24), 0.55),
    }
    for name in design.MATERIALS:
        me.materials.append(materials[name])
    for poly, m in zip(me.polygons, mats):
        poly.material_index = m
        poly.use_smooth = True

    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()

    uv = me.uv_layers.new(name="UVMap")
    for loop in me.loops:
        co = me.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = uv_for(co.x, co.y)

    obj = bpy.data.objects.new("Manta", me)
    bpy.context.collection.objects.link(obj)
    return obj


def make_armature():
    data = bpy.data.armatures.new("MantaRig")
    arm = bpy.data.objects.new("MantaRig", data)
    bpy.context.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for name, (head, tail, _) in design.BONES.items():
        eb = data.edit_bones.new(name)
        eb.head = head
        eb.tail = tail
        eb.roll = 0.0
    for name, (_, _, parent) in design.BONES.items():
        if parent:
            data.edit_bones[name].parent = data.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
    return arm


def probe_axes(arm):
    """Check the rest-frame sign conventions in clips.py. Raises if the rig does not match them."""
    ctx = bpy.context.view_layer

    def tip(bone, end="tail"):
        ctx.update()
        pb = arm.pose.bones[bone]
        return (pb.tail if end == "tail" else pb.head).copy()

    def rot(bone, euler):
        arm.pose.bones[bone].rotation_euler = euler
        ctx.update()

    checks = [
        ("wing_L1 +flap lifts tip (z up)", "wing_L1", (0.3, 0, 0), "tail", 2, +1),
        ("wing_R1 +flap lifts tip (z up)", "wing_R1", (0.3, 0, 0), "tail", 2, +1),
        ("body +pitch raises nose (z up)", "body", (0.3, 0, 0), "tail", 2, +1),
        ("tail1 +bend raises tip (z up)", "tail1", (0.3, 0, 0), "tail", 2, +1),
        ("head_L +yaw sends lobe out (+Y)", "head_L", (0, 0, 0.3), "tail", 1, +1),
        ("head_R -yaw sends lobe out (-Y)", "head_R", (0, 0, -0.3), "tail", 1, -1),
    ]
    report = {}
    for label, bone, euler, end, axis, sign in checks:
        rot(bone, (0, 0, 0))
        before = tip(bone, end)[axis]
        rot(bone, euler)
        after = tip(bone, end)[axis]
        rot(bone, (0, 0, 0))
        delta = (after - before) * sign
        report[label] = round(delta, 4)
        if delta <= 0:
            raise SystemExit(f"rig convention mismatch: {label} (delta {after - before:+.4f})")
    return report


def skin(mesh_obj, arm, weights):
    joints, w = weights
    groups = {name: mesh_obj.vertex_groups.new(name=name) for name in design.BONE_NAMES}
    for v in range(len(joints)):
        for j in range(joints.shape[1]):
            if w[v, j] > 0.0:
                groups[design.BONE_NAMES[joints[v, j]]].add([v], float(w[v, j]), "REPLACE")
    mod = mesh_obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm  # the armature modifier does the skinning; the mesh stays a root node (glTF skinned-mesh rule)


def keyframe_clips(arm):
    summary = {}
    arm.animation_data_create()
    for name, (duration, loop, fn) in clips.CLIPS.items():
        act = bpy.data.actions.new(name)
        act.use_fake_user = True
        arm.animation_data.action = act
        n = round(duration * FPS)
        for f in range(n + 1):  # the last key equals the first for loops, so the cycle closes exactly
            pose = fn(f / FPS)
            for bone, (rx, ry, rz) in pose.items():
                pb = arm.pose.bones[bone]
                pb.rotation_euler = (rx, ry, rz)
                pb.keyframe_insert("rotation_euler", frame=f, group=bone)
        for pb in arm.pose.bones:
            pb.rotation_euler = (0.0, 0.0, 0.0)
        summary[name] = {"duration_s": duration, "loop": loop, "frames": n + 1, "fps": FPS}
    arm.animation_data.action = None
    return summary


def export(out_dir, mesh_obj, arm):
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    glb = os.path.join(out_dir, "Manta.glb")
    bpy.ops.export_scene.gltf(
        filepath=glb,
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_yup=True,
        export_animations=True,
        export_animation_mode="ACTIONS",
        export_force_sampling=True,
        export_optimize_animation_size=False,
        export_skins=True,
        export_materials="EXPORT",
        export_image_format="AUTO",
    )
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "Manta.blend"), compress=True)
    return glb


def main():
    args = parse_args()
    out = os.path.abspath(args.out)
    tex_dir = os.path.join(out, "textures")
    os.makedirs(tex_dir, exist_ok=True)

    tex_paths = textures.write_all(tex_dir)
    reset_scene()
    mesh_obj = make_mesh(tex_paths)
    arm = make_armature()
    axes = probe_axes(arm)
    weights = design.skin_weights([tuple(v.co) for v in mesh_obj.data.vertices])
    skin(mesh_obj, arm, weights)
    summary = keyframe_clips(arm)
    glb = export(out, mesh_obj, arm)

    meta = {
        "fps": FPS,
        "units": "metres",
        "clips": summary,
        "axis_probe": axes,
        "bones": design.BONE_NAMES,
        "vertices": len(mesh_obj.data.vertices),
        "triangles": sum(len(p.vertices) - 2 for p in mesh_obj.data.polygons),
    }
    with open(os.path.join(out, "manta_clips.json"), "w", encoding="utf8") as f:
        json.dump(meta, f, indent=1)
    print("exported", glb, "verts", meta["vertices"], "tris", meta["triangles"], "clips", len(summary))


if __name__ == "__main__":
    main()
