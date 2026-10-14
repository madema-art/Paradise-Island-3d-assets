"""
Proof of concept: build a low-poly tropical fish with a painted texture,
save the .blend source and export a .glb.

Runs under the full Blender app or the bpy module:

  blender -b --factory-startup -P tools/blender/build_tropical_fish.py -- --out assets/test/tropical_fish
  /opt/bpy-venv/bin/python tools/blender/build_tropical_fish.py -- --out assets/test/tropical_fish

Conventions: the fish swims along +X (nose at +X), Z is up, Y is the side-to-side axis.
glTF export converts to Y-up.
"""
import argparse
import math
import os
import sys

import bpy  # noqa: E402  (must precede bmesh when running as the bpy module)
import bmesh  # noqa: E402


# --- geometry ---------------------------------------------------------------

def ellipsoid(center, radii, segs=12, rings=8):
    """Low-poly ellipsoid, long axis along X. Returns (verts, faces), closed."""
    cx, cy, cz = center
    rx, ry, rz = radii
    verts = [(cx - rx, cy, cz)]  # tail pole
    for i in range(1, rings):
        t = math.pi * i / rings
        for j in range(segs):
            p = 2.0 * math.pi * j / segs
            verts.append((
                cx - rx * math.cos(t),
                cy + ry * math.sin(t) * math.cos(p),
                cz + rz * math.sin(t) * math.sin(p),
            ))
    verts.append((cx + rx, cy, cz))  # nose pole
    last = len(verts) - 1

    def ring(i, j):
        return 1 + (i - 1) * segs + (j % segs)

    faces = []
    for j in range(segs):
        faces.append((0, ring(1, j), ring(1, j + 1)))
    for i in range(1, rings - 1):
        for j in range(segs):
            faces.append((ring(i, j), ring(i, j + 1), ring(i + 1, j + 1), ring(i + 1, j)))
    for j in range(segs):
        faces.append((last, ring(rings - 1, j + 1), ring(rings - 1, j)))
    return verts, faces


def taper_tail(verts, cx, rx, amount=0.5):
    """Narrow the rear half of the body so it reads as a fish, not an egg."""
    out = []
    for x, y, z in verts:
        if x < cx:
            f = 1.0 - amount * (cx - x) / rx
            y, z = y * f, z * f
        out.append((x, y, z))
    return out


def fish_parts():
    """Return [(verts, faces, material_index)] for every part of the fish."""
    body_v, body_f = ellipsoid((0.0, 0.0, 0.0), (0.5, 0.2, 0.3), segs=12, rings=8)
    body_v = taper_tail(body_v, 0.0, 0.5)

    parts = [(body_v, body_f, 0)]

    # Forked caudal (tail) fin, behind the body
    tail_v = [
        (-0.38, 0.0, 0.07),   # root top
        (-0.86, 0.0, 0.34),   # tip top
        (-0.70, 0.0, 0.00),   # notch
        (-0.86, 0.0, -0.34),  # tip bottom
        (-0.38, 0.0, -0.07),  # root bottom
    ]
    parts.append((tail_v, [(0, 1, 2), (0, 2, 4), (4, 2, 3)], 0))

    # Dorsal fin on the back
    dorsal_v = [(-0.22, 0.0, 0.12), (-0.14, 0.0, 0.40), (0.02, 0.0, 0.36), (0.16, 0.0, 0.10)]
    parts.append((dorsal_v, [(0, 1, 2, 3)], 0))

    # Anal fin on the belly
    anal_v = [(-0.18, 0.0, -0.10), (-0.12, 0.0, -0.28), (0.02, 0.0, -0.25), (0.10, 0.0, -0.10)]
    parts.append((anal_v, [(0, 1, 2, 3)], 0))

    # Pectoral fins, one per side
    for s in (1.0, -1.0):
        pec_v = [
            (0.24, 0.15 * s, 0.02),
            (0.10, 0.38 * s, -0.05),
            (0.04, 0.36 * s, -0.10),
            (0.20, 0.14 * s, -0.08),
        ]
        parts.append((pec_v, [(0, 1, 2, 3)], 0))

    # Eyes: separate material slot so they can be glossy black
    for s in (1.0, -1.0):
        eye_v, eye_f = ellipsoid((0.31, 0.155 * s, 0.07), (0.065, 0.065, 0.065), segs=6, rings=4)
        parts.append((eye_v, eye_f, 1))

    return parts


def add_part(bm, verts, faces, mat_index):
    """Append one part to the combined bmesh. Normals are made consistent per part."""
    tmp = bmesh.new()
    tverts = [tmp.verts.new(v) for v in verts]
    tmp.verts.ensure_lookup_table()
    for f in faces:
        face = tmp.faces.new([tverts[i] for i in f])
        face.material_index = mat_index
    bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces[:])

    vmap = {}
    for v in tmp.verts:
        vmap[v] = bm.verts.new(v.co)
    bm.verts.ensure_lookup_table()
    for f in tmp.faces:
        nf = bm.faces.new([vmap[v] for v in f.verts])
        nf.material_index = f.material_index
    tmp.free()


# --- texture ----------------------------------------------------------------

