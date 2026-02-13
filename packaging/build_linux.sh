#!/usr/bin/env bash
set -euo pipefail

# Build OpenPixMod as a Linux executable with app icon.
pyinstaller --noconfirm --windowed --onefile --name OpenPixMod --icon ui/Logo.png app.py

echo "Build complete. Check dist/OpenPixMod"
