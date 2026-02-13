from __future__ import annotations

import numpy as np


def apply_adjustments_rgba(
    rgba: np.ndarray,
    brightness: float = 1.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    gamma: float = 1.0,
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

    # Gamma
    g = float(max(0.1, gamma))
    rgb = np.clip(rgb, 0.0, 255.0) / 255.0
    rgb = np.power(rgb, 1.0 / g) * 255.0

    out[..., :3] = np.clip(rgb, 0.0, 255.0)
    return out.astype(np.uint8)
