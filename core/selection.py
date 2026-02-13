from __future__ import annotations

from collections import deque
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw


def _distance_mask(rgb: np.ndarray, ref: Tuple[int, int, int], tolerance: int) -> np.ndarray:
    tol2 = int(tolerance) * int(tolerance)
    r, g, b = int(ref[0]), int(ref[1]), int(ref[2])
    arr = rgb.astype(np.int32)
    dr = arr[..., 0] - r
    dg = arr[..., 1] - g
    db = arr[..., 2] - b
    d2 = dr * dr + dg * dg + db * db
    return d2 <= tol2


def color_range_mask(rgb: np.ndarray, seed_xy: Tuple[int, int], tolerance: int) -> np.ndarray:
    h, w, _ = rgb.shape
    x, y = seed_xy
    if x < 0 or y < 0 or x >= w or y >= h:
        return np.zeros((h, w), dtype=bool)
    ref = tuple(int(v) for v in rgb[y, x, :3])
    return _distance_mask(rgb, ref, tolerance)


def magic_wand_mask(
    rgb: np.ndarray,
    seed_xy: Tuple[int, int],
    tolerance: int,
    contiguous: bool = True,
) -> np.ndarray:
    h, w, _ = rgb.shape
    x0, y0 = seed_xy
    if x0 < 0 or y0 < 0 or x0 >= w or y0 >= h:
        return np.zeros((h, w), dtype=bool)

    if not contiguous:
        return color_range_mask(rgb, seed_xy, tolerance)

    ref = tuple(int(v) for v in rgb[y0, x0, :3])
    dist_ok = _distance_mask(rgb, ref, tolerance)

    out = np.zeros((h, w), dtype=bool)
    q: deque[tuple[int, int]] = deque()
    q.append((x0, y0))
    out[y0, x0] = True
    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))

    while q:
        cx, cy = q.popleft()
        for dx, dy in dirs:
            nx, ny = cx + dx, cy + dy
            if nx < 0 or ny < 0 or nx >= w or ny >= h:
                continue
            if out[ny, nx] or not dist_ok[ny, nx]:
                continue
            out[ny, nx] = True
            q.append((nx, ny))

    return out


def bounding_rect(mask: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    ys, xs = np.where(mask)
    if ys.size == 0 or xs.size == 0:
        return None
    x0 = int(xs.min())
    y0 = int(ys.min())
    x1 = int(xs.max()) + 1
    y1 = int(ys.max()) + 1
    return (x0, y0, x1 - x0, y1 - y0)


def polygon_mask(shape_hw: Tuple[int, int], points_xy: list[Tuple[int, int]]) -> np.ndarray:
    h, w = shape_hw
    if h <= 0 or w <= 0 or len(points_xy) < 3:
        return np.zeros((h, w), dtype=bool)
    img = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(img)
    draw.polygon(points_xy, fill=255, outline=255)
    arr = np.array(img, dtype=np.uint8)
    return arr > 0


def combine_selection_masks(
    current: Optional[np.ndarray],
    incoming: np.ndarray,
    op: str,
) -> np.ndarray:
    op_norm = op.strip().lower()
    if current is None or op_norm == "replace":
        return incoming.copy()
    if current.shape != incoming.shape:
        return incoming.copy()
    if op_norm == "add":
        return current | incoming
    if op_norm == "subtract":
        return current & (~incoming)
    if op_norm == "intersect":
        return current & incoming
    return incoming.copy()
