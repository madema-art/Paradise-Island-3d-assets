"""Coarse whole-body signed distance sampler (trilinear) for collision pushes, AO and placement of hair/cloth."""
import os

import numpy as np
from scipy import ndimage

import hdesign
from hsdf import Grid

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CACHE = os.path.join(ROOT, "build", "castaway", "sdf_coarse.npz")


class Sampler:
    def __init__(self, bmin, voxel, field):
        self.bmin, self.voxel, self.field = np.asarray(bmin, float), float(voxel), field

    def dist(self, P):
        q = ((np.atleast_2d(P) - self.bmin) / self.voxel).T
        return ndimage.map_coordinates(self.field, q, order=1, mode="nearest")

    def grad(self, P, eps=0.003):
        P = np.atleast_2d(P)
        g = np.zeros_like(P)
        for a in range(3):
            o = np.zeros(3)
            o[a] = eps
            g[:, a] = (self.dist(P + o) - self.dist(P - o)) / (2 * eps)
        n = np.linalg.norm(g, axis=1, keepdims=True)
        return g / np.maximum(n, 1e-9)


def body_sampler(voxel=0.004, use_cache=True):
    if use_cache and os.path.exists(CACHE):
        z = np.load(CACHE)
        if abs(float(z["voxel"]) - voxel) < 1e-9:
            return Sampler(z["bmin"], voxel, z["field"])
    D = hdesign.build()
    lo, hi = hdesign.mesh_bounds(D, margin=0.08)
    g = Grid(lo, hi, voxel)
    for op, p, k in D.ops:
        g.apply(p, k, op)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    np.savez(CACHE, bmin=g.bmin, voxel=voxel, field=g.field)
    return Sampler(g.bmin, voxel, g.field)
