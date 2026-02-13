# Packaging Icons

This project uses `assets/Logo.png` as the app icon source.

## Windows (PyInstaller)

Run:

```bat
packaging\build_windows.bat
```

This builds `dist\OpenPixMod.exe` with:

- executable icon from `assets\Logo.png`

## Linux (PyInstaller + desktop entry)

Run:

```bash
bash packaging/build_linux.sh
```

Both scripts use the project virtual environment (`.venv`) Python explicitly.

Then install:

1. Copy binary to a location on `PATH`, e.g. `/usr/local/bin/OpenPixMod`.
2. Copy icon as `Logo.png` to an icon dir, e.g.:
   - `~/.local/share/icons/hicolor/256x256/apps/Logo.png`
3. Copy desktop file:
   - `packaging/openpixmod.desktop` -> `~/.local/share/applications/openpixmod.desktop`

Adjust `Exec=` and `Icon=` in `openpixmod.desktop` if needed for your install paths.

