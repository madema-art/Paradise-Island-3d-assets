"""
Structural validator for .glb files. Pure Python, no Blender needed.

Checks that the file is a well-formed GLB 2.0, that every primitive has finite
geometry with valid accessors, that the mesh has real triangles, and that each
material's base-colour texture points at an embedded PNG or JPEG.

Usage:
  python3 tools/blender/validate_glb.py path/to/model.glb [--json report.json] [--min-triangles 20]

Exit code 0 = pass, 1 = fail.
"""
import argparse
import json
import math
import os
import struct
import sys

GLB_MAGIC = b"glTF"
CHUNK_JSON = 0x4E4F534A
CHUNK_BIN = 0x004E4942
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

TYPE_COUNTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
COMPONENT = {  # componentType -> (struct code, byte size)
    5121: ("B", 1),  # UNSIGNED_BYTE
    5123: ("H", 2),  # UNSIGNED_SHORT
    5125: ("I", 4),  # UNSIGNED_INT
    5126: ("f", 4),  # FLOAT
}


def read_glb(path):
    with open(path, "rb") as f:
        data = f.read()
    if len(data) < 12:
        raise ValueError("file too small to be a GLB")
    magic, version, length = struct.unpack_from("<4sII", data, 0)
    if magic != GLB_MAGIC:
        raise ValueError("bad magic, not a GLB file")
    if version != 2:
        raise ValueError(f"unsupported glTF version {version}")
    if length != len(data):
        raise ValueError(f"header length {length} != file size {len(data)}")

    chunks = {}
    off = 12
    while off < length:
        clen, ctype = struct.unpack_from("<II", data, off)
        if off + 8 + clen > length:
            raise ValueError("chunk overruns file")
        chunks.setdefault(ctype, data[off + 8: off + 8 + clen])
        off += 8 + clen
    if CHUNK_JSON not in chunks:
        raise ValueError("missing JSON chunk")
    gltf = json.loads(chunks[CHUNK_JSON].decode("utf-8"))
    return gltf, chunks.get(CHUNK_BIN, b"")


def read_accessor(gltf, blob, idx):
    acc = gltf["accessors"][idx]
    view = gltf["bufferViews"][acc["bufferView"]]
    ncomp = TYPE_COUNTS[acc["type"]]
    code, size = COMPONENT[acc["componentType"]]
    stride = view.get("byteStride", ncomp * size)
    base = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    count = acc["count"]
    if count and base + stride * (count - 1) + ncomp * size > len(blob):
        raise ValueError(f"accessor {idx} overruns the binary chunk")
    fmt = "<" + code * ncomp
    return [struct.unpack_from(fmt, blob, base + i * stride) for i in range(count)]


