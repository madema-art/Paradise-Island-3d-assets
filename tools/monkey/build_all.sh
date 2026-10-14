#!/usr/bin/env bash
# Full monkey build, strictly sequential (each stage reads the previous stage's output).
#   bash tools/monkey/build_all.sh                 # everything from scratch (~8 min)
#   SKIP_SCULPT=1 bash tools/monkey/build_all.sh   # reuse the cached high-res sculpt (~4 min)
#   FROM=animate bash tools/monkey/build_all.sh    # start at: mesh | textures | coconut | assemble | animate | export | package
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
PY="${BPY_PYTHON:-/opt/bpy-venv/bin/python}"
OUT=build/monkey
FROM="${FROM:-mesh}"
mkdir -p "$OUT"
CACHE="$OUT/sculpt_cache.npz"
[ -z "${SKIP_SCULPT:-}" ] && [ "$FROM" = "mesh" ] && rm -f "$CACHE"
stages=(mesh textures coconut assemble animate export package)
run=0
for s in "${stages[@]}"; do
  [ "$s" = "$FROM" ] && run=1
  [ $run -eq 0 ] && continue
  echo "== $s"
  case "$s" in
    mesh)     "$PY" tools/monkey/build_monkey_mesh.py --cache "$CACHE" --tris "${TRIS:-56000}" --out "$OUT/mesh.npz" ;;
    textures) "$PY" tools/monkey/paint_textures.py --mesh "$OUT/mesh.npz" --out "$OUT/tex" ;;
    coconut)  "$PY" tools/monkey/build_coconut.py --out "$OUT/coconut" ;;
    assemble) "$PY" tools/monkey/assemble_monkey.py --mesh "$OUT/mesh.npz" --tex "$OUT/tex" --out "$OUT/Monkey_rig.blend" ;;
    animate)  "$PY" tools/monkey/animate_monkey.py --blend "$OUT/Monkey_rig.blend" --out "$OUT/Monkey_anim.blend" ;;
    export)   "$PY" tools/monkey/export_glb.py --out "$OUT/Monkey.glb"
              "$PY" tools/monkey/export_glb.py --lite --out "$OUT/Monkey_lite.glb"
              "$PY" tools/monkey/export_glb.py --lod1 --out "$OUT/Monkey_lod1.glb" ;;
    package)  "$PY" tools/monkey/package_assets.py ;;
  esac
done
echo "== done"
