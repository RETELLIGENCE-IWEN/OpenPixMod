from __future__ import annotations
from dataclasses import dataclass
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


@dataclass
class LayerRenderInput:
    src_rgba_pil: Optional[Image.Image]
    visible: bool = True
    blend_mode: str = "normal"
    img_scale: float = 1.0
    img_offset: Tuple[float, float] = (0.0, 0.0)
    palette_rgbs: Optional[List[Tuple[int, int, int]]] = None
    tolerance: int = 30
    opacity: float = 1.0
    rotation_deg: int = 0
    color_key_mode: str = "rgb"
    hsv_h_tol: int = 12
    hsv_s_tol: int = 40
    hsv_v_tol: int = 40
    mask_grow_shrink: int = 0
    mask_feather_radius: int = 0
    remove_islands_min_size: int = 0
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    gamma: float = 1.0
    vibrance: float = 1.0
    temperature: int = 0
    selection_enabled: bool = False
    selection_invert: bool = False
    selection_rect: Optional[Tuple[int, int, int, int]] = None
    selection_mask: Optional[np.ndarray] = None


def _process_layer_rgba(layer: LayerRenderInput) -> Optional[np.ndarray]:
    if (not layer.visible) or layer.src_rgba_pil is None:
        return None

    src_np = pil_to_np_rgba(layer.src_rgba_pil)
    remove_mask = build_color_key_remove_mask(
        src_np,
        layer.palette_rgbs or [],
        int(layer.tolerance),
        mode=layer.color_key_mode,
        hsv_h_tol=int(layer.hsv_h_tol),
        hsv_s_tol=int(layer.hsv_s_tol),
        hsv_v_tol=int(layer.hsv_v_tol),
    )

    if layer.selection_enabled:
        sel: Optional[np.ndarray] = None
        if layer.selection_mask is not None and layer.selection_mask.shape == remove_mask.shape:
            sel = layer.selection_mask.astype(bool)
        elif layer.selection_rect is not None:
            sx, sy, sw, sh = layer.selection_rect
            h, w = remove_mask.shape
            x0 = max(0, int(sx))
            y0 = max(0, int(sy))
            x1 = min(w, int(sx + sw))
            y1 = min(h, int(sy + sh))
            sel = np.zeros_like(remove_mask, dtype=bool)
            if x1 > x0 and y1 > y0:
                sel[y0:y1, x0:x1] = True
        if sel is not None:
            if layer.selection_invert:
                sel = ~sel
            remove_mask &= sel

    src_np = src_np.copy()
    src_np[..., 3] = refine_alpha_mask(
        src_np[..., 3],
        remove_mask,
        grow_shrink=int(layer.mask_grow_shrink),
        feather_radius=int(layer.mask_feather_radius),
        remove_islands_min_size=int(layer.remove_islands_min_size),
    )

    src_np = apply_adjustments_rgba(
        src_np,
        brightness=float(layer.brightness),
        contrast=float(layer.contrast),
        saturation=float(layer.saturation),
        gamma=float(layer.gamma),
        vibrance=float(layer.vibrance),
        temperature=int(layer.temperature),
    )

    if layer.opacity < 1.0:
        a = src_np[..., 3].astype(np.float32)
        src_np[..., 3] = np.clip(a * float(layer.opacity), 0, 255).astype(np.uint8)

    return src_np


