"""
Hair, beard, moustache and eyebrow cards for the castaway.

  * make_atlas(): procedural strand atlas (1024x1024 RGBA, 4x2 cells of 256x512). Alpha is a cut-out mask (alphaMode MASK).
  * generate(): guide curves grown from the scalp / face surface (volume push, gravity, SDF collision), meshed as ribbons.
  * weights: roots inherit the skin weights; long cards blend into the hair / beard chain bones with height.

  /opt/bpy-venv/bin/python tools/castaway/hair_cards.py --mesh build/castaway/mesh.npz --out build/castaway/hair.npz
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import hdesign  # noqa: E402
from sdf_sampler import body_sampler  # noqa: E402

P3 = hdesign.P

# ------------------------------------------------------------------------------------------------ strand atlas
PALETTE = dict(
    pale=np.array([222, 196, 132]), bleach=np.array([236, 214, 158]), honey=np.array([196, 150, 78]),
    gold=np.array([212, 168, 90]), dark=np.array([150, 108, 54]), root=np.array([128, 94, 48]), brown=np.array([120, 88, 44]),
)
CELL_W, CELL_H = 256, 512
CELLS = {"scalp_clump": (0, 0), "scalp_wavy": (1, 0), "scalp_thin": (2, 0), "scalp_wide": (3, 0),
         "beard_coarse": (0, 1), "beard_curly": (1, 1), "stache": (2, 1), "brow": (3, 1)}


def _lerp(a, b, t):
    return a + (b - a) * t


def draw_cell(rng, kind, ss=3):
    W, H = CELL_W * ss, CELL_H * ss
    rgb = Image.new("RGB", (W, H), (0, 0, 0))
    alpha = Image.new("L", (W, H), 0)
    dr_c, dr_a = ImageDraw.Draw(rgb), ImageDraw.Draw(alpha)
    spec = dict(
        scalp_clump=dict(n=110, width=2.5, taper=0.80, wave=5, lenr=(0.70, 1.0), light=0.55, root=0.60, spread=0.34),
        scalp_wavy=dict(n=70, width=3.0, taper=0.62, wave=22, lenr=(0.72, 1.0), light=0.50, root=0.55, spread=0.30),
        scalp_thin=dict(n=9, width=3.0, taper=0.50, wave=14, lenr=(0.55, 1.0), light=0.70, root=0.40, spread=0.22),
        scalp_wide=dict(n=140, width=2.3, taper=0.55, wave=7, lenr=(0.55, 1.0), light=0.50, root=0.62, spread=0.42),
        beard_coarse=dict(n=100, width=3.0, taper=0.72, wave=9, lenr=(0.70, 1.0), light=0.45, root=0.68, spread=0.34),
        beard_curly=dict(n=84, width=2.9, taper=0.60, wave=30, lenr=(0.65, 1.0), light=0.45, root=0.66, spread=0.34),
        stache=dict(n=40, width=3.6, taper=0.45, wave=8, lenr=(0.80, 1.0), light=0.60, root=0.50, spread=0.36),
        brow=dict(n=34, width=4.4, taper=0.30, wave=5, lenr=(0.85, 1.0), light=0.30, root=0.55, spread=0.40),
    )[kind]
    cx = W * 0.5
    for _ in range(spec["n"]):
        x0 = cx + rng.normal(0, spec["spread"] * W * 0.5)
        x0 = float(np.clip(x0, W * 0.12, W * 0.88))
        ln = rng.uniform(*spec["lenr"]) * H * 0.985
        phase = rng.uniform(0, 6.28)
        freq = rng.uniform(1.0, 2.2)
        amp = spec["wave"] * ss * rng.uniform(0.4, 1.2)
        tone = np.clip(rng.normal(spec["light"], 0.30), 0, 1)
        base = _lerp(PALETTE["honey"], PALETTE["pale"], tone)
        if rng.random() < 0.16:
            base = _lerp(PALETTE["dark"], PALETTE["honey"], rng.random())
        if rng.random() < 0.07:
            base = PALETTE["bleach"]
        width = spec["width"] * ss * rng.uniform(0.7, 1.3)
        nseg = 26
        prev = None
        for k in range(nseg + 1):
            v = k / nseg
            y = v * ln + 2 * ss
            x = cx + (x0 - cx) * (1.0 - spec["taper"] * v ** 1.3) + amp * np.sin(phase + v * 3.14 * freq) * (0.25 + v)
            pt = (x, y)
            if prev is not None:
                col = _lerp(_lerp(base * 0.82 + PALETTE["root"] * 0.18, base, min(v * 2.2, 1.0)), PALETTE["bleach"], max(v - 0.55, 0) * 0.5 * (0.4 + tone))
                col = col * np.clip(rng.normal(1.0, 0.02), 0.94, 1.06)
                col = tuple(int(c) for c in np.clip(col, 0, 255))
                w = max(int(width * (1.0 - 0.55 * v)), 2)
                dr_c.line([prev, pt], fill=col, width=w)
                dr_a.line([prev, pt], fill=255, width=w)
            prev = pt
    # root darkening and a gentle fuzz at the very top so cards blend into the scalp shell
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.9 * ss))
    rgb = rgb.resize((CELL_W, CELL_H), Image.LANCZOS)
    alpha = alpha.resize((CELL_W, CELL_H), Image.LANCZOS)
    return rgb, alpha


def make_atlas(path, seed=3):
    rng = np.random.default_rng(seed)
    atlas = Image.new("RGBA", (CELL_W * 4, CELL_H * 2), (0, 0, 0, 0))
    for kind, (c, r) in CELLS.items():
        rgb, a = draw_cell(rng, kind)
        # bleed colour into transparent texels so mip-mapping does not darken the edges
        arr = np.array(rgb).astype(np.float32)
        m = np.array(a) > 8
        from scipy import ndimage
        _, (iy, ix) = ndimage.distance_transform_edt(~m, return_indices=True)
        arr = arr[iy, ix]
        tile = Image.fromarray(arr.astype(np.uint8)).convert("RGBA")
        tile.putalpha(a)
        atlas.paste(tile, (c * CELL_W, r * CELL_H))
    atlas.save(path)
    print(f"[hair] atlas {atlas.size} -> {path}")
    return atlas


# ------------------------------------------------------------------------------------------------ scalp cap (opaque under-layer)
def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def region_scalp(P):
    x, f, z = P[:, 0], -P[:, 1], P[:, 2]
    ax = np.abs(x)
    hair_z = 1.936 - 0.030 * smoothstep(0.020, 0.075, ax)
    front = (z > hair_z) & (f > -0.02)
    back = (z > 1.815) & (f <= 0.015)
    ear_d = np.minimum(np.linalg.norm(P - P3(0.0775, -0.004, 1.884), axis=1), np.linalg.norm(P - P3(-0.0775, -0.004, 1.884), axis=1))
    return (front | back) & (ear_d > 0.032)


def region_beard(P):
    x, f, z = P[:, 0], -P[:, 1], P[:, 2]
    ax = np.abs(x)
    cheek_line = 1.852 - 0.034 * smoothstep(0.030, 0.062, ax)
    ear_d = np.minimum(np.linalg.norm(P - P3(0.0775, -0.004, 1.884), axis=1), np.linalg.norm(P - P3(-0.0775, -0.004, 1.884), axis=1))
    lips = (ax < 0.0245) & (f > 0.080) & (np.abs(z - hdesign.MOUTH_Z) < 0.0125)
    nose = (ax < 0.016) & (z > 1.815)
    return (z < cheek_line) & (z > 1.700) & (f > -0.045) & (ear_d > 0.034) & (~lips) & (~nose)


def sample_surface(V, F, N, mask_fn, count, rng):
    cen = V[F].mean(axis=1)
    ok = mask_fn(cen)
    tri = np.nonzero(ok)[0]
    a, b, c = V[F[tri, 0]], V[F[tri, 1]], V[F[tri, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    pick = rng.choice(len(tri), size=count, p=area / area.sum())
    t = tri[pick]
    u, v = rng.random(count), rng.random(count)
    flip = u + v > 1
    u, v = np.where(flip, 1 - u, u), np.where(flip, 1 - v, v)
    w = 1 - u - v
    P = V[F[t, 0]] * w[:, None] + V[F[t, 1]] * u[:, None] + V[F[t, 2]] * v[:, None]
    Nn = N[F[t, 0]] * w[:, None] + N[F[t, 1]] * u[:, None] + N[F[t, 2]] * v[:, None]
    Nn /= np.linalg.norm(Nn, axis=1, keepdims=True)
    keep = mask_fn(P)
    return P[keep], Nn[keep]


# ------------------------------------------------------------------------------------------------ guides
def unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)


def grow(sdf, roots, normals, d0, lengths, segs, vol, grav, stiff, noise_amp, rng, margin=0.007, wave=0.0):
    n = len(roots)
    pts = np.zeros((n, segs + 1, 3))
    pts[:, 0] = roots
    d = unit(d0)
    pos = roots.copy()
    side = unit(np.cross(d, normals))
    phase = rng.uniform(0, 6.28, n)
    for s in range(segs):
        frac = (s + 1) / segs
        g = sdf.grad(pos)
        w_out = vol * (1.0 - frac) ** 1.4
        w_g = grav * frac ** 0.75 * (0.35 + lengths * 2.2)
        target = d * stiff + g * w_out[:, None] if np.ndim(w_out) else d * stiff + g * w_out
        target = target + np.array([0, 0, -1.0]) * (w_g[:, None] if np.ndim(w_g) else w_g)
        target = target + rng.normal(0, noise_amp, (n, 3)) + side * (wave * np.sin(phase + frac * 6.0))[:, None]
        d = unit(0.55 * d + 0.45 * unit(target))
        pos = pos + d * (lengths / segs)[:, None]
        sd = sdf.dist(pos)
        push = np.clip(margin - sd, 0, None)
        pos = pos + sdf.grad(pos) * push[:, None]
        pts[:, s + 1] = pos
    return pts


def ribbons(pts, widths, taper, view, cell, atlas_cell_uv, flipv=False):
    """pts (n,S+1,3) -> verts (n*(S+1)*2,3), faces, uv, vertex normals (card normals)."""
    n, S1, _ = pts.shape
    tang = np.zeros_like(pts)
    tang[:, 1:-1] = pts[:, 2:] - pts[:, :-2]
    tang[:, 0] = pts[:, 1] - pts[:, 0]
    tang[:, -1] = pts[:, -1] - pts[:, -2]
    tang = unit(tang)
    side = unit(np.cross(tang, view[:, None, :]))
    s = np.linspace(0, 1, S1)[None, :]
    w = widths[:, None] * (1.0 - (1.0 - taper) * s ** 1.5)
    left = pts - side * (w * 0.5)[..., None]
    right = pts + side * (w * 0.5)[..., None]
    V = np.stack([left, right], axis=2).reshape(-1, 3)
    nrm = np.broadcast_to(unit(np.cross(side, tang))[:, :, None, :], (n, S1, 2, 3)).reshape(-1, 3)
    u0, v0, du, dv = atlas_cell_uv       # per-card arrays (n,)
    uu = np.stack([np.zeros((n, S1)), np.ones((n, S1))], axis=2)
    vv = np.broadcast_to(s[:, :, None], (n, S1, 2))
    UV = np.stack([u0[:, None, None] + uu * du[:, None, None], v0[:, None, None] - vv * dv[:, None, None]], axis=3).reshape(-1, 2)
    F = []
    idx = np.arange(n * S1 * 2).reshape(n, S1, 2)
    for k in range(S1 - 1):
        a, b, c, d = idx[:, k, 0], idx[:, k, 1], idx[:, k + 1, 0], idx[:, k + 1, 1]
        F.append(np.stack([a, b, d], 1))
        F.append(np.stack([a, d, c], 1))
    F = np.concatenate(F)
    return V, F, UV, nrm


def cell_uv(kinds, rng):
    u0 = np.zeros(len(kinds)); v0 = np.zeros(len(kinds)); du = np.zeros(len(kinds)); dv = np.zeros(len(kinds))
    for i, k in enumerate(kinds):
        c, r = CELLS[k]
        u0[i] = c * CELL_W / (CELL_W * 4) + 0.012 / 4
        du[i] = (CELL_W / (CELL_W * 4)) - 0.024 / 4
        v0[i] = 1.0 - r * 0.5 - 0.004
        dv[i] = 0.5 - 0.008
    return u0, v0, du, dv


# ------------------------------------------------------------------------------------------------ main generation
def generate(mesh_path, seed=5):
    z = np.load(mesh_path)
    V, F, N, W = z["V"].astype(np.float64), z["F"].astype(np.int64), z["N"].astype(np.float64), z["W"]
    bones = [str(b) for b in z["bones"]]
    rng = np.random.default_rng(seed)
    sdf = body_sampler()
    skin_tree = cKDTree(V)
    out = []   # list of dict(V,F,UV,N,roots,kind_group,chain)

    crown = P3(0.0, 0.025, 2.0)

    # ---------------------------------------------------------------- scalp hair (three depth layers for coverage + volume)
    def keepout_face(pts, extra=0.0):
        """True for cards that stay clear of the face mask (eyes, nose, brows, cheeks)."""
        x, f, zz = pts[..., 0], -pts[..., 1], pts[..., 2]
        zone = ((f > 0.060 + extra) & (zz > 1.795) & (zz < 1.918) & (np.abs(x) < 0.074)) | ((f > 0.040) & (zz > 1.770) & (zz < 1.925) & (np.abs(x) < 0.088))
        return ~zone[:, 1:].any(axis=1)

    for layer, (count, len_scale, vol, width) in enumerate(((330, 1.0, 0.40, (0.040, 0.072)), (250, 1.0, 0.62, (0.035, 0.062)), (110, 0.55, 0.30, (0.030, 0.050)))):
        roots, nrm = sample_surface(V, F, N, region_scalp, int(count * 1.5), rng)
        d_crown = np.linalg.norm(roots - crown, axis=1)
        roots, nrm = roots[d_crown > 0.032], nrm[d_crown > 0.032]
        n = len(roots)
        x, f, zz = roots[:, 0], -roots[:, 1], roots[:, 2]
        flow = unit(roots - crown)
        flow = unit(flow - nrm * (flow * nrm).sum(1, keepdims=True))
        # unkempt: most of the front hair is swept back/sideways, a few locks fall forward over the temples
        front = (f > 0.03) & (zz > 1.90)
        sweep = unit(np.stack([np.sign(x) * 0.6, 0.55 * np.ones(n), -0.2 * np.ones(n)], 1))
        d0 = unit(0.55 * nrm + 0.45 * flow + rng.normal(0, 0.22, (n, 3)))
        d0[front] = unit(0.40 * nrm[front] + 0.30 * flow[front] + 0.45 * sweep[front] + rng.normal(0, 0.18, (front.sum(), 3)))
        back = f < -0.02
        side = (np.abs(x) > 0.045) & ~back
        sweep_back = unit(np.stack([np.sign(x) * 0.15, 0.95 * np.ones(n), -0.25 * np.ones(n)], 1))
        d0[side] = unit(0.30 * nrm[side] + 0.75 * sweep_back[side] + rng.normal(0, 0.12, (side.sum(), 3)))
        L = np.where(back, rng.uniform(0.24, 0.40, n), np.where(side, rng.uniform(0.15, 0.27, n), rng.uniform(0.09, 0.19, n)))
        L = L * len_scale * rng.uniform(0.75, 1.2, n)
        pts = grow(sdf, roots, nrm, d0, L, 8, vol=vol, grav=0.95, stiff=0.9, noise_amp=0.08, rng=rng, wave=0.06)
        ok = keepout_face(pts)
        keep_idx = np.nonzero(ok)[0][:count]
        roots, nrm, pts, L, d0 = roots[keep_idx], nrm[keep_idx], pts[keep_idx], L[keep_idx], d0[keep_idx]
        n = len(roots)
        kinds = rng.choice(["scalp_clump", "scalp_wavy", "scalp_thin", "scalp_wide"], size=n, p=[0.34, 0.26, 0.10, 0.30])
        view = unit(nrm * np.cos(rng.uniform(-1.0, 1.0, n))[:, None] + unit(np.cross(nrm, unit(pts[:, 1] - pts[:, 0]))) * np.sin(rng.uniform(-1.0, 1.0, n))[:, None])
        widths = rng.uniform(*width, n) * np.where(kinds == "scalp_thin", 0.55, 1.0)
        Vc, Fc, UV, Nc = ribbons(pts, widths, 0.40, view, None, cell_uv(kinds, rng))
        out.append(dict(V=Vc, F=Fc, UV=UV, N=Nc, roots=roots, S1=9, kind="hair", ncards=n, tag=f"scalp{layer}"))

    # ---------------------------------------------------------------- fringe: short locks that blend the hairline into the face
    def fringe_mask(Pq):
        x, f, zz = Pq[:, 0], -Pq[:, 1], Pq[:, 2]
        hl = 1.936 - 0.030 * smoothstep(0.020, 0.075, np.abs(x))
        return (f > 0.0) & (zz > hl + 0.002) & (zz < hl + 0.040) & (np.abs(x) < 0.074)
    roots, nrm = sample_surface(V, F, N, fringe_mask, 110, rng)
    n = len(roots)
    x = roots[:, 0]
    d0 = unit(np.stack([np.sign(x) * (0.15 + 0.5 * np.abs(x) / 0.07), -0.55 * np.ones(n), 0.20 * np.ones(n)], 1) + nrm * 0.5 + rng.normal(0, 0.20, (n, 3)))
    L = rng.uniform(0.045, 0.095, n)
    pts = grow(sdf, roots, nrm, d0, L, 5, vol=0.25, grav=1.1, stiff=0.9, noise_amp=0.07, rng=rng, wave=0.06, margin=0.004)
    kinds = rng.choice(["scalp_clump", "scalp_wavy", "scalp_thin"], size=n, p=[0.45, 0.35, 0.2])
    view = unit(nrm)
    Vc, Fc, UV, Nc = ribbons(pts, rng.uniform(0.022, 0.040, n), 0.35, view, None, cell_uv(kinds, rng))
    out.append(dict(V=Vc, F=Fc, UV=UV, N=Nc, roots=roots, S1=6, kind="hair", ncards=n, tag="fringe"))

    # ---------------------------------------------------------------- beard
    for layer, (count, lscale, width) in enumerate(((250, 1.0, (0.026, 0.050)), (150, 0.7, (0.022, 0.040)))):
        roots, nrm = sample_surface(V, F, N, region_beard, int(count * 1.4), rng)
        x, f, zz = roots[:, 0], -roots[:, 1], roots[:, 2]
        n = len(roots)
        outward = np.stack([np.sign(x) * np.minimum(np.abs(x) / 0.05, 1.0), np.zeros(n), np.zeros(n)], 1)
        near_mouth = np.exp(-(((np.abs(x) - 0.018) / 0.030) ** 2 + ((zz - 1.790) / 0.020) ** 2))
        d0 = unit(0.40 * nrm + np.array([0, 0, -1.0]) * 0.75 + outward * (0.20 + 0.55 * near_mouth)[:, None]
                  + np.array([0, -1.0, 0]) * 0.08 + rng.normal(0, 0.12, (n, 3)))
        chin = np.exp(-((x / 0.036) ** 2 + ((zz - 1.765) / 0.030) ** 2))
        L = (0.060 + 0.14 * chin + 0.03 * rng.random(n)) * lscale * rng.uniform(0.7, 1.3, n)
        L = np.where(zz > 1.80, L * 0.60, L)
        pts = grow(sdf, roots, nrm, d0, L, 6, vol=0.50, grav=0.38, stiff=1.0, noise_amp=0.09, rng=rng, margin=0.006, wave=0.10)
        # keep the nose, eyes and cheekbones clear
        xs, fs, zs = pts[..., 0], -pts[..., 1], pts[..., 2]
        clear = ~(((np.abs(xs) < 0.050) & (fs > 0.085) & (zs > 1.818)) | ((fs > 0.040) & (zs > 1.862)))[:, 1:].any(axis=1)
        keep_idx = np.nonzero(clear)[0][:count]
        roots, nrm, pts, L, chin = roots[keep_idx], nrm[keep_idx], pts[keep_idx], L[keep_idx], chin[keep_idx]
        n = len(roots)
        kinds = rng.choice(["beard_coarse", "beard_curly"], size=n, p=[0.55, 0.45])
        view = unit(nrm * np.cos(rng.uniform(-0.9, 0.9, n))[:, None] + unit(np.cross(nrm, unit(pts[:, 1] - pts[:, 0]))) * np.sin(rng.uniform(-0.9, 0.9, n))[:, None])
        widths = rng.uniform(*width, n) * (1.0 + 0.4 * chin)
        Vc, Fc, UV, Nc = ribbons(pts, widths, 0.38, view, None, cell_uv(kinds, rng))
        out.append(dict(V=Vc, F=Fc, UV=UV, N=Nc, roots=roots, S1=7, kind="beard", ncards=n, tag=f"beard{layer}"))

    # ---------------------------------------------------------------- moustache
    def stache_mask(Pq):
        x, f, zz = Pq[:, 0], -Pq[:, 1], Pq[:, 2]
        return (np.abs(x) < 0.030) & (zz > hdesign.MOUTH_Z + 0.0075) & (zz < 1.826) & (f > 0.060) & ~((np.abs(x) < 0.012) & (zz > 1.818))
    roots, nrm = sample_surface(V, F, N, stache_mask, 130, rng)
    n = len(roots)
    x = roots[:, 0]
    d0 = unit(np.stack([np.sign(x) * 0.75, -0.15 * np.ones(n), -0.60 * np.ones(n)], 1) + rng.normal(0, 0.15, (n, 3)) + nrm * 0.30)
    L = rng.uniform(0.024, 0.042, n) * (0.7 + 0.8 * np.abs(x) / 0.03)
    pts = grow(sdf, roots, nrm, d0, L, 4, vol=0.4, grav=0.35, stiff=1.0, noise_amp=0.07, rng=rng, margin=0.0035, wave=0.05)
    kinds = np.array(["stache"] * n)
    view = unit(nrm * 0.8 + np.array([0, 0, 1.0]) * 0.2)
    Vc, Fc, UV, Nc = ribbons(pts, rng.uniform(0.013, 0.022, n), 0.35, view, None, cell_uv(kinds, rng))
    out.append(dict(V=Vc, F=Fc, UV=UV, N=Nc, roots=roots, S1=5, kind="stache", ncards=n, tag="stache"))

    # ---------------------------------------------------------------- eyebrows (thick, bushy, growing up and outward)
    broots, bnrm = [], []
    for s, t in ((1.0, "L"), (-1.0, "R")):
        def brow_mask(Pq, s=s):
            x, f, zz = Pq[:, 0], -Pq[:, 1], Pq[:, 2]
            return (x * s > 0.008) & (x * s < 0.056) & (zz > 1.8935 + 0.0 * x) & (zz < 1.9055) & (f > 0.060)
        r_, n_ = sample_surface(V, F, N, brow_mask, 55, rng)
        broots.append(r_); bnrm.append(n_)
    roots, nrm = np.concatenate(broots), np.concatenate(bnrm)
    n = len(roots)
    x, zz = roots[:, 0], roots[:, 2]
    sgn = np.sign(x)
    d0 = unit(np.stack([sgn * 0.75, -0.25 * np.ones(n), 0.35 * np.ones(n)], 1) + nrm * 0.55 + rng.normal(0, 0.12, (n, 3)))
    L = rng.uniform(0.016, 0.032, n)
    pts = grow(sdf, roots, nrm, d0, L, 3, vol=0.35, grav=0.18, stiff=1.0, noise_amp=0.05, rng=rng, margin=0.0025, wave=0.04)
    kinds = np.array(["brow"] * n)
    view = unit(nrm)
    Vc, Fc, UV, Nc = ribbons(pts, rng.uniform(0.009, 0.015, n), 0.45, view, None, cell_uv(kinds, rng))
    out.append(dict(V=Vc, F=Fc, UV=UV, N=Nc, roots=roots, S1=4, kind="brow", ncards=n, tag="brow"))

    return out, V, W, bones, skin_tree


def card_weights(parts, skin_V, skin_W, skin_bones, skin_tree):
    """Per-vertex (n,4) bone indices / weights for each part. Returns (names, list of (idx,w))."""
    names = ["head", "jaw", "neck2",
             "hair_back_L_1", "hair_back_L_2", "hair_back_M_1", "hair_back_M_2", "hair_back_R_1", "hair_back_R_2", "hair_side_L", "hair_side_R",
             "beard_C_1", "beard_C_2", "beard_L_1", "beard_R_1", "lid_up_L"]
    names = names[:-1]
    ni = {n: i for i, n in enumerate(names)}
    bi = {n: i for i, n in enumerate(skin_bones)}
    res = []
    for part in parts:
        V = part["V"]
        S1 = part["S1"]
        n = part["ncards"]
        roots = part["roots"]
        _, nn = skin_tree.query(roots)
        # collapse the skin weights of the nearest vertex into {head, jaw, neck2} (everything else on the face goes to head/jaw)
        base = np.zeros((n, len(names)))
        for k in range(n):
            w = skin_W[nn[k]]
            head_like = sum(w[bi[b]] for b in skin_bones if b == "head" or b.startswith(("lid_", "brow_", "cheek_", "lip_up", "lip_corner", "eye_")))
            jaw_like = w[bi["jaw"]] + w[bi["lip_low"]]
            neck_like = sum(w[bi[b]] for b in ("neck1", "neck2", "spine4") if b in bi)
            tot = head_like + jaw_like + neck_like + 1e-9
            base[k, ni["head"]] = head_like / tot
            base[k, ni["jaw"]] = jaw_like / tot
            base[k, ni["neck2"]] = neck_like / tot
        base_v = np.repeat(base, S1 * 2, axis=0)             # (n*S1*2, nb)
        Wv = base_v.copy()
        z = V[:, 2]
        rx = np.repeat(roots[:, 0], S1 * 2)
        rf = -np.repeat(roots[:, 1], S1 * 2)
        if part["kind"] == "hair":
            a1 = smoothstep(1.86, 1.80, z)
            a2 = smoothstep(1.76, 1.68, z)
            back = (rf < -0.02)
            chain = np.where(rx > 0.028, 0, np.where(rx < -0.028, 2, 1))   # L, M, R
            sidec = (~back) & (np.abs(rx) > 0.05)
            for ci, nm in enumerate(("L", "M", "R")):
                sel = back & (chain == ci)
                Wv[sel] = 0
                Wv[sel, ni["head"]] = (1 - a1)[sel]
                Wv[sel, ni[f"hair_back_{nm}_1"]] = (a1 * (1 - a2))[sel]
                Wv[sel, ni[f"hair_back_{nm}_2"]] = (a1 * a2)[sel]
            for nm, sgn in (("L", 1.0), ("R", -1.0)):
                sel = sidec & (rx * sgn > 0)
                Wv[sel] = 0
                Wv[sel, ni["head"]] = (1 - a1)[sel]
                Wv[sel, ni[f"hair_side_{nm}"]] = a1[sel]
        elif part["kind"] == "beard":
            a1 = smoothstep(1.775, 1.725, z)
            a2 = smoothstep(1.70, 1.62, z)
            central = np.abs(rx) < 0.028
            for sel, c1, c2 in ((central, "beard_C_1", "beard_C_2"),):
                Wv_head = base_v[sel]
                Wv[sel] = Wv_head * (1 - a1[sel])[:, None]
                Wv[sel, ni[c1]] = (a1 * (1 - a2))[sel]
                Wv[sel, ni[c2]] = (a1 * a2)[sel]
            for nm, sgn in (("L", 1.0), ("R", -1.0)):
                sel = (~central) & (rx * sgn > 0)
                Wv[sel] = base_v[sel] * (1 - a1[sel] * 0.9)[:, None]
                Wv[sel, ni[f"beard_{nm}_1"]] = (a1 * 0.9)[sel]
        # normalise, keep top 4
        Wv /= np.maximum(Wv.sum(axis=1, keepdims=True), 1e-9)
        order = np.argsort(-Wv, axis=1)[:, :4]
        idx = order
        w = np.take_along_axis(Wv, order, axis=1)
        w /= np.maximum(w.sum(axis=1, keepdims=True), 1e-9)
        res.append((idx, w))
    return names, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh", default="build/castaway/mesh.npz")
    ap.add_argument("--out", default="build/castaway/hair.npz")
    ap.add_argument("--atlas", default="build/castaway/tex/hair_atlas.png")
    a = ap.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(a.atlas)), exist_ok=True)
    make_atlas(a.atlas)
    parts, skinV, skinW, skin_bones, tree = generate(a.mesh)
    names, ws = card_weights(parts, skinV, skinW, skin_bones, tree)
    data = {}
    tot = 0
    for i, (p, (idx, w)) in enumerate(zip(parts, ws)):
        data[f"V{i}"], data[f"F{i}"], data[f"UV{i}"], data[f"N{i}"] = p["V"].astype(np.float32), p["F"].astype(np.int32), p["UV"].astype(np.float32), p["N"].astype(np.float32)
        data[f"I{i}"], data[f"W{i}"] = idx.astype(np.int16), w.astype(np.float32)
        data[f"tag{i}"] = np.array(p["tag"])
        data[f"kind{i}"] = np.array(p["kind"])
        tot += len(p["F"])
        print(f"[hair] {p['tag']:8s} cards={p['ncards']:4d} tris={len(p['F'])}")
    data["n"] = np.array(len(parts))
    data["bones"] = np.array(names)
    np.savez_compressed(a.out, **data)
    print(f"[hair] total {tot} tris -> {a.out}")


if __name__ == "__main__":
    main()
