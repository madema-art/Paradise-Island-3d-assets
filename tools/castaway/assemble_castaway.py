"""
Stage 3: assemble the rigged castaway in Blender (bpy): skin mesh (head + body materials), eyes, hair cards, mouth parts,
maro, armature, materials. Saves the editable .blend.

  /opt/bpy-venv/bin/python tools/castaway/assemble_castaway.py --out build/castaway/Castaway_rig.blend
"""
import argparse
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "monkey"))

import bpy  # noqa: E402
from mathutils import Matrix  # noqa: E402
from PIL import Image  # noqa: E402

import hdesign  # noqa: E402
import rig_build  # noqa: E402
from meshutil import mesh_from_arrays  # noqa: E402


def load_image(path, cs):
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = cs
    return img


def occlusion_group():
    if "glTF Material Output" in bpy.data.node_groups:
        return bpy.data.node_groups["glTF Material Output"]
    ng = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
    ng.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    return ng


def prepare_textures(tex_dir, out_dir, head_res=2048, body_res=2048):
    """Runtime textures: JPEG albedo/normal (4:4:4), 1024px PNG ORM; eye/hair/cloth/wood textures copied as PNG."""
    os.makedirs(out_dir, exist_ok=True)
    paths = {}

    def conv(src, dst, kind, size=None, q=92):
        p = os.path.join(tex_dir, src)
        if not os.path.exists(p):
            return None
        im = Image.open(p)
        im = im.convert("RGBA" if kind == "pngA" else "RGB")
        if size and im.size[0] != size:
            im = im.resize((size, size), Image.LANCZOS)
        out = os.path.join(out_dir, dst)
        if kind == "jpg":
            im.save(out, "JPEG", quality=q, subsampling=0, optimize=True)
        else:
            im.save(out, "PNG", optimize=True)
        paths[dst.split(".")[0]] = out
        print(f"[tex] {dst}: {im.size} {os.path.getsize(out) / 1024:.0f} KB")
        return out

    for tag, res in (("head", head_res), ("body", body_res)):
        conv(f"skin_{tag}_albedo.png", f"skin_{tag}_albedo.jpg", "jpg", res, 92)
        conv(f"skin_{tag}_normal.png", f"skin_{tag}_normal.jpg", "jpg", res, 94)
        conv(f"skin_{tag}_orm.png", f"skin_{tag}_orm.png", "png", 1024)
    for name in ("eye_albedo", "hair_atlas", "mouth_albedo", "maro_albedo", "maro_orm", "maro_normal", "wood_albedo", "wood_normal", "wood_orm"):
        p = os.path.join(tex_dir, f"{name}.png")
        if os.path.exists(p):
            out = os.path.join(out_dir, f"{name}.png")
            Image.open(p).save(out, "PNG", optimize=True)
            paths[name] = out
    return paths


