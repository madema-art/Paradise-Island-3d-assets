"""
Generate the preview material in assets/monkey/previews/ (needs the packaged GLBs, node + playwright-core).

  python3 tools/monkey/make_previews.py --parts reference,poses,textures,turntable,gifs
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CAPTURE = os.path.join(ROOT, "viewer", "tests", "capture.mjs")
ASSETS = os.path.join(ROOT, "assets", "monkey")
OUT = os.path.join(ASSETS, "previews")
TMP = os.path.join(ROOT, "build", "monkey", "preview_tmp")
META = json.load(open(os.path.join(ASSETS, "monkey_clips.json")))


def font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def capture(clips, out, *extra):
    cmd = ["node", CAPTURE, "--clips", clips, "--out", out, *extra]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-800:], r.stderr[-800:])
        raise SystemExit("capture failed")
    return r.stdout


def label(im, text, size=18, pos=(12, 8), fill=(30, 36, 42)):
    ImageDraw.Draw(im).text(pos, text, font=font(size), fill=fill)


# ------------------------------------------------------------------ character reference sheet
def reference():
    d = os.path.join(TMP, "ref")
    shutil.rmtree(d, ignore_errors=True)
    q = "ground=0&bg=d9dee2&light=overcast"
    size = "560x470"
    views = [("Front", "Front"), ("Three-quarter front", "3/4"), ("Side (left)", "Side"), ("Back", "Back"), ("Top", "Top")]
    shots = {}
    for title, cam in views:
        capture("pose_stand", d, "--times", "0", "--cam", cam, "--size", size, "--query", q)
        src = os.path.join(d, f"pose_stand_{cam.replace('/', '')}_0.png")
        shots[title] = Image.open(src).convert("RGB")
        os.rename(src, os.path.join(d, f"v_{cam.replace('/', '')}.png"))
    closeups = [("Face · front", "0.0,0.33,0.78,0,0.31,0.44"), ("Face · three-quarter", "0.26,0.37,0.78,0,0.31,0.44"),
                ("Face · profile", "0.70,0.33,0.44,0,0.31,0.44"), ("Hands", "0.30,0.12,0.78,0.0,0.03,0.33"),
                ("Feet", "-0.42,0.14,-0.28,0.0,0.03,0.02"), ("Tail & haunch", "-0.55,0.35,-0.75,0,0.22,-0.2")]
    for title, cam in closeups:
        capture("pose_stand", d, "--times", "0", "--cam", "3/4", "--camera", cam, "--size", size, "--query", q)
        src = os.path.join(d, "pose_stand_34_0.png")
        shots[title] = Image.open(src).convert("RGB")
    W, H = 560, 470
    pad = 14
    head = 90
    sheet = Image.new("RGB", (pad + 5 * (W + pad), head + 2 * (H + pad + 24) + pad), (233, 236, 238))
    dr = ImageDraw.Draw(sheet)
    dr.text((pad, 14), "Paradise Island · Monkey · character reference", font=font(30), fill=(28, 34, 40))
    n_tri = sum(json.load(open(os.path.join(ASSETS, "validation", "Monkey_structure.json")))["triangles"] for _ in [0])
    info = json.load(open(os.path.join(ASSETS, "validation", "Monkey_structure.json")))
    dr.text((pad, 54), f"Long-tailed-macaque-like · ~0.46 m head-body, 0.95 m with tail · {info['triangles']:,} tris (LOD0) · "
            f"{info['skins'][0]} bones · 2048 albedo / normal / ORM · {len(META)} animation clips", font=font(17), fill=(70, 80, 88))
    for i, (title, _) in enumerate(views):
        x, y = pad + i * (W + pad), head
        sheet.paste(shots[title], (x, y + 24))
        dr.text((x + 4, y), title, font=font(16), fill=(28, 34, 40))
    for i, (title, _) in enumerate(closeups):
        x, y = pad + (i % 5) * (W + pad), head + (H + pad + 24)
        if i < 5:
            sheet.paste(shots[title], (x, y + 24))
            dr.text((x + 4, y), title, font=font(16), fill=(28, 34, 40))
    # sixth close-up goes under the first column of an extra slot on the right if there is room
    last_title = closeups[5][0]
    sheet.paste(shots[last_title].crop((0, 0, W, H)), (pad + 4 * (W + pad), head + (H + pad + 24) + 24)) if False else None
    os.makedirs(OUT, exist_ok=True)
    sheet.save(os.path.join(OUT, "character_reference_sheet.png"), optimize=True)
    # a second sheet for the tail close-up + rest of the detail
    print("[previews] character_reference_sheet.png", sheet.size)


# ------------------------------------------------------------------ pose sheets
GROUP_SHEETS = [
    ("idle_locomotion", "Idle & locomotion", ["idle", "alert_idle", "walk", "scurry", "turn_in_place_L", "turn_in_place_R", "hop", "branch_walk"]),
    ("climbing", "Climbing", ["climb_start", "climb_up", "climb_down", "climb_hang_idle", "climb_dismount"]),
    ("posture_behavior", "Posture & behaviour", ["sit_down", "sit_idle", "stand_up", "groom", "scratch", "look_around", "investigate", "curious", "startled"]),
    ("social", "Social", ["threat_display", "social_greet", "pose_present", "pose_threat", "pose_crouch", "pose_sit", "pose_stand"]),
    ("coconut", "Coconut", ["coconut_approach", "coconut_reach", "coconut_grab_lift", "coconut_hold_idle", "coconut_inspect", "coconut_guard",
                            "coconut_tug_holder", "coconut_tug_challenger", "coconut_triumph", "coconut_lose", "coconut_carry_walk", "pose_coconut_hold"]),
]


def poses(phases=6):
    d = os.path.join(TMP, "phases")
    shutil.rmtree(d, ignore_errors=True)
    capture("all", d, "--phases", str(phases), "--cam", "auto", "--size", "440x380")
    os.makedirs(os.path.join(OUT, "pose_sheets"), exist_ok=True)
    tile = 340
    for key, title, clips in GROUP_SHEETS:
        rows = []
        for c in clips:
            fs = sorted(glob.glob(os.path.join(d, f"{c}__*.png")))
            if not fs:
                continue
            ims = [Image.open(f).convert("RGB") for f in fs]
            if c.startswith("pose_"):                       # static poses: show one frame, wide
                ims = ims[:1]
            ims = [i.resize((tile, int(i.height * tile / i.width)), Image.LANCZOS) for i in ims]
            h = ims[0].height
            row = Image.new("RGB", (tile * phases, h), (28, 33, 38))
            for i, im in enumerate(ims):
                row.paste(im, (i * tile, 0))
            m = META.get(c, {})
            tag = f"{c}   {m.get('seconds', 0):.2f}s  {'loop' if m.get('loop') else 'one-shot'}" if not c.startswith("pose_") else f"{c}   (static pose)"
            ImageDraw.Draw(row).text((10, 8), tag, font=font(18), fill=(255, 255, 255))
            rows.append(row)
        # pack static poses (single tile) side by side to save space
        sheet = Image.new("RGB", (tile * phases, sum(r.height for r in rows)), (28, 33, 38))
        y = 0
        for r in rows:
            sheet.paste(r, (0, y))
            y += r.height
        sheet.save(os.path.join(OUT, "pose_sheets", f"{key}.jpg"), quality=90, optimize=True)
        print("[previews] pose_sheets", key, sheet.size)


# ------------------------------------------------------------------ textures + UV layout
def textures():
    import numpy as np
    src = os.path.join(ASSETS, "textures", "source")
    alb = Image.open(os.path.join(src, "monkey_albedo.png")).convert("RGB")
    nrm = Image.open(os.path.join(src, "monkey_normal.png")).convert("RGB")
    orm = Image.open(os.path.join(src, "monkey_orm.png")).convert("RGB")
    r, g, b = orm.split()
    ao = Image.merge("RGB", (r, r, r))
    rough = Image.merge("RGB", (g, g, g))
    mesh = np.load(os.path.join(ROOT, "build", "monkey", "mesh.npz"))
    uv = mesh["uv"]
    S = alb.width
    wire = Image.new("RGB", (S, S), (14, 17, 20))
    dr = ImageDraw.Draw(wire)
    for tri in uv:
        p = [(float(u) * S, (1.0 - float(v)) * S) for u, v in tri]
        dr.line([p[0], p[1], p[2], p[0]], fill=(120, 190, 160), width=1)
    over = Image.blend(alb.point(lambda x: int(x * 0.45)), wire, 0.5)
    over = Image.composite(wire, alb.point(lambda x: int(x * 0.5)), wire.convert("L").point(lambda x: 255 if x > 40 else 0))
    T = 640
    cols = [("Albedo (sRGB)", alb), ("Normal map (tangent space, OpenGL)", nrm), ("Ambient occlusion (ORM.R)", ao),
            ("Roughness (ORM.G)", rough), ("UV layout over albedo", over)]
    eye = Image.open(os.path.join(ASSETS, "textures", "eye_albedo.png")).convert("RGB").resize((T, T // 2), Image.LANCZOS)
    coco = Image.open(os.path.join(ASSETS, "textures", "coconut_albedo.jpg")).convert("RGB").resize((T, T // 2), Image.LANCZOS)
    pad, head = 12, 56
    sheet = Image.new("RGB", (pad + 3 * (T + pad), head + 2 * (T + 34 + pad)), (233, 236, 238))
    dr = ImageDraw.Draw(sheet)
    dr.text((pad, 14), "Monkey texture set · 2048² atlas, one UV set (UVMap), seams hidden by 3D-continuous painting", font=font(22), fill=(28, 34, 40))
    slots = cols + [("Eye (equirect, 512×256)", eye), ("Coconut albedo (512×256)", coco)]
    for i, (title, im) in enumerate(slots):
        x, y = pad + (i % 3) * (T + pad), head + (i // 3) * (T + 34 + pad)
        im = im.resize((T, T if im.height == im.width else T // 2), Image.LANCZOS)
        sheet.paste(im, (x, y + 28))
        dr.text((x + 2, y + 4), title, font=font(17), fill=(28, 34, 40))
    sheet.save(os.path.join(OUT, "texture_atlas_overview.png"), optimize=True)
    over.resize((1536, 1536), Image.LANCZOS).save(os.path.join(OUT, "uv_layout.png"), optimize=True)
    print("[previews] texture_atlas_overview.png, uv_layout.png")


# ------------------------------------------------------------------ turntable
def turntable(n=60):
    d = os.path.join(TMP, "turn")
    shutil.rmtree(d, ignore_errors=True)
    capture("idle", d, "--turntable", str(n), "--size", "420x420", "--dist", "1.45", "--height", "0.40", "--query", "light=studio")
    frames = [Image.open(f).convert("RGB") for f in sorted(glob.glob(os.path.join(d, "turn_*.png")))]
    os.makedirs(OUT, exist_ok=True)
    pal = [f.quantize(colors=96, method=Image.MEDIANCUT, dither=Image.NONE) for f in frames]
    pal[0].save(os.path.join(OUT, "turntable.gif"), save_all=True, append_images=pal[1:], duration=50, loop=0, optimize=True)
    print("[previews] turntable.gif", len(frames), os.path.getsize(os.path.join(OUT, "turntable.gif")) // 1024, "KB")
    ff = shutil.which("ffmpeg") or next(iter(glob.glob("/opt/pw-browsers/ffmpeg-*/ffmpeg-linux")), None)
    if ff:
        subprocess.run([ff, "-y", "-loglevel", "error", "-framerate", "20", "-i", os.path.join(d, "turn_%03d.png"),
                        "-c:v", "libvpx", "-b:v", "1.5M", "-pix_fmt", "yuv420p", os.path.join(OUT, "turntable.webm")], check=False)
        if os.path.exists(os.path.join(OUT, "turntable.webm")):
            print("[previews] turntable.webm", os.path.getsize(os.path.join(OUT, "turntable.webm")) // 1024, "KB")


# ------------------------------------------------------------------ animation GIFs
GIF_CLIPS = ["walk", "scurry", "climb_up", "alert_idle", "groom", "sit_down", "startled", "coconut_reach", "coconut_grab_lift",
             "coconut_tug_holder", "coconut_triumph", "coconut_lose", "threat_display", "coconut_carry_walk"]


def gifs(frames=22):
    d = os.path.join(TMP, "gif")
    shutil.rmtree(d, ignore_errors=True)
    capture(",".join(GIF_CLIPS), d, "--phases", str(frames), "--cam", "auto", "--size", "420x340")
    os.makedirs(os.path.join(OUT, "gifs"), exist_ok=True)
    for c in GIF_CLIPS:
        fs = sorted(glob.glob(os.path.join(d, f"{c}__*.png")))
        ims = [Image.open(f).convert("RGB") for f in fs]
        pal = [i.quantize(colors=80, method=Image.MEDIANCUT, dither=Image.NONE) for i in ims]
        dur = max(40, int(META[c]["seconds"] * 1000 / len(ims)))
        pal[0].save(os.path.join(OUT, "gifs", f"{c}.gif"), save_all=True, append_images=pal[1:], duration=dur, loop=0, optimize=True)
        print("[previews] gif", c, os.path.getsize(os.path.join(OUT, "gifs", f"{c}.gif")) // 1024, "KB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="reference,poses,textures,turntable,gifs")
    a = ap.parse_args()
    for part in a.parts.split(","):
        {"reference": reference, "poses": poses, "textures": textures, "turntable": turntable, "gifs": gifs}[part]()
