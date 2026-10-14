"""Generate docs/CASTAWAY_ANIMATION_LIBRARY.md and assets/castaway/README.md from the packaged metadata (assets/castaway/castaway_clips.json + MANIFEST.json).

  python3 tools/castaway/make_docs.py
"""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
A = os.path.join(ROOT, "assets/castaway")
idx = json.load(open(os.path.join(A, "castaway_clips.json")))
man = json.load(open(os.path.join(A, "MANIFEST.json")))["files"]
C = idx["clips"]
TIERS = [("base_loop", "Base loops"), ("transition", "Transitions"), ("interaction_action", "Interaction actions"), ("emotional_reaction", "Emotional reactions"), ("personality_action", "Personality actions")]


def mb(n):
    return f"{n / 1e6:.2f} MB"


def row(n, r):
    rm = r["root_motion"]
    root = rm["type"] + (f" {rm['reference_speed_m_s']} m/s" if rm.get("reference_speed_m_s") else "") + (f" climb {rm['climb_speed_m_s']:.2f} m/s" if rm.get("climb_speed_m_s") else "")
    props = ", ".join(r["props"]["uses"]) or "-"
    st = "verified" if r["status"] == "verified" else "**in development**"
    return f"| `{n}` | {r['duration_s']:.2f} | {'loop' if r['loop'] else 'once'} | {st} | {root} | {props} | {r['description']} |"


def library_doc():
    L = []
    c = idx["counts"]
    L.append("# Castaway animation library\n")
    L.append(f"Generated from `assets/castaway/castaway_clips.json` by `tools/castaway/make_docs.py`. **{c['total']} clips** at 30 fps "
             f"(**{c['verified']} verified**, **{c['in_development']} in development**) plus **{c['upper_variants']} upper-body layer variants** (`<clip>__upper`).\n")
    L.append("Status rules: *verified* = reviewed frame by frame in skinned Three.js contact sheets of the real GLB **and** the automatic QA passes (IK reach error ≤ 25 mm, "
             "no bones more than 30 mm below the ground plane unless the clip is in water or a canoe, hands on the staff/paddle within tolerance). *In development* = authored and "
             "playable, with the issue listed in `status_note`.\n")
    L.append("## Conventions\n")
    for k, v in idx["conventions"].items():
        L.append(f"- **{k.replace('_', ' ')}**: {v}")
    L.append("\n## Animation packs\n")
    L.append("| File | Clips | Size |\n|---|---|---|")
    L.append(f"| `Castaway.glb` | model + {len(idx['core_clips'])} core clips ({', '.join(idx['core_clips'])}) | {mb(idx['files']['Castaway.glb'])} |")
    for k, p in idx["packs"].items():
        L.append(f"| `{p['file']}` | {len(p['clips'])} (+ upper-body layers) | {mb(p['bytes'])} |")
    L.append("\nPacks are skeleton-only GLBs: load the model once, then load a pack with `GLTFLoader` and pass `gltf.animations` to the `AnimationMixer` of the model "
             "(tracks bind by node name).\n")
    for tier, label in TIERS:
        ns = [n for n, r in C.items() if r["tier"] == tier]
        if not ns:
            continue
        L.append(f"## {label} ({len(ns)})\n")
        groups = {}
        for n in ns:
            groups.setdefault(C[n]["group"], []).append(n)
        for g, gn in groups.items():
            L.append(f"### {g}\n")
            L.append("| Clip | s | Play | Status | Root motion | Props | Description |\n|---|---|---|---|---|---|---|")
            for n in gn:
                L.append(row(n, C[n]))
            L.append("")
    dev = [(n, r) for n, r in C.items() if r["status"] != "verified"]
    L.append("## Clips in development\n")
    if dev:
        for n, r in dev:
            L.append(f"- `{n}`: {r['status_note']}")
    else:
        L.append("None.")
    L.append("")
    return "\n".join(L)


def readme():
    L = ["# Castaway (`assets/castaway/`)\n",
         "Rigged human castaway for Paradise Island: 2.00 m, lanky, lean and fit, deeply suntanned, with a long wild sun-bleached beard and hair, a frayed maro "
         "(loincloth) and bare chest/feet; a separate reusable walking staff / fishing pole / spear; 142 clips in animation packs. Built independently in this "
         "repository (Blender 5.2 `bpy` + numpy kinematics). **Not integrated into the game.**\n",
         "| File | What | Size |", "|---|---|---|"]
    desc = {"Castaway.glb": "Model (LOD0) + core clips (idle, walk, brisk walk, run)", "Castaway_lod1.glb": "LOD1: skin 19k tris, 1024² skin atlases, fewer hair cards", "Castaway_lite.glb": "Lite: skin 7.8k tris, 512² atlases, core hair cards",
            "Staff.glb": "Walking staff / fishing pole / spear (2.10 m) with attach empties, grip wraps, line guides, optional line + hook",
            "castaway_clips.json": "Machine-readable metadata for every clip", "castaway_face.json": "Face controls, expression and viseme presets", "castaway_grips.json": "Staff mount transforms (hands, back)",
            "castaway_bones.json": "Skeleton, bone groups, upper-body mask", "staff_points.json": "Staff attach points", "MANIFEST.json": "Hashes, sizes, triangle counts"}
    for f, r in sorted(man.items()):
        if f.startswith(("previews/", "validation/", "props/", "source/")):
            continue
        d = desc.get(f, "Animation pack (skeleton only)" if f.startswith("Castaway_anim_") else "")
        extra = f" · {r['triangles']:,} tris" if "triangles" in r and r["triangles"] else ""
        L.append(f"| `{f}` | {d}{extra} | {mb(r['bytes'])} |")
    L.append("| `props/*.glb` | Low-poly **proxy** props for viewer tests (canoe, paddle, boulder, rock, log, campfire, palm trunk): not final art | |")
    L.append("| `source/Castaway_rig.blend` | Editable rig/model source (bpy 5.2.2, images packed) | |")
    L.append("| `previews/` | Reference sheet, UV layouts, texture atlases, wireframes, staff sheet, turntable and clip GIFs, per-group animation contact sheets | |")
    L.append("| `validation/` | Structural + Khronos validator reports | |")
    L.append("\nSee `docs/CASTAWAY_ANIMATION_LIBRARY.md` (every clip), `docs/CASTAWAY_INTEGRATION.md` (how to wire it into a game) and `docs/CASTAWAY_HANDOFF.md` (rebuild + status).")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    open(os.path.join(ROOT, "docs/CASTAWAY_ANIMATION_LIBRARY.md"), "w").write(library_doc())
    open(os.path.join(A, "README.md"), "w").write(readme())
    print("docs written")
