"""Hand-crafted walking staff / fishing pole / spear prop (Staff.glb).

Local frame (exported GLB): butt at the origin, shaft along +Y (the castaway's `prop_staff` bone axis), length 2.10 m,
"front" (guide rings, line) towards +Z in glTF (= the castaway's facing direction when held upright).
Nodes: Staff (shaft + tip), Staff_wraps (cord grips), Staff_guides (lashed line guides), Staff_line + Staff_hook (optional,
slack fishing line), and attach empties: attach_butt, attach_grip_low/main/upper, attach_tip, attach_guide_1..4, attach_line,
attach_carry (centre for slinging), attach_hand_hint. Their world positions are also written to build/staff/staff_points.json.

  /opt/bpy-venv/bin/python tools/castaway/staff_build.py [--out build/castaway/Staff.glb]
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "monkey"))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

L = 2.10
POINTS = {"attach_butt": 0.0, "attach_grip_low": 0.62, "attach_grip_main": 1.07, "attach_grip_upper": 1.52, "attach_tip": L,
          "attach_carry": 1.05}
GUIDES = [0.82, 1.30, 1.68, 1.97]
WRAPS = [(0.93, 1.21), (1.43, 1.61), (0.52, 0.60)]


def centreline(z):
    """Slightly bent, organic centreline (m) and radius of the branch at height z."""
    cx = 0.0055 * np.sin(z * 2.9 + 0.4) + 0.0025 * np.sin(z * 7.3)
    cy = 0.0045 * np.sin(z * 2.1 + 1.7)
    return cx, cy


def radius(z):
    r = 0.0172 - 0.0058 * (z / L) ** 1.3
    for zk, a, w in ((0.34, 0.0016, 0.03), (0.88, 0.0012, 0.025), (1.46, 0.0014, 0.03), (1.80, 0.001, 0.02)):   # knots / old nodes
        r = r + a * np.exp(-((z - zk) / w) ** 2)
    r = r + 0.0006 * np.sin(z * 31.0) * 0.5
    tip = np.clip((z - 1.90) / (L - 1.90), 0, 1)          # sharpened, fire-hardened spear tip
    r = r * (1 - 0.94 * tip ** 0.85)
    butt = np.clip((0.035 - z) / 0.035, 0, 1)
    r = r * (1 - 0.18 * butt ** 2)                        # rounded-off butt
    return r


def tube(pts, radii, sides=18, closed_start=False, closed_end=False, v_scale=1.0, u_scale=1.0, frames=None):
    """Tube mesh around a polyline. Returns V, F, UV. UV: u around, v along (cumulative length * v_scale)."""
    pts = np.asarray(pts, float)
    n = len(pts)
    T = np.gradient(pts, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    ref = np.array([0.0, 0.0, 1.0]) if abs(T[0, 2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    N = np.cross(T[0], ref)
    N /= np.linalg.norm(N)
    Ns, Bs = [], []
    for i in range(n):                        # parallel transport
        if i:
            v = np.cross(T[i - 1], T[i])
            s = np.linalg.norm(v)
            if s > 1e-9:
                ax = v / s
                ang = np.arcsin(np.clip(s, -1, 1))
                N = N * np.cos(ang) + np.cross(ax, N) * np.sin(ang) + ax * (ax @ N) * (1 - np.cos(ang))
        N = N - T[i] * (N @ T[i])
        N /= np.linalg.norm(N)
        Ns.append(N.copy())
        Bs.append(np.cross(T[i], N))
    Ns, Bs = np.array(Ns), np.array(Bs)
    th = np.linspace(0, 2 * np.pi, sides + 1)
    V, UV = [], []
    seglen = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    for i in range(n):
        ring = pts[i][None] + radii[i] * (np.cos(th)[:, None] * Ns[i][None] + np.sin(th)[:, None] * Bs[i][None])
        V.append(ring)
        UV.append(np.stack([th / (2 * np.pi) * u_scale, np.full(sides + 1, seglen[i] * v_scale)], 1))
    V = np.concatenate(V)
    UV = np.concatenate(UV)
    F = []
    w = sides + 1
    for i in range(n - 1):
        for j in range(sides):
            a, b, c, d = i * w + j, i * w + j + 1, (i + 1) * w + j + 1, (i + 1) * w + j
            F += [(a, b, c), (a, c, d)]
    F = np.array(F)
    return V, F, UV


def merge(parts):
    Vs, Fs, UVs, off = [], [], [], 0
    for V, F, UV in parts:
        Vs.append(V)
        Fs.append(F + off)
        UVs.append(UV)
        off += len(V)
    return np.concatenate(Vs), np.concatenate(Fs), np.concatenate(UVs)


def build_geometry():
    zs = np.linspace(0, L, 170)
    cx, cy = centreline(zs)
    pts = np.stack([cx, cy, zs], 1)
    shaft = tube(pts, radius(zs), sides=20, v_scale=1.0 / L)
    # end caps are closed by the radius going to ~0 at both ends (tip) / a small butt disc
    V, F, UV = shaft
    # butt cap
    w = 21
    c0 = len(V)
    V = np.vstack([V, pts[0][None] - np.array([0, 0, 0.0])])
    UV = np.vstack([UV, [[0.5, 0.0]]])
    F = np.vstack([F, np.array([(c0, j + 1, j) for j in range(20)])])
    wood = (V, F, UV)

    def at(z):
        x, y = centreline(np.array([z]))
        return np.array([x[0], y[0], z])

    # --- cord wraps: helical rope tubes around the shaft
    wr = []
    for z0, z1 in WRAPS:
        turns = (z1 - z0) / 0.0075
        n = int(turns * 9)
        zz = np.linspace(z0, z1, n)
        ph = np.linspace(0, 2 * np.pi * turns, n)
        r = radius(zz) + 0.0030
        cxx, cyy = centreline(zz)
        p = np.stack([cxx + r * np.cos(ph), cyy + r * np.sin(ph), zz], 1)
        wr.append(tube(p, np.full(n, 0.0033), sides=7, v_scale=14.0, u_scale=1.0))
    wraps = merge(wr)
    # --- line guides: lashed loops standing off the front (-Y in Blender = glTF +Z? front = castaway facing -Y)
    gd = []
    for z in GUIDES:
        c = at(z)
        r0 = radius(z)
        front = np.array([0.0, -1.0, 0.0])
        # lashing: a short helical binding under the ring
        n = 90
        zz = np.linspace(z - 0.016, z + 0.016, n)
        ph = np.linspace(0, 2 * np.pi * 4, n)
        r = radius(zz) + 0.0022
        cxx, cyy = centreline(zz)
        gd.append(tube(np.stack([cxx + r * np.cos(ph), cyy + r * np.sin(ph), zz], 1), np.full(n, 0.0021), sides=6, v_scale=18))
        # ring: a small circle of twine (radius 6 mm) in the plane containing the shaft axis and the front direction
        m = 40
        a = np.linspace(-np.pi * 0.62, np.pi * 1.62, m)
        ring = np.array([c + front * (r0 + 0.003 + 0.006 + 0.006 * np.cos(x)) + np.array([0, 0, 1]) * 0.006 * np.sin(x) for x in a])
        gd.append(tube(ring, np.full(m, 0.0016), sides=6, v_scale=30))
    guides = merge(gd)
    # --- optional line + hook: a slack line from the top guide to a hook that hangs ~0.9 m below the tip
    top = at(GUIDES[-1]) + np.array([0, -1, 0]) * (radius(GUIDES[-1]) + 0.009)
    t = np.linspace(0, 1, 60)
    hook = top + np.array([0.0, -0.10, -0.95])
    line_pts = np.array([top * (1 - s) + hook * s + np.array([0, -0.08 * np.sin(np.pi * s) * (1 - s), 0.0]) + np.array([0, 0, -0.12 * np.sin(np.pi * s)]) for s in t])
    line = tube(line_pts, np.full(len(t), 0.0007), sides=5, v_scale=40)
    ha = np.linspace(0.15, 1.45 * np.pi, 24)
    hook_pts = np.array([hook + np.array([0, 0.012 * (1 - np.cos(x)) * 0.0 + 0.0, 0]) + np.array([0, 0.009 * np.sin(x), -0.012 - 0.012 * np.cos(x)]) for x in ha])
    hook_m = tube(hook_pts, np.full(len(ha), 0.0009), sides=5, v_scale=30)
    return wood, wraps, guides, line, hook_m, at


# --------------------------------------------------------------------------------------------------------- textures
def pnoise(h, w, sy, sx, seed):
    rng = np.random.default_rng(seed)
    a = rng.standard_normal((h, w))
    a = gaussian_filter(a, (sy, sx), mode=("nearest", "wrap"))
    return (a - a.mean()) / (a.std() + 1e-9)


def paint_wood(out_dir, W=256, H=2048):
    os.makedirs(out_dir, exist_ok=True)
    v = np.linspace(0, L, H)[:, None] * np.ones((1, W))
    u = np.ones((H, 1)) * np.linspace(0, 1, W, endpoint=False)[None]
    grain = pnoise(H, W, 18, 0.8, 1)
    fine = pnoise(H, W, 3, 0.5, 2)
    blot = pnoise(H, W, 60, 4, 3)
    streak = pnoise(H, W, 220, 0.6, 4)
    base = np.array([0.40, 0.275, 0.165])
    dark = np.array([0.20, 0.13, 0.08])
    light = np.array([0.66, 0.52, 0.36])
    t = np.clip(0.5 + 0.22 * grain + 0.10 * fine + 0.12 * blot, 0, 1)[..., None]
    col = dark * (1 - t) + base * t
    col = col + (light - base) * np.clip(0.35 * streak + 0.1, 0, 1)[..., None] * 0.35
    # hand-polished sections: lighter, smoother
    wear = np.zeros((H, 1))
    for z0, z1 in ((0.92, 1.24), (1.42, 1.62), (0.45, 0.62)):
        wear += np.exp(-(((v[:, :1] - 0.5 * (z0 + z1)) / (0.5 * (z1 - z0))) ** 6))
    wear = np.clip(wear, 0, 1)
    col = col * (1 - 0.35 * wear[..., None]) + np.array([0.52, 0.38, 0.24]) * 0.35 * wear[..., None]
    # knots (dark spots) near the thickened nodes
    for zk in (0.34, 0.88, 1.46, 1.80):
        d2 = ((v - zk) / 0.022) ** 2 + (((u - 0.31 - 0.2 * zk) % 1 - 0.5 + 0.5) / 0.07) ** 2
        col = col * (1 - 0.55 * np.exp(-d2)[..., None])
    # charred, hardened tip and weathered butt
    tipm = np.clip((v - 1.93) / 0.05, 0, 1)[..., None]
    col = col * (1 - tipm) + np.array([0.06, 0.045, 0.04]) * tipm * (0.7 + 0.3 * fine[..., None].clip(-1, 1) * 0.5)
    buttm = np.clip((0.12 - v) / 0.12, 0, 1)[..., None]
    col = col * (1 - 0.5 * buttm) + np.array([0.24, 0.20, 0.15]) * 0.5 * buttm
    col = np.clip(col, 0, 1)
    height = 0.6 * grain + 0.25 * fine + 0.5 * pnoise(H, W, 5, 0.35, 7) * (1 - 0.6 * wear)
    height *= 1 - 0.7 * wear
    gy, gx = np.gradient(gaussian_filter(height, 0.8, mode=("nearest", "wrap")))
    nx, ny = -gx * 5.0, gy * 5.0
    nz = np.ones_like(nx)
    nn = np.sqrt(nx ** 2 + ny ** 2 + nz ** 2)
    nrm = np.stack([nx / nn, ny / nn, nz / nn], -1) * 0.5 + 0.5
    rough = np.clip(0.78 - 0.30 * wear + 0.1 * fine, 0.3, 1.0)
    ao = np.clip(0.9 + 0.07 * grain, 0.6, 1.0)
    orm = np.stack([ao, rough, np.zeros_like(rough)], -1)
    for name, arr, mode in (("staff_wood_albedo", col, "jpg"), ("staff_wood_normal", nrm, "jpg"), ("staff_wood_orm", orm, "png")):
        im = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))
        p = os.path.join(out_dir, f"{name}.{mode}")
        im.save(p, "JPEG", quality=92, subsampling=0) if mode == "jpg" else im.save(p, optimize=True)
    # cord / twine (tiling twisted fibres)
    n = 256
    yy, xx = np.mgrid[0:n, 0:n] / n
    twist = (xx * 6 + yy * 2) % 1.0
    strand = 0.5 + 0.5 * np.sin(2 * np.pi * twist * 3)
    fibre = pnoise(n, n, 0.7, 0.4, 11)
    cb = np.array([0.55, 0.43, 0.27])
    ccol = cb[None, None] * (0.55 + 0.45 * strand[..., None]) * (0.9 + 0.12 * fibre[..., None])
    Image.fromarray((np.clip(ccol, 0, 1) * 255).astype(np.uint8)).save(os.path.join(out_dir, "staff_cord_albedo.jpg"), quality=90)
    h2 = strand * 0.8 + 0.2 * fibre
    gy, gx = np.gradient(h2)
    nn = np.sqrt((gx * 3) ** 2 + (gy * 3) ** 2 + 1)
    Image.fromarray(((np.stack([-gx * 3 / nn, gy * 3 / nn, 1 / nn], -1) * 0.5 + 0.5) * 255).astype(np.uint8)).save(os.path.join(out_dir, "staff_cord_normal.jpg"), quality=92)
    orm2 = np.stack([0.7 + 0.3 * strand, np.full_like(strand, 0.92), np.zeros_like(strand)], -1)
    Image.fromarray((orm2 * 255).astype(np.uint8)).save(os.path.join(out_dir, "staff_cord_orm.png"), optimize=True)


# --------------------------------------------------------------------------------------------------------- bpy assembly
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "build/castaway/Staff.glb"))
    ap.add_argument("--tex", default=os.path.join(ROOT, "build/castaway/staff_tex"))
    a = ap.parse_args()
    import bpy
    from meshutil import mesh_from_arrays

    paint_wood(a.tex)
    wood, wraps, guides, line, hook, at = build_geometry()
    bpy.ops.wm.read_factory_settings(use_empty=True)

    def tex_mat(name, stem, ext_alb="jpg"):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

        def img(suffix, ext, cs):
            im = bpy.data.images.load(os.path.join(a.tex, f"{stem}_{suffix}.{ext}"), check_existing=True)
            im.colorspace_settings.name = cs
            n = nt.nodes.new("ShaderNodeTexImage")
            n.image = im
            return n
        alb = img("albedo", ext_alb, "sRGB")
        nt.links.new(alb.outputs["Color"], bsdf.inputs["Base Color"])
        nrm = img("normal", "jpg", "Non-Color")
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(nrm.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
        orm = img("orm", "png", "Non-Color")
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(orm.outputs["Color"], sep.inputs["Color"])
        nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
        nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
        if "glTF Material Output" not in bpy.data.node_groups:
            ng = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
            ng.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
        grp = nt.nodes.new("ShaderNodeGroup")
        grp.node_tree = bpy.data.node_groups["glTF Material Output"]
        nt.links.new(sep.outputs["Red"], grp.inputs["Occlusion"])
        return mat

    def flat_mat(name, rgb, rough):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        b = mat.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (*rgb, 1)
        b.inputs["Roughness"].default_value = rough
        return mat

    wood_m = tex_mat("StaffWood", "staff_wood")
    cord_m = tex_mat("StaffCord", "staff_cord")
    line_m = flat_mat("StaffLine", (0.82, 0.82, 0.78), 0.4)
    hook_m = flat_mat("StaffHook", (0.55, 0.55, 0.57), 0.35)
    hook_m.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 1.0

    def add(name, geom, mat, parent=None, smooth=True):
        V, F, UV = geom
        # welding of the tube seam is not needed: UV seam needs split vertices already
        me = mesh_from_arrays(bpy, name, V, F)
        uv = me.uv_layers.new(name="UVMap")
        loops = np.array([l.vertex_index for l in me.loops])
        uv.data.foreach_set("uv", UV[loops].ravel())
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        bpy.context.collection.objects.link(ob)
        for p in me.polygons:
            p.use_smooth = smooth
        if parent is not None:
            ob.parent = parent
        return ob

    root = bpy.data.objects.new("Staff_root", None)
    bpy.context.collection.objects.link(root)
    add("Staff", wood, wood_m, root)
    add("Staff_wraps", wraps, cord_m, root)
    add("Staff_guides", guides, cord_m, root)
    add("Staff_line", line, line_m, root)
    add("Staff_hook", hook, hook_m, root)
    pts = {}
    for nm, z in POINTS.items():
        p = at(z)
        e = bpy.data.objects.new(nm, None)
        e.empty_display_size = 0.03
        e.location = tuple(p)
        e.parent = root
        bpy.context.collection.objects.link(e)
        pts[nm] = [float(x) for x in p]
    for i, z in enumerate(GUIDES, 1):
        p = at(z) + np.array([0, -1, 0]) * (radius(z) + 0.012)
        e = bpy.data.objects.new(f"attach_guide_{i}", None)
        e.location = tuple(p)
        e.parent = root
        bpy.context.collection.objects.link(e)
        pts[f"attach_guide_{i}"] = [float(x) for x in p]
    p = at(GUIDES[-1]) + np.array([0, -1, 0]) * (radius(GUIDES[-1]) + 0.012)
    e = bpy.data.objects.new("attach_line", None)
    e.location = tuple(p)
    e.parent = root
    bpy.context.collection.objects.link(e)
    pts["attach_line"] = [float(x) for x in p]
    for o in bpy.data.objects:
        o.select_set(True)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=a.out, export_format="GLB", use_selection=True, export_yup=True, export_apply=False,
                              export_image_format="AUTO", export_extras=True)
    print(f"[staff] {a.out} {os.path.getsize(a.out) / 1e6:.2f} MB")
    tri = sum(len(g[1]) for g in (wood, wraps, guides, line, hook))
    meta = dict(length_m=L, triangles=int(tri), points_blender_zup=pts, grips=dict(main=POINTS["attach_grip_main"], upper=POINTS["attach_grip_upper"],
                low=POINTS["attach_grip_low"]), guide_heights=GUIDES, axis="shaft along +Y in glTF; front (guides) towards +Z in glTF",
                parts=["Staff", "Staff_wraps", "Staff_guides", "Staff_line", "Staff_hook"])
    os.makedirs(os.path.join(ROOT, "build/staff"), exist_ok=True)
    json.dump(meta, open(os.path.join(ROOT, "build/staff/staff_points.json"), "w"), indent=1)
    print(f"[staff] {tri} triangles")


if __name__ == "__main__":
    main()
