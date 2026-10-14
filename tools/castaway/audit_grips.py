"""QA: for every clip that holds a prop (staff/paddle) report how far each gripping hand is from the prop axis (ideal = palm offset 22 mm).
  /opt/bpy-venv/bin/python tools/castaway/audit_grips.py [clip ...]
"""
import importlib
import sys

import numpy as np

import clipkit as CK
import params as PR
from pose_lib import RIG
import rigkit as RK

MODS = ["clips_locomotion", "clips_transitions", "clips_posture", "clips_staff", "clips_personality", "clips_survival", "clips_fishing", "clips_canoe", "clips_wildlife", "clips_climb"]


def audit(name, step=3):
    spec = CK.CLIPS[name]
    n, times = CK.frame_times(spec)
    worst = {"R": 0.0, "L": 0.0}
    sk = RIG.sk
    prop = "prop_aux" if "paddle" in spec["meta"].get("props", []) else "prop_staff"
    for t in times[::step]:
        prm, opts = spec["fn"](t)
        p, sol = PR.finish(prm, arm_mode=opts.get("arm_mode", ("fk", "fk")), arm_space=opts.get("arm_space", ("world", "world")), stance=opts.get("stance", (False, False)),
                           ground=opts.get("ground", 0.0))
        pos, R = p.props[prop]
        axis = R @ np.array([0, 0, 1.0])
        root = np.asarray(p.root_pos, float)
        for sd in "RL":
            w = float(prm[f"arm{sd}_w"][0]) if opts.get("arm_mode", ("fk", "fk"))[0 if sd == "L" else 1] == "blend" else (1.0 if opts.get("arm_mode", ("fk", "fk"))[0 if sd == "L" else 1] == "ik" else 0.0)
            if w < 0.95:
                continue
            h = sol.head(f"attach_hand_{sd}") - root
            d = h - pos
            perp = np.linalg.norm(d - (d @ axis) * axis)
            along = d @ axis
            if -0.05 < along < 2.2:
                worst[sd] = max(worst[sd], abs(perp - 0.010))
    return worst


if __name__ == "__main__":
    for m in MODS:
        importlib.import_module(m)
    names = sys.argv[1:] or [n for n, s in CK.CLIPS.items() if (s["meta"].get("staff_use") or "paddle" in s["meta"].get("props", []) or "staff" in s["meta"].get("props", [])) and not n.startswith("_")]
    for n in names:
        w = audit(n)
        flag = "  <-- CHECK" if max(w.values()) > 0.05 else ""
        print(f"{n:24s} grip dev R {w['R'] * 1000:6.1f} mm  L {w['L'] * 1000:6.1f} mm{flag}")
