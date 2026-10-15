"""Measure the packaged castaway: bind-pose height per mesh, skeleton, materials, textures, draw calls, triangle counts.
  python3 tools/castaway/measure_glb.py assets/castaway/Castaway.glb [--json out.json]
"""
import json, struct, sys
import numpy as np

CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def load(path):
    b = open(path, "rb").read()
    jl, _ = struct.unpack_from("<II", b, 12)
    j = json.loads(b[20:20 + jl])
    off = 20 + jl
    bl = struct.unpack_from("<I", b, off)[0]
    return j, b[off + 8:off + 8 + bl]


def acc(j, bin_, i):
    a = j["accessors"][i]
    bv = j["bufferViews"][a["bufferView"]]
    n = NC[a["type"]]
    dt = np.dtype(CT[a["componentType"]])
    stride = bv.get("byteStride", n * dt.itemsize)
    o = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    arr = np.ndarray((a["count"], n), dt, bin_, o, (stride, dt.itemsize))
    return arr.astype(np.float64) if dt.kind == "f" else arr


def world_mats(j):
    nodes = j["nodes"]
    par = {c: i for i, n in enumerate(nodes) for c in n.get("children", [])}
    cache = {}

    def M(i):
        if i in cache:
            return cache[i]
        n = nodes[i]
        m = np.eye(4)
        if "matrix" in n:
            m = np.array(n["matrix"]).reshape(4, 4).T
        else:
            t = np.array(n.get("translation", [0, 0, 0]))
            q = n.get("rotation", [0, 0, 0, 1])
            s = np.array(n.get("scale", [1, 1, 1]))
            x, y, z, w = q
            R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                          [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
            m[:3, :3] = R * s
            m[:3, 3] = t
        cache[i] = (M(par[i]) @ m) if i in par else m
        return cache[i]
    return M


def main():
    path = sys.argv[1]
    j, bin_ = load(path)
    M = world_mats(j)
    out = dict(file=path.split("/")[-1], meshes={}, draw_calls=0, triangles=0)
    ymin, ymax = 1e9, -1e9
    for ni, n in enumerate(j["nodes"]):
        if "mesh" not in n:
            continue
        mesh = j["meshes"][n["mesh"]]
        for pr in mesh["primitives"]:
            P = acc(j, bin_, pr["attributes"]["POSITION"])
            tri = j["accessors"][pr["indices"]]["count"] // 3 if "indices" in pr else len(P) // 3
            out["draw_calls"] += 1
            out["triangles"] += tri
            # bind pose: skinned meshes are already in bind space (inverse bind mats cancel the node); use vertices directly
            lo, hi = P[:, 1].min(), P[:, 1].max()
            mat = j["materials"][pr["material"]]["name"] if "material" in pr else None
            out["meshes"][f"{mesh.get('name')}/{mat}"] = dict(tris=tri, verts=len(P), y_min=round(lo, 4), y_max=round(hi, 4), x_span=round(P[:, 0].max() - P[:, 0].min(), 3), z_span=round(P[:, 2].max() - P[:, 2].min(), 3), skinned="JOINTS_0" in pr["attributes"])
    out["skeleton_joints"] = len(j["skins"][0]["joints"]) if j.get("skins") else 0
    out["materials"] = [m["name"] for m in j.get("materials", [])]
    out["images"] = [dict(name=i.get("name"), mime=i.get("mimeType"), bytes=j["bufferViews"][i["bufferView"]]["byteLength"]) for i in j.get("images", [])]
    out["animations"] = len(j.get("animations", []))
    print(json.dumps(out, indent=1))
    if "--json" in sys.argv:
        json.dump(out, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)


if __name__ == "__main__":
    main()
