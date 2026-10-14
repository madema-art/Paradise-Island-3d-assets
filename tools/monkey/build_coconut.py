"""
Coconut prop: husked coconut with three ridges, fibre albedo + normal map, saved as Coconut.blend / coconut.glb.

  /opt/bpy-venv/bin/python tools/monkey/build_coconut.py --out build/monkey/coconut
"""
import argparse
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402

from meshutil import mesh_from_arrays  # noqa: E402
from paint_textures import Noise3, smoothstep, strands  # noqa: E402

RADIUS = 0.062          # metres (a husked coconut is ~12-13 cm across)
ELONG = 1.10            # long axis (Z) stretch


def surface(theta, phi):
    """Point + normal on the ridged ellipsoid. theta from the +Z pole, phi around Z."""
    ridge = 1.0 + 0.055 * np.cos(3 * phi) ** 2 * np.sin(theta) ** 2 - 0.035 * np.sin(theta) ** 2
    r = RADIUS * ridge
    x = r * np.sin(theta) * np.cos(phi)
    y = r * np.sin(theta) * np.sin(phi)
    z = r * np.cos(theta) * ELONG
    return np.stack([x, y, z], -1)


def build(out, tex=512, segs=64, rings=40):
    os.makedirs(out, exist_ok=True)
    nA, nB = Noise3(11), Noise3(12)

    # ---- mesh (UV sphere, displaced by fibre noise)
    th = np.linspace(0, math.pi, rings + 1)
    ph = np.linspace(0, 2 * math.pi, segs + 1)
    TH, PH = np.meshgrid(th, ph, indexing="ij")
    P0 = surface(TH, PH)
    disp = (nB(P0.reshape(-1, 3), 0.006) - 0.5).reshape(P0.shape[:2]) * 0.0016
    nrm = P0 / np.linalg.norm(P0, axis=-1, keepdims=True)
    P1 = P0 + nrm * disp[..., None]
    verts, uvs, idx = [], [], []
    for i in range(rings + 1):
        for j in range(segs + 1):
            verts.append(P1[i, j])
            uvs.append((j / segs, 1.0 - i / rings))
    faces = []
    for i in range(rings):
        for j in range(segs):
            a = i * (segs + 1) + j
            b = a + 1
            c = a + segs + 1
            d = c + 1
            if i > 0:
                faces.append((a, c, b))
            if i < rings - 1:
                faces.append((b, c, d))
    verts = np.array(verts)
    faces = np.array(faces)
    # outward winding
    n0 = np.cross(verts[faces[:, 1]] - verts[faces[:, 0]], verts[faces[:, 2]] - verts[faces[:, 0]])
    c0 = verts[faces].mean(1)
    if (n0 * c0).sum() < 0:
        faces = faces[:, ::-1]
    uv_corner = np.array(uvs)[faces]                     # (m,3,2)

    # ---- textures: evaluate the surface analytically per texel (UV sphere layout)
    u = (np.arange(tex) + 0.5) / tex
    v = (np.arange(tex // 2) + 0.5) / (tex // 2)
    U, Vv = np.meshgrid(u, v)
    theta = (1 - Vv) * math.pi
    phi = U * 2 * math.pi
    S = surface(theta, phi).reshape(-1, 3)
    N = S / np.linalg.norm(S, axis=1, keepdims=True)
    # fibres run pole to pole: flow = d/dtheta direction
    e = 1e-3
    T = (surface(theta + e, phi) - surface(theta - e, phi)).reshape(-1, 3)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    h = 0.6 * strands(nA, S, T, 0.0016, 6, 0.0022) + 0.4 * strands(nB, S, T, 0.0045, 5, 0.005)
    clump = nB(S + 4.0, 0.016)
    base = np.array([0.33, 0.215, 0.12])
    light = np.array([0.52, 0.38, 0.22])
    dark = np.array([0.14, 0.085, 0.05])
    col = base + (light - base) * np.clip(h * 1.5 - 0.35, 0, 1)[:, None]
    col = col + (dark - col) * np.clip((0.5 - h) * 1.6, 0, 1)[:, None] * 0.7
    col = col * (0.82 + 0.36 * clump[:, None])
    # darker band where the husk meets at the three ridges
    ridge = np.cos(3 * phi).reshape(-1) ** 2
    col = col * (1.0 - 0.18 * ridge[:, None])
    # soft end caps: the "eye" end is darker with a small tuft
    pole = smoothstep(0.88, 1.0, np.abs(np.cos(theta)).reshape(-1))
    col = col + (dark - col) * pole[:, None] * 0.55
    albedo = np.clip(col, 0, 1).reshape(tex // 2, tex, 3)
    # normal map from the strand height
    eps = 0.0004
    bT = T
    bB = np.cross(N, T)
    hp = lambda q: 0.6 * strands(nA, q, T, 0.0016, 6, 0.0022) + 0.4 * strands(nB, q, T, 0.0045, 5, 0.005)
    gT = (hp(S + bT * eps) - h) / eps
    gB = (hp(S + bB * eps) - h) / eps
    nt = np.stack([-gT * 0.0011 * 11, -gB * 0.0011 * 11, np.ones_like(gT)], 1)
    nt /= np.linalg.norm(nt, axis=1, keepdims=True)
    normal = (nt * 0.5 + 0.5).reshape(tex // 2, tex, 3)
    Image.fromarray((albedo[::-1] * 255).astype(np.uint8)).save(os.path.join(out, "coconut_albedo.jpg"), quality=92)
    Image.fromarray((normal[::-1] * 255).astype(np.uint8)).save(os.path.join(out, "coconut_normal.jpg"), quality=95, subsampling=0)

    # ---- Blender object
    bpy.ops.wm.read_factory_settings(use_empty=True)
    me = mesh_from_arrays(bpy, "CoconutMesh", verts, faces)
    layer = me.uv_layers.new(name="UVMap")
    layer.data.foreach_set("uv", uv_corner.reshape(-1).astype(np.float32))
    for p in me.polygons:
        p.use_smooth = True
    mat = bpy.data.materials.new("Coconut")
    mat.use_nodes = True
    nt_ = mat.node_tree
    bsdf = nt_.nodes["Principled BSDF"]
    t1 = nt_.nodes.new("ShaderNodeTexImage")
    t1.image = bpy.data.images.load(os.path.join(out, "coconut_albedo.jpg"))
    nt_.links.new(t1.outputs["Color"], bsdf.inputs["Base Color"])
    t2 = nt_.nodes.new("ShaderNodeTexImage")
    t2.image = bpy.data.images.load(os.path.join(out, "coconut_normal.jpg"))
    t2.image.colorspace_settings.name = "Non-Color"
    nm = nt_.nodes.new("ShaderNodeNormalMap")
    nt_.links.new(t2.outputs["Color"], nm.inputs["Color"])
    nt_.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.92
    me.materials.append(mat)
    ob = bpy.data.objects.new("Coconut", me)
    bpy.context.scene.collection.objects.link(ob)
    for img in bpy.data.images:
        img.pack()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "Coconut.blend"), relative_remap=True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(out, "coconut.glb"), export_format="GLB", use_selection=False,
                              export_yup=True, export_apply=True)
    print(f"[coconut] {len(verts)} verts {len(faces)} tris -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="build/monkey/coconut")
    build(ap.parse_args().out)
