"""Face control table for the viewer / game: for every face control, the node-local rotation (xyzw) and translation deltas of the face bones at the
reference value (and at the negative reference for signed controls), computed by the same kinematics that bakes the clips. Also expression and viseme presets.

  /opt/bpy-venv/bin/python tools/castaway/export_face_controls.py [--out build/castaway/lib/castaway_face.json]
"""
import argparse
import json
import os
import sys

import numpy as np
from scipy.spatial.transform import Rotation as Rot

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
import anim_pack  # noqa: E402
import params as PR  # noqa: E402
import pose_lib as PL  # noqa: E402
import rigkit as RK  # noqa: E402
from glb_tools import Glb  # noqa: E402
from pose_lib import RIG  # noqa: E402

CONTROLS = [  # key, label, unit, ref (value giving "1.0"), min, max, signed
    ("jaw", "Jaw open", "deg", 20.0, 0.0, 1.5, False),
    ("jaw_side", "Jaw side (+ his left)", "deg", 8.0, -1.0, 1.0, True),
    ("jaw_fwd", "Jaw forward", "m", 0.010, 0.0, 1.0, False),
    ("smile_L", "Smile L", "0..1", 1.0, -0.5, 1.0, True),
    ("smile_R", "Smile R", "0..1", 1.0, -0.5, 1.0, True),
    ("frown", "Frown", "0..1", 1.0, 0.0, 1.0, False),
    ("pucker", "Pucker / whistle", "0..1", 1.0, 0.0, 1.0, False),
    ("lip_up", "Upper lip raise", "0..1", 1.0, -0.5, 1.0, True),
    ("lip_low", "Lower lip raise", "0..1", 1.0, -0.5, 1.0, True),
    ("brow_L", "Brow L raise", "0..1", 1.0, -0.6, 1.0, True),
    ("brow_R", "Brow R raise", "0..1", 1.0, -0.6, 1.0, True),
    ("furrow", "Brow furrow", "0..1", 1.0, 0.0, 1.0, False),
    ("blink_L", "Blink L", "0..1", 1.0, 0.0, 1.0, False),
    ("blink_R", "Blink R", "0..1", 1.0, 0.0, 1.0, False),
    ("wide", "Eyes wide", "0..1", 1.0, 0.0, 1.0, False),
    ("squint", "Squint", "0..1", 1.0, 0.0, 1.0, False),
    ("cheek", "Cheek raise", "0..1", 1.0, 0.0, 1.0, False),
]
EXTRA = [("eye_yaw", "Gaze yaw", "deg", 25.0, -1.0, 1.0, True), ("eye_pitch", "Gaze pitch", "deg", 20.0, -1.0, 1.0, True)]

PRESETS = {
    "neutral": {},
    "friendly": dict(smile_L=0.5, smile_R=0.4, cheek=0.3, brow_L=0.1, brow_R=0.2),
    "grin": dict(smile_L=1.0, smile_R=0.95, cheek=0.8, jaw=0.35, squint=0.3),
    "frown": dict(frown=0.8, furrow=0.5, brow_L=-0.2, brow_R=-0.2, lip_low=0.3),
    "anger": dict(frown=0.7, furrow=1.0, squint=0.5, jaw=0.2, lip_up=0.4),
    "surprise": dict(wide=1.0, brow_L=1.0, brow_R=1.0, jaw=0.6),
    "sad": dict(frown=0.6, brow_L=0.5, brow_R=0.3, furrow=0.3, lip_low=0.4),
    "laugh": dict(smile_L=1.0, smile_R=1.0, cheek=1.0, squint=0.8, jaw=0.9),
    "sun_squint": dict(squint=0.9, furrow=0.3, cheek=0.4),
    "whistle": dict(pucker=1.0, jaw=0.12),
    "smirk": dict(smile_L=0.8, smile_R=0.05, brow_R=0.5, cheek=0.2),
    "sleepy": dict(blink_L=0.8, blink_R=0.8, jaw=0.15),
}
VISEMES = {          # coarse mouth shapes for lip-sync (jaw is in units of 20 degrees)
    "sil": {},
    "AA": dict(jaw=0.9, lip_low=-0.2),
    "EE": dict(jaw=0.25, smile_L=0.6, smile_R=0.6, lip_up=0.3),
    "IH": dict(jaw=0.3, smile_L=0.3, smile_R=0.3),
    "OH": dict(jaw=0.5, pucker=0.6),
    "OO": dict(jaw=0.18, pucker=1.0),
    "FV": dict(jaw=0.12, lip_low=0.9, lip_up=0.2),
    "MBP": dict(jaw=0.0, lip_low=0.5, lip_up=-0.2, pucker=0.2),
    "TH": dict(jaw=0.2, lip_up=0.2),
    "L": dict(jaw=0.3, lip_up=0.1),
}


