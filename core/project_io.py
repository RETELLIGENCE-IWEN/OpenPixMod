from __future__ import annotations

import json
from pathlib import Path

from core.state import PaletteColor, ProjectState, LayerState, BrushPreset


PROJECT_VERSION = 2


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


def _palette_from_raw(raw_palette: list[dict]) -> list[PaletteColor]:
    palette: list[PaletteColor] = []
    for item in raw_palette:
        rgb = item.get("rgb", [0, 0, 0])
        if not isinstance(rgb, list) or len(rgb) != 3:
            continue
        palette.append(
            PaletteColor(
                rgb=(int(rgb[0]), int(rgb[1]), int(rgb[2])),
                enabled=bool(item.get("enabled", True)),
            )
        )
    return palette


def _preset_to_raw(preset: BrushPreset) -> dict:
    return {
        "preset_id": preset.preset_id,
        "name": preset.name,
        "tool_mode": preset.tool_mode,
        "size": preset.size,
        "hardness": preset.hardness,
        "spacing": preset.spacing,
        "flow": preset.flow,
        "opacity": preset.opacity,
        "jitter_size": preset.jitter_size,
        "jitter_angle": preset.jitter_angle,
        "jitter_scatter": preset.jitter_scatter,
        "blend_mode": preset.blend_mode,
        "symmetry_x": bool(preset.symmetry_x),
        "symmetry_y": bool(preset.symmetry_y),
    }


def _preset_from_raw(raw: dict, idx: int) -> BrushPreset:
    fallback_id = f"custom_{idx + 1}"
    preset_id = str(raw.get("preset_id", fallback_id)).strip() or fallback_id
    return BrushPreset(
        preset_id=preset_id,
        name=str(raw.get("name", f"Custom Brush {idx + 1}")),
        tool_mode=str(raw.get("tool_mode", "paint")).lower(),
        size=float(raw.get("size", 24.0)),
        hardness=float(raw.get("hardness", 0.8)),
        spacing=float(raw.get("spacing", 0.12)),
        flow=float(raw.get("flow", 1.0)),
        opacity=float(raw.get("opacity", 1.0)),
        jitter_size=float(raw.get("jitter_size", 0.0)),
        jitter_angle=float(raw.get("jitter_angle", 0.0)),
        jitter_scatter=float(raw.get("jitter_scatter", 0.0)),
        blend_mode=str(raw.get("blend_mode", "normal")).lower(),
        symmetry_x=bool(raw.get("symmetry_x", False)),
        symmetry_y=bool(raw.get("symmetry_y", False)),
    )


def _layer_to_raw(layer: LayerState, project_file: Path) -> dict:
    return {
        "name": layer.name,
        "src_path": _normalize_src_for_save(layer.src_path, project_file),
        "visible": bool(layer.visible),
        "blend_mode": layer.blend_mode,
        "img_scale": layer.img_scale,
        "img_off_x": layer.img_off_x,
        "img_off_y": layer.img_off_y,
        "rotation_deg": layer.rotation_deg,
        "tolerance": layer.tolerance,
        "color_key_mode": layer.color_key_mode,
        "hsv_h_tol": layer.hsv_h_tol,
        "hsv_s_tol": layer.hsv_s_tol,
        "hsv_v_tol": layer.hsv_v_tol,
        "palette": [{"rgb": list(p.rgb), "enabled": bool(p.enabled)} for p in layer.palette],
        "mask_feather_radius": layer.mask_feather_radius,
        "mask_grow_shrink": layer.mask_grow_shrink,
        "remove_islands_min_size": layer.remove_islands_min_size,
        "opacity": layer.opacity,
        "brightness": layer.brightness,
        "contrast": layer.contrast,
        "saturation": layer.saturation,
        "gamma": layer.gamma,
        "vibrance": layer.vibrance,
        "temperature": layer.temperature,
        "alpha_paint_mask_data": layer.alpha_paint_mask_data,
    }


def _layer_from_raw(state_raw: dict, project_file: Path, idx: int) -> LayerState:
    return LayerState(
        name=str(state_raw.get("name", f"Layer {idx + 1}")),
        src_path=_normalize_src_for_load(state_raw.get("src_path"), project_file),
        visible=bool(state_raw.get("visible", True)),
        blend_mode=str(state_raw.get("blend_mode", "normal")).lower(),
        img_scale=float(state_raw.get("img_scale", 1.0)),
        img_off_x=float(state_raw.get("img_off_x", 0.0)),
        img_off_y=float(state_raw.get("img_off_y", 0.0)),
        rotation_deg=int(state_raw.get("rotation_deg", 0)),
        tolerance=int(state_raw.get("tolerance", 30)),
        color_key_mode=str(state_raw.get("color_key_mode", "rgb")).lower(),
        hsv_h_tol=int(state_raw.get("hsv_h_tol", 12)),
        hsv_s_tol=int(state_raw.get("hsv_s_tol", 40)),
        hsv_v_tol=int(state_raw.get("hsv_v_tol", 40)),
        palette=_palette_from_raw(state_raw.get("palette", [])),
        mask_feather_radius=int(state_raw.get("mask_feather_radius", 0)),
        mask_grow_shrink=int(state_raw.get("mask_grow_shrink", 0)),
        remove_islands_min_size=int(state_raw.get("remove_islands_min_size", 0)),
        opacity=float(state_raw.get("opacity", 1.0)),
        brightness=float(state_raw.get("brightness", 1.0)),
        contrast=float(state_raw.get("contrast", 1.0)),
        saturation=float(state_raw.get("saturation", 1.0)),
        gamma=float(state_raw.get("gamma", 1.0)),
        vibrance=float(state_raw.get("vibrance", 1.0)),
        temperature=int(state_raw.get("temperature", 0)),
        alpha_paint_mask_data=state_raw.get("alpha_paint_mask_data"),
    )


