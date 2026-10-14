#!/usr/bin/env bash
# Installs the Blender tooling for this asset workshop. Idempotent: safe to re-run.
#
#   1. Blender application (Ubuntu archive package, currently 4.0.2) + numpy for it
#   2. bpy module (Blender as a Python package, pinned) in a venv outside the repo
#   3. Khronos glTF validator (npm, pinned) in tools/blender/node_modules
#
# Container disks are ephemeral, so re-run this at the start of each session.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BPY_VERSION="${BPY_VERSION:-5.2.2}"       # PyPI wheels exist for CPython 3.13 on linux x86_64
PY="${PYTHON:-python3.13}"
VENV="${BPY_VENV:-/opt/bpy-venv}"
SUDO=""
[ "$(id -u)" -ne 0 ] && SUDO="sudo"

echo "==> Blender application"
if command -v blender >/dev/null 2>&1; then
  echo "    already installed: $(blender --version | head -1)"
else
  export DEBIAN_FRONTEND=noninteractive
  $SUDO apt-get update -q
  $SUDO apt-get install -y -q blender python3-numpy
fi
# The Ubuntu Blender build imports numpy from the system Python for glTF I/O
dpkg -s python3-numpy >/dev/null 2>&1 || $SUDO apt-get install -y -q python3-numpy

echo "==> bpy ${BPY_VERSION} in ${VENV}"
if [ ! -x "${VENV}/bin/python" ]; then
  command -v "${PY}" >/dev/null 2>&1 || { echo "error: ${PY} not found (bpy ${BPY_VERSION} needs CPython 3.13)"; exit 1; }
  if command -v uv >/dev/null 2>&1; then
    uv venv -q --python "${PY}" "${VENV}"
  else
    "${PY}" -m venv "${VENV}"
  fi
fi
if command -v uv >/dev/null 2>&1; then
  uv pip install -q --python "${VENV}/bin/python" "bpy==${BPY_VERSION}"
else
  "${VENV}/bin/pip" install -q "bpy==${BPY_VERSION}"
fi
"${VENV}/bin/python" -c "import bpy; print('    bpy', bpy.app.version_string, 'OK')" 2>/dev/null

echo "==> Khronos glTF validator"
if command -v npm >/dev/null 2>&1; then
  (cd "${HERE}" && npm install --silent --no-audit --no-fund)
  echo "    gltf-validator installed in ${HERE}/node_modules"
else
  echo "    npm not found, skipping (structural validator still works: validate_glb.py)"
fi

echo "==> done"
