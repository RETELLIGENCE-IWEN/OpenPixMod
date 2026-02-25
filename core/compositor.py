from __future__ import annotations
from typing import Tuple, Optional, List
import numpy as np
from PIL import Image

from core.mask_color_key import build_color_key_remove_mask
from core.mask_ops import refine_alpha_mask
from core.adjustments import apply_adjustments_rgba

def pil_to_np_rgba(img: Image.Image) -> np.ndarray:
    arr = np.array(img.convert("RGBA"), dtype=np.uint8)
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError("Expected RGBA image")
    return arr

def np_rgba_to_pil(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(arr, mode="RGBA")

def composite_to_canvas(
    src_rgba_pil: Optional[Image.Image],
    out_size: Tuple[int, int],
    img_scale: float,
    img_offset: Tuple[float, float],
    palette_rgbs: List[Tuple[int, int, int]],
    tolerance: int,
    opacity: float,
    rotation_deg: int = 0,
    color_key_mode: str = "rgb",
    hsv_h_tol: int = 12,
    hsv_s_tol: int = 40,
    hsv_v_tol: int = 40,
    mask_grow_shrink: int = 0,
    mask_feather_radius: int = 0,
    remove_islands_min_size: int = 0,
    high_quality: bool = True,
    nearest_neighbor: bool = False,
    brightness: float = 1.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    gamma: float = 1.0,
    vibrance: float = 1.0,
    temperature: int = 0,
    selection_enabled: bool = False,
    selection_invert: bool = False,
    selection_rect: Optional[Tuple[int, int, int, int]] = None,
    selection_mask: Optional[np.ndarray] = None,
) -> Image.Image:
    out_w, out_h = out_size
    canvas = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))

    if src_rgba_pil is None:
        return canvas

    # 1) Apply color-key alpha on source (in source resolution)
    src_np = pil_to_np_rgba(src_rgba_pil)
    remove_mask = build_color_key_remove_mask(
        src_np,
        palette_rgbs,
        tolerance,
        mode=color_key_mode,
        hsv_h_tol=hsv_h_tol,
        hsv_s_tol=hsv_s_tol,
        hsv_v_tol=hsv_v_tol,
    )
    if selection_enabled:
        sel: Optional[np.ndarray] = None
        if selection_mask is not None and selection_mask.shape == remove_mask.shape:
            sel = selection_mask.astype(bool)
        elif selection_rect is not None:
            sx, sy, sw, sh = selection_rect
            h, w = remove_mask.shape
            x0 = max(0, int(sx))
            y0 = max(0, int(sy))
            x1 = min(w, int(sx + sw))
            y1 = min(h, int(sy + sh))
            sel = np.zeros_like(remove_mask, dtype=bool)
            if x1 > x0 and y1 > y0:
                sel[y0:y1, x0:x1] = True
        if sel is not None:
            if selection_invert:
                sel = ~sel
            remove_mask &= sel
    src_np = src_np.copy()
    src_np[..., 3] = refine_alpha_mask(
        src_np[..., 3],
        remove_mask,
        grow_shrink=mask_grow_shrink,
        feather_radius=mask_feather_radius,
        remove_islands_min_size=remove_islands_min_size,
    )

    # 2) Apply non-destructive color adjustments
    src_np = apply_adjustments_rgba(
        src_np,
        brightness=brightness,
        contrast=contrast,
        saturation=saturation,
        gamma=gamma,
        vibrance=vibrance,
        temperature=temperature,
    )

    # 3) Apply global opacity multiplier
    if opacity < 1.0:
        a = src_np[..., 3].astype(np.float32)
        a = np.clip(a * float(opacity), 0, 255).astype(np.uint8)
        src_np = src_np.copy()
        src_np[..., 3] = a

    src_masked = np_rgba_to_pil(src_np)

    # 4) Rotation
    rot = int(rotation_deg) % 360
    if rot != 0:
        src_masked = src_masked.rotate(-rot, expand=True, resample=Image.Resampling.BICUBIC)

    # 5) Scale image (image-scale relative to output canvas)
    scale = max(0.01, float(img_scale))
    new_w = max(1, int(round(src_masked.width * scale)))
    new_h = max(1, int(round(src_masked.height * scale)))

    if nearest_neighbor:
        resample = Image.Resampling.NEAREST
    else:
        resample = Image.Resampling.LANCZOS if high_quality else Image.Resampling.BILINEAR
    scaled = src_masked.resize((new_w, new_h), resample=resample)

    # 6) Paste with offset (centered at canvas center + offset)
    off_x, off_y = img_offset
    cx = out_w * 0.5
    cy = out_h * 0.5
    x = int(round(cx - new_w * 0.5 + off_x))
    y = int(round(cy - new_h * 0.5 + off_y))

    canvas.alpha_composite(scaled, dest=(x, y))
    return canvas
