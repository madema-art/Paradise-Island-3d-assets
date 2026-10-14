"""Staff mounting transforms for the viewer / game: where the Staff.glb node sits inside a bone's local frame so the shaft is gripped by a hand
(or slung on the back). Node-local components equal the Blender bone-local components (no axis swizzle), so the values below can be used directly
as THREE.Object3D position / quaternion when the Staff root is parented to the named bone.

  /opt/bpy-venv/bin/python tools/castaway/export_grips.py [--out build/castaway/lib/castaway_grips.json]
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
import pose_lib as PL  # noqa: E402
import rigkit as RK  # noqa: E402
from kin import unit  # noqa: E402
from pose_lib import RIG  # noqa: E402

GRIP_Y = {"main": 1.07, "upper": 1.52, "low": 0.62, "mid": 1.05}


def quat(R):
    return [round(float(x), 6) for x in Rot.from_matrix(R).as_quat()]


def hand_mount(side, a_w, r_w, along):
    sk = RIG.sk
    n_w = -unit(r_w)
    d_w = unit(np.cross(a_w, n_w))
    F = PL.frame(d_w, n_w)
    D = F @ RIG.hand_rest[side]["F"].T          # hand rotation that realises this grip
    ib = sk.i(f"attach_hand_{side}")
    Rb = sk.Rrest[ib]
    a_l = Rb.T @ (D.T @ a_w)
    n_l = Rb.T @ (D.T @ n_w)
    z = unit(n_l)
    y = unit(a_l)
    x = unit(np.cross(y, z))
    R = np.stack([x, y, z], axis=1)
    p = n_l * (RK.HAND_OFFSET - 0.012) - R @ np.array([0.0, along, 0.0])
    return dict(bone=f"attach_hand_{side}", q=quat(R), p=[round(float(v), 5) for v in p])


def back_mount():
    sk = RIG.sk
    ib = sk.i("spine3")
    a_w = unit(np.array([0.34, 0.12, 0.93]))
    z_w = unit(np.array([0.0, 1.0, 0.0]) - a_w * (a_w[1]))
    x_w = unit(np.cross(a_w, z_w))
    Rw = np.stack([x_w, a_w, z_w], axis=1)
    Rl = sk.Rrest[ib].T @ Rw
    centre_w = np.array([-0.02, 0.15, 1.40])
    p = sk.Rrest[ib].T @ (centre_w - sk.head[ib]) - Rl @ np.array([0.0, 1.05, 0.0])
    return dict(bone="spine3", q=quat(Rl), p=[round(float(v), 5) for v in p])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "build/castaway/lib/castaway_grips.json"))
    a = ap.parse_args()
    up = np.array([0.0, 0.0, 1.0])
    out = dict(note="Parent the Staff root node to `bone`; set its position/quaternion to p/q. Shaft = Staff local +Y, guides side = local +Z.", grips={})
    for side, rx in (("R", 1.0), ("L", -1.0)):
        for gname, along in GRIP_Y.items():
            out["grips"][f"{side}_{gname}"] = hand_mount(side, up, np.array([rx, 0.0, 0.0]), along)
        out["grips"][f"{side}_over_horizontal"] = hand_mount(side, np.array([0.0, -1.0, 0.0]), np.array([0.0, 0.0, 1.0]), GRIP_Y["main"])
    out["grips"]["back_sling"] = back_mount()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(out, open(a.out, "w"), indent=1)
    print(f"[grips] {len(out['grips'])} mounts -> {a.out}")


if __name__ == "__main__":
    main()
