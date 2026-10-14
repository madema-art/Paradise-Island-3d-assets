"""
Pure-numpy kinematics for the castaway rig (no Blender needed while authoring animation).

Conventions (Blender armature space == modelling space): faces -Y, +X is his LEFT, +Z up.
  euler(pitch, roll, yaw) in degrees, composed as Rz(yaw) @ Ry(roll) @ Rx(pitch), about the *rest-frame world axes*:
     pitch  +  : rotate the forward-pointing end DOWN / bend forward / jaw opens
     roll   +  : lean to his LEFT (top toward +X)
     yaw    +  : turn to his LEFT
FK deltas are expressed relative to the parent's current orientation but about the rest-frame axes ("D" matrices).
Translations are given in world axes (character frame) relative to the rest position that follows the parent.

Math (Blender pose bones):  M_b = M_p . L_b . B_b   (L = rest local, B = pose basis = T(loc) R(quat) in bone space)
  world rotation  Rw_b = Q_p D_b Rrest_b      (Q_p = Rw_p Rrest_p^T, the parent's world delta)
  basis rotation  B_b  = Rrest_b^T D_b Rrest_b
"""
import json
import os

import numpy as np
from scipy.spatial.transform import Rotation as Rot

HERE = os.path.dirname(os.path.abspath(__file__))
I3 = np.eye(3)


def Rx(a):
    c, s = np.cos(np.radians(a)), np.sin(np.radians(a))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def Ry(a):
    c, s = np.cos(np.radians(a)), np.sin(np.radians(a))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def Rz(a):
    c, s = np.cos(np.radians(a)), np.sin(np.radians(a))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def euler(pitch=0.0, roll=0.0, yaw=0.0):
    return Rz(yaw) @ Ry(roll) @ Rx(pitch)


def axis_angle(axis, deg):
    a = np.asarray(axis, float)
    n = np.linalg.norm(a)
    if n < 1e-12 or abs(deg) < 1e-12:
        return I3.copy()
    return Rot.from_rotvec(a / n * np.radians(deg)).as_matrix()


def unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def frame(a, b):
    """Orthonormal frame with columns [a, b', a x b'] (b made perpendicular to a)."""
    a = unit(a)
    b = np.asarray(b, float) - a * (np.asarray(b, float) @ a)
    b = unit(b)
    return np.stack([a, b, np.cross(a, b)], axis=1)


class Skeleton:
    def __init__(self, path=None):
        path = path or os.path.join(HERE, "rest_pose.json")
        data = json.load(open(path))["bones"]
        order, seen = [], set()
        byname = {b["name"]: b for b in data}

        def visit(n):
            if n in seen:
                return
            p = byname[n]["parent"]
            if p:
                visit(p)
            seen.add(n)
            order.append(n)

        for b in data:
            visit(b["name"])
        self.names = order
        self.idx = {n: i for i, n in enumerate(order)}
        n = len(order)
        self.parent = np.array([self.idx[byname[b]["parent"]] if byname[b]["parent"] else -1 for b in order])
        self.head = np.array([byname[b]["head"] for b in order], float)
        self.tail = np.array([byname[b]["tail"] for b in order], float)
        self.Rrest = np.array([np.array(byname[b]["matrix"], float)[:3, :3] for b in order])
        self.length = np.linalg.norm(self.tail - self.head, axis=1)
        self.deform = np.array([byname[b]["deform"] for b in order])
        self.Lrot = np.zeros((n, 3, 3))
        self.Lpos = np.zeros((n, 3))
        for i in range(n):
            p = self.parent[i]
            if p < 0:
                self.Lrot[i] = self.Rrest[i]
                self.Lpos[i] = self.head[i]
            else:
                self.Lrot[i] = self.Rrest[p].T @ self.Rrest[i]
                self.Lpos[i] = self.Rrest[p].T @ (self.head[i] - self.head[p])
        self.n = n
        # rest-frame bone axes in world
        self.axis_rest = self.Rrest[:, :, 1]

    def i(self, name):
        return self.idx[name]

    def children(self, name):
        i = self.idx[name]
        return [self.names[j] for j in range(self.n) if self.parent[j] == i]

    # ---------------------------------------------------------------------------------------------- evaluation
    def evaluate(self, D, tw=None):
        """D: dict bone->3x3 delta (default identity). tw: dict bone->world-axis translation offset (3,).
        Returns Solved with world rotations/heads/tails and the Blender basis (rotation matrices + local translations)."""
        n = self.n
        Rw = np.zeros((n, 3, 3))
        Hw = np.zeros((n, 3))
        Q = np.zeros((n, 3, 3))
        B = np.zeros((n, 3, 3))
        T = np.zeros((n, 3))
        tw = tw or {}
        for i, name in enumerate(self.names):
            p = self.parent[i]
            Db = D.get(name, I3)
            if p < 0:
                Rw_p, H_p, Q_p = I3, np.zeros(3), I3
            else:
                Rw_p, H_p, Q_p = Rw[p], Hw[p], Q[p]
            Q[i] = Q_p @ Db
            Rw[i] = Q[i] @ self.Rrest[i]
            B[i] = self.Rrest[i].T @ Db @ self.Rrest[i]
            frame_p = Rw_p @ self.Lrot[i]                    # orientation of the bone before its own basis is applied
            off = tw.get(name)
            t_local = frame_p.T @ off if off is not None else np.zeros(3)
            T[i] = t_local
            if p < 0:
                Hw[i] = self.Lpos[i] + frame_p @ t_local
            else:
                Hw[i] = H_p + Rw_p @ self.Lpos[i] + frame_p @ t_local
        tail = Hw + np.einsum("nij,nj->ni", Rw, np.stack([np.zeros(n), self.length, np.zeros(n)], 1))
        return Solved(self, Rw, Hw, tail, Q, B, T)


