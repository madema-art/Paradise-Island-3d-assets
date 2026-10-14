"""Compact keypose authoring on top of params/rigkit: P() builds a pose from named parts, seq() interpolates, mk() wraps a clip fn.

Arms: FK vectors (fwd, out, twist, elbow, wrist flex, wrist dev) and/or IK hand targets (palm point, finger dir, palm normal, twist)
with a weight (0 = FK, 1 = IK, 'blend' arm mode). IK targets live in the clip's arm space (world / pelvis / chest / head) and are
given in REST-pose world coordinates of that space's bone (e.g. mouth = (0, -0.09, 1.795) in head space).
"""
import numpy as np

import clipkit as CK
import params as PR
import rigkit as RK
from clipkit import clip, keys, smooth, seg
from kin import unit
from rigkit import FT, ik_hand

TAU = 2 * np.pi
HZ, AZ = RK.HIP_Z, RK.ANKLE_Z

# landmarks in rest coordinates (x lateral +left, y = -forward, z up)
MOUTH = np.array([0.0, -0.09, 1.795])
NOSE = np.array([0.0, -0.11, 1.84])
CHIN = np.array([0.0, -0.075, 1.745])
EYES = np.array([0.0, -0.085, 1.877])
TOPHEAD = np.array([0.0, 0.0, 1.985])
NAPE = np.array([0.0, 0.07, 1.73])
SIDEHEAD_L = np.array([0.085, 0.01, 1.87])
SIDEHEAD_R = np.array([-0.085, 0.01, 1.87])
CHEST = np.array([0.0, -0.10, 1.50])
BELLY = np.array([0.0, -0.12, 1.22])
HIP_L = np.array([0.20, 0.0, 1.00])
HIP_R = np.array([-0.20, 0.0, 1.00])


def v3(x, f, z):
    """(lateral, forward, height) -> rest coordinates."""
    return np.array([x, -f, z], float)


def ik(pt, fd, pn, twist=0.0):
    return ik_hand(pt, unit(np.asarray(fd, float)), unit(np.asarray(pn, float)), twist)


def side_sign(side):
    return 1.0 if side == "L" else -1.0


def P(base=None, pel=None, sp=None, hd=None, eye=None, armL=None, armR=None, ikL=None, ikR=None, wL=None, wR=None, face=None,
      gL=None, gR=None, ftL=None, ftR=None, toeL=None, toeR=None, look=None, **kw):
    p = PR.copy(base) if base is not None else RK.stand()
    for sd in ("L", "R"):
        if not np.any(p[f"arm{sd}_ik"]):
            p[f"arm{sd}_ik"] = RK.hang_ik(sd)
    for k, v in (("pel", pel), ("sp", sp), ("hd", hd), ("eye", eye), ("armL", armL), ("armR", armR), ("ftL", ftL), ("ftR", ftR), ("toeL", toeL),
                 ("toeR", toeR)):
        if v is not None:
            p[k] = PR.update(p, **{k: v})[k]
    if ikL is not None:
        p["armL_ik"] = np.asarray(ikL, float)
        p["armL_w"] = np.array([1.0 if wL is None else wL])
    if ikR is not None:
        p["armR_ik"] = np.asarray(ikR, float)
        p["armR_w"] = np.array([1.0 if wR is None else wR])
    if wL is not None:
        p["armL_w"] = np.array([float(wL)])
    if wR is not None:
        p["armR_w"] = np.array([float(wR)])
    if face:
        for k, v in face.items():
            p["face"][PR.FACE_KEYS.index(k)] = v
    if gL is not None:
        p["fL"] = RK.G(gL) if isinstance(gL, str) else np.asarray(gL, float)
    if gR is not None:
        p["fR"] = RK.G(gR) if isinstance(gR, str) else np.asarray(gR, float)
    if look is not None:
        p["look"] = np.asarray(look, float)
    for k, v in kw.items():
        p[k] = np.asarray(v, float)
    return p


def mood(p, m=0.0):
    return RK.face_neutral(PR.copy(p), m)


def O(spL="world", spR="world", stance=(True, True), **kw):
    return dict(arm_mode=("blend", "blend"), arm_space=(spL, spR), stance=stance, **kw)


def seq(t, kf, ease="smooth"):
    return keys(t, kf, ease=ease)


def cyc(t, T):
    return (t % T) / T


def sw(t, T, ph=0.0):
    return float(np.sin(TAU * (t / T + ph)))


def blink_wrap(fn, seconds, seed, every=(2.6, 4.6)):
    return RK.with_blinks(fn, seconds, seed, every)


def mk(name, group, seconds, loop=False, blinks=True, seed=None, **meta):
    """Decorator: fn(t) -> (pose, opts); adds blinks and registers the clip."""
    def deco(fn):
        f = RK.with_blinks(fn, seconds, seed if seed is not None else (abs(hash(name)) % 997), every=(2.4, 4.4)) if blinks else fn
        clip(name, group, seconds, loop=loop, **meta)(f)
        return f
    return deco


def shake(t, f, amp, t0=0.0, t1=1e9, fade=0.15):
    """Oscillation at f Hz with soft onset/offset."""
    env = smooth(seg(t, t0, t0 + fade)) * (1.0 - smooth(seg(t, t1 - fade, t1)))
    return amp * env * np.sin(TAU * f * (t - t0))


def env(t, a, b, c, d):
    return float(CK.pulse(t, a, b, c, d))


def add(p, **kw):
    """Add offsets to parameter vectors (in place on a copy)."""
    p = PR.copy(p)
    for k, v in kw.items():
        v = np.asarray(v, float)
        p[k][:v.size] = p[k][:v.size] + v
    return p


def addf(p, **kw):
    p = PR.copy(p)
    for k, v in kw.items():
        p["face"][PR.FACE_KEYS.index(k)] += v
    return p