def save_project(path: str, state: ProjectState) -> None:
    project_file = Path(path)
    legacy = state.active_layer()
    payload = {
        "version": PROJECT_VERSION,
        "state": {
            "out_w": state.out_w,
            "out_h": state.out_h,
            "high_quality_resample": state.high_quality_resample,
            "nearest_neighbor": state.nearest_neighbor,
            "show_pixel_grid": state.show_pixel_grid,
            "selection_enabled": state.selection_enabled,
            "selection_invert": state.selection_invert,
            "sel_x": state.sel_x,
            "sel_y": state.sel_y,
            "sel_w": state.sel_w,
            "sel_h": state.sel_h,
            "layers": [_layer_to_raw(layer, project_file) for layer in state.layers],
            "active_layer_index": int(state.active_layer_index),
            "brush_engine_version": int(state.brush_engine_version),
            "active_brush_id": state.active_brush_id,
            "custom_brush_presets": [_preset_to_raw(p) for p in state.custom_brush_presets],
            # legacy active layer fields for downgrade compatibility
            "src_path": _normalize_src_for_save(legacy.src_path, project_file),
            "img_scale": legacy.img_scale,
            "img_off_x": legacy.img_off_x,
            "img_off_y": legacy.img_off_y,
            "rotation_deg": legacy.rotation_deg,
            "tolerance": legacy.tolerance,
            "color_key_mode": legacy.color_key_mode,
            "hsv_h_tol": legacy.hsv_h_tol,
            "hsv_s_tol": legacy.hsv_s_tol,
            "hsv_v_tol": legacy.hsv_v_tol,
            "palette": [{"rgb": list(p.rgb), "enabled": bool(p.enabled)} for p in legacy.palette],
            "mask_feather_radius": legacy.mask_feather_radius,
            "mask_grow_shrink": legacy.mask_grow_shrink,
            "remove_islands_min_size": legacy.remove_islands_min_size,
            "opacity": legacy.opacity,
            "brightness": legacy.brightness,
            "contrast": legacy.contrast,
            "saturation": legacy.saturation,
            "gamma": legacy.gamma,
            "vibrance": legacy.vibrance,
            "temperature": legacy.temperature,
        },
    }
    project_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_project(path: str) -> ProjectState:
    project_file = Path(path)
    raw = json.loads(project_file.read_text(encoding="utf-8"))
    state_raw = raw.get("state", {})

    layers_raw = state_raw.get("layers")
    layers: list[LayerState]
    if isinstance(layers_raw, list) and layers_raw:
        layers = [_layer_from_raw(item, project_file, idx) for idx, item in enumerate(layers_raw)]
    else:
        # Backward-compatible migration from single-layer schema
        layers = [_layer_from_raw(state_raw, project_file, 0)]

    presets_raw = state_raw.get("custom_brush_presets", [])
    custom_presets: list[BrushPreset] = []
    if isinstance(presets_raw, list):
        for idx, item in enumerate(presets_raw):
            if isinstance(item, dict):
                custom_presets.append(_preset_from_raw(item, idx))

    state = ProjectState(
        out_w=int(state_raw.get("out_w", 512)),
        out_h=int(state_raw.get("out_h", 512)),
        high_quality_resample=bool(state_raw.get("high_quality_resample", True)),
        nearest_neighbor=bool(state_raw.get("nearest_neighbor", False)),
        show_pixel_grid=bool(state_raw.get("show_pixel_grid", False)),
        selection_enabled=bool(state_raw.get("selection_enabled", False)),
        selection_invert=bool(state_raw.get("selection_invert", False)),
        sel_x=int(state_raw.get("sel_x", 0)),
        sel_y=int(state_raw.get("sel_y", 0)),
        sel_w=int(state_raw.get("sel_w", 0)),
        sel_h=int(state_raw.get("sel_h", 0)),
        layers=layers,
        active_layer_index=int(state_raw.get("active_layer_index", 0)),
        brush_engine_version=int(state_raw.get("brush_engine_version", 1)),
        active_brush_id=str(state_raw.get("active_brush_id", "soft_round")),
        custom_brush_presets=custom_presets,
    )
    state._ensure_layers()
    return state
