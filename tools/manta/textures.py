"""
Procedural base-colour textures for the manta (numpy only, no PIL).

Dorsal: slate-navy with pale, blotchy spots (the real reef manta reads from above as a mottled dark back).
Ventral: near-white with faint grey mottling, so the underside stays bright against the water.
Both are planar-mapped over the disc (see build_manta.uv_for).
"""
import os
import struct
import zlib

import numpy as np


def _value_noise(h, w, cells, rng):
    grid = rng.random((cells + 1, cells + 1))
    ys = np.linspace(0, cells, h, endpoint=False)
    xs = np.linspace(0, cells, w, endpoint=False)
    y0, x0 = np.floor(ys).astype(int), np.floor(xs).astype(int)
    fy, fx = ys - y0, xs - x0
    fy = fy * fy * (3 - 2 * fy)
    fx = fx * fx * (3 - 2 * fx)
    rows0, rows1 = grid[y0], grid[y0 + 1]
    top = rows0[:, x0] * (1 - fx) + rows0[:, x0 + 1] * fx
    bot = rows1[:, x0] * (1 - fx) + rows1[:, x0 + 1] * fx
    return top * (1 - fy)[:, None] + bot * fy[:, None]


def _fbm(h, w, cells, rng, octaves=4):
    out = np.zeros((h, w))
    amp, total = 1.0, 0.0
    for o in range(octaves):
        out += amp * _value_noise(h, w, cells * (2 ** o), rng)
        total += amp
        amp *= 0.5
    out /= total
    return (out - out.min()) / max(out.max() - out.min(), 1e-9)


def _smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def dorsal(size=512, seed=7):
    rng = np.random.default_rng(seed)
    base = _fbm(size, size, 6, rng)
    spots = _fbm(size, size, 22, rng)
    dark = np.array([0.08, 0.13, 0.19])
    mid = np.array([0.19, 0.26, 0.32])
    pale = np.array([0.70, 0.74, 0.76])
    col = dark * (1 - base[..., None]) + mid * base[..., None]
    mask = _smoothstep(0.60, 0.72, spots)[..., None] * 0.5
    col = col * (1 - mask) + pale * mask
    return col


def ventral(size=256, seed=11):
    rng = np.random.default_rng(seed)
    mottle = _fbm(size, size, 5, rng, octaves=3)
    white = np.array([0.93, 0.94, 0.93])
    grey = np.array([0.78, 0.81, 0.82])
    return white * (1 - 0.35 * mottle[..., None]) + grey * (0.35 * mottle[..., None])


def write_png(path, rgb01):
    rgb = (np.clip(rgb01, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[y].tobytes() for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)


def write_all(tex_dir):
    write_png(os.path.join(tex_dir, "manta_dorsal.png"), dorsal())
    write_png(os.path.join(tex_dir, "manta_ventral.png"), ventral())
    return {"dorsal": os.path.join(tex_dir, "manta_dorsal.png"), "ventral": os.path.join(tex_dir, "manta_ventral.png")}