def _blend(base: np.ndarray, top: np.ndarray, mode: str) -> np.ndarray:
    base_rgb = base[..., :3].astype(np.float32) / 255.0
    top_rgb = top[..., :3].astype(np.float32) / 255.0
    base_a = base[..., 3:4].astype(np.float32) / 255.0
    top_a = top[..., 3:4].astype(np.float32) / 255.0

    mode = (mode or "normal").lower()
    if mode == "multiply":
        blend_rgb = base_rgb * top_rgb
    elif mode == "screen":
        blend_rgb = 1.0 - (1.0 - base_rgb) * (1.0 - top_rgb)
    elif mode == "overlay":
        blend_rgb = np.where(base_rgb <= 0.5, 2.0 * base_rgb * top_rgb, 1.0 - 2.0 * (1.0 - base_rgb) * (1.0 - top_rgb))
    else:
        blend_rgb = top_rgb

    out_a = top_a + base_a * (1.0 - top_a)
    premul_top = blend_rgb * top_a
    premul_base = base_rgb * base_a
    out_premul = premul_top + premul_base * (1.0 - top_a)
    out_rgb = np.where(out_a > 0, out_premul / np.maximum(out_a, 1e-6), 0.0)

    out = np.empty_like(base)
    out[..., :3] = np.clip(out_rgb * 255.0, 0, 255).astype(np.uint8)
    out[..., 3] = np.clip(out_a[..., 0] * 255.0, 0, 255).astype(np.uint8)
    return out


def composite_layers_to_canvas(
    layers: List[LayerRenderInput],
    out_size: Tuple[int, int],
    high_quality: bool = True,
    nearest_neighbor: bool = False,
) -> Image.Image:
    out_w, out_h = out_size
    base = np.zeros((out_h, out_w, 4), dtype=np.uint8)

    if nearest_neighbor:
        resample = Image.Resampling.NEAREST
    else:
        resample = Image.Resampling.LANCZOS if high_quality else Image.Resampling.BILINEAR

    for layer in layers:
        layer_np = _process_layer_rgba(layer)
        if layer_np is None:
            continue
        layer_img = np_rgba_to_pil(layer_np)

        rot = int(layer.rotation_deg) % 360
        if rot != 0:
            layer_img = layer_img.rotate(-rot, expand=True, resample=Image.Resampling.BICUBIC)

        scale = max(0.01, float(layer.img_scale))
        new_w = max(1, int(round(layer_img.width * scale)))
        new_h = max(1, int(round(layer_img.height * scale)))
        scaled = layer_img.resize((new_w, new_h), resample=resample)

        off_x, off_y = layer.img_offset
        cx = out_w * 0.5
        cy = out_h * 0.5
        x = int(round(cx - new_w * 0.5 + off_x))
        y = int(round(cy - new_h * 0.5 + off_y))

        tile = np.zeros_like(base)
        arr = pil_to_np_rgba(scaled)
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(out_w, x + scaled.width)
        y1 = min(out_h, y + scaled.height)
        if x1 <= x0 or y1 <= y0:
            continue

        sx0 = x0 - x
        sy0 = y0 - y
        sx1 = sx0 + (x1 - x0)
        sy1 = sy0 + (y1 - y0)
        tile[y0:y1, x0:x1] = arr[sy0:sy1, sx0:sx1]
        base = _blend(base, tile, layer.blend_mode)

    return np_rgba_to_pil(base)


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
    layer = LayerRenderInput(
        src_rgba_pil=src_rgba_pil,
        visible=True,
        blend_mode="normal",
        img_scale=img_scale,
        img_offset=img_offset,
        palette_rgbs=palette_rgbs,
        tolerance=tolerance,
        opacity=opacity,
        rotation_deg=rotation_deg,
        color_key_mode=color_key_mode,
        hsv_h_tol=hsv_h_tol,
        hsv_s_tol=hsv_s_tol,
        hsv_v_tol=hsv_v_tol,
        mask_grow_shrink=mask_grow_shrink,
        mask_feather_radius=mask_feather_radius,
        remove_islands_min_size=remove_islands_min_size,
        brightness=brightness,
        contrast=contrast,
        saturation=saturation,
        gamma=gamma,
        vibrance=vibrance,
        temperature=temperature,
        selection_enabled=selection_enabled,
        selection_invert=selection_invert,
        selection_rect=selection_rect,
        selection_mask=selection_mask,
    )
    return composite_layers_to_canvas([layer], out_size=out_size, high_quality=high_quality, nearest_neighbor=nearest_neighbor)
