"""
Minimal signed-distance-field toolkit (numpy) used to sculpt the monkey procedurally.

Convention: negative inside, positive outside. Everything is in metres, Blender world axes.
Fields are evaluated only inside each primitive's bounding box, then folded into one
global grid with polynomial smooth min/max, so a full-body grid stays cheap.
"""
import numpy as np


def rot_matrix(rx=0.0, ry=0.0, rz=0.0):
    """World-from-local rotation, degrees, applied X then Y then Z."""
    rx, ry, rz = np.radians([rx, ry, rz])
    cx, sx, cy, sy, cz, sz = np.cos(rx), np.sin(rx), np.cos(ry), np.sin(ry), np.cos(rz), np.sin(rz)
    mx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    my = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    mz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return mz @ my @ mx


class Prim:
    bone = None      # bone this primitive deforms with (set by the design)
    name = ""

    def bounds(self):
        raise NotImplementedError

    def dist(self, P):
        raise NotImplementedError


class Sphere(Prim):
    def __init__(self, c, r):
        self.c = np.asarray(c, float)
        self.r = float(r)

    def bounds(self):
        return self.c - self.r, self.c + self.r

    def dist(self, P):
        return np.linalg.norm(P - self.c, axis=-1) - self.r


class Ellipsoid(Prim):
    """Ellipsoid with optional rotation (degrees). Uses the standard 1st-order distance bound."""

    def __init__(self, c, radii, rot=(0, 0, 0)):
        self.c = np.asarray(c, float)
        self.r = np.asarray(radii, float)
        self.R = rot_matrix(*rot)

    def bounds(self):
        half = np.sqrt(((self.R * self.r) ** 2).sum(axis=1))
        return self.c - half, self.c + half

    def dist(self, P):
        q = (P - self.c) @ self.R
        k0 = np.linalg.norm(q / self.r, axis=-1)
        k1 = np.linalg.norm(q / (self.r * self.r), axis=-1)
        return np.where(k1 > 1e-9, k0 * (k0 - 1.0) / np.maximum(k1, 1e-9), -self.r.min())


class RoundCone(Prim):
    """Capsule whose radius tapers linearly from ra at a to rb at b."""

    def __init__(self, a, b, ra, rb):
        self.a = np.asarray(a, float)
        self.b = np.asarray(b, float)
        self.ra, self.rb = float(ra), float(rb)
        self.ba = self.b - self.a
        self.baba = float(self.ba @ self.ba)

    def bounds(self):
        r = max(self.ra, self.rb)
        return np.minimum(self.a, self.b) - r, np.maximum(self.a, self.b) + r

    def dist(self, P):
        pa = P - self.a
        t = np.clip((pa @ self.ba) / self.baba, 0.0, 1.0)
        closest = self.a + t[..., None] * self.ba
        return np.linalg.norm(P - closest, axis=-1) - (self.ra + (self.rb - self.ra) * t)


def smin(a, b, k):
    if k <= 1e-9:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h * h * k * 0.25


def smax(a, b, k):
    if k <= 1e-9:
        return np.maximum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.maximum(a, b) + h * h * k * 0.25


class Grid:
    def __init__(self, bmin, bmax, voxel):
        self.bmin = np.asarray(bmin, float)
        self.voxel = float(voxel)
        self.shape = tuple(int(np.ceil((bmax[i] - bmin[i]) / voxel)) + 1 for i in range(3))
        self.field = np.full(self.shape, 1.0, np.float32)

    def _box(self, prim, pad):
        lo, hi = prim.bounds()
        i0 = np.maximum(np.floor((lo - pad - self.bmin) / self.voxel).astype(int), 0)
        i1 = np.minimum(np.ceil((hi + pad - self.bmin) / self.voxel).astype(int) + 1, self.shape)
        if np.any(i1 <= i0):
            return None
        return i0, i1

    def _points(self, i0, i1):
        ax = [self.bmin[a] + np.arange(i0[a], i1[a]) * self.voxel for a in range(3)]
        X, Y, Z = np.meshgrid(*ax, indexing="ij")
        return np.stack([X, Y, Z], axis=-1).astype(np.float32)

    def apply(self, prim, k=0.0, op="add"):
        box = self._box(prim, abs(k) + 2 * self.voxel)
        if box is None:
            return
        i0, i1 = box
        sl = tuple(slice(i0[a], i1[a]) for a in range(3))
        d = prim.dist(self._points(i0, i1)).astype(np.float32)
        cur = self.field[sl]
        if op == "add":
            self.field[sl] = smin(cur, d, k)
        elif op == "sub":
            self.field[sl] = smax(cur, -d, k)
        else:
            raise ValueError(op)

    def mesh(self):
        from skimage.measure import marching_cubes
        # Pad so surfaces touching the grid edge still close
        f = np.pad(self.field, 1, constant_values=1.0)
        verts, faces, _, _ = marching_cubes(f, level=0.0, spacing=(self.voxel,) * 3)
        verts = verts + self.bmin - self.voxel
        return verts.astype(np.float64), faces.astype(np.int64)
