"""Blender side of extras: teeth/gums/tongue + maro objects from extras.npz."""
import os

import bpy
import numpy as np

from meshutil import mesh_from_arrays


def _mat(name, paths, tex, rough, alpha=False, color=(0.5, 0.5, 0.5)):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = rough
    if tex in paths:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(paths[tex], check_existing=True)
        t.image.colorspace_settings.name = "sRGB"
        nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
        if alpha:
            nt.links.new(t.outputs["Alpha"], b.inputs["Alpha"])
            try:
                mat.blend_method = "CLIP"
            except Exception:
                pass
    else:
        b.inputs["Base Color"].default_value = (*color, 1)
    mat.use_backface_culling = not alpha
    return mat


def build(path, paths, D):
    z = np.load(path)
    mouth_mat = _mat("CastawayMouth", paths, "mouth_albedo", 0.35)
    maro_mat = _mat("CastawayMaro", paths, "maro_albedo", 0.92, alpha=True, color=(0.45, 0.34, 0.23))
    objs = []
    for nm in [str(n) for n in z["parts"]]:
        V, F, N, UV = z[f"V_{nm}"], z[f"F_{nm}"].astype(np.int32), z[f"N_{nm}"], z[f"UV_{nm}"]
        me = mesh_from_arrays(bpy, "Castaway_" + nm + "Mesh", V, F)
        layer = me.uv_layers.new(name="UVMap")
        layer.data.foreach_set("uv", UV[F.reshape(-1)].reshape(-1).astype(np.float32))
        for p in me.polygons:
            p.use_smooth = True
        try:
            me.normals_split_custom_set_from_vertices(N.astype(np.float32).tolist())
        except Exception:
            pass
        me.materials.append(mouth_mat if str(z[f"tag_{nm}"]) == "mouth" else maro_mat)
        ob = bpy.data.objects.new("Castaway_" + nm, me)
        bpy.context.scene.collection.objects.link(ob)
        bones = [str(b) for b in z[f"B_{nm}"]]
        I, W = z[f"I_{nm}"], z[f"W_{nm}"]
        groups = [ob.vertex_groups.new(name=b) for b in bones]
        for k in range(4):
            for bi in np.unique(I[:, k]):
                sel = np.nonzero((I[:, k] == bi) & (W[:, k] > 0.001))[0]
                for vi in sel:
                    groups[int(bi)].add([int(vi)], float(W[vi, k]), "ADD")
        objs.append(ob)
    return objs