TEX_SIZE = 512
BASE_ORANGE = (0.98, 0.42, 0.10)
BELLY = (1.00, 0.78, 0.36)
BAND = (0.96, 0.95, 0.90)
OUTLINE = (0.08, 0.05, 0.04)
BLUE = (0.05, 0.30, 0.66)
TAIL = (1.00, 0.80, 0.22)
BAND_X = (0.22, -0.02, -0.26)  # world X of the three white bands
BAND_HALF = 0.045


def smoothstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def paint(x, z, n):
    """Colour at fish-space (x, z). n is a small deterministic brush variation."""
    c = mix(BASE_ORANGE, BELLY, smoothstep(-0.02, -0.16, z))  # lighter belly
    c = mix(c, TAIL, 1.0 - smoothstep(-0.52, -0.46, x))       # tail region
    c = mix(c, BLUE, smoothstep(0.24, 0.30, z))               # blue back cap
    for bx in BAND_X:
        d = abs(x - bx)
        c = mix(c, BAND, 1.0 - smoothstep(BAND_HALF - 0.005, BAND_HALF + 0.005, d))
        outline = (1.0 - smoothstep(BAND_HALF + 0.004, BAND_HALF + 0.012, d)) \
            * smoothstep(BAND_HALF - 0.002, BAND_HALF + 0.002, d)
        c = mix(c, OUTLINE, outline)
    shade = 1.0 + 0.04 * math.sin(37.0 * x + 9.0 * math.sin(23.0 * z)) + n
    return tuple(min(1.0, max(0.0, ch * shade)) for ch in c)


def paint_texture(png_path, bounds):
    x0, x1, z0, z1 = bounds
    img = bpy.data.images.new("FishPaint", width=TEX_SIZE, height=TEX_SIZE, alpha=False)
    flat = []
    for py in range(TEX_SIZE):
        z = z0 + (py + 0.5) / TEX_SIZE * (z1 - z0)
        for px in range(TEX_SIZE):
            x = x0 + (px + 0.5) / TEX_SIZE * (x1 - x0)
            # Deterministic per-pixel grain so the surface does not look flat
            n = (((px * 73856093) ^ (py * 19349663)) % 1024 / 1023.0 - 0.5) * 0.03
            r, g, b = paint(x, z, n)
            flat.extend((r, g, b, 1.0))
    img.pixels.foreach_set(flat)
    img.update()
    os.makedirs(os.path.dirname(png_path), exist_ok=True)
    img.filepath_raw = png_path
    img.file_format = "PNG"
    img.save()
    return img


# --- materials, UVs, export -------------------------------------------------

def make_paint_material(img):
    mat = bpy.data.materials.new("FishPaint")
    mat.use_nodes = True
    mat.use_backface_culling = False  # fins are single-sided planes; export doubleSided
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.45
    bsdf.inputs["Metallic"].default_value = 0.0
    return mat


def make_eye_material():
    mat = bpy.data.materials.new("FishEye")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.015, 0.015, 0.02, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.12
    return mat


def assign_planar_uvs(mesh, bounds):
    """Side-view projection: U along the fish length, V along its height."""
    x0, x1, z0, z1 = bounds
    layer = mesh.uv_layers.new(name="UVMap")
    for loop in mesh.loops:
        co = mesh.vertices[loop.vertex_index].co
        layer.data[loop.index].uv = ((co.x - x0) / (x1 - x0), (co.z - z0) / (z1 - z0))


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default="assets/test/tropical_fish", help="output directory")
    return p.parse_args(argv)


def main():
    args = parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)

    parts = fish_parts()
    all_verts = [v for verts, _, _ in parts for v in verts]
    xs = [v[0] for v in all_verts]
    zs = [v[2] for v in all_verts]
    bounds = (min(xs), max(xs), min(zs), max(zs))

    bm = bmesh.new()
    for verts, faces, mat_index in parts:
        add_part(bm, verts, faces, mat_index)
    mesh = bpy.data.meshes.new("TropicalFishMesh")
    bm.to_mesh(mesh)
    bm.free()

    img = paint_texture(os.path.join(out, "textures", "FishPaint.png"), bounds)
    mesh.materials.append(make_paint_material(img))
    mesh.materials.append(make_eye_material())
    assign_planar_uvs(mesh, bounds)
    mesh.validate()
    mesh.update()

    obj = bpy.data.objects.new("TropicalFish", mesh)
    bpy.context.scene.collection.objects.link(obj)

    # Embed the texture so the .blend is self-contained; the PNG stays alongside it too
    img.pack()

    blend_path = os.path.join(out, "TropicalFish.blend")
    glb_path = os.path.join(out, "TropicalFish.glb")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)

    bpy.ops.export_scene.gltf(
        filepath=glb_path,
        export_format="GLB",
        use_selection=False,
        export_yup=True,
        export_materials="EXPORT",
        export_image_format="AUTO",
        export_normals=True,
        export_texcoords=True,
    )

    print(f"[build] vertices={len(mesh.vertices)} polygons={len(mesh.polygons)} "
          f"materials={len(mesh.materials)} uv_layers={len(mesh.uv_layers)}")
    print(f"[build] blend -> {blend_path}")
    print(f"[build] glb   -> {glb_path}")


if __name__ == "__main__":
    main()
