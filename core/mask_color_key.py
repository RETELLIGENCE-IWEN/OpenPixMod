from __future__ import annotations
import numpy as np
from typing import List, Tuple

def _rgb_to_hsv_image(rgb_u8: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rgb = rgb_u8.astype(np.float32) / 255.0
    r = rgb[..., 0]
    g = rgb[..., 1]
    b = rgb[..., 2]

    cmax = np.maximum(np.maximum(r, g), b)
    cmin = np.minimum(np.minimum(r, g), b)
    delta = cmax - cmin

    h = np.zeros_like(cmax, dtype=np.float32)
    nz = delta > 1e-8

    m = nz & (cmax == r)
    h[m] = (60.0 * ((g[m] - b[m]) / delta[m])) % 360.0
    m = nz & (cmax == g)
    h[m] = 60.0 * (((b[m] - r[m]) / delta[m]) + 2.0)
    m = nz & (cmax == b)
    h[m] = 60.0 * (((r[m] - g[m]) / delta[m]) + 4.0)

    s = np.zeros_like(cmax, dtype=np.float32)
    nz_v = cmax > 1e-8
    s[nz_v] = (delta[nz_v] / cmax[nz_v]) * 255.0
    v = cmax * 255.0
    return h, s, v


def _rgb_to_hsv_single(rgb: Tuple[int, int, int]) -> tuple[float, float, float]:
    r = float(rgb[0]) / 255.0
    g = float(rgb[1]) / 255.0
    b = float(rgb[2]) / 255.0

    cmax = max(r, g, b)
    cmin = min(r, g, b)
    delta = cmax - cmin

    if delta <= 1e-8:
        h = 0.0
    elif cmax == r:
        h = (60.0 * ((g - b) / delta)) % 360.0
    elif cmax == g:
        h = 60.0 * (((b - r) / delta) + 2.0)
    else:
        h = 60.0 * (((r - g) / delta) + 4.0)

    s = 0.0 if cmax <= 1e-8 else (delta / cmax) * 255.0
    v = cmax * 255.0
    return h, s, v


def build_color_key_remove_mask(
    rgba: np.ndarray,
    palette_rgbs: List[Tuple[int, int, int]],
    tolerance: int,
    mode: str = "rgb",
    hsv_h_tol: int = 12,
    hsv_s_tol: int = 40,
    hsv_v_tol: int = 40,
) -> np.ndarray:
    if rgba.dtype != np.uint8 or rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("rgba must be HxWx4 uint8")

    if not palette_rgbs:
        return np.zeros((rgba.shape[0], rgba.shape[1]), dtype=bool)

    mode_norm = mode.strip().lower()
    if mode_norm == "hsv":
        h_img, s_img, v_img = _rgb_to_hsv_image(rgba[..., :3])
        h_tol = float(max(0, min(180, int(hsv_h_tol))))
        s_tol = float(max(0, min(255, int(hsv_s_tol))))
        v_tol = float(max(0, min(255, int(hsv_v_tol))))

        remove = np.zeros((rgba.shape[0], rgba.shape[1]), dtype=bool)
        for rgb in palette_rgbs:
            h0, s0, v0 = _rgb_to_hsv_single(rgb)
            dh = np.abs(h_img - h0)
            dh = np.minimum(dh, 360.0 - dh)  # circular hue distance
            ds = np.abs(s_img - s0)
            dv = np.abs(v_img - v0)
            remove |= (dh <= h_tol) & (ds <= s_tol) & (dv <= v_tol)
        return remove

    # default: RGB euclidean
    if tolerance <= 0:
        return np.zeros((rgba.shape[0], rgba.shape[1]), dtype=bool)
    rgb = rgba[..., :3].astype(np.int32)
    tol2 = int(tolerance) * int(tolerance)
    remove = np.zeros((rgba.shape[0], rgba.shape[1]), dtype=bool)

    for (R, G, B) in palette_rgbs:
        dr = rgb[..., 0] - int(R)
        dg = rgb[..., 1] - int(G)
        db = rgb[..., 2] - int(B)
        d2 = dr * dr + dg * dg + db * db
        remove |= (d2 <= tol2)

    return remove


def apply_color_key_alpha(
    rgba: np.ndarray,
    palette_rgbs: List[Tuple[int, int, int]],
    tolerance: int,
    mode: str = "rgb",
    hsv_h_tol: int = 12,
    hsv_s_tol: int = 40,
    hsv_v_tol: int = 40,
) -> np.ndarray:
    """
    rgba: HxWx4 uint8
    Returns: new rgba with alpha set to 0 for pixels close to any palette color.
    Distance: Euclidean in RGB (v0.1)
    """
    if rgba.dtype != np.uint8 or rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("rgba must be HxWx4 uint8")

    remove = build_color_key_remove_mask(
        rgba,
        palette_rgbs,
        tolerance,
        mode=mode,
        hsv_h_tol=hsv_h_tol,
        hsv_s_tol=hsv_s_tol,
        hsv_v_tol=hsv_v_tol,
    )
    alpha = rgba[..., 3].copy()
    alpha[remove] = 0
    out = rgba.copy()
    out[..., 3] = alpha
    return out
