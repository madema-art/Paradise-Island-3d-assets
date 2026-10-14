"""Where do IK reach errors occur? python reach_diag.py clip [clip ...]  -> time, side, miss (mm), IK weight"""
import importlib, sys
import numpy as np
import clipkit as CK, params as PR
MODS = ["clips_locomotion", "clips_transitions", "clips_posture", "clips_staff", "clips_personality", "clips_survival", "clips_fishing", "clips_canoe", "clips_wildlife", "clips_climb"]
for m in MODS: importlib.import_module(m)
for name in sys.argv[1:]:
    spec = CK.CLIPS[name]; n, times = CK.frame_times(spec); rows = []
    for t in times[::3]:
        prm, opts = spec["fn"](t)
        p, sol = PR.finish(prm, arm_mode=opts.get("arm_mode", ("fk", "fk")), arm_space=opts.get("arm_space", ("world", "world")), stance=opts.get("stance", (False, False)), ground=opts.get("ground", 0.0))
        for k, v in p.report.items():
            if v > 0.02:
                rows.append((t, k, round(v * 1000)))
    rows.sort(key=lambda r: -r[2])
    print(name, "worst:", rows[:4], " first/last bad t:", (min(r[0] for r in rows), max(r[0] for r in rows)) if rows else None)
