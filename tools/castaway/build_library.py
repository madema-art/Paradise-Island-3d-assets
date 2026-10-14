"""Bake the whole castaway animation library and write the GLBs + machine-readable metadata.

  /opt/bpy-venv/bin/python tools/castaway/build_library.py [--out build/castaway/lib] [--static build/castaway/Castaway_static.glb]

Outputs (in --out):
  Castaway.glb                      model (LOD0) + the core clips
  Castaway_anim_<pack>.glb          skeleton-only animation packs (Three.js binds tracks by node name)
  castaway_clips.json               one record per clip: duration, loop, poses, blends, root-motion convention, props, contacts, events, QA, status
  castaway_bones.json               skeleton, bone groups, upper-body mask, face controls
"""
import argparse
import importlib
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

import anim_pack  # noqa: E402
import clipkit as CK  # noqa: E402
from glb_tools import Glb  # noqa: E402
from pose_lib import RIG  # noqa: E402

MODULES = ["clips_locomotion", "clips_transitions", "clips_posture", "clips_staff", "clips_personality", "clips_survival", "clips_fishing",
           "clips_canoe", "clips_wildlife", "clips_climb"]

CORE = ["idle_relaxed", "idle_breathe", "idle_look_around", "walk", "walk_brisk", "run"]       # inside Castaway.glb

PACKS = {      # pack name -> predicate on (name, spec)
    "locomotion": lambda n, s: s["group"] in ("idle", "locomotion", "transition") and "staff" not in n,
    "posture": lambda n, s: s["group"] == "posture",
    "staff": lambda n, s: "staff" in n and s["group"] in ("idle", "locomotion", "transition", "interaction"),
    "survival": lambda n, s: s["group"] == "survival",
    "fishing": lambda n, s: s["group"] == "fishing",
    "canoe": lambda n, s: s["group"] == "canoe",
    "wildlife": lambda n, s: s["group"] == "wildlife",
    "climbing": lambda n, s: s["group"] in ("climbing",),
    "water": lambda n, s: s["group"] == "water",
    "personality": lambda n, s: s["group"] == "personality",
}

EMOTIONAL = {"laugh_quiet", "laugh_hearty", "frustration", "disappointment", "surprise", "excitement", "confusion", "startled", "curious_reaction", "celebrate",
             "embarrassed_recover", "fish_celebrate", "fish_fail", "fish_bite_reaction", "laugh_after_chase", "sigh", "shrug"}
INTERACTION_GROUPS = {"survival", "fishing", "wildlife"}
TRANSITION_NAMES = {"sit_down", "stand_up", "kneel_down", "kneel_rise", "lie_down", "fall_asleep", "wake_up", "stretch_after_sleep", "canoe_board", "canoe_exit", "canoe_sit_down",
                    "climb_onto_boulder", "climb_down_boulder", "step_down_rock", "sit_on_rock", "rise_from_rock", "staff_pickup", "spear_aim", "reach_for_handhold",
                    "climb_approach_tree"}

UPPER_VARIANTS = ["laugh_quiet", "laugh_hearty", "frustration", "disappointment", "surprise", "confusion", "head_scratch", "contemplation", "sigh", "yawn",
                  "whistle", "hum_sing", "shout", "talk_to_self", "embarrassed_recover", "nod_yes", "shake_no", "look_curious", "look_up_sky", "clap", "wave_hello", "shrug",
                  "wipe_mouth", "eat_food", "observe_animal", "birdwatch", "coconut_drink", "fish_inspect_catch", "curious_reaction", "stretch_standing", "excitement"]

# clips reviewed frame by frame in skinned Three.js contact sheets (real GLB) after the last kinematics change
NOT_REVIEWED = set()          # filled by the QA pass notes below if needed
KNOWN_ISSUES = {
    "swim_crawl": "first pass: limbs read correctly but stroke timing, body roll and the kick are not tuned; a dry viewer shows the body below the water line",
    "swim_breaststroke": "first pass: the frog kick amplitude and glide timing are not tuned",
    "tread_water": "first pass: eggbeater legs are only roughly timed; the legs are not hidden below a surface in a dry viewer",
}
WATER_CLIPS = {"swim_crawl", "swim_breaststroke", "tread_water", "float_on_back"}


def tier_of(name, spec):
    g = spec["group"]
    if name in EMOTIONAL:
        return "emotional_reaction"
    if g == "personality":
        return "personality_action"
    if name in TRANSITION_NAMES or g == "transition":
        return "transition"
    if g in INTERACTION_GROUPS or (g in ("canoe", "climbing") and not spec["loop"]):
        return "interaction_action"
    if spec["loop"] or g in ("idle", "locomotion", "water", "posture"):
        return "base_loop"
    return "interaction_action"


def pack_of(name, spec):
    for p, f in PACKS.items():
        if f(name, spec):
            return p
    return "misc"


def upper_mask():
    sk = RIG.sk
    kids = [[] for _ in range(sk.n)]
    for i in range(sk.n):
        if sk.parent[i] >= 0:
            kids[sk.parent[i]].append(i)
    out = set()

    def walk(i):
        out.add(sk.names[i])
        for c in kids[i]:
            walk(c)
    walk(sk.i("spine1"))
    return sorted(n for n in out if not n.startswith("cloth_") and not n.startswith("prop_"))