def pose_for(face=None, eye=(0.0, 0.0)):
    prm = RK.stand()
    for k, v in (face or {}).items():
        prm["face"][PR.FACE_KEYS.index(k)] = v
    prm["eye"] = np.array(eye, float)
    _, sol = PR.finish(prm, arm_mode=("fk", "fk"), stance=(True, True))
    return sol


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "build/castaway/lib/castaway_face.json"))
    ap.add_argument("--static", default=os.path.join(ROOT, "build/castaway/Castaway_static.glb"))
    a = ap.parse_args()
    glb = Glb(a.static)
    q0, t0 = anim_pack.rest_nodes(glb)
    sk = RIG.sk
    base = pose_for()
    bq0, bt0 = base.quats(), base.T

    def delta(sol):
        out = {}
        q, T = sol.quats(), sol.T
        for i, n in enumerate(sk.names):
            dq = Rot.from_quat(np.roll(q[i], -1)) * Rot.from_quat(np.roll(bq0[i], -1)).inv()
            ang = np.degrees(dq.magnitude())
            dt = T[i] - bt0[i]
            if ang > 0.02 or np.linalg.norm(dt) > 1e-5:
                R0 = Rot.from_quat(q0[i]).as_matrix()
                out[n] = dict(q=[round(float(x), 6) for x in np.roll(q[i], -1)], t=[round(float(x), 6) for x in (R0 @ dt)])
        return out

    ctrls = []
    for key, label, unit, ref, lo, hi, signed in CONTROLS + EXTRA:
        if key == "eye_yaw":
            pos, neg = delta(pose_for(eye=(ref, 0.0))), delta(pose_for(eye=(-ref, 0.0)))
        elif key == "eye_pitch":
            pos, neg = delta(pose_for(eye=(0.0, ref))), delta(pose_for(eye=(0.0, -ref)))
        else:
            pos = delta(pose_for({key: ref}))
            neg = delta(pose_for({key: -ref})) if signed else None
        ctrls.append(dict(key=key, label=label, unit=unit, reference_value=ref, min=lo, max=hi, signed=signed, pos=pos, neg=neg))
    # rest frame of the face bones (node-local) so the viewer can reset them every frame
    face_bones = sorted({b for c in ctrls for b in c["pos"]} | {b for c in ctrls if c["neg"] for b in c["neg"]})
    rest = {b: dict(q=[float(x) for x in q0[sk.i(b)]], t=[float(x) for x in t0[sk.i(b)]]) for b in face_bones}
    data = dict(
        note="Weights multiply the reference deltas: node rotation = clip_rotation * slerp(identity, q, w), node translation = clip_translation + w * t (node-local axes, "
             "the same frames as the baked clips). Signed controls use `neg` for w < 0.",
        controls=ctrls, face_bones=face_bones, rest=rest, presets=PRESETS, visemes=VISEMES)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(data, open(a.out, "w"), indent=1)
    print(f"[face] {len(ctrls)} controls, {len(face_bones)} bones -> {a.out} ({os.path.getsize(a.out) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
