#!/usr/bin/env bash
# Run every monkey build stage strictly in order (never overlap them: later stages read earlier outputs).
#   bash tools/monkey/build_all.sh            # full rebuild
#   SKIP_SCULPT=1 bash tools/monkey/build_all.sh   # reuse cached high-res sculpt
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
PY="${BPY_PYTHON:-/opt/bpy-venv/bin/python}"
OUT=build/monkey
mkdir -p "$OUT"
CACHE="$OUT/sculpt_cache.npz"
[ -z "${SKIP_SCULPT:-}" ] && rm -f "$CACHE"
echo "== 1/3 mesh";   "$PY" tools/monkey/build_monkey_mesh.py --cache "$CACHE" --tris "${TRIS:-46000}" --out "$OUT/mesh.npz"
echo "== 2/3 textures"; "$PY" tools/monkey/paint_textures.py --mesh "$OUT/mesh.npz" --out "$OUT/tex"
echo "== 3/3 assemble"; "$PY" tools/monkey/assemble_monkey.py --mesh "$OUT/mesh.npz" --tex "$OUT/tex" --out "$OUT/Monkey_rig.blend"
echo "== done: $OUT/Monkey_rig.blend"
