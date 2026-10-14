"""Convert baked clips into glTF animation channels and write them into GLBs (main model and/or animation packs)."""
import copy
import os

import numpy as np

import clipkit as CK
from glb_tools import Glb, reduce_quat, reduce_vec, qmul_xyzw, swz_quat_wxyz, swz_vec
from pose_lib import RIG
from scipy.spatial.transform import Rotation as Rot

TOL_DEG = 0.12
TOL_M = 0.0003


def rest_nodes(glb):
    sk = RIG.sk
    rr, tt = [], []
    for n in sk.names:
        q, t = glb.rest_local(n)
        rr.append(q)
        tt.append(t)
    return np.array(rr), np.array(tt)


def channels_for(B, glb, rest=None, tol_deg=TOL_DEG, tol_m=TOL_M):
    sk = RIG.sk
    q0, t0 = rest or rest_nodes(glb)
    n = B.quat.shape[0]
    fps = CK.FPS
    times = np.arange(n) / fps
    quat = B.quat
    trans = B.trans
    if B.loop:                                     # close the loop with a copy of the first frame
        times = np.append(times, n / fps)
        quat = np.concatenate([quat, quat[:1]])
        trans = np.concatenate([trans, trans[:1]])
    chans = []
    stats = dict(keys_rot=0, keys_trans=0, tracks=0)
    for bi, name in enumerate(sk.names):
        qb = quat[:, bi][:, [1, 2, 3, 0]]                         # wxyz -> xyzw; node frames equal the Blender bone frames, so no axis swizzle
        qa = qmul_xyzw(np.broadcast_to(q0[bi], qb.shape), qb)
        # canonical sign continuity
        for i in range(1, len(qa)):
            if np.dot(qa[i], qa[i - 1]) < 0:
                qa[i] = -qa[i]
        idx = reduce_quat(times, qa, tol_deg)
        chans.append((name, "rotation", times[idx], qa[idx]))
        stats["keys_rot"] += len(idx)
        tb = trans[:, bi]
        if np.max(np.abs(tb)) > 1e-6:
            tg = tb                                                  # bone-local components are identical in both frames
            R0 = Rot.from_quat(q0[bi]).as_matrix()
            ta = t0[bi] + tg @ R0.T
            idx = reduce_vec(times, ta, tol_m)
            chans.append((name, "translation", times[idx], ta[idx]))
            stats["keys_trans"] += len(idx)
        stats["tracks"] += 1
    return chans, stats


def add_clips(glb, bakes, rest=None, extras_fn=None):
    rest = rest or rest_nodes(glb)
    tot = dict(keys_rot=0, keys_trans=0, tracks=0)
    for B in bakes:
        chans, st = channels_for(B, glb, rest)
        extras = extras_fn(B) if extras_fn else None
        glb.add_animation(B.name, chans, extras=extras)
        for k in tot:
            tot[k] += st[k]
    return tot


def strip_to_skeleton(glb):
    """Turn a model GLB into a skeleton-only GLB (nodes + names), ready to receive animations (an animation pack)."""
    j = glb.json
    for n in j["nodes"]:
        n.pop("mesh", None)
        n.pop("skin", None)
    for k in ("meshes", "skins", "materials", "textures", "images", "samplers", "accessors", "bufferViews", "extensionsUsed",
              "extensionsRequired", "animations"):
        j.pop(k, None)
    j["bufferViews"] = []
    j["accessors"] = []
    glb.bin = bytearray()
    return glb


def write_pack(main_static, out_path, bakes, extras_fn=None):
    glb = Glb(main_static)
    rest = rest_nodes(glb)
    strip_to_skeleton(glb)
    st = add_clips(glb, bakes, rest, extras_fn)
    glb.save(out_path)
    return st, os.path.getsize(out_path)


def write_main(main_static, out_path, bakes, extras_fn=None):
    glb = Glb(main_static)
    st = add_clips(glb, bakes, None, extras_fn)
    glb.save(out_path)
    return st, os.path.getsize(out_path)
