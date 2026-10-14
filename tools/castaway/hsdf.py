"""SDF helpers for the castaway: re-exports the shared toolkit from tools/monkey and adds frame-aligned primitives."""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MONKEY = os.path.join(os.path.dirname(HERE), "monkey")
if MONKEY not in sys.path:
    sys.path.insert(0, MONKEY)

from sdf import Ellipsoid, Grid, Prim, RoundCone, Sphere, rot_matrix, smax, smin  # noqa: E402,F401


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def frame_from(along, hint):
    """Orthonormal frame (columns a, b, c): a = along, b = hint projected perpendicular to a, c = a x b."""
    a = unit(along)
    b = np.asarray(hint, float) - a * (np.asarray(hint, float) @ a)
    b = unit(b)
    return np.stack([a, b, np.cross(a, b)], axis=1)


class FrameEllipsoid(Prim):
    """Ellipsoid with arbitrary orientation: radii (ra, rb, rc) along the frame columns."""

    def __init__(self, c, radii, frame):
        self.c = np.asarray(c, float)
        self.r = np.asarray(radii, float)
        self.R = np.asarray(frame, float)

    def bounds(self):
        half = np.sqrt(((self.R * self.r) ** 2).sum(axis=1))
        return self.c - half, self.c + half

    def dist(self, P):
        q = (P - self.c) @ self.R
        k0 = np.linalg.norm(q / self.r, axis=-1)
        k1 = np.linalg.norm(q / (self.r * self.r), axis=-1)
        return np.where(k1 > 1e-9, k0 * (k0 - 1.0) / np.maximum(k1, 1e-9), -self.r.min())


def ellipsoid_between(a, b, ra, rb, rc, hint=(1, 0, 0), t=0.5, off=(0, 0, 0)):
    """Ellipsoid whose long axis runs a->b. Centre at a + t(b-a) + off; radii: along = |b-a|/2*1.0 scaled by `ra` factor."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    c = a + (b - a) * t + np.asarray(off, float)
    half = np.linalg.norm(b - a) * 0.5
    return FrameEllipsoid(c, (half * ra, rb, rc), frame_from(b - a, hint))


class Loft(Prim):
    """Foot-like body lofted along the forward axis. Stations: f (forward, metres), centre x, half width, z bottom, z top.
    Blender convention: forward = -Y. Cross-sections are superellipses; ends are capped."""

    def __init__(self, stations, expo=2.4, round_end=0.012):
        st = np.asarray(stations, float)
        self.f, self.xc, self.w, self.zb, self.zt = st.T
        self.n = expo
        self.round_end = round_end

    def bounds(self):
        lo = np.array([(self.xc - self.w).min(), -self.f.max(), self.zb.min()])
        hi = np.array([(self.xc + self.w).max(), -self.f.min(), self.zt.max()])
        return lo, hi

    def dist(self, P):
        f = -P[..., 1]
        fc = np.clip(f, self.f[0], self.f[-1])
        xc = np.interp(fc, self.f, self.xc)
        w = np.interp(fc, self.f, self.w)
        zb = np.interp(fc, self.f, self.zb)
        zt = np.interp(fc, self.f, self.zt)
        zc, h = (zb + zt) * 0.5, (zt - zb) * 0.5
        qx = np.abs(P[..., 0] - xc) / w
        qz = np.abs(P[..., 2] - zc) / h
        r = (qx ** self.n + qz ** self.n) ** (1.0 / self.n)
        dxz = (r - 1.0) * np.minimum(w, h) * 0.95
        df = np.maximum(self.f[0] - f, f - self.f[-1])
        out = np.sqrt(np.maximum(dxz, 0) ** 2 + np.maximum(df, 0) ** 2)
        return out + np.minimum(np.maximum(dxz, df), 0.0)