def skin_material(name, paths, tag):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    alb = nt.nodes.new("ShaderNodeTexImage")
    alb.image = load_image(paths[f"skin_{tag}_albedo"], "sRGB")
    nt.links.new(alb.outputs["Color"], bsdf.inputs["Base Color"])
    nrm = nt.nodes.new("ShaderNodeTexImage")
    nrm.image = load_image(paths[f"skin_{tag}_normal"], "Non-Color")
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(nrm.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    orm = nt.nodes.new("ShaderNodeTexImage")
    orm.image = load_image(paths[f"skin_{tag}_orm"], "Non-Color")
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(orm.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    grp = nt.nodes.new("ShaderNodeGroup")
    grp.node_tree = occlusion_group()
    nt.links.new(sep.outputs["Red"], grp.inputs["Occlusion"])
    for nme, val in (("Sheen Weight", 0.22), ("Sheen Roughness", 0.55)):
        if nme in bsdf.inputs:
            bsdf.inputs[nme].default_value = val
    if "Sheen Tint" in bsdf.inputs:
        bsdf.inputs["Sheen Tint"].default_value = (0.20, 0.13, 0.10, 1.0)    # glTF exports the tint pre-multiplied by the weight
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.45
    mat.use_backface_culling = True
    return mat


def eye_material(paths):
    mat = bpy.data.materials.new("CastawayEye")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = load_image(paths["eye_albedo"], "sRGB")
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.08
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.9
    return mat


def hair_material(paths):
    mat = bpy.data.materials.new("CastawayHair")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = load_image(paths["hair_atlas"], "sRGB")
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    bsdf.inputs["Roughness"].default_value = 0.55
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.45
    mat.use_backface_culling = False
    try:
        mat.blend_method = "CLIP"
        mat.alpha_threshold = 0.5
    except Exception:
        pass
    return mat


def simple_material(name, color, rough=0.6, tex=None, paths=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    if tex and paths and tex in paths:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = load_image(paths[tex], "sRGB")
        nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    return mat


# --------------------------------------------------------------------------- meshes
def add_weights(ob, W, names):
    for bi, bname in enumerate(names):
        col = W[:, bi]
        idx = np.nonzero(col > 0)[0]
        if len(idx) == 0:
            continue
        vg = ob.vertex_groups.new(name=bname)
        for vi in idx:
            vg.add([int(vi)], float(col[vi]), "REPLACE")


def build_skin(z, mats):
    V, F, N, uv, grp = z["V"], z["F"], z["N"], z["uv"], z["group"]
    W, names = z["W"], [str(n) for n in z["bones"]]
    me = mesh_from_arrays(bpy, "CastawaySkinMesh", V, F)
    layer = me.uv_layers.new(name="UVMap")
    layer.data.foreach_set("uv", uv.reshape(-1).astype(np.float32))
    for p in me.polygons:
        p.use_smooth = True
    try:
        me.normals_split_custom_set_from_vertices(N.astype(np.float32).tolist())
    except Exception as exc:
        print("[warn] custom normals not set:", exc)
    for m in mats:
        me.materials.append(m)
    me.polygons.foreach_set("material_index", grp.astype(np.int32))
    ob = bpy.data.objects.new("Castaway_Body", me)
    bpy.context.scene.collection.objects.link(ob)
    add_weights(ob, W, names)
    return ob


def eye_mesh(center, mat, name):
    """UV sphere with poles on the gaze axis (-Y); equirect UVs."""
    segs, rings = 32, 20
    r = hdesign.EYE_R
    verts, uvs = [], []
    for i in range(rings + 1):
        th = math.pi * i / rings
        for j in range(segs + 1):
            ph = 2 * math.pi * j / segs
            verts.append((r * math.sin(th) * math.cos(ph), -r * math.cos(th), r * math.sin(th) * math.sin(ph)))
            uvs.append((j / segs, 1.0 - i / rings))
    faces = []
    for i in range(rings):
        for j in range(segs):
            a = i * (segs + 1) + j
            faces.append((a, a + segs + 1, a + segs + 2, a + 1))
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


def build_hair(path, mat):
    z = np.load(path)
    bones = [str(b) for b in z["bones"]]
    Vs, Fs, UVs, Ns, Is, Ws = [], [], [], [], [], []
    off = 0
    keep_tags = [t for t in os.environ.get("HAIR_TAGS", "").split(",") if t]          # LODs keep a subset of the card layers
    for i in range(int(z["n"])):
        if keep_tags and str(z[f"tag{i}"]) not in keep_tags:
            continue
        Vs.append(z[f"V{i}"]); Fs.append(z[f"F{i}"] + off); UVs.append(z[f"UV{i}"]); Ns.append(z[f"N{i}"])
        Is.append(z[f"I{i}"]); Ws.append(z[f"W{i}"])
        off += len(z[f"V{i}"])
    V, F, UV, N = np.concatenate(Vs), np.concatenate(Fs), np.concatenate(UVs), np.concatenate(Ns)
    I, W = np.concatenate(Is), np.concatenate(Ws)
    me = mesh_from_arrays(bpy, "CastawayHairMesh", V, F)
    layer = me.uv_layers.new(name="UVMap")
    uv_loop = UV[F.reshape(-1)]
    layer.data.foreach_set("uv", uv_loop.reshape(-1).astype(np.float32))
    for p in me.polygons:
        p.use_smooth = True
    try:
        me.normals_split_custom_set_from_vertices(N.astype(np.float32).tolist())
    except Exception as exc:
        print("[warn] hair normals:", exc)
    me.materials.append(mat)
    ob = bpy.data.objects.new("Castaway_Hair", me)
    bpy.context.scene.collection.objects.link(ob)
    groups = {}
    for bi, bname in enumerate(bones):
        groups[bi] = ob.vertex_groups.new(name=bname)
    for k in range(4):
        for bi in np.unique(I[:, k]):
            sel = np.nonzero((I[:, k] == bi) & (W[:, k] > 0.001))[0]
            for vi in sel:
                groups[int(bi)].add([int(vi)], float(W[vi, k]), "ADD")
    return ob


def add_generic_mesh(name, V, F, uv, mat, rig_bone, N=None):
    me = mesh_from_arrays(bpy, name + "Mesh", V, F)
    if uv is not None:
        layer = me.uv_layers.new(name="UVMap")
        layer.data.foreach_set("uv", uv[F.reshape(-1)].reshape(-1).astype(np.float32) if uv.ndim == 2 else uv.reshape(-1).astype(np.float32))
    for p in me.polygons:
        p.use_smooth = True
    if N is not None:
        try:
            me.normals_split_custom_set_from_vertices(N.astype(np.float32).tolist())
        except Exception:
            pass
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    vg = ob.vertex_groups.new(name=rig_bone)
    vg.add(list(range(len(V))), 1.0, "REPLACE")
    return ob


def bind(objs, rig):
    for ob in objs:
        mod = ob.modifiers.new("Armature", "ARMATURE")
        mod.object = rig
        ob.parent = rig
        ob.matrix_parent_inverse = Matrix.Identity(4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh", default="build/castaway/mesh.npz")
    ap.add_argument("--hair", default="build/castaway/hair.npz")
    ap.add_argument("--extras", default="build/castaway/extras.npz", help="mouth parts / maro (optional)")
    ap.add_argument("--tex", default="build/castaway/tex")
    ap.add_argument("--out", default="build/castaway/Castaway_rig.blend")
    ap.add_argument("--head-res", type=int, default=2048)
    ap.add_argument("--body-res", type=int, default=2048)
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    runtime = os.path.join(os.path.dirname(out), "textures")
    D = hdesign.build()
    z = np.load(a.mesh)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    paths = prepare_textures(a.tex, runtime, a.head_res, a.body_res)
    mats = [skin_material("CastawaySkinHead", paths, "head"), skin_material("CastawaySkinBody", paths, "body")]
    body = build_skin(z, mats)
    ratio = float(os.environ.get("SKIN_RATIO", "1.0"))
    if ratio < 0.999:                                                                  # LOD: collapse-decimate the skin (seams are split verts, so UV borders hold)
        bpy.context.view_layer.objects.active = body
        mod = body.modifiers.new("Decimate", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = ratio
        mod.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=mod.name)
        print(f"[lod] skin decimated to {len(body.data.polygons)} tris")
    objs = [body]
    eye_mat = eye_material(paths)
    for t in ("L", "R"):
        e = eye_mesh(D.lm[f"eye_{t}"], eye_mat, f"Castaway_Eye_{t}")
        vg = e.vertex_groups.new(name=f"eye_{t}")
        vg.add(list(range(len(e.data.vertices))), 1.0, "REPLACE")
        objs.append(e)
    if os.path.exists(a.hair):
        objs.append(build_hair(a.hair, hair_material(paths)))
    if os.path.exists(a.extras):
        import extras_build
        objs += extras_build.build(a.extras, paths, D)
    rig = rig_build.build_armature(D)
    bind(objs, rig)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.render.fps = 30
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.wm.save_as_mainfile(filepath=out, relative_remap=True)
    rig_build.dump_rest(rig, os.path.join(HERE, "rest_pose.json"), D)
    print(f"[done] {out} bones={len(rig.data.bones)} skin_tris={len(body.data.polygons)}")


if __name__ == "__main__":
    main()
