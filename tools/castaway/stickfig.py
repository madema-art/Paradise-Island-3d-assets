"""Stick-figure contact sheets for fast animation review (PIL only)."""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import clipkit as CK
from pose_lib import RIG

SK = RIG.sk

LIMBS = [("spine", ["pelvis", "spine1", "spine2", "spine3", "spine4", "neck1", "neck2", "head"], (230, 230, 230)),
         ("armL", ["clavicle_L", "upper_arm_L", "forearm_L", "hand_L"], (255, 170, 80)),
         ("armR", ["clavicle_R", "upper_arm_R", "forearm_R", "hand_R"], (110, 200, 255)),
         ("legL", ["thigh_L", "shin_L", "foot_L"], (255, 120, 80)),
         ("legR", ["thigh_R", "shin_R", "foot_R"], (80, 160, 255))]


def font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def joints(sol, bones):
    pts = []
    for b in bones:
        pts.append(sol.head(b))
    pts.append(sol.tail(bones[-1]))
    return np.array(pts)


def draw_pose(dr, sol, project, ox, oy, scale, props=True, world_shift=0.0, extra=None):
    for name, bones, col in LIMBS:
        P = joints(sol, bones)
        xy = [project(p) for p in P]
        pts = [(ox + (x + world_shift) * scale, oy - y * scale) for x, y in xy]
        dr.line(pts, fill=col, width=3)
    # fingers / toes tip lines
    for t in ("L", "R"):
        for nm in ("f_middle_3", "toe3_1", "hallux_2"):
            b = f"{nm}_{t}"
            if b in SK.idx:
                a, c = sol.head(b), sol.tail(b)
                p1, p2 = project(a), project(c)
                dr.line([(ox + (p1[0] + world_shift) * scale, oy - p1[1] * scale), (ox + (p2[0] + world_shift) * scale, oy - p2[1] * scale)], fill=(200, 200, 120), width=2)
    hc = project(sol.head("head") + (sol.tail("head") - sol.head("head")) * 0.55)
    r = 0.105 * scale
    dr.ellipse([ox + (hc[0] + world_shift) * scale - r, oy - hc[1] * scale - r, ox + (hc[0] + world_shift) * scale + r, oy - hc[1] * scale + r], outline=(230, 230, 230), width=2)
    # eyes direction
    ec = sol.head("eye_L")
    ed = sol.tail("eye_L") - ec
    p1, p2 = project(ec), project(ec + ed * 4.0)
    dr.line([(ox + (p1[0] + world_shift) * scale, oy - p1[1] * scale), (ox + (p2[0] + world_shift) * scale, oy - p2[1] * scale)], fill=(120, 255, 120), width=1)
    if props:
        for bn, col, ln in (("prop_staff", (200, 150, 90), 2.1), ("prop_aux", (150, 200, 120), 1.4)):
            a = sol.head(bn)
            axis = sol.rot(bn)[:, 1]
            b = a + axis * ln
            moved = np.linalg.norm(a - SK.head[SK.i(bn)]) > 1e-3 or abs(sol.rot(bn)[2, 1] - 1.0) > 1e-3
            if moved:
                p1, p2 = project(a), project(b)
                dr.line([(ox + (p1[0] + world_shift) * scale, oy - p1[1] * scale), (ox + (p2[0] + world_shift) * scale, oy - p2[1] * scale)], fill=col, width=4)


def side(p):
    return (-p[1], p[2])


def front(p):
    return (p[0], p[2])


def sheet(B, path, frames=8, scale=150, ground_z=0.0, extra=None, size=None, hold_end=True):
    n = B.quat.shape[0]
    idxs = np.linspace(0, n - (0 if B.loop else 1), frames, endpoint=not B.loop).astype(int)
    pw, ph = int(1.3 * scale), int(2.45 * scale)
    W = pw * len(idxs)
    img = Image.new("RGB", (W, ph * 2 + 26), (28, 32, 38))
    dr = ImageDraw.Draw(img)
    f = font(13)
    spec = B.spec
    dr.text((8, 4), f"{B.name}  {spec['seconds']:.2f}s {'loop' if B.loop else 'one-shot'}  {spec['group']}  reach={B.metrics['reach_miss_mm']}  minz={B.metrics['min_z']}", font=f, fill=(255, 255, 255))
    for col, i in enumerate(idxs):
        sol = B.sols[i]
        for row, proj in enumerate((side, front)):
            ox = col * pw + pw * 0.5
            oy = 22 + row * ph + ph - 0.12 * scale
            dr.line([(col * pw, oy - ground_z * scale), ((col + 1) * pw, oy - ground_z * scale)], fill=(90, 110, 80), width=2)
            draw_pose(dr, sol, proj, ox, oy, scale)
            if row == 0:
                dr.text((col * pw + 6, 22), f"f{i}", font=f, fill=(180, 180, 180))
    img.save(path)
    return path
