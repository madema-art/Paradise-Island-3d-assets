"""
Stage 3: assemble the rigged monkey in Blender (bpy).

Builds: welded body mesh (per-corner UVs, smooth custom normals), skin weights as vertex groups,
the armature (deform skeleton + IK control rig), eyeballs, materials, and saves an editable .blend.

  /opt/bpy-venv/bin/python tools/monkey/assemble_monkey.py --mesh build/monkey/mesh.npz \
        --tex build/monkey/tex --out build/monkey/Monkey_rig.blend
"""
import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from PIL import Image  # noqa: E402

import design  # noqa: E402
from meshutil import mesh_from_arrays  # noqa: E402

UP = Vector((0, 0, 1))
FORWARD = Vector((0, -1, 0))


# --------------------------------------------------------------------------- textures
def prepare_textures(tex_dir, out_dir):
    """Write the web-friendly runtime textures: JPEG albedo/normal (4:4:4), 1024px PNG ORM."""
    os.makedirs(out_dir, exist_ok=True)
    paths = {}
    img = Image.open(os.path.join(tex_dir, "monkey_albedo.png")).convert("RGB")
    paths["albedo"] = os.path.join(out_dir, "monkey_albedo.jpg")
    img.save(paths["albedo"], "JPEG", quality=92, subsampling=0, optimize=True)
    img = Image.open(os.path.join(tex_dir, "monkey_normal.png")).convert("RGB")
    paths["normal"] = os.path.join(out_dir, "monkey_normal.jpg")
    img.save(paths["normal"], "JPEG", quality=95, subsampling=0, optimize=True)
    img = Image.open(os.path.join(tex_dir, "monkey_orm.png")).convert("RGB").resize((1024, 1024), Image.LANCZOS)
    paths["orm"] = os.path.join(out_dir, "monkey_orm.png")
    img.save(paths["orm"], "PNG", optimize=True)
    img = Image.open(os.path.join(tex_dir, "eye_albedo.png")).convert("RGB")
    paths["eye"] = os.path.join(out_dir, "eye_albedo.png")
    img.save(paths["eye"], "PNG", optimize=True)
    for k, p in paths.items():
        print(f"[tex] {k}: {os.path.basename(p)} {os.path.getsize(p) / 1024:.0f} KB")
    return paths


def load_image(path, colorspace):
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = colorspace
    return img


def occlusion_group():
    """glTF Material Output node group: the exporter reads the 'Occlusion' input from it."""
    if "glTF Material Output" in bpy.data.node_groups:
        return bpy.data.node_groups["glTF Material Output"]
    ng = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
    ng.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    return ng