def image_size(blob, view):
    """(width, height) of an embedded PNG or JPEG, or None if it is neither."""
    raw = blob[view["byteOffset"]: view["byteOffset"] + view["byteLength"]]
    if raw.startswith(PNG_SIGNATURE) and raw[12:16] == b"IHDR":
        return struct.unpack(">II", raw[16:24])
    if raw[:2] == b"\xff\xd8":                        # JPEG: walk the markers to the first SOFn
        i = 2
        while i + 9 < len(raw):
            if raw[i] != 0xFF:
                i += 1
                continue
            marker = raw[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seglen = struct.unpack(">H", raw[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", raw[i + 5:i + 9])
                return w, h
            i += 2 + seglen
    return None


def validate(gltf, blob, min_triangles):
    errors, warnings = [], []
    meshes = gltf.get("meshes", [])
    materials = gltf.get("materials", [])
    textures = gltf.get("textures", [])
    images = gltf.get("images", [])
    summary = {"meshes": len(meshes), "primitives": 0, "vertices": 0, "triangles": 0,
               "materials": [], "images": []}

    if not meshes:
        errors.append("no meshes in file")

    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for mi, mesh in enumerate(meshes):
        for pi, prim in enumerate(mesh.get("primitives", [])):
            tag = f"mesh[{mi}].primitive[{pi}]"
            attrs = prim.get("attributes", {})
            summary["primitives"] += 1
            if "POSITION" not in attrs:
                errors.append(f"{tag}: no POSITION attribute")
                continue

            positions = read_accessor(gltf, blob, attrs["POSITION"])
            if not positions:
                errors.append(f"{tag}: zero vertices")
                continue
            if any(not all(math.isfinite(c) for c in p) for p in positions):
                errors.append(f"{tag}: non-finite vertex positions")
            for p in positions:
                for k in range(3):
                    lo[k] = min(lo[k], p[k])
                    hi[k] = max(hi[k], p[k])
            summary["vertices"] += len(positions)

            if "indices" in prim:
                idx = [i for (i,) in read_accessor(gltf, blob, prim["indices"])]
            else:
                idx = list(range(len(positions)))
            if prim.get("mode", 4) != 4:
                errors.append(f"{tag}: mode {prim.get('mode')} is not TRIANGLES")
            if len(idx) % 3:
                errors.append(f"{tag}: index count {len(idx)} is not a multiple of 3")
            if idx and max(idx) >= len(positions):
                errors.append(f"{tag}: index {max(idx)} out of range")
            degenerate = sum(1 for t in range(0, len(idx) - 2, 3)
                             if len({idx[t], idx[t + 1], idx[t + 2]}) < 3)
            if degenerate:
                warnings.append(f"{tag}: {degenerate} degenerate triangles")
            summary["triangles"] += len(idx) // 3

            if "TEXCOORD_0" not in attrs:
                warnings.append(f"{tag}: no TEXCOORD_0, textured materials will not map")
            else:
                uvs = read_accessor(gltf, blob, attrs["TEXCOORD_0"])
                outside = sum(1 for u, v in uvs if not (-1e-3 <= u <= 1 + 1e-3 and -1e-3 <= v <= 1 + 1e-3))
                if outside:
                    warnings.append(f"{tag}: {outside} UVs outside [0,1]")

            mat = prim.get("material")
            if mat is None:
                warnings.append(f"{tag}: no material, renders with the default grey")
            elif mat >= len(materials):
                errors.append(f"{tag}: material index {mat} does not exist")

    if summary["triangles"] < min_triangles:
        errors.append(f"only {summary['triangles']} triangles (minimum {min_triangles})")
    if any(lo[k] > hi[k] for k in range(3)):
        errors.append("no vertices read, cannot compute bounds")
    else:
        summary["bounds_min"] = [round(c, 4) for c in lo]
        summary["bounds_max"] = [round(c, 4) for c in hi]
        flat_axes = [k for k in range(3) if hi[k] - lo[k] <= 1e-6]
        if flat_axes:
            errors.append(f"geometry is flat along axis {flat_axes}")

    for mi, m in enumerate(materials):
        pbr = m.get("pbrMetallicRoughness", {})
        entry = {"name": m.get("name", f"material[{mi}]"),
                 "base_color_factor": pbr.get("baseColorFactor", [1, 1, 1, 1]),
                 "base_color_texture": None}
        bct = pbr.get("baseColorTexture")
        if bct is not None:
            tex = textures[bct["index"]]
            img = images[tex["source"]]
            if "bufferView" not in img:
                errors.append(f"material {entry['name']}: texture is not embedded")
            else:
                size = image_size(blob, gltf["bufferViews"][img["bufferView"]])
                if size is None:
                    errors.append(f"material {entry['name']}: embedded image is neither PNG nor JPEG")
                else:
                    entry["base_color_texture"] = {"width": size[0], "height": size[1],
                                                   "mimeType": img.get("mimeType")}
                    if size[0] == 0 or size[1] == 0:
                        errors.append(f"material {entry['name']}: zero-sized texture")
        else:
            warnings.append(f"material {entry['name']}: no base colour texture")
        summary["materials"].append(entry)

    summary["images"] = [img.get("mimeType", "?") for img in images]
    summary["skins"] = [len(sk.get("joints", [])) for sk in gltf.get("skins", [])]
    summary["animations"] = [a.get("name", "?") for a in gltf.get("animations", [])]
    for ai, an in enumerate(gltf.get("animations", [])):
        for ch in an.get("channels", []):
            if ch["target"].get("node") is None or ch["target"]["node"] >= len(gltf.get("nodes", [])):
                errors.append(f"animation {an.get('name', ai)}: channel targets a missing node")
                break
        for sm in an.get("samplers", []):
            acc = gltf["accessors"][sm["input"]]
            if acc.get("count", 0) < 1:
                errors.append(f"animation {an.get('name', ai)}: empty sampler")
                break
    if not summary["materials"]:
        errors.append("no materials in file")
    return summary, errors, warnings


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("glb")
    p.add_argument("--json", help="write the report to this path")
    p.add_argument("--min-triangles", type=int, default=20)
    args = p.parse_args()

    summary = {"file": os.path.basename(args.glb), "bytes": os.path.getsize(args.glb)}
    try:
        gltf, blob = read_glb(args.glb)
        result, errors, warnings = validate(gltf, blob, args.min_triangles)
        summary.update(result)
    except (ValueError, KeyError, IndexError, struct.error, json.JSONDecodeError) as exc:
        errors, warnings = [f"could not parse: {exc}"], []

    summary["errors"] = errors
    summary["warnings"] = warnings
    summary["status"] = "FAIL" if errors else "PASS"

    print(json.dumps(summary, indent=2))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(summary, f, indent=2)
            f.write("\n")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
