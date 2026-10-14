"""
Clip registry, interpolation helpers, baking (pose -> per-bone basis arrays) and QA metrics.

A clip function takes t (seconds) and returns (params, opts):
    params : dict from params.base()/update()
    opts   : dict(arm_mode=('fk'|'ik', ...), arm_space=('world'|'pelvis'|'chest'|'head', ...), stance=(bool, bool),
                  world=dict(pos=(x,y,z), yaw=deg))   # world= the virtual root motion (metadata/QA only)
Registration: @clip("walk", group="locomotion", seconds=1.18, loop=True, speed=1.4, ...)
"""
import json
import os

import numpy as np

import params as PR
import secondary
from kin import Rz
from pose_lib import RIG, SIDES

FPS = 30
CLIPS = {}


def clip(name, group, seconds, loop=False, speed=None, root="inplace", desc="", **meta):
    def deco(fn):
        CLIPS[name] = dict(fn=fn, name=name, group=group, seconds=float(seconds), loop=bool(loop), speed=speed, root=root, desc=desc, meta=meta)
        return fn
    return deco


# ------------------------------------------------------------------------------------------------ interpolation
def smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def smoother(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * x * (x * (x * 6 - 15) + 10)


def seg(t, a, b):
    return float(np.clip((t - a) / (b - a), 0.0, 1.0)) if b != a else (1.0 if t >= b else 0.0)


def ease_io(x, p=2.0):
    x = np.clip(x, 0.0, 1.0)
    return x ** p / (x ** p + (1 - x) ** p)


def pulse(t, a, b, c, d):
    """0 -> 1 between a..b, hold to c, 1 -> 0 between c..d (smooth)."""
    return smooth(seg(t, a, b)) * (1.0 - smooth(seg(t, c, d)))


def keys(t, kf, cyclic=False, period=None, ease="smooth"):
    """Interpolate keyposes. kf: list of (time, params-dict). Catmull-Rom through the keys (clamped for non-cyclic)."""
    times = np.array([k[0] for k in kf], float)
    P = [k[1] for k in kf]
    n = len(kf)
    if cyclic:
        period = period or times[-1]
        t = t % period
        times = np.concatenate([times, [times[0] + period]])
        P = P + [P[0]]
        n += 1
    else:
        t = float(np.clip(t, times[0], times[-1]))
    i = int(np.clip(np.searchsorted(times, t, side="right") - 1, 0, n - 2))
    t0, t1 = times[i], times[i + 1]
    u = (t - t0) / max(t1 - t0, 1e-9)
    if ease == "smooth":
        u2 = smooth(u)
        return PR.mix(P[i], P[i + 1], u2)
    # Catmull-Rom (uniform)
    def at(j):
        if cyclic:
            return P[j % (n - 1)]
        return P[int(np.clip(j, 0, n - 1))]
    p0, p1, p2, p3 = at(i - 1), P[i], P[i + 1], at(i + 2)
    out = {}
    for k in p1:
        out[k] = 0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * u + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * u ** 2
                        + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * u ** 3)
    return out


def blend_add(a, b, w=1.0):
    """a + w*b (b treated as an additive offset set, same keys)."""
    return {k: a[k] + b[k] * w for k in a}


def zero_like(d):
    return {k: np.zeros_like(v) for k, v in d.items()}


def offset(**kw):
    """Additive parameter offsets (missing keys are zero)."""
    d = PR.DEFAULT()
    z = {k: np.zeros_like(v) for k, v in d.items()}
    for k, v in kw.items():
        v = np.asarray(v, float)
        nv = z[k].copy()
        nv[:v.size] = v.ravel()
        z[k] = nv
    return z


# ------------------------------------------------------------------------------------------------ baking
class Baked:
    def __init__(self, name, spec, n_frames, loop):
        self.name, self.spec, self.n, self.loop = name, spec, n_frames, loop
        self.quat = None       # (n_frames, nb, 4) wxyz Blender basis
        self.trans = None      # (n_frames, nb, 3)
        self.sols = []
        self.poses = []
        self.world = []        # per-frame (pos, yaw) virtual root
        self.metrics = {}


def frame_times(spec):
    n = int(round(spec["seconds"] * FPS))
    if spec["loop"]:
        return n, [i / FPS for i in range(n)]
    return n + 1, [i / FPS for i in range(n + 1)]


def bake(name, with_secondary=True, verbose=False):
    spec = CLIPS[name]
    n, times = frame_times(spec)
    sk = RIG.sk
    B = Baked(name, spec, n, spec["loop"])
    quats, trans, sols, poses = [], [], [], []
    for t in times:
        prm, opts = spec["fn"](t)
        p, sol = PR.finish(prm, arm_mode=opts.get("arm_mode", ("fk", "fk")), arm_space=opts.get("arm_space", ("world", "world")),
                           stance=opts.get("stance", (False, False)), ground=opts.get("ground", 0.0))
        sols.append(sol)
        poses.append(p)
        B.world.append(opts.get("world", dict(pos=(0, 0, 0), yaw=0.0)))
    if with_secondary:
        D_sec = secondary.simulate(sols, spec["loop"], floor=spec["meta"].get("floor", 0.012))
        sols = [PR_resolve(poses[i], D_sec[i]) for i in range(len(poses))]
    for sol in sols:
        quats.append(sol.quats())
        trans.append(sol.T.copy())
    B.quat, B.trans, B.sols, B.poses = np.array(quats), np.array(trans), sols, poses
    B.metrics = qa_metrics(B)
    return B


