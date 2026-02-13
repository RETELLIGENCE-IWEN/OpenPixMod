#!/usr/bin/env bash
set -euo pipefail

# Build OpenPixMod as a Linux executable with app icon.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_EXE="${ROOT_DIR}/.venv/bin/python"

if [[ ! -x "${PYTHON_EXE}" ]]; then
  echo "ERROR: venv Python not found at ${PYTHON_EXE}"
  echo "Create it first: python3 -m venv .venv"
  exit 1
fi

cd "${ROOT_DIR}"
"${PYTHON_EXE}" -m PyInstaller --noconfirm OpenPixMod.spec

echo "Build complete. Check dist/OpenPixMod"