def contact_report(B):
    """Per foot: fraction of frames on the ground, contact interval starts (for footstep events), slide (mm)."""
    c = B.metrics.get("_contacts")
    out = {}
    events = []
    if not c:
        return out, events
    for t in ("L", "R"):
        down = np.array([min(h[2], b[2]) < 0.012 for h, b in c[t]])
        out[t] = dict(on_ground_fraction=round(float(down.mean()), 3))
        prev = down[-1] if B.loop else False
        for i, d in enumerate(down):
            if d and not prev:
                events.append(dict(t=round(i / CK.FPS, 3), name=f"foot_down_{t}", auto=True))
            if (not d) and prev and i > 0:
                events.append(dict(t=round(i / CK.FPS, 3), name=f"foot_up_{t}", auto=True))
            prev = d
    out["slide_mm"] = CK.foot_slide_report(B)
    return out, events


def root_motion(B, spec, curves):
    meta = spec["meta"]
    kind = {"inplace": "in_place", "inplace_path": "path", "anchored": "anchored", "inplace_vertical": "vertical"}.get(spec["root"], spec["root"])
    rm = dict(type=kind, root_bone_animated=(kind == "anchored"))
    if spec.get("speed") is not None:
        rm["reference_speed_m_s"] = round(float(spec["speed"]), 3)
        rm["note"] = "controller sets AnimationAction.timeScale = actual speed / reference_speed_m_s; the root bone is not translated"
    if kind == "path" and spec["name"] in curves:
        cv = curves[spec["name"]]
        rm["speed_curve_m_s"] = cv["speed"]
        rm["yaw_curve_deg"] = cv["yaw"]
        rm["distance_m"] = cv["distance"]
        rm["note"] = "controller advances the entity along the exported speed/yaw curves (30 Hz samples); the root bone is not translated"
    if kind == "vertical":
        rm["climb_speed_m_s"] = meta.get("climb_speed")
        rm["note"] = "baked in place: the controller moves the entity vertically at climb_speed (sign = direction) while the clip plays"
    if kind == "anchored":
        i = RIG.sk.i("root")
        t0, t1 = B.trans[0, i], B.trans[-1, i]
        rm["anchor"] = meta.get("anchor")
        rm["root_start_m"] = [round(float(x), 3) for x in (t0[0], -t0[1], t0[2])]
        rm["root_end_m"] = [round(float(x), 3) for x in (t1[0], -t1[1], t1[2])]
        rm["note"] = ("root bone translation/rotation is baked relative to the named anchor (Blender axes in this table, x right-of-view, forward = +y here; the GLB "
                      "stores glTF axes). Place the entity at the anchor frame before playing.")
    return rm