def PR_resolve(p, D_sec):
    D_extra = dict(getattr(p, "_extraD", {}))
    D_extra.update(D_sec)
    from pose_lib import solve
    return solve(p, extra_D=D_extra)


# ------------------------------------------------------------------------------------------------ QA metrics
def qa_metrics(B):
    sk = RIG.sk
    m = {}
    # IK misses
    miss = {}
    for p in B.poses:
        for k, v in p.report.items():
            miss[k] = max(miss.get(k, 0.0), v)
    m["reach_miss_mm"] = {k: round(v * 1000, 1) for k, v in miss.items()}
    # foot slide on stance feet (needs speed or world motion): contact point drift in WORLD coordinates
    from pose_lib import ground_points
    slide = {}
    for t_i, t in enumerate(SIDES):
        pts = []
        for f, sol in enumerate(B.sols):
            gp = ground_points(sol, t)
            w = B.world[f]
            wp = np.asarray(w["pos"], float)
            yaw = w["yaw"]
            ball = Rz(yaw) @ gp["ball"] + wp
            heel = Rz(yaw) @ gp["heel"] + wp
            pts.append((heel, ball))
        slide[t] = pts
    m["_contacts"] = slide
    # lowest point of any bone (ground penetration check)
    prim = np.array([sk.deform[i] and not sk.names[i].startswith(("hair_", "beard_", "cloth_", "lid_", "brow_", "lip_", "cheek_", "eye_"))
                     for i in range(sk.n)])
    lows = [min(sol.Hw[prim][:, 2].min(), sol.Tw[prim][:, 2].min()) for sol in B.sols]
    m["min_z"] = round(float(min(lows)), 3)
    return m


def foot_slide_report(B, thresh_z=0.012):
    """Max horizontal drift (mm) of a planted foot's ball/heel in world space over each contiguous stance interval."""
    out = {}
    for t in SIDES:
        pts = B.metrics["_contacts"][t]
        worst = 0.0
        run = []
        for heel, ball in pts + [(np.array([0, 0, 9.0]), np.array([0, 0, 9.0]))]:
            low = min(heel[2], ball[2]) < thresh_z
            if low:
                run.append((heel, ball))
            else:
                if len(run) > 2:
                    # use whichever point is on the ground for most of the run
                    for idx in (0, 1):
                        arr = np.array([r[idx] for r in run if r[idx][2] < thresh_z])
                        if len(arr) > 2:
                            worst = max(worst, float(np.linalg.norm(arr[:, :2] - arr[0, :2], axis=1).max()))
                run = []
        out[t] = round(worst * 1000, 1)
    return out


# ------------------------------------------------------------------------------------------------ parallel / cached baking
import hashlib
import pickle
import sys as _sys

CORE_MODULES = ["clipkit", "params", "pose_lib", "kin", "secondary", "rigkit", "staffkit", "posekit", "steps", "gaitkit", "pathgait", "hdesign"]


class BakedLite:
    """Pickleable result of a bake (no solved poses): everything the GLB writer, metadata and reports need."""

    def __init__(self, d):
        self.__dict__.update(d)
        self.sols, self.poses = [], []


def _src(mod):
    m = _sys.modules.get(mod)
    f = getattr(m, "__file__", None)
    return open(f, "rb").read() if f else b""


def clip_key(name):
    spec = CLIPS[name]
    h = hashlib.sha1()
    for m in CORE_MODULES:
        h.update(_src(m))
    h.update(_src(spec["fn"].__module__))
    h.update(name.encode())
    return h.hexdigest()[:16]


def _uses_prop(B, bone):
    sk = RIG.sk
    i = sk.i(bone)
    for p in B.poses:
        pos, R = p.props[bone]
        if np.linalg.norm(pos - sk.head[i]) > 1e-3 or abs(R[2, 2] - 1) > 1e-3:
            return True
    return False


def _bake_worker(args):
    name, cache_dir = args
    B = bake(name)
    d = dict(name=B.name, spec={k: v for k, v in B.spec.items() if k != "fn"}, n=B.n, loop=B.loop, quat=B.quat, trans=B.trans, world=B.world,
             metrics=B.metrics, staff_used=_uses_prop(B, "prop_staff"), aux_used=_uses_prop(B, "prop_aux"))
    with open(os.path.join(cache_dir, f"{name}.{clip_key(name)}.pkl"), "wb") as f:
        pickle.dump(d, f)
    return name


def bake_many(names, procs=4, cache_dir=None, verbose=True):
    """Bake clips in parallel with an on-disk cache (key = core sources + the clip's module source). Returns {name: BakedLite}."""
    import multiprocessing as mp
    root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    cache_dir = cache_dir or os.path.join(root, "build/castaway/bakecache")
    os.makedirs(cache_dir, exist_ok=True)
    todo = [n for n in names if not os.path.exists(os.path.join(cache_dir, f"{n}.{clip_key(n)}.pkl"))]
    if todo:
        if verbose:
            print(f"[bake] {len(todo)} clip(s) to bake, {len(names) - len(todo)} cached", flush=True)
        ctx = mp.get_context("fork")
        with ctx.Pool(min(procs, len(todo))) as pool:
            for n in pool.imap_unordered(_bake_worker, [(n, cache_dir) for n in todo]):
                if verbose:
                    print(f"[bake] done {n}", flush=True)
    out = {}
    for n in names:
        with open(os.path.join(cache_dir, f"{n}.{clip_key(n)}.pkl"), "rb") as f:
            d = pickle.load(f)
        spec = dict(CLIPS[n])
        d["spec"] = spec
        out[n] = BakedLite(d)
    return out
