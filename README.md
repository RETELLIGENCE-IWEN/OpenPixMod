# OpenPixMod

OpenPixMod is a desktop image editing tool focused on background removal, masking, and palette-based color keying.
<p align="center">
  <img src="ui/Logo.png" alt="OpenPixMod Logo" width="300">
</p>

## Features

- Open common image formats and export to `PNG`, `JPG`, `WEBP`, and `TIFF`
- Palette-based color key removal (`RGB` distance or `HSV` tolerances)
- Selection tools: rectangle, magic wand, color range, and lasso
- Mask controls: grow/shrink, feather, and remove small islands
- Image transforms: scale, move, rotate, flip, fit, and center
- Non-destructive adjustments: opacity, brightness, contrast, saturation, gamma
- Undo/redo and named snapshots
- Batch export using current project settings
- Save/load project files (`.opm` or `.json`)

## Requirements

- Python 3.10+
- `PySide6`
- `Pillow`
- `numpy`
- Optional for packaging: `pyinstaller`

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install PySide6 Pillow numpy
python app.py
```

## Project Structure

- `app.py`: application entry point
- `ui/`: Qt UI widgets and main window
- `core/`: image processing, compositing, state, project IO, and batch logic
- `packaging/`: build scripts and desktop packaging files

## Packaging

Windows:

```powershell
pip install pyinstaller
packaging\build_windows.bat
```

Linux:

```bash
pip install pyinstaller
bash packaging/build_linux.sh
```

See `packaging/README.md` for icon and desktop entry details.

## Notes

- App icon is loaded from `ui/Logo.png`.
- `.venv/` and `.blueprints/` are ignored by git in this repo.
