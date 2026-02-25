from __future__ import annotations

import json
from pathlib import Path

from core.state import PaletteColor, ProjectState


PROJECT_VERSION = 1


def _normalize_src_for_save(src_path: str | None, project_file: Path) -> str | None:
    if not src_path:
        return None
    try:
        src = Path(src_path).resolve()
        base = project_file.parent.resolve()
        return str(src.relative_to(base))
    except Exception:
        return src_path


def _normalize_src_for_load(src_path: str | None, project_file: Path) -> str | None:
    if not src_path:
        return None
    p = Path(src_path)
    if p.is_absolute():
        return str(p)
    return str((project_file.parent / p).resolve())


def save_project(path: str, state: ProjectState) -> None:
    project_file = Path(path)
    payload = {
        "version": PROJECT_VERSION,
        "state": {
            "src_path": _normalize_src_for_save(state.src_path, project_file),
            "out_w": state.out_w,
            "out_h": state.out_h,
            "img_scale": state.img_scale,
            "img_off_x": state.img_off_x,
            "img_off_y": state.img_off_y,
            "rotation_deg": state.rotation_deg,
            "tolerance": state.tolerance,
            "color_key_mode": state.color_key_mode,
            "hsv_h_tol": state.hsv_h_tol,
            "hsv_s_tol": state.hsv_s_tol,
            "hsv_v_tol": state.hsv_v_tol,
            "palette": [{"rgb": list(p.rgb), "enabled": bool(p.enabled)} for p in state.palette],
            "mask_feather_radius": state.mask_feather_radius,
            "mask_grow_shrink": state.mask_grow_shrink,
            "remove_islands_min_size": state.remove_islands_min_size,
            "selection_enabled": state.selection_enabled,
            "selection_invert": state.selection_invert,
            "sel_x": state.sel_x,
            "sel_y": state.sel_y,
            "sel_w": state.sel_w,
            "sel_h": state.sel_h,
            "opacity": state.opacity,
            "high_quality_resample": state.high_quality_resample,
            "nearest_neighbor": state.nearest_neighbor,
            "show_pixel_grid": state.show_pixel_grid,
            "brightness": state.brightness,
            "contrast": state.contrast,
            "saturation": state.saturation,
            "gamma": state.gamma,
            "vibrance": state.vibrance,
            "temperature": state.temperature,
        },
    }
    project_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_project(path: str) -> ProjectState:
    project_file = Path(path)
    raw = json.loads(project_file.read_text(encoding="utf-8"))
    state_raw = raw.get("state", {})

    palette = []
    for item in state_raw.get("palette", []):
        rgb = item.get("rgb", [0, 0, 0])
        if not isinstance(rgb, list) or len(rgb) != 3:
            continue
        palette.append(
            PaletteColor(
                rgb=(int(rgb[0]), int(rgb[1]), int(rgb[2])),
                enabled=bool(item.get("enabled", True)),
            )
        )

    return ProjectState(
        src_path=_normalize_src_for_load(state_raw.get("src_path"), project_file),
        out_w=int(state_raw.get("out_w", 512)),
        out_h=int(state_raw.get("out_h", 512)),
        img_scale=float(state_raw.get("img_scale", 1.0)),
        img_off_x=float(state_raw.get("img_off_x", 0.0)),
        img_off_y=float(state_raw.get("img_off_y", 0.0)),
        rotation_deg=int(state_raw.get("rotation_deg", 0)),
        tolerance=int(state_raw.get("tolerance", 30)),
        color_key_mode=str(state_raw.get("color_key_mode", "rgb")).lower(),
        hsv_h_tol=int(state_raw.get("hsv_h_tol", 12)),
        hsv_s_tol=int(state_raw.get("hsv_s_tol", 40)),
        hsv_v_tol=int(state_raw.get("hsv_v_tol", 40)),
        palette=palette,
        mask_feather_radius=int(state_raw.get("mask_feather_radius", 0)),
        mask_grow_shrink=int(state_raw.get("mask_grow_shrink", 0)),
        remove_islands_min_size=int(state_raw.get("remove_islands_min_size", 0)),
        selection_enabled=bool(state_raw.get("selection_enabled", False)),
        selection_invert=bool(state_raw.get("selection_invert", False)),
        sel_x=int(state_raw.get("sel_x", 0)),
        sel_y=int(state_raw.get("sel_y", 0)),
        sel_w=int(state_raw.get("sel_w", 0)),
        sel_h=int(state_raw.get("sel_h", 0)),
        opacity=float(state_raw.get("opacity", 1.0)),
        high_quality_resample=bool(state_raw.get("high_quality_resample", True)),
        nearest_neighbor=bool(state_raw.get("nearest_neighbor", False)),
        show_pixel_grid=bool(state_raw.get("show_pixel_grid", False)),
        brightness=float(state_raw.get("brightness", 1.0)),
        contrast=float(state_raw.get("contrast", 1.0)),
        saturation=float(state_raw.get("saturation", 1.0)),
        gamma=float(state_raw.get("gamma", 1.0)),
        vibrance=float(state_raw.get("vibrance", 1.0)),
        temperature=int(state_raw.get("temperature", 0)),
    )
