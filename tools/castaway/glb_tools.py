"""
Minimal GLB reader/writer used to (a) patch materials that Blender's exporter cannot express (alphaMode MASK, doubleSided,
extensions), (b) append skeletal animations computed by the numpy kinematics, split into animation packs.

Blender -> glTF axis conversion used by the exporter: (x, y, z)_blender -> (x, z, -y)_gltf. Bone local transforms are
conjugated by that swizzle, so for a bone with rest node transform (q0, t0) and Blender basis (q_b, t_b):
    q_anim = q0 * swz(q_b)        t_anim = t0 + R(q0) * swz(t_b)
"""
import json
import struct

import numpy as np
from scipy.spatial.transform import Rotation as Rot, Slerp

MAGIC = 0x46546C67
JSON_T = 0x4E4F534A
BIN_T = 0x004E4942


def swz_vec(v):
    v = np.asarray(v, float)
    return np.stack([v[..., 0], v[..., 2], -v[..., 1]], axis=-1)


def swz_quat_wxyz(q):
    """Blender quaternion (w, x, y, z) -> glTF quaternion (x, y, z, w) with the axis swizzle applied."""
    q = np.asarray(q, float)
    return np.stack([q[..., 1], q[..., 3], -q[..., 2], q[..., 0]], axis=-1)


def qmul_xyzw(a, b):
    ax, ay, az, aw = np.moveaxis(a, -1, 0)
    bx, by, bz, bw = np.moveaxis(b, -1, 0)
    return np.stack([aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw,
                     aw * bw - ax * bx - ay * by - az * bz], axis=-1)


class Glb:
    def __init__(self, path):
        data = open(path, "rb").read()
        magic, version, length = struct.unpack_from("<III", data, 0)
        assert magic == MAGIC and version == 2
        off = 12
        self.json = None
        self.bin = b""
        while off < length:
            clen, ctype = struct.unpack_from("<II", data, off)
            chunk = data[off + 8: off + 8 + clen]
            if ctype == JSON_T:
                self.json = json.loads(chunk.decode("utf8"))
            elif ctype == BIN_T:
                self.bin = bytearray(chunk)
            off += 8 + clen
        self.bin = bytearray(self.bin)
        self.node_by_name = {n.get("name"): i for i, n in enumerate(self.json["nodes"])}

    # ------------------------------------------------------------------------------------------- binary helpers
    def _align(self):
        while len(self.bin) % 4:
            self.bin.append(0)

    def add_accessor(self, arr, typ, minmax=False):
        arr = np.ascontiguousarray(arr, dtype=np.float32)
        self._align()
        off = len(self.bin)
        self.bin += arr.tobytes()
        bv = {"buffer": 0, "byteOffset": off, "byteLength": arr.nbytes}
        self.json["bufferViews"].append(bv)
        acc = {"bufferView": len(self.json["bufferViews"]) - 1, "componentType": 5126, "count": int(arr.shape[0]), "type": typ}
        if minmax:
            a2 = arr.reshape(arr.shape[0], -1)
            acc["min"] = [float(x) for x in a2.min(axis=0)]
            acc["max"] = [float(x) for x in a2.max(axis=0)]
        self.json.setdefault("accessors", []).append(acc)
        return len(self.json["accessors"]) - 1

    def add_animation(self, name, channels, extras=None):
        """channels: list of (node_name, path ('rotation'|'translation'), times (n,), values (n,4|3))"""
        anim = {"name": name, "samplers": [], "channels": []}
        cache = {}
        for node, path, times, values in channels:
            key = id(times)
            if key not in cache:
                cache[key] = self.add_accessor(times, "SCALAR", minmax=True)
            out = self.add_accessor(values, "VEC4" if path == "rotation" else "VEC3")
            anim["samplers"].append({"input": cache[key], "output": out, "interpolation": "LINEAR"})
            anim["channels"].append({"sampler": len(anim["samplers"]) - 1, "target": {"node": self.node_by_name[node], "path": path}})
        if extras:
            anim["extras"] = extras
        self.json.setdefault("animations", []).append(anim)

    # ------------------------------------------------------------------------------------------- node helpers
    def rest_local(self, name):
        n = self.json["nodes"][self.node_by_name[name]]
        return np.array(n.get("rotation", [0, 0, 0, 1]), float), np.array(n.get("translation", [0, 0, 0]), float)

    def material(self, name):
        for m in self.json["materials"]:
            if m.get("name") == name:
                return m
        raise KeyError(name)

    def save(self, path):
        js = dict(self.json)
        js["buffers"] = [{"byteLength": len(self.bin)}]
        jb = json.dumps(js, separators=(",", ":")).encode("utf8")
        while len(jb) % 4:
            jb += b" "
        self._align()
        total = 12 + 8 + len(jb) + 8 + len(self.bin)
        with open(path, "wb") as f:
            f.write(struct.pack("<III", MAGIC, 2, total))
            f.write(struct.pack("<II", len(jb), JSON_T))
            f.write(jb)
            f.write(struct.pack("<II", len(self.bin), BIN_T))
            f.write(bytes(self.bin))


# ------------------------------------------------------------------------------------------------ keyframe reduction
def reduce_quat(times, q, tol_deg=0.15):
    """Error-bounded keyframe reduction (RDP with slerp) for a quaternion track (n,4 xyzw). Always keeps the end points."""
    n = len(times)
    if n <= 2:
        return np.arange(n)
    q = q.copy()
    for i in range(1, n):          # make the sequence continuous
        if np.dot(q[i], q[i - 1]) < 0:
            q[i] = -q[i]
    if np.max(np.abs(q - q[0])) < 1e-6:
        return np.array([0, n - 1])
    keep = np.zeros(n, bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    rots = Rot.from_quat(q)
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        sl = Slerp([times[a], times[b]], Rot.from_quat(q[[a, b]]))
        interp = sl(times[a + 1:b])
        err = np.degrees((interp.inv() * rots[a + 1:b]).magnitude())
        k = int(np.argmax(err))
        if err[k] > tol_deg:
            m = a + 1 + k
            keep[m] = True
            stack += [(a, m), (m, b)]
    return np.nonzero(keep)[0]


def reduce_vec(times, v, tol=0.0003):
    n = len(times)
    if n <= 2:
        return np.arange(n)
    if np.max(np.abs(v - v[0])) < 1e-7:
        return np.array([0, n - 1])
    keep = np.zeros(n, bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        t = (times[a + 1:b] - times[a]) / (times[b] - times[a])
        lin = v[a] + (v[b] - v[a]) * t[:, None]
        err = np.linalg.norm(lin - v[a + 1:b], axis=1)
        k = int(np.argmax(err))
        if err[k] > tol:
            m = a + 1 + k
            keep[m] = True
            stack += [(a, m), (m, b)]
    return np.nonzero(keep)[0]
