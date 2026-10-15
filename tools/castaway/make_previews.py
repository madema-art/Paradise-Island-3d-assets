"""Castaway previews, rendered from the REAL packaged GLBs in headless Three.js (no approximations):
  reference sheet (infographic), UV layouts, texture atlases, wireframes, staff sheet, turntable + clip GIFs, per-group animation contact sheets.

  /opt/bpy-venv/bin/python tools/castaway/make_previews.py [--only sheet,uv,atlas,wire,staff,gifs,anim]
Output: build/castaway/previews/  (copied to assets/castaway/previews/ by --install)
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
A = os.path.join(ROOT, "assets/castaway")
OUT = os.path.join(ROOT, "build/castaway/previews")
SHOT = os.path.join(ROOT, "viewer/tests/shot.mjs")
BG = (28, 32, 38)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONTB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def font(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


def shot(model, views, out, size="640x800", fov=30, light="studio", extra=None, clip=None, times=None, wire=None, hide=None, ground=True):
    os.makedirs(out, exist_ok=True)
    cmd = ["node", SHOT, "--model", os.path.relpath(model, ROOT), "--views", views, "--out", out, "--size", size, "--fov", str(fov), "--light", light]
    if not ground:
        cmd += ["--ground", "0"]
    if extra:
        cmd += ["--extra", extra]
    if clip:
        cmd += ["--clip", clip]
    if times:
        cmd += ["--times", ",".join(f"{t:.3f}" for t in times)]
    if wire:
        cmd += ["--wire", wire]
    if hide:
        cmd += ["--hide", hide]
    subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True)


def caption(img, text, sub=None, h=34):
    w = img.width
    out = Image.new("RGB", (w, img.height + h), BG)
    out.paste(img, (0, h))
    d = ImageDraw.Draw(out)
    d.text((10, 6), text, font=font(17, True), fill=(235, 228, 214))
    if sub:
        d.text((w - 8 - d.textlength(sub, font=font(12)), 11), sub, font=font(12), fill=(150, 160, 166))
    return out


def tile(imgs, cols, gap=10, bg=BG):
    rows = [imgs[i:i + cols] for i in range(0, len(imgs), cols)]
    ws = [sum(i.width for i in r) + gap * (len(r) - 1) for r in rows]
    W = max(ws)
    H = sum(max(i.height for i in r) for r in rows) + gap * (len(rows) - 1)
    sheet = Image.new("RGB", (W, H), bg)
    y = 0
    for r in rows:
        x = 0
        for i in r:
            sheet.paste(i, (x, y))
            x += i.width + gap
        y += max(i.height for i in r) + gap
    return sheet


# ------------------------------------------------------------------------------------------------ renders
def renders():
    d = os.path.join(OUT, "_r")
    M = os.path.join(A, "Castaway.glb")
    shot(M, "front:0,1.0,5.3,0,0.97,0;side:5.3,1.0,0,0,0.97,0;back:0,1.0,-5.3,0,0.97,0;hero:2.6,1.25,3.9,0,0.98,0", d, "560x800", 28)
    shot(M, "face:0.0,1.86,0.95,0,1.84,0;face34:0.72,1.9,0.74,0,1.83,0;profile:0.95,1.85,0.1,0,1.83,0", d, "560x640", 26)
    shot(M, "hair_back:-0.3,1.85,-1.2,0,1.78,0;beard:0.5,1.72,0.9,0,1.72,0", d, "560x640", 26)
    shot(M, "torso:0.0,1.4,2.7,0,1.38,0;torso34:1.35,1.45,2.3,0,1.38,0;back_t:0.0,1.45,-2.7,0,1.38,0", d, "560x700", 26)
    shot(M, "handR:-0.80,0.95,0.75,-0.50,0.96,-0.07;handL:0.80,0.95,0.75,0.50,0.96,-0.07", d, "560x560", 24)
    shot(M, "feet:0.55,0.22,0.95,0.0,0.06,0.0", d, "700x420", 28)
    shot(M, "maro_f:0.0,1.0,1.9,0,0.98,0;maro_b:0.0,1.0,-1.9,0,0.98,0", d, "560x640", 26)
    # wireframes (no hair cards, flat shaded)
    W = os.path.join(OUT, "_w")
    shot(M, "wfront:0,1.0,5.3,0,0.97,0;wside:5.3,1.0,0,0,0.97,0", W, "560x800", 28, wire="flat", hide="CastawayHair")
    shot(M, "whead:0.7,1.88,0.8,0,1.84,0;whead_f:0.0,1.86,0.95,0,1.84,0", W, "620x640", 24, wire="flat", hide="CastawayHair")
    shot(M, "whand:-0.8,0.95,0.75,-0.50,0.96,-0.07", W, "560x560", 24, wire="flat", hide="CastawayHair")
    shot(M, "whair:0.7,1.9,0.9,0,1.8,0", W, "620x640", 24, wire="1")
    # staff
    S = os.path.join(A, "Staff.glb")
    shot(S, "full:1.6,1.05,3.2,0,1.05,0;grip:0.30,1.07,0.50,0,1.07,0;guides:0.35,1.68,0.55,0,1.68,0;tip:0.3,2.0,0.5,0,1.98,0;butt:0.3,0.12,0.5,0,0.1,0", os.path.join(OUT, "_s"), "420x700", 30, ground=False)


def L(*p):
    return os.path.join(OUT, *p)


def img(p, crop=None):
    i = Image.open(p).convert("RGB")
    return i.crop(crop) if crop else i


def sheet(idx):
    r = L("_r")
    big = img(os.path.join(r, "hero.png"))
    parts = {}
    parts["front"] = caption(img(f"{r}/front.png"), "FRONT", "A-pose rest, 2.00 m")
    parts["side"] = caption(img(f"{r}/side.png"), "SIDE")
    parts["back"] = caption(img(f"{r}/back.png"), "BACK", "deep tan, sun-weathered")
    face = [caption(img(f"{r}/{k}.png"), t) for k, t in (("face", "FACE · front"), ("face34", "FACE · 3/4"), ("profile", "FACE · profile"))]
    hair = [caption(img(f"{r}/hair_back.png"), "HAIR · back, long, wild, sun-bleached"), caption(img(f"{r}/beard.png"), "BEARD & MOUSTACHE · bushy")]
    torso = [caption(img(f"{r}/torso.png"), "TORSO · lean, fit"), caption(img(f"{r}/torso34.png"), "TORSO · 3/4"), caption(img(f"{r}/back_t.png"), "BACK")]
    hands = [caption(img(f"{r}/handR.png"), "HAND · right (large, rough knuckles)"), caption(img(f"{r}/handL.png"), "HAND · left")]
    feet = caption(img(f"{r}/feet.png"), "FEET · bare, long, rough soles & toes")
    maro = [caption(img(f"{r}/maro_f.png"), "MARO · front"), caption(img(f"{r}/maro_b.png"), "MARO · back, frayed hem")]
    w = os.path.join(OUT, "_w")
    wires = [caption(img(f"{w}/wfront.png"), "WIREFRAME · LOD0 skin 46k tris"), caption(img(f"{w}/whead.png"), "WIREFRAME · head"), caption(img(f"{w}/whand.png"), "WIREFRAME · hand"),
             caption(img(f"{w}/whair.png"), "HAIR CARDS · 18k tris")]
    sd = os.path.join(OUT, "_s")
    staff = [caption(img(f"{sd}/full.png"), "STAFF · 2.10 m, pole + spear"), caption(img(f"{sd}/grip.png"), "grip wraps"), caption(img(f"{sd}/guides.png"), "lashed line guides"),
             caption(img(f"{sd}/tip.png"), "fire-hardened tip")]
    # pose strip from existing contact renders
    poses = [Image.open(L(f"pose_{n}.png")).convert("RGB") for n in ("walk", "run", "sit_idle", "fish_cast", "canoe_paddle", "tree_climb_up", "laugh_hearty", "dance_stomp") if os.path.exists(L(f"pose_{n}.png"))]
    # materials swatches
    tex = []
    base = os.path.join(ROOT, "build/castaway/textures")
    for f, t in (("skin_head_albedo.jpg", "skin head albedo"), ("skin_body_albedo.jpg", "skin body albedo"), ("skin_head_normal.jpg", "head normal"), ("skin_body_orm.png", "body ORM (AO/rough/metal)"),
                 ("hair_atlas.png", "hair card atlas (alpha)"), ("maro_albedo.png", "maro cloth"), ("eye_albedo.png", "eye (equirect)")):
        p = os.path.join(base, f)
        if os.path.exists(p):
            i = Image.open(p).convert("RGBA")
            bgc = Image.new("RGBA", i.size, (60, 64, 70, 255))
            i = Image.alpha_composite(bgc, i).convert("RGB")
            i.thumbnail((300, 300))
            tex.append(caption(i, t))
    cols = []
    H = 0
    top = tile([parts["front"], parts["side"], parts["back"]], 3)
    # layout
    W = 3560
    sheet_img = Image.new("RGB", (W, 3700), BG)
    d = ImageDraw.Draw(sheet_img)
    d.rectangle([0, 0, W, 120], fill=(20, 24, 28))
    d.text((40, 24), "THE CASTAWAY", font=font(60, True), fill=(235, 228, 214))
    d.text((600, 48), "Paradise Island · character reference sheet · rendered from the real GLB in Three.js (r186)", font=font(24), fill=(160, 170, 176))
    c = idx["counts"]
    stats = (f"2.00 m · skin 46.0k tris (LOD0) / 19.3k (LOD1) / 7.8k (lite) · hair+beard cards 18.5k · 110 joints · 2048² skin atlases (head, body) · "
             f"{c['total']} clips ({c['verified']} verified, {c['in_development']} in development) + {c['upper_variants']} upper-body layers")
    d.text((40, 90), stats, font=font(19), fill=(224, 164, 88))
    y0 = 140
    hero = caption(big, "HERO", "tropical sun / neutral studio")
    sheet_img.paste(hero, (30, y0))
    x = 30 + hero.width + 20
    sheet_img.paste(tile([parts["front"], parts["side"], parts["back"]], 3), (x, y0))
    y1 = y0 + 860
    sheet_img.paste(tile(face, 3), (30, y1 + 20))
    sheet_img.paste(tile(hair, 2), (30 + 3 * 570 + 20, y1 + 20))
    y2 = y1 + 700
    sheet_img.paste(tile(torso, 3), (30, y2))
    sheet_img.paste(tile(hands, 2), (30 + 3 * 570 + 20, y2))
    sheet_img.paste(feet, (x + 3 * 570 + 20, y0))      # free area right of the front/side/back row
    y3 = y2 + 760
    sheet_img.paste(tile(maro, 2), (30, y3))
    sheet_img.paste(tile(wires, 4), (30 + 2 * 570 + 20, y3))
    y4 = y3 + 700
    sheet_img.paste(tile(staff, 4), (30, y4))
    if poses:
        strip = tile(poses, 4)
        sheet_img.paste(strip.resize((min(strip.width, 1900), int(strip.height * min(strip.width, 1900) / strip.width))), (1800, y4))
    if tex:
        sheet_img.paste(tile(tex, 7), (30, y4 + 740))
    sheet_img = sheet_img.crop((0, 0, W, min(sheet_img.height, y4 + 740 + 360)))
    sheet_img.save(L("castaway_reference_sheet.png"), optimize=True)
    sheet_img.resize((W // 2, sheet_img.height // 2)).save(L("castaway_reference_sheet_small.jpg"), quality=88)
    print("[prev] reference sheet", sheet_img.size)


def uv_layouts():
    z = np.load(os.path.join(ROOT, "build/castaway/mesh.npz"))
    uv = z["uv"].astype(np.float64)
    F = z["F"]
    grp = z["group"]
    S = 1024
    outs = []
    for g, tag in ((0, "head"), (1, "body")):
        base = Image.open(os.path.join(ROOT, f"build/castaway/tex/skin_{tag}_albedo.png")).convert("RGB").resize((S, S))
        base = Image.blend(base, Image.new("RGB", (S, S), (20, 24, 28)), 0.55)
        d = ImageDraw.Draw(base)
        sel = np.nonzero(grp == g)[0]
        for fi in sel:
            p = uv[fi]                      # uv is (faces, 3, 2)
            pts = [(float(a[0]) * S, (1 - float(a[1])) * S) for a in p]
            d.line(pts + [pts[0]], fill=(120, 220, 170), width=1)
        outs.append(caption(base, f"UV layout · {tag} atlas 2048² ({len(sel):,} tris)"))
    t = tile(outs, 2)
    t.save(L("castaway_uv_layouts.png"), optimize=True)
    print("[prev] uv", t.size)


def atlases():
    base = os.path.join(ROOT, "build/castaway/textures")
    items = []
    import io
    sys.path.insert(0, HERE)
    import measure_glb as MG
    j, bin_ = MG.load(os.path.join(ROOT, "assets/castaway/Castaway.glb"))      # the packaged LOD0 GLB is the source of truth (build/castaway/textures is overwritten by LOD builds)
    emb = {}
    for im in j["images"]:
        bv = j["bufferViews"][im["bufferView"]]
        o = bv.get("byteOffset", 0)
        emb[im["name"]] = Image.open(io.BytesIO(bin_[o:o + bv["byteLength"]])).copy()
    for f, t in (("skin_head_albedo", "head · albedo"), ("skin_head_normal", "head · normal"), ("skin_head_orm", "head · ORM (R AO, G rough, B metal)"),
                 ("skin_body_albedo", "body · albedo"), ("skin_body_normal", "body · normal"), ("skin_body_orm", "body · ORM"),
                 ("hair_atlas", "hair/beard/brow strand atlas (RGBA)"), ("maro_albedo", "maro cloth albedo"), ("eye_albedo", "eye albedo")):
        src = emb[f]
        i = src.convert("RGBA")
        bgc = Image.new("RGBA", i.size, (60, 64, 70, 255))
        i = Image.alpha_composite(bgc, i).convert("RGB")
        i.thumbnail((620, 620))
        items.append(caption(i, t, f"{src.size[0]}×{src.size[1]}"))
    sd = os.path.join(ROOT, "build/castaway/staff_tex")
    for f, t in (("staff_wood_albedo.jpg", "staff wood albedo"), ("staff_wood_normal.jpg", "staff wood normal"), ("staff_cord_albedo.jpg", "staff cord albedo")):
        i = Image.open(os.path.join(sd, f)).convert("RGB")
        i.thumbnail((300, 620))
        items.append(caption(i, t, f"{Image.open(os.path.join(sd, f)).size[0]}×{Image.open(os.path.join(sd, f)).size[1]}"))
    t = tile(items, 4)
    t.save(L("castaway_texture_atlases.jpg"), quality=90)
    print("[prev] atlases", t.size)


def wire_sheet():
    w = os.path.join(OUT, "_w")
    t = tile([caption(img(f"{w}/wfront.png"), "WIRE · front"), caption(img(f"{w}/wside.png"), "WIRE · side"), caption(img(f"{w}/whead.png"), "WIRE · head 3/4"),
              caption(img(f"{w}/whead_f.png"), "WIRE · head front"), caption(img(f"{w}/whand.png"), "WIRE · hand"), caption(img(f"{w}/whair.png"), "HAIR CARDS wire")], 3)
    t.save(L("castaway_wireframes.png"), optimize=True)


def staff_sheet():
    sd = os.path.join(OUT, "_s")
    t = tile([caption(img(f"{sd}/{k}.png"), c) for k, c in (("full", "Staff.glb · 2.10 m"), ("grip", "main grip (1.07 m)"), ("guides", "line guides"), ("tip", "tip"), ("butt", "butt"))], 5)
    t.save(L("castaway_staff.png"), optimize=True)


# ------------------------------------------------------------------------------------------------ animation previews
def pose_stills(idx):
    """One representative still per clip used in the reference sheet (mid-clip), from the real pack GLBs via a temporary merged GLB."""
    import importlib
    sys.path.insert(0, HERE)
    import anim_pack
    import clipkit as CK
    names = ["walk", "run", "sit_idle", "fish_cast", "canoe_paddle", "tree_climb_up", "laugh_hearty", "dance_stomp"]
    for m in ("clips_locomotion", "clips_transitions", "clips_posture", "clips_staff", "clips_personality", "clips_survival", "clips_fishing", "clips_canoe", "clips_wildlife", "clips_climb"):
        importlib.import_module(m)
    bk = CK.bake_many(names, verbose=False)
    tmp = os.path.join(ROOT, "build/castaway/_preview_pose.glb")
    anim_pack.write_main(os.path.join(A, "Castaway.glb"), tmp, [bk[n] for n in names]) if False else anim_pack.write_main(os.path.join(ROOT, "build/castaway/Castaway_static.glb"), tmp, [bk[n] for n in names])
    for n in names:
        rec = idx["clips"][n]
        t = rec["duration_s"] * (0.35 if not rec["loop"] else 0.3)
        extra = []
        if n in ("fish_cast",) or rec["props"]["uses"] and "staff" in rec["props"]["uses"]:
            extra = ["build/castaway/Staff.glb@prop_staff"]
        if "paddle" in rec["props"]["uses"]:
            extra += ["build/castaway/props/Paddle.glb@prop_aux", "build/castaway/props/Canoe.glb"]
        if "palm" in rec["props"]["uses"]:
            extra += ["build/castaway/props/PalmTrunk.glb"]
        cam = {"canoe_paddle": "a:3.2,1.6,3.8,0,0.7,0", "tree_climb_up": "a:3.0,1.6,3.4,0,1.1,0.3"}.get(n, "a:2.9,1.25,4.3,0,0.95,0")
        shot(tmp, cam, os.path.join(OUT, "_p"), "440x640", 30, clip=n, times=[t], extra=",".join(extra) if extra else None)
        os.replace(os.path.join(OUT, "_p", "a.png"), L(f"pose_{n}.png"))
        i = Image.open(L(f"pose_{n}.png")).convert("RGB")
        caption(i, n, f"{rec['duration_s']:.1f}s").save(L(f"pose_{n}.png"))


def gifs(idx):
    import importlib
    sys.path.insert(0, HERE)
    import anim_pack
    import clipkit as CK
    for m in ("clips_locomotion", "clips_transitions", "clips_posture", "clips_staff", "clips_personality", "clips_survival", "clips_fishing", "clips_canoe", "clips_wildlife", "clips_climb"):
        importlib.import_module(m)
    names = ["walk", "run", "walk_staff", "fish_cast", "canoe_paddle", "tree_climb_up", "laugh_hearty", "dance_stomp", "spear_thrust", "wade"]
    bk = CK.bake_many(names, verbose=False)
    tmp = os.path.join(ROOT, "build/castaway/_preview_gif.glb")
    anim_pack.write_main(os.path.join(ROOT, "build/castaway/Castaway_static.glb"), tmp, [bk[n] for n in names])
    os.makedirs(L("gifs"), exist_ok=True)
    # turntable
    az = np.linspace(0, 2 * np.pi, 36, endpoint=False)
    views = ";".join(f"t{i:02d}:{5.3 * np.sin(a):.3f},1.15,{5.3 * np.cos(a):.3f},0,0.97,0" for i, a in enumerate(az))
    shot(os.path.join(ROOT, "build/castaway/Castaway_static.glb"), views, os.path.join(OUT, "_g"), "400x560", 28)
    fr = [Image.open(os.path.join(OUT, "_g", f"t{i:02d}.png")).convert("P", palette=Image.ADAPTIVE) for i in range(36)]
    fr[0].save(L("gifs", "castaway_turntable.gif"), save_all=True, append_images=fr[1:], duration=70, loop=0, optimize=True)
    for n in names:
        rec = idx["clips"][n]
        N = 24
        times = [rec["duration_s"] * i / N for i in range(N)] if rec["loop"] else [rec["duration_s"] * i / (N - 1) for i in range(N)]
        extra = []
        if "staff" in rec["props"]["uses"]:
            extra = ["build/castaway/Staff.glb@prop_staff"]
        if "paddle" in rec["props"]["uses"]:
            extra += ["build/castaway/props/Paddle.glb@prop_aux", "build/castaway/props/Canoe.glb"]
        if "palm" in rec["props"]["uses"]:
            extra += ["build/castaway/props/PalmTrunk.glb"]
        cam = {"canoe_paddle": "a:3.2,1.6,3.8,0,0.7,0", "tree_climb_up": "a:3.0,1.6,3.4,0,1.1,0.3"}.get(n, "a:2.9,1.25,4.3,0,0.95,0")
        shot(tmp, cam, os.path.join(OUT, "_g"), "360x500", 30, clip=n, times=times, extra=",".join(extra) if extra else None)
        fr = [Image.open(os.path.join(OUT, "_g", f"a_{i:02d}.png")).convert("P", palette=Image.ADAPTIVE) for i in range(N)]
        fr[0].save(L("gifs", f"{n}.gif"), save_all=True, append_images=fr[1:], duration=int(1000 * rec["duration_s"] / N), loop=0, optimize=True)
        print("[prev] gif", n)


def anim_sheets(idx):
    """Per-group contact sheets with the existing montage tool (real skinned GLB, one row per clip)."""
    groups = {}
    for n, r in idx["clips"].items():
        groups.setdefault(r["group"], []).append(n)
    os.makedirs(L("anim"), exist_ok=True)
    for g, ns in groups.items():
        for k in range(0, len(ns), 7):
            part = ns[k:k + 7]
            out = L("anim", f"anim_{g}_{k // 7 + 1}.jpg")
            subprocess.run([sys.executable, os.path.join(HERE, "montage.py"), out, *part, "--frames=5", "--views=a", "--size=230x320"], cwd=ROOT, check=True, capture_output=True)
            print("[prev] anim sheet", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="sheet,uv,atlas,wire,staff,anim,gifs")
    ap.add_argument("--install", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    idx = json.load(open(os.path.join(A, "castaway_clips.json")))
    only = a.only.split(",")
    if "sheet" in only or "wire" in only or "staff" in only:
        renders()
    if "sheet" in only:
        pose_stills(idx)
        sheet(idx)
    if "uv" in only:
        uv_layouts()
    if "atlas" in only:
        atlases()
    if "wire" in only:
        wire_sheet()
    if "staff" in only:
        staff_sheet()
    if "gifs" in only:
        gifs(idx)
    if "anim" in only:
        anim_sheets(idx)
    if a.install:
        import shutil
        dst = os.path.join(A, "previews")
        shutil.rmtree(dst, ignore_errors=True)
        os.makedirs(dst)
        for f in sorted(os.listdir(OUT)):
            p = os.path.join(OUT, f)
            if f.startswith("_") or f.startswith("pose_"):
                continue
            if os.path.isdir(p):
                shutil.copytree(p, os.path.join(dst, f))
            else:
                shutil.copy(p, dst)
        print("[prev] installed ->", dst)


if __name__ == "__main__":
    main()