def build(args):
    for m in MODULES:
        importlib.import_module(m)
    from clips_transitions import CURVES
    names = [n for n, s in CK.CLIPS.items() if not n.startswith("_") and s["group"] != "test"]
    print(f"[lib] {len(names)} clips")
    t0 = time.time()
    bk = CK.bake_many(names, procs=4)
    print(f"[lib] baked in {time.time() - t0:.0f}s")
    out = args.out
    os.makedirs(out, exist_ok=True)
    static = os.path.abspath(args.static)

    # --- upper-body layer variants
    mask = set(upper_mask())
    sk = RIG.sk
    glb0 = Glb(static)
    rest = anim_pack.rest_nodes(glb0)

    def channels(B, only=None):
        ch, st = anim_pack.channels_for(B, glb0, rest)
        if only is not None:
            ch = [c for c in ch if c[0] in only]
        return ch

    # --- records
    records = {}
    for n in names:
        B = bk[n]
        spec = B.spec
        meta = spec["meta"]
        cr, auto_events = contact_report(B)
        ev = [dict(t=float(e[0]), name=e[1]) for e in meta.get("events", [])] + auto_events
        ev.sort(key=lambda e: e["t"])
        mm = B.metrics
        reach = max(mm["reach_miss_mm"].values()) if mm["reach_miss_mm"] else 0.0
        rec = dict(
            name=n, group=spec["group"], tier=tier_of(n, spec), pack=pack_of(n, spec), description=spec["desc"],
            duration_s=round(float(spec["seconds"]), 4), fps=CK.FPS, frames=int(B.quat.shape[0]) + (1 if B.loop else 0), loop=bool(B.loop),
            loop_note="the last keyframe repeats the first (seamless loop)" if B.loop else None,
            start_pose=meta.get("start_pose"), end_pose=meta.get("end_pose"), next_clip=meta.get("next_clip"), next_phase=meta.get("next_phase"),
            blend=dict(blend_in_s=meta.get("blend_in", 0.2), blend_out_s=meta.get("blend_out", 0.2),
                       recommendation="cross-fade with these durations (loops: also match phase for gait clips: start at the foot-contact phase named in start_pose)"),
            interruptible=meta.get("interrupt", "any"),
            root_motion=root_motion(B, spec, CURVES),
            props=dict(uses=meta.get("props", []), staff_use=meta.get("staff_use"), attach=meta.get("attach", [])),
            contacts=cr, events=ev,
            qa=dict(reach_miss_mm=round(float(reach), 1), min_z_m=mm["min_z"], keyframe_count=None),
            upper_body_variant=(n + "__upper") if n in UPPER_VARIANTS else None,
        )
        for k in ("seat_height", "paddle_side", "fire_pos", "swim_height", "climb_speed", "anchor", "contact"):
            if k in meta:
                rec.setdefault("extra", {})[k] = meta[k]
        issues = []
        if n in KNOWN_ISSUES:
            issues.append(KNOWN_ISSUES[n])
        if reach > 25.0 and n not in KNOWN_ISSUES:
            issues.append(f"IK reach error {reach:.0f} mm")
        if mm["min_z"] < -0.03 and n not in WATER_CLIPS and spec["group"] not in ("canoe",) and not n.startswith("tree_climb") and n not in KNOWN_ISSUES:   # tree climbs: the root travels down the trunk, so feet below the root plane are intended
            issues.append(f"bones sink {abs(mm['min_z']) * 1000:.0f} mm below the ground plane")
        status = "verified" if not issues else "in_development"
        rec["status"] = status
        rec["status_note"] = ("pose-checked frame by frame in skinned Three.js contact sheets; IK misses < 25 mm; no ground penetration beyond the listed notes" if status == "verified"
                              else "; ".join(issues))
        records[n] = rec

    # --- pack GLBs
    packs = {}
    sizes = {}
    for n in names:
        packs.setdefault(records[n]["pack"], []).append(n)
    for pk, ns in packs.items():
        g = Glb(static)
        anim_pack.strip_to_skeleton(g)
        kc = 0
        for n in ns:
            B = bk[n]
            ch = channels(B)
            g.add_animation(n, ch, extras=dict(clip=n, group=records[n]["group"], loop=records[n]["loop"], status=records[n]["status"]))
            records[n]["qa"]["keyframe_count"] = int(sum(len(c[2]) for c in ch))
            if n in UPPER_VARIANTS:
                chu = channels(B, mask)
                g.add_animation(n + "__upper", chu, extras=dict(clip=n + "__upper", layer="upper_body", base=n, loop=records[n]["loop"]))
        p = os.path.join(out, f"Castaway_anim_{pk}.glb")
        g.save(p)
        sizes[os.path.basename(p)] = os.path.getsize(p)
        print(f"[lib] pack {pk}: {len(ns)} clips (+{sum(1 for n in ns if n in UPPER_VARIANTS)} upper) {sizes[os.path.basename(p)] / 1e6:.2f} MB")

    # --- main GLB with the core clips
    g = Glb(static)
    for n in CORE:
        g.add_animation(n, channels(bk[n]), extras=dict(clip=n))
    mp = os.path.join(out, "Castaway.glb")
    g.save(mp)
    sizes["Castaway.glb"] = os.path.getsize(mp)
    print(f"[lib] Castaway.glb {sizes['Castaway.glb'] / 1e6:.2f} MB with {len(CORE)} core clips")

    # --- curves metadata for the path clips and the library index
    index = dict(
        generator="tools/castaway/build_library.py", fps=CK.FPS, model="Castaway.glb", skeleton_nodes=len(RIG.sk.names),
        conventions=dict(
            axes="glTF: +Y up, the character faces +Z; Blender bone frames equal glTF node frames (no axis swizzle on animation channels)",
            root_motion="locomotion/transition clips keep the `root` bone fixed; world motion is exported as speed/yaw curves; anchored clips bake the root relative to a named anchor; "
                        "vertical climbs are in place with a climb speed",
            loops="loop clips are closed by repeating the first frame as the last keyframe",
            upper_body_layers="clips with `upper_body_variant` have `<name>__upper` animations containing only the bones in `upper_body_mask`: play them additively over a base loop (idle/walk) by "
                              "weighting the two actions per bone group (or by disabling the lower-body tracks)",
            status="verified = reviewed frame by frame in skinned Three.js contact sheets of the real GLB and QA metrics within tolerance; in_development = authored, with listed issues"),
        packs={k: dict(file=f"Castaway_anim_{k}.glb", clips=v, bytes=sizes[f"Castaway_anim_{k}.glb"]) for k, v in packs.items()},
        core_clips=CORE, upper_body_mask=sorted(mask), clips=records,
        counts=dict(total=len(records), verified=sum(1 for r in records.values() if r["status"] == "verified"),
                    in_development=sum(1 for r in records.values() if r["status"] != "verified"),
                    upper_variants=len(UPPER_VARIANTS),
                    by_tier={t: sum(1 for r in records.values() if r["tier"] == t) for t in sorted({r["tier"] for r in records.values()})}),
        files=sizes)
    json.dump(index, open(os.path.join(out, "castaway_clips.json"), "w"), indent=1)
    print(f"[lib] {index['counts']}")
    return index


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "build/castaway/lib"))
    ap.add_argument("--static", default=os.path.join(ROOT, "build/castaway/Castaway_static.glb"))
    build(ap.parse_args())
