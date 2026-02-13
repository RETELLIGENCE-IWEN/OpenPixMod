from __future__ import annotations

from pathlib import Path
from typing import Iterable

from core.compositor import composite_to_canvas
from core.io import load_image_rgba, save_image
from core.state import ProjectState


def iter_images(folder: str) -> Iterable[Path]:
    exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}
    root = Path(folder)
    for p in root.iterdir():
        if p.is_file() and p.suffix.lower() in exts:
            yield p


def batch_export_with_state(
    input_dir: str,
    output_dir: str,
    state: ProjectState,
    suffix: str = "_opm",
    ext: str = ".png",
) -> int:
    out_root = Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    count = 0
    for src_path in iter_images(input_dir):
        src_img = load_image_rgba(str(src_path))
        out_img = composite_to_canvas(
            src_rgba_pil=src_img,
            out_size=(state.out_w, state.out_h),
            img_scale=state.img_scale,
            img_offset=(state.img_off_x, state.img_off_y),
            rotation_deg=state.rotation_deg,
            palette_rgbs=state.enabled_palette_rgbs(),
            tolerance=state.tolerance,
            opacity=state.opacity,
            color_key_mode=state.color_key_mode,
            hsv_h_tol=state.hsv_h_tol,
            hsv_s_tol=state.hsv_s_tol,
            hsv_v_tol=state.hsv_v_tol,
            mask_grow_shrink=state.mask_grow_shrink,
            mask_feather_radius=state.mask_feather_radius,
            remove_islands_min_size=state.remove_islands_min_size,
            high_quality=state.high_quality_resample,
            nearest_neighbor=state.nearest_neighbor,
            brightness=state.brightness,
            contrast=state.contrast,
            saturation=state.saturation,
            gamma=state.gamma,
            selection_enabled=state.selection_enabled,
            selection_invert=state.selection_invert,
            selection_rect=(state.sel_x, state.sel_y, state.sel_w, state.sel_h),
        )
        out_name = f"{src_path.stem}{suffix}{ext}"
        save_image(str(out_root / out_name), out_img)
        count += 1
    return count
