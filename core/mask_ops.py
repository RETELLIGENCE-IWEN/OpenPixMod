from __future__ import annotations

from collections import deque

import numpy as np
from PIL import Image, ImageFilter


def _morph_mask(mask: np.ndarray, steps: int) -> np.ndarray:
    if steps == 0:
        return mask

    img = Image.fromarray(mask.astype(np.uint8) * 255, mode="L")
    count = abs(int(steps))
    if steps > 0:
        for _ in range(count):
            img = img.filter(ImageFilter.MaxFilter(3))
    else:
        for _ in range(count):
            img = img.filter(ImageFilter.MinFilter(3))
    return np.array(img, dtype=np.uint8) > 127


def _remove_small_opaque_islands(alpha: np.ndarray, min_size: int) -> np.ndarray:
    if min_size <= 0:
        return alpha

    h, w = alpha.shape
    opaque = alpha > 0
    visited = np.zeros((h, w), dtype=bool)
    out = alpha.copy()
    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))

    for y in range(h):
        for x in range(w):
            if not opaque[y, x] or visited[y, x]:
                continue

            q: deque[tuple[int, int]] = deque()
            comp: list[tuple[int, int]] = []
            q.append((y, x))
            visited[y, x] = True

            while q:
                cy, cx = q.popleft()
                comp.append((cy, cx))
                for dy, dx in dirs:
                    ny, nx = cy + dy, cx + dx
                    if ny < 0 or nx < 0 or ny >= h or nx >= w:
                        continue
                    if visited[ny, nx] or not opaque[ny, nx]:
                        continue
                    visited[ny, nx] = True
                    q.append((ny, nx))

            if len(comp) < min_size:
                for cy, cx in comp:
                    out[cy, cx] = 0

    return out


def refine_alpha_mask(
    alpha: np.ndarray,
    remove_mask: np.ndarray,
    grow_shrink: int = 0,
    feather_radius: int = 0,
    remove_islands_min_size: int = 0,
) -> np.ndarray:
    if alpha.dtype != np.uint8 or alpha.ndim != 2:
        raise ValueError("alpha must be HxW uint8")
    if remove_mask.ndim != 2 or remove_mask.shape != alpha.shape:
        raise ValueError("remove_mask must match alpha shape")

    rm = _morph_mask(remove_mask.astype(bool), int(grow_shrink))

    out = alpha.copy()
    out[rm] = 0
    out = _remove_small_opaque_islands(out, int(remove_islands_min_size))

    if feather_radius > 0 and np.any(rm):
        out_img = Image.fromarray(out, mode="L")
        out_img = out_img.filter(ImageFilter.GaussianBlur(radius=float(feather_radius)))
        out = np.array(out_img, dtype=np.uint8)

    return out
