"""
Generate the non-skin parts of the castaway: teeth, gums, tongue and the maro (loincloth).

  /opt/bpy-venv/bin/python tools/castaway/extras_gen.py --mesh build/castaway/mesh.npz --out build/castaway/extras.npz

Output npz: parts (names); per part: V_, F_, UV_ (per vertex), N_, B_ (bone names), I_/W_ (per-vertex bone index / weight).
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "monkey"))

import hdesign  # noqa: E402
from paint_textures import Noise3, smoothstep  # noqa: E402
from sdf_sampler import body_sampler  # noqa: E402

P3 = hdesign.P
MZ = hdesign.MOUTH_Z


def unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)


def uvsphere(center, radii, rings=7, segs=10):
    V, F = [], []
    for i in range(rings + 1):
        th = np.pi * i / rings
        for j in range(segs):
            ph = 2 * np.pi * j / segs
            V.append([np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)])
    V = np.array(V)
    for i in range(rings):
        for j in range(segs):
            a = i * segs + j
            b = i * segs + (j + 1) % segs
            c = a + segs
            d = b + segs
            if i > 0:
                F.append([a, c, b])
            if i < rings - 1:
                F.append([b, c, d])
    N = unit(V / np.asarray(radii))
    return np.asarray(center) + V * np.asarray(radii), np.array(F), N


# ----------------------------------------------------------------------------------------------- mouth
def mouth_parts():
    parts = {}
    # arch positions (x, f) for 12 upper / 12 lower teeth (one side listed, mirrored)
    specs = [  # width x, depth f, height z, centre x, centre f
        (0.0086, 0.0066, 0.0105, 0.0045, 0.0790),   # central incisor
        (0.0072, 0.0062, 0.0090, 0.0125, 0.0765),   # lateral incisor
        (0.0078, 0.0078, 0.0108, 0.0195, 0.0710),   # canine
        (0.0068, 0.0086, 0.0078, 0.0245, 0.0620),   # premolar 1
        (0.0068, 0.0088, 0.0074, 0.0270, 0.0525),   # premolar 2
    ]
    for arch, zc0, sgn, tag, bone in (("upper", MZ + 0.0010, 1.0, "teeth_upper", "head"), ("lower", MZ - 0.0010, -1.0, "teeth_lower", "jaw")):
        Vs, Fs, Ns, UVs = [], [], [], []
        off = 0
        for s in (1.0, -1.0):
            for k, (w, d, h, cx, cf) in enumerate(specs):
                hh = h * (1.0 if arch == "upper" else 0.82)
                c = P3(s * cx, cf, zc0 + sgn * hh * 0.5)
                V, F, N = uvsphere(c, (w * 0.5, d * 0.5, hh * 0.5), rings=5, segs=8)
                # squarish crowns: push the equator outwards a little
                V = c + (V - c) * 1.0
                Vs.append(V); Fs.append(F + off); Ns.append(N); off += len(V)
                u = (np.arange(len(V)) % 8) / 8 * 0.45 + 0.02
                UVs.append(np.stack([u, 0.55 + 0.4 * (V[:, 2] - V[:, 2].min()) / max(np.ptp(V[:, 2]), 1e-6)], 1))
        parts[tag] = dict(V=np.concatenate(Vs), F=np.concatenate(Fs), N=np.concatenate(Ns), UV=np.concatenate(UVs), bone=bone)
    # gums: swept rounded strip along each arch
    for arch, tag, bone in (("upper", "gum_upper", "head"), ("lower", "gum_lower", "jaw")):
        pts = []
        for s, rng_ in ((-1.0, range(4, -1, -1)), (1.0, range(0, 5))):
            for k in rng_:
                w, d, h, cx, cf = specs[k]
                pts.append(P3(s * cx, cf + 0.001, 0.0))
        pts = np.array(pts)
        z0 = MZ + 0.0095 if arch == "upper" else MZ - 0.0090
        ring = []
        for p in pts:
            for a in np.linspace(0, 2 * np.pi, 8, endpoint=False):
                ring.append(p + np.array([0, -0.0042 * np.cos(a), 0]) + np.array([0, 0, z0 + 0.0042 * np.sin(a)]))
        ring = np.array(ring).reshape(len(pts), 8, 3)
        V = ring.reshape(-1, 3)
        F = []
        for i in range(len(pts) - 1):
            for j in range(8):
                a, b = i * 8 + j, i * 8 + (j + 1) % 8
                c, d = a + 8, b + 8
                F += [[a, c, b], [b, c, d]]
        N = unit(V - np.repeat(pts + np.array([0, 0, z0]), 8, axis=0))
        UV = np.stack([0.55 + 0.4 * (np.arange(len(V)) % 8) / 8, 0.55 + 0.4 * np.repeat(np.arange(len(pts)), 8) / len(pts)], 1)
        parts[tag] = dict(V=V, F=np.array(F), N=N, UV=UV, bone=bone)
    # tongue
    V, F, N = uvsphere(P3(0, 0.046, MZ - 0.0105), (0.0185, 0.034, 0.0085), rings=8, segs=12)
    UV = np.stack([0.02 + 0.45 * (np.arange(len(V)) % 12) / 12, 0.02 + 0.45 * (V[:, 1] - V[:, 1].min()) / max(np.ptp(V[:, 1]), 1e-6)], 1)
    parts["tongue"] = dict(V=V, F=F, N=N, UV=UV, bone="jaw")
    return parts


def mouth_texture(path, size=256):
    rng = np.random.default_rng(5)
    img = np.zeros((size, size, 3), np.float32)
    n = Noise3(21)
    ys, xs = np.mgrid[0:size, 0:size]
    P = np.stack([xs, ys, np.zeros_like(xs)], -1).reshape(-1, 3).astype(np.float32)
    noise = n(P, 8.0).reshape(size, size)
    fine = n(P + 3.3, 2.0).reshape(size, size)
    h = size // 2
    # image rows are v flipped: top half = v in [0.5, 1]
    teeth = np.array([0.80, 0.73, 0.57])[None, None] * (0.93 + 0.14 * noise[..., None]) * (0.96 + 0.08 * np.sin(xs[..., None] * 0.9))
    gum = np.array([0.60, 0.28, 0.28])[None, None] * (0.9 + 0.2 * noise[..., None])
    tongue = np.array([0.63, 0.30, 0.30])[None, None] * (0.88 + 0.24 * fine[..., None])
    tongue = tongue * (1.0 - 0.10 * (np.sin(xs[..., None] * 0.2) > 0.4))
    img[:h, :h] = teeth[:h, :h]
    img[:h, h:] = gum[:h, h:]
    img[h:, :h] = tongue[h:, :h]
    img[h:, h:] = gum[h:, h:]
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(path)
    print("[extras] mouth texture", path)


# ----------------------------------------------------------------------------------------------- maro
def push_out(sdf, p, gap):
    for _ in range(3):
        sd = sdf.dist(p)
        d = np.clip(gap - sd, 0, None)
        p = p + sdf.grad(p) * d[:, None]
    return p


def surface_along(sdf, origin, direction, r0=0.0, r1=0.45, step=0.002):
    """First positive->negative crossing of the SDF when marching from `origin` along `direction` (outward = inside->outside)."""
    ts = np.arange(r0, r1, step)
    best = np.full(len(origin), np.nan)
    pts = origin[:, None, :] + direction[:, None, :] * ts[None, :, None]
    sd = sdf.dist(pts.reshape(-1, 3)).reshape(len(origin), len(ts))
    inside = sd < 0
    # last inside sample along the ray from the centre = outer surface
    last = (inside * np.arange(len(ts))[None, :]).max(axis=1)
    has = inside.any(axis=1)
    t = ts[last]
    return np.where(has, t, np.nan)


def grid_mesh(P, nu, nv, wrap_u=False):
    """P: (nv, nu, 3) grid -> V, F, uv(u,v in 0..1)"""
    V = P.reshape(-1, 3)
    F = []
    nu_c = nu if wrap_u else nu - 1
    for j in range(nv - 1):
        for i in range(nu_c):
            a = j * nu + i
            b = j * nu + (i + 1) % nu
            c = (j + 1) * nu + i
            d = (j + 1) * nu + (i + 1) % nu
            F += [[a, b, d], [a, d, c]]
    uu = np.tile(np.linspace(0, 1, nu), nv)
    vv = np.repeat(np.linspace(0, 1, nv), nu)
    return V, np.array(F), np.stack([uu, vv], 1)


def maro_parts(sdf, rng):
    nz = Noise3(31)
    parts = {}

    def noise3(P, cell):
        return nz(P.astype(np.float32), cell)

    # ---- waist band (wrapped, slightly diagonal)
    nu, nv = 101, 9
    th = np.linspace(0, 2 * np.pi, nu)
    center = np.array([0.0, -0.004, float(hdesign.zmap(1.0))])
    z_top_base = float(hdesign.zmap(1.112))
    z_bot_base = float(hdesign.zmap(0.998))
    P = np.zeros((nv, nu, 3))
    for i, a in enumerate(th):
        d = np.array([np.sin(a), -np.cos(a), 0.0])           # a=0 -> front (-Y)
        tilt = -0.020 * np.cos(a) + 0.018 * np.sin(a)          # lower at the front, higher at the right hip (the wrap)
        zt = z_top_base + tilt + 0.004 * np.sin(5 * a + 1.0)
        zb = z_bot_base + 0.6 * tilt + 0.004 * np.sin(7 * a)
        for j in range(nv):
            v = j / (nv - 1)
            z = zt + (zb - zt) * v
            o = np.array([center[0], center[1], z])
            r = surface_along(sdf, o[None], d[None], 0.02, 0.32)[0]
            if np.isnan(r):
                r = 0.16
            fold = noise3(np.array([[a * 0.12, z * 3.0, 0.0]]), 0.04)[0] - 0.5
            gap = 0.0065 + 0.004 * fold + 0.0045 * np.sin(a * 9 + v * 3) * (1 - v) ** 2 + 0.003 * v
            P[j, i] = o + d * (r + gap)
    V, F, UV = grid_mesh(P, nu, nv)
    UV = np.stack([UV[:, 0] * 0.5, 0.5 + UV[:, 1] * 0.3], 1)
    parts["maro_band"] = dict(V=V, F=F, UV=UV, kind="band")

    # ---- front and back aprons
    for tag, sign in (("front", -1.0), ("back", 1.0)):
        nu, nv = 14, 16
        width0 = 0.165 if tag == "front" else 0.178
        P = np.zeros((nv, nu, 3))
        len_ = 0.30 if tag == "front" else 0.26
        for i in range(nu):
            u = i / (nu - 1) * 2 - 1
            length = len_ * (1 - 0.10 * abs(u) ** 2) * (1 - 0.08 * (noise3(np.array([[u * 3, 0.5, sign]]), 0.5)[0]))
            for j in range(nv):
                v = j / (nv - 1)
                w = width0 * (1 - 0.18 * v)
                x = u * w * 0.5
                z = float(hdesign.zmap(1.075)) - v * length - 0.01 * (1 - abs(u))
                # find the body surface along +-Y at (x, z)
                o = np.array([[x, 0.0, z]])
                d = np.array([[0.0, sign, 0.0]])
                r = surface_along(sdf, o, d, 0.0, 0.30)[0]
                if np.isnan(r):
                    r = 0.10
                swing = 0.006 + 0.030 * v ** 1.3 + 0.008 * (noise3(np.array([[x * 8, z * 4, sign]]), 0.06)[0] - 0.5)
                P[j, i] = np.array([x, sign * (r + swing), z])
        V, F, UV = grid_mesh(P, nu, nv)
        UV = np.stack([0.5 + UV[:, 0] * 0.5, 0.0 + UV[:, 1] * 0.5], 1) if tag == "front" else np.stack([UV[:, 0] * 0.5, 0.0 + UV[:, 1] * 0.5], 1)
        parts[f"maro_{tag}"] = dict(V=V, F=F, UV=UV, kind=tag)

    # ---- crotch strap joining the aprons
    path = np.array([P3(0, 0.099, 1.02), P3(0, 0.092, 0.975), P3(0, 0.070, 0.935), P3(0, 0.035, 0.915), P3(0, -0.005, 0.912),
                     P3(0, -0.045, 0.922), P3(0, -0.082, 0.950), P3(0, -0.108, 1.000)])
    nv = 22
    ts = np.linspace(0, 1, nv)
    seg = np.linspace(0, len(path) - 1, nv)
    cen = np.array([np.interp(seg, np.arange(len(path)), path[:, k]) for k in range(3)]).T
    nu = 7
    P = np.zeros((nv, nu, 3))
    for j in range(nv):
        for i in range(nu):
            u = (i / (nu - 1) * 2 - 1) * 0.034
            P[j, i] = cen[j] + np.array([u, 0, 0])
    P = push_out(sdf, P.reshape(-1, 3), 0.0075).reshape(nv, nu, 3)
    V, F, UV = grid_mesh(P, nu, nv)
    UV = np.stack([UV[:, 0] * 0.25 + 0.25, 0.55 + UV[:, 1] * 0.4], 1)
    parts["maro_strap"] = dict(V=V, F=F, UV=UV, kind="strap")

    # ---- knot at the left hip and two hanging ends
    knot_c = P3(0.158, -0.030, 1.040)
    nu, nv = 10, 10
    P = np.zeros((nv, nu, 3))
    for j in range(nv):
        v = j / (nv - 1)
        for i in range(nu):
            u = i / (nu - 1) * 2 - 1
            P[j, i] = knot_c + np.array([0.020 * u, 0.022 * np.cos(v * 3.14) , 0.03 * (0.5 - v)])
    ends = []
    for k, (dx, dy, ln, twist) in enumerate(((0.012, 0.010, 0.27, 0.4), (-0.005, -0.012, 0.21, -0.5))):
        nu2, nv2 = 5, 14
        P2 = np.zeros((nv2, nu2, 3))
        for j in range(nv2):
            v = j / (nv2 - 1)
            for i in range(nu2):
                u = (i / (nu2 - 1) * 2 - 1) * 0.026 * (1 - 0.2 * v)
                c = knot_c + np.array([dx + 0.012 * v, dy + 0.004 * np.sin(v * 4 + k), -v * ln - 0.010])
                P2[j, i] = c + np.array([u * np.cos(twist * v), u * np.sin(twist * v), 0.0])
        P2 = push_out(sdf, P2.reshape(-1, 3), 0.008).reshape(nv2, nu2, 3)
        V, F, UV = grid_mesh(P2, nu2, nv2)
        UV = np.stack([0.5 + UV[:, 0] * 0.25, 0.5 + UV[:, 1] * 0.45], 1)
        parts[f"maro_end{k}"] = dict(V=V, F=F, UV=UV, kind="knot")
    return parts


def maro_texture(path, size=1024):
    """Coarse hand-woven bark-cloth / tapa look: warp+weft threads, stains, a darker border; alpha = frayed outline."""
    rng = np.random.default_rng(9)
    n = Noise3(41)
    ys, xs = np.mgrid[0:size, 0:size]
    P = np.stack([xs, ys, np.zeros_like(xs)], -1).reshape(-1, 3).astype(np.float32)
    big = n(P, 90.0).reshape(size, size)
    mid = n(P + 1.7, 24.0).reshape(size, size)
    fine = n(P + 8.3, 3.5).reshape(size, size)
    warp = 0.5 + 0.5 * np.sin(xs * 2 * np.pi / 7.0 + fine * 3.0)
    weft = 0.5 + 0.5 * np.sin(ys * 2 * np.pi / 6.0 + fine * 2.0)
    weave = 0.55 * warp + 0.45 * weft
    base = np.array([0.46, 0.35, 0.24])
    dark = np.array([0.27, 0.19, 0.13])
    light = np.array([0.62, 0.50, 0.36])
    col = base[None, None] * (0.8 + 0.4 * weave[..., None])
    col = col * (0.85 + 0.30 * mid[..., None]) * (0.9 + 0.2 * big[..., None])
    stain = np.clip((big - 0.58) * 4, 0, 1)[..., None]
    col = col * (1 - 0.35 * stain) + dark * 0.35 * stain
    # frayed alpha along every tile edge (tiles are 0.5 x 0.5 of the atlas); threads hang from the bottom edges
    alpha = np.ones((size, size), np.float32)
    for tile_y in (0, 1):
        for tile_x in (0, 1):
            y0, x0 = tile_y * size // 2, tile_x * size // 2
            sub = (ys - y0) / (size / 2)
            subx = (xs - x0) / (size / 2)
            inside = (sub >= 0) & (sub < 1) & (subx >= 0) & (subx < 1)
            thread = (n(P + 20 + tile_x * 3 + tile_y * 5, 2.2).reshape(size, size))
            edge_bottom = 1 - np.clip((1 - sub) / 0.07 - (thread - 0.5) * 1.8, 0, 1)
            alpha = np.where(inside & (edge_bottom > 0.55 + 0.2 * thread) & (sub > 0.93), 0, alpha)
    out = np.concatenate([np.clip(col, 0, 1), alpha[..., None]], axis=2)
    Image.fromarray((out[::-1] * 255).astype(np.uint8), "RGBA").save(path)
    print("[extras] maro texture", path)


# ----------------------------------------------------------------------------------------------- weights
def weights_for(V, skin_V, skin_W, skin_bones, names, rng=None, mode="skin"):
    """Nearest-skin-vertex weights restricted/renamed to `names`."""
    tree = cKDTree(skin_V)
    _, nn = tree.query(V)
    bi = {n: i for i, n in enumerate(skin_bones)}
    W = np.zeros((len(V), len(names)), np.float32)
    for j, n in enumerate(names):
        if n in bi:
            W[:, j] = skin_W[nn, bi[n]]
    s = W.sum(axis=1, keepdims=True)
    W = np.where(s > 1e-6, W / np.maximum(s, 1e-6), 0)
    return W


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh", default="build/castaway/mesh.npz")
    ap.add_argument("--out", default="build/castaway/extras.npz")
    ap.add_argument("--tex", default="build/castaway/tex")
    a = ap.parse_args()
    os.makedirs(a.tex, exist_ok=True)
    rng = np.random.default_rng(3)
    z = np.load(a.mesh)
    skinV, skinW = z["V"].astype(np.float64), z["W"]
    skin_bones = [str(b) for b in z["bones"]]
    sdf = body_sampler()
    data = {}
    names_all = []
    # mouth
    mouth_texture(os.path.join(a.tex, "mouth_albedo.png"))
    for nm, p in mouth_parts().items():
        names_all.append(nm)
        data[f"V_{nm}"], data[f"F_{nm}"], data[f"N_{nm}"], data[f"UV_{nm}"] = p["V"], p["F"], p["N"], p["UV"]
        data[f"B_{nm}"] = np.array([p["bone"]])
        data[f"I_{nm}"] = np.zeros((len(p["V"]), 4), np.int16)
        data[f"W_{nm}"] = np.tile(np.array([1.0, 0, 0, 0], np.float32), (len(p["V"]), 1))
        data[f"tag_{nm}"] = np.array("mouth")
    # maro
    maro_texture(os.path.join(a.tex, "maro_albedo.png"))
    mp = maro_parts(sdf, rng)
    for nm, p in mp.items():
        V = p["V"]
        kind = p["kind"]
        if kind == "band" or kind == "strap":
            names = ["pelvis", "spine1", "thigh_L", "thigh_R"]
            W = weights_for(V, skinV, skinW, skin_bones, names)
            # the band follows the pelvis even where the skin weights are thigh-heavy (keeps the wrap rigid above the crotch)
            if kind == "band":
                W = 0.7 * W + 0.3 * np.array([[0.8, 0.2, 0, 0]])
        else:
            if kind == "front":
                names = ["pelvis", "thigh_L", "thigh_R", "cloth_front_1", "cloth_front_2"]
            elif kind == "back":
                names = ["pelvis", "thigh_L", "thigh_R", "cloth_back_1", "cloth_back_2"]
            else:
                names = ["pelvis", "thigh_L", "thigh_R", "cloth_knot_1", "cloth_knot_2"]
            Wskin = weights_for(V, skinV, skinW, skin_bones, names[:3])
            zt = {"front": (1.075, 0.80), "back": (1.075, 0.82), "knot": (1.040, 0.76)}[kind]
            zt = (float(hdesign.zmap(zt[0])), float(hdesign.zmap(zt[1])) + (0.04 if False else 0.0))
            v = np.clip((zt[0] - V[:, 2]) / (zt[0] - zt[1]), 0, 1)
            a1 = smoothstep(0.10, 0.45, v)
            a2 = smoothstep(0.50, 0.95, v)
            W = np.zeros((len(V), 5), np.float32)
            W[:, :3] = Wskin * (1 - a1)[:, None]
            W[:, 3] = a1 * (1 - a2)
            W[:, 4] = a1 * a2
        W /= np.maximum(W.sum(axis=1, keepdims=True), 1e-9)
        order = np.argsort(-W, axis=1)[:, :4]
        Wt = np.take_along_axis(W, order, axis=1)
        Wt /= np.maximum(Wt.sum(axis=1, keepdims=True), 1e-9)
        # normals from the grid faces
        fn = np.cross(V[p["F"][:, 1]] - V[p["F"][:, 0]], V[p["F"][:, 2]] - V[p["F"][:, 0]])
        N = np.zeros_like(V)
        for k in range(3):
            np.add.at(N, p["F"][:, k], fn)
        N = unit(N)
        names_all.append(nm)
        data[f"V_{nm}"], data[f"F_{nm}"], data[f"N_{nm}"], data[f"UV_{nm}"] = V, p["F"], N, p["UV"]
        data[f"B_{nm}"] = np.array(names)
        data[f"I_{nm}"] = order.astype(np.int16)
        data[f"W_{nm}"] = Wt.astype(np.float32)
        data[f"tag_{nm}"] = np.array("maro")
        print(f"[extras] {nm}: {len(V)} verts {len(p['F'])} tris")
    data["parts"] = np.array(names_all)
    np.savez_compressed(a.out, **data)
    print(f"[extras] -> {a.out}")


if __name__ == "__main__":
    main()
