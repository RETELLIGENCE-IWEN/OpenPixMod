from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

@dataclass
class PaletteColor:
    rgb: Tuple[int, int, int]
    enabled: bool = True

@dataclass
class ProjectState:
    # Source
    src_path: Optional[str] = None

    # Output canvas settings
    out_w: int = 512
    out_h: int = 512

    # Image placement (image transform in output-canvas coords)
    img_scale: float = 1.0        # scale applied to source image before compositing
    img_off_x: float = 0.0        # translation in output canvas px
    img_off_y: float = 0.0
    rotation_deg: int = 0         # 0/90/180/270

    # Background removal
    tolerance: int = 30           # RGB euclidean distance threshold (0..255*sqrt(3))
    color_key_mode: str = "rgb"   # "rgb" or "hsv"
    hsv_h_tol: int = 12           # 0..180 degrees
    hsv_s_tol: int = 40           # 0..255
    hsv_v_tol: int = 40           # 0..255
    palette: List[PaletteColor] = field(default_factory=list)
    mask_feather_radius: int = 0  # 0..20
    mask_grow_shrink: int = 0     # -20..20, + expands removed area
    remove_islands_min_size: int = 0  # 0 disables; removes tiny opaque islands
    selection_enabled: bool = False
    selection_invert: bool = False
    sel_x: int = 0
    sel_y: int = 0
    sel_w: int = 0
    sel_h: int = 0

    # Global opacity (transparency)
    opacity: float = 1.0          # 0..1

    # Preview options
    high_quality_resample: bool = True
    nearest_neighbor: bool = False
    show_pixel_grid: bool = False

    # Color adjustments (non-destructive)
    brightness: float = 1.0       # 0.1..3.0
    contrast: float = 1.0         # 0.1..3.0
    saturation: float = 1.0       # 0.0..3.0
    gamma: float = 1.0            # 0.1..3.0

    def enabled_palette_rgbs(self) -> List[Tuple[int, int, int]]:
        return [p.rgb for p in self.palette if p.enabled]