class Solved:
    def __init__(self, sk, Rw, Hw, Tw, Q, B, T):
        self.sk, self.Rw, self.Hw, self.Tw, self.Q, self.B, self.T = sk, Rw, Hw, Tw, Q, B, T

    def head(self, name):
        return self.Hw[self.sk.idx[name]]

    def tail(self, name):
        return self.Tw[self.sk.idx[name]]

    def rot(self, name):
        return self.Rw[self.sk.idx[name]]

    def quats(self):
        """Basis rotations as (n,4) w,x,y,z."""
        q = Rot.from_matrix(self.B).as_quat()          # x,y,z,w
        q = np.concatenate([q[:, 3:4], q[:, :3]], axis=1)
        sign = np.where(q[:, 0:1] < 0, -1.0, 1.0)
        return q * sign


# --------------------------------------------------------------------------------------------------------------------
class TwoBoneIK:
    """Analytic two-bone IK with a pole vector, using the rest bend direction to keep the hinge orientation continuous."""

    def __init__(self, sk, upper, lower, end, fallback_pole):
        self.sk = sk
        self.upper, self.lower, self.end = upper, lower, end
        iu, il, ie = sk.i(upper), sk.i(lower), sk.i(end)
        self.S = sk.head[iu]
        self.E = sk.head[il]
        self.W = sk.head[ie]
        self.L1 = np.linalg.norm(self.E - self.S)
        self.L2 = np.linalg.norm(self.W - self.E)
        chord = unit(self.W - self.S)
        base = self.S + chord * ((self.E - self.S) @ chord)
        pp = self.E - base
        if np.linalg.norm(pp) < 1e-4:
            pp = np.asarray(fallback_pole, float)
        self.pole_rest = unit(pp - chord * (pp @ chord))
        self.n_rest = unit(np.cross(chord, self.pole_rest))
        self.a1_rest = unit(self.E - self.S)
        self.a2_rest = unit(self.W - self.E)
        self.F1_rest = frame(self.a1_rest, self.n_rest)
        self.F2_rest = frame(self.a2_rest, self.n_rest)

    def solve(self, S, T, pole, twist_deg=0.0):
        """Returns (Qu, Ql, Eworld, Tactual, miss). S shoulder/hip world pos, T target for the end joint."""
        d = np.linalg.norm(T - S)
        chord = unit(T - S)
        reach = self.L1 + self.L2 - 1e-4
        dmin = abs(self.L1 - self.L2) + 1e-3
        dc = min(max(d, dmin), reach)
        Tact = S + chord * dc
        miss = float(np.linalg.norm(T - Tact))
        pv = np.asarray(pole, float)
        if twist_deg:
            pv = axis_angle(chord, twist_deg) @ pv
        pp = pv - chord * (pv @ chord)
        if np.linalg.norm(pp) < 1e-6:
            pp = self.pole_rest - chord * (self.pole_rest @ chord)
        pp = unit(pp)
        a = (self.L1 ** 2 - self.L2 ** 2 + dc ** 2) / (2 * dc)
        h = np.sqrt(max(self.L1 ** 2 - a ** 2, 0.0))
        E = S + chord * a + pp * h
        u1, u2 = unit(E - S), unit(Tact - E)
        n_new = unit(np.cross(chord, pp))
        F1 = frame(u1, n_new)
        F2 = frame(u2, n_new)
        Qu = F1 @ self.F1_rest.T
        Ql = F2 @ self.F2_rest.T
        return Qu, Ql, E, Tact, miss


def twist_about(Rdelta, axis):
    """Twist angle (deg) of rotation matrix Rdelta about a unit axis (swing-twist decomposition)."""
    q = Rot.from_matrix(Rdelta).as_quat()   # x,y,z,w
    proj = float(np.dot(q[:3], unit(axis)))
    ang = 2.0 * np.degrees(np.arctan2(proj, q[3]))
    if ang > 180:
        ang -= 360
    if ang < -180:
        ang += 360
    return ang
