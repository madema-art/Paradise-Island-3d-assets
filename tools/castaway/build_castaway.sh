#!/usr/bin/env bash
# Full castaway asset build (static model). Stages: mesh, skin, misc, hair, extras, assemble, export.
#   bash tools/castaway/build_castaway.sh                 # everything
#   FROM=hair bash tools/castaway/build_castaway.sh       # resume from a stage
#   CLEAN=1 ...  also removes caches (sculpt + SDF sampler) so geometry edits take effect
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=${PY:-/opt/bpy-venv/bin/python}
B=build/castaway
mkdir -p $B/tex
FROM=${FROM:-mesh}
stages=(mesh skin misc hair extras assemble export)
run=0
for s in "${stages[@]}"; do
  [ "$s" = "$FROM" ] && run=1
  [ $run = 1 ] || continue
  echo "== $s"
  case $s in
    mesh)
      [ "${CLEAN:-1}" = 1 ] && rm -f $B/sculpt.npz $B/sdf_coarse.npz
      $PY tools/castaway/rig_build.py -- tools/castaway/rest_pose.json
      $PY tools/castaway/build_castaway_mesh.py --cache $B/sculpt.npz --out $B/mesh.npz ;;
    skin) $PY tools/castaway/paint_skin.py --mesh $B/mesh.npz --out $B/tex ;;
    misc) $PY tools/castaway/paint_misc.py $B/tex ;;
    hair) $PY tools/castaway/hair_cards.py --mesh $B/mesh.npz --out $B/hair.npz ;;
    extras) $PY tools/castaway/extras_gen.py --mesh $B/mesh.npz --out $B/extras.npz --tex $B/tex ;;
    assemble) $PY tools/castaway/assemble_castaway.py --out $B/Castaway_rig.blend ;;
    export) $PY tools/castaway/export_castaway.py --blend $B/Castaway_rig.blend --out $B/Castaway_static.glb ;;
  esac
done
echo "== done"