def make_fur_material(paths):
    mat = bpy.data.materials.new("MonkeyFur")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    albedo = nt.nodes.new("ShaderNodeTexImage")
    albedo.image = load_image(paths["albedo"], "sRGB")
    albedo.label = "Albedo"
    nt.links.new(albedo.outputs["Color"], bsdf.inputs["Base Color"])

    normal = nt.nodes.new("ShaderNodeTexImage")
    normal.image = load_image(paths["normal"], "Non-Color")
    normal.label = "Normal"
    nmap = nt.nodes.new("ShaderNodeNormalMap")
    nmap.inputs["Strength"].default_value = 1.0
    nt.links.new(normal.outputs["Color"], nmap.inputs["Color"])
    nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])

    orm = nt.nodes.new("ShaderNodeTexImage")
    orm.image = load_image(paths["orm"], "Non-Color")
    orm.label = "ORM"
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(orm.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    grp = nt.nodes.new("ShaderNodeGroup")
    grp.node_tree = occlusion_group()
    nt.links.new(sep.outputs["Red"], grp.inputs["Occlusion"])

    # soft fur-like rim; exported as KHR_materials_sheen
    for name, val in (("Sheen Weight", 0.35), ("Sheen Roughness", 0.55)):
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = val
    if "Sheen Tint" in bsdf.inputs:
        bsdf.inputs["Sheen Tint"].default_value = (0.78, 0.68, 0.52, 1.0)
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.25
    mat.use_backface_culling = True
    return mat


def make_eye_material(paths):
    mat = bpy.data.materials.new("MonkeyEye")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = load_image(paths["eye"], "sRGB")
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.06
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.9
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = 0.0
    return mat


# --------------------------------------------------------------------------- meshes
def build_body(z, D, mat):
    V, F, N, uv = z["V"], z["F"], z["N"], z["uv"]
    W, names = z["W"], [str(n) for n in z["bones"]]
    me = mesh_from_arrays(bpy, "MonkeyBodyMesh", V, F)
    layer = me.uv_layers.new(name="UVMap")
    layer.data.foreach_set("uv", uv.reshape(-1).astype(np.float32))
    for p in me.polygons:
        p.use_smooth = True
    try:
        me.normals_split_custom_set_from_vertices(N.astype(np.float32).tolist())
    except Exception as exc:  # older/newer API fallback: keep plain smooth shading
        print("[warn] custom normals not set:", exc)
    me.materials.append(mat)
    ob = bpy.data.objects.new("Monkey_Body", me)
    bpy.context.scene.collection.objects.link(ob)
    for bi, bname in enumerate(names):
        col = W[:, bi]
        idx = np.nonzero(col > 0)[0]
        if len(idx) == 0:
            continue
        vg = ob.vertex_groups.new(name=bname)
        for vi in idx:
            vg.add([int(vi)], float(col[vi]), "REPLACE")
    return ob


def eye_mesh(center, mat, name):
    """UV sphere with its poles on the gaze axis (-Y), UVs in polar layout for eye_albedo.png."""
    segs, rings = 32, 20
    r = design.EYE_R
    verts, uvs = [], []
    for i in range(rings + 1):
        th = math.pi * i / rings
        for j in range(segs + 1):
            ph = 2 * math.pi * j / segs
            x = r * math.sin(th) * math.cos(ph)
            z = r * math.sin(th) * math.sin(ph)
            y = -r * math.cos(th)
            verts.append((x, y, z))
            uvs.append((j / segs, 1.0 - i / rings))
    faces, fuv = [], []
    for i in range(rings):
        for j in range(segs):
            a = i * (segs + 1) + j
            b = a + 1
            c = a + segs + 1
            d = c + 1
            faces.append((a, c, d, b))
    me = bpy.data.meshes.new(name + "Mesh")
    me.from_pydata([tuple(np.array(v) + center) for v in verts], [], faces)
    layer = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            layer.data[li].uv = uvs[me.loops[li].vertex_index]
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


# --------------------------------------------------------------------------- armature
def roll_vector(d):
    d = Vector(d).normalized()
    return FORWARD if abs(d.dot(UP)) > 0.9 else UP


def build_armature(D):
    arm = bpy.data.armatures.new("MonkeyArmature")
    ob = bpy.data.objects.new("MonkeyRig", arm)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.edit_bones
    made = {}
    for name, b in D.bones.items():
        e = eb.new(name)
        e.head = Vector(b["head"])
        e.tail = Vector(b["tail"])
        e.align_roll(roll_vector(e.tail - e.head))
        e.use_deform = True
        made[name] = e
    for name, b in D.bones.items():
        if b["parent"]:
            p = made[b["parent"]]
            made[name].parent = p
            if (made[name].head - p.tail).length < 1e-6:
                made[name].use_connect = True

    # ---- IK control rig (non-deforming) ------------------------------------------------
    def ctrl(name, head, tail, like=None, parent="root", size=None):
        e = eb.new(name)
        e.head, e.tail = Vector(head), Vector(tail)
        if like is not None:
            e.roll = made[like].roll
        else:
            e.align_roll(UP)
        e.parent = made[parent]
        e.use_deform = False
        made[name] = e
        return e

    for s, t in design.SIDES:
        for limb, ik_like, pole_dir, pole_name in (
            ("arm", f"hand_{t}", Vector((0, 1, 0)), f"pole_elbow_{t}"),
            ("leg", f"foot_{t}", Vector((0, -1, 0)), f"pole_knee_{t}"),
        ):
            src = D.bones[ik_like]
            ctrl(f"ik_{'hand' if limb == 'arm' else 'foot'}_{t}", src["head"], src["tail"], like=ik_like)
            joint = D.bones[f"forearm_{t}" if limb == "arm" else f"shin_{t}"]["head"]  # elbow / knee
            ph = Vector(joint) + pole_dir * 0.14
            ctrl(pole_name, ph, ph + Vector((0, 0, 0.03)))
    ctrl("ik_head_target", design.P(0, 0.52, 0.34), design.P(0, 0.55, 0.34))  # optional look target
    bpy.ops.object.mode_set(mode="OBJECT")
    return ob


def add_constraints(rig):
    """IK on the arms/legs with hands/feet following the control bones' orientation."""
    pose = rig.pose
    for t in ("L", "R"):
        for tip, tgt, pole, ori in (
            (f"forearm_{t}", f"ik_hand_{t}", f"pole_elbow_{t}", f"hand_{t}"),
            (f"shin_{t}", f"ik_foot_{t}", f"pole_knee_{t}", f"foot_{t}"),
        ):
            pb = pose.bones[tip]
            c = pb.constraints.new("IK")
            c.name = "IK"
            c.target = rig
            c.subtarget = tgt
            c.pole_target = rig
            c.pole_subtarget = pole
            c.chain_count = 2
            c.use_tail = True
            c.use_stretch = False
            c.pole_angle = 0.0
            cr = pose.bones[ori].constraints.new("COPY_ROTATION")
            cr.name = "FollowCtrl"
            cr.target = rig
            cr.subtarget = tgt
            cr.target_space = "WORLD"
            cr.owner_space = "WORLD"
    # bone display + groups
    for pb in pose.bones:
        pb.rotation_mode = "QUATERNION"
    return pose


def tune_pole_angles(rig):
    """Pick the pole angle that keeps each elbow/knee closest to its rest position."""
    pose = rig.pose
    bpy.context.view_layer.update()
    for t in ("L", "R"):
        for tip, joint in ((f"forearm_{t}", f"forearm_{t}"), (f"shin_{t}", f"shin_{t}")):
            c = pose.bones[tip].constraints["IK"]
            rest = rig.data.bones[joint].head_local.copy()
            best, best_err = 0.0, 1e9
            for k in range(-12, 12):
                ang = k * math.pi / 12
                c.pole_angle = ang
                bpy.context.view_layer.update()
                err = (rig.matrix_world @ pose.bones[joint].head - rest).length
                if err < best_err:
                    best, best_err = ang, err
            c.pole_angle = best
            bpy.context.view_layer.update()
            print(f"[ik] {tip}: pole_angle={math.degrees(best):.0f}deg joint error {best_err * 1000:.1f}mm")


def bind(body, eyes, rig):
    for ob in [body] + eyes:
        mod = ob.modifiers.new("Armature", "ARMATURE")
        mod.object = rig
        ob.parent = rig
        ob.matrix_parent_inverse = Matrix.Identity(4)
    for ob, side in zip(eyes, ("L", "R")):
        vg = ob.vertex_groups.new(name=f"eye_{side}")
        vg.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh", default="build/monkey/mesh.npz")
    ap.add_argument("--tex", default="build/monkey/tex")
    ap.add_argument("--out", default="build/monkey/Monkey_rig.blend")
    ap.add_argument("--runtime-tex", default=None, help="where to write runtime JPEG/PNG textures")
    a = ap.parse_args()

    out = os.path.abspath(a.out)
    runtime = os.path.abspath(a.runtime_tex or os.path.join(os.path.dirname(out), "textures"))
    D = design.build()
    z = np.load(a.mesh)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    paths = prepare_textures(a.tex, runtime)
    fur = make_fur_material(paths)
    eye_mat = make_eye_material(paths)

    body = build_body(z, D, fur)
    eyes = [eye_mesh(D.bones[f"eye_{t}"]["head"], eye_mat, f"Monkey_Eye_{t}") for t in ("L", "R")]
    rig = build_armature(D)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="POSE")
    add_constraints(rig)
    bind(body, eyes, rig)
    tune_pole_angles(rig)
    bpy.ops.object.mode_set(mode="OBJECT")

    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.render.fps = 30
    bpy.ops.wm.save_as_mainfile(filepath=out, relative_remap=True)
    print(f"[done] {out}  bones={len(rig.data.bones)} body_tris={len(body.data.polygons)}")


if __name__ == "__main__":
    main()
