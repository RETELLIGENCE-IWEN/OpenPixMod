from __future__ import annotations

import numpy as np


def apply_adjustments_rgba(
    rgba: np.ndarray,
    brightness: float = 1.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    gamma: float = 1.0,
    vibrance: float = 1.0,
    temperature: int = 0,
) -> np.ndarray:
    if rgba.dtype != np.uint8 or rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("rgba must be HxWx4 uint8")

    out = rgba.astype(np.float32).copy()
    rgb = out[..., :3]

    # Brightness
    rgb *= float(max(0.1, brightness))

    # Contrast around mid-gray
    c = float(max(0.1, contrast))
    rgb = (rgb - 127.5) * c + 127.5

    # Saturation
    s = float(max(0.0, saturation))
    luma = rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114
    rgb = luma[..., None] + (rgb - luma[..., None]) * s

    # Vibrance (boost lower-saturation areas more than already saturated areas)
    v = float(max(0.0, vibrance))
    if abs(v - 1.0) > 1e-6:
        maxc = np.max(rgb, axis=2)
        minc = np.min(rgb, axis=2)
        sat = np.clip((maxc - minc) / 255.0, 0.0, 1.0)
        amt = (v - 1.0) * (1.0 - sat)
        rgb = luma[..., None] + (rgb - luma[..., None]) * (1.0 + amt[..., None])

    # White balance temperature (simple warm/cool shift)
    t = int(max(-100, min(100, int(temperature))))
    if t != 0:
        shift = float(t) * 1.25
        rgb[..., 0] += shift
        rgb[..., 2] -= shift

    # Gamma
    g = float(max(0.1, gamma))
    rgb = np.clip(rgb, 0.0, 255.0) / 255.0
    rgb = np.power(rgb, 1.0 / g) * 255.0

    out[..., :3] = np.clip(rgb, 0.0, 255.0)
    return out.astype(np.uint8)
