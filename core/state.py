from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class PaletteColor:
    rgb: Tuple[int, int, int]
    enabled: bool = True


@dataclass
class BrushPreset:
    preset_id: str
    name: str
    tool_mode: str = "paint"
    size: float = 24.0
    hardness: float = 0.8
    spacing: float = 0.12
    flow: float = 1.0
    opacity: float = 1.0
    jitter_size: float = 0.0
    jitter_angle: float = 0.0
    jitter_scatter: float = 0.0
    blend_mode: str = "normal"
    symmetry_x: bool = False
    symmetry_y: bool = False


@dataclass
class LayerState:
    name: str = "Layer 1"
    src_path: Optional[str] = None
    visible: bool = True
    blend_mode: str = "normal"

    # Image placement (image transform in output-canvas coords)
    img_scale: float = 1.0
    img_off_x: float = 0.0
    img_off_y: float = 0.0
    rotation_deg: int = 0

    # Background removal
    tolerance: int = 30
    color_key_mode: str = "rgb"
    hsv_h_tol: int = 12
    hsv_s_tol: int = 40
    hsv_v_tol: int = 40
    palette: List[PaletteColor] = field(default_factory=list)
    mask_feather_radius: int = 0
    mask_grow_shrink: int = 0
    remove_islands_min_size: int = 0

    # Per-layer opacity
    opacity: float = 1.0

    # Color adjustments (non-destructive)
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    gamma: float = 1.0
    vibrance: float = 1.0
    temperature: int = 0

    # Non-destructive alpha painting mask stored as PNG(base64) grayscale
    # (same pixel size as source image). None means fully opaque.
    alpha_paint_mask_data: Optional[str] = None

    def enabled_palette_rgbs(self) -> List[Tuple[int, int, int]]:
        return [p.rgb for p in self.palette if p.enabled]


@dataclass
class ProjectState:
    # Output canvas settings
    out_w: int = 512
    out_h: int = 512

    # Preview options
    high_quality_resample: bool = True
    nearest_neighbor: bool = False
    show_pixel_grid: bool = False

    # Selection (shared workspace selection)
    selection_enabled: bool = False
    selection_invert: bool = False
    sel_x: int = 0
    sel_y: int = 0
    sel_w: int = 0
    sel_h: int = 0

    # Layer stack
    layers: List[LayerState] = field(default_factory=lambda: [LayerState()])
    active_layer_index: int = 0

    # Brush workspace
    brush_engine_version: int = 1
    active_brush_id: str = "soft_round"
    custom_brush_presets: List[BrushPreset] = field(default_factory=list)

    def _ensure_layers(self) -> None:
        if not self.layers:
            self.layers = [LayerState()]
        self.active_layer_index = max(0, min(int(self.active_layer_index), len(self.layers) - 1))

    def active_layer(self) -> LayerState:
        self._ensure_layers()
        return self.layers[self.active_layer_index]

    # ---- Legacy compatibility accessors (active-layer mapped) ----
    @property
    def src_path(self) -> Optional[str]:
        return self.active_layer().src_path

    @src_path.setter
    def src_path(self, value: Optional[str]) -> None:
        self.active_layer().src_path = value

    @property
    def img_scale(self) -> float:
        return self.active_layer().img_scale

    @img_scale.setter
    def img_scale(self, value: float) -> None:
        self.active_layer().img_scale = float(value)

    @property
    def img_off_x(self) -> float:
        return self.active_layer().img_off_x

    @img_off_x.setter
    def img_off_x(self, value: float) -> None:
        self.active_layer().img_off_x = float(value)

    @property
    def img_off_y(self) -> float:
        return self.active_layer().img_off_y

    @img_off_y.setter
    def img_off_y(self, value: float) -> None:
        self.active_layer().img_off_y = float(value)

    @property
    def rotation_deg(self) -> int:
        return self.active_layer().rotation_deg

    @rotation_deg.setter
    def rotation_deg(self, value: int) -> None:
        self.active_layer().rotation_deg = int(value)

    @property
    def tolerance(self) -> int:
        return self.active_layer().tolerance

    @tolerance.setter
    def tolerance(self, value: int) -> None:
        self.active_layer().tolerance = int(value)

    @property
    def color_key_mode(self) -> str:
        return self.active_layer().color_key_mode

    @color_key_mode.setter
    def color_key_mode(self, value: str) -> None:
        self.active_layer().color_key_mode = str(value)

    @property
    def hsv_h_tol(self) -> int:
        return self.active_layer().hsv_h_tol

    @hsv_h_tol.setter
    def hsv_h_tol(self, value: int) -> None:
        self.active_layer().hsv_h_tol = int(value)

    @property
    def hsv_s_tol(self) -> int:
        return self.active_layer().hsv_s_tol

    @hsv_s_tol.setter
    def hsv_s_tol(self, value: int) -> None:
        self.active_layer().hsv_s_tol = int(value)

    @property
    def hsv_v_tol(self) -> int:
        return self.active_layer().hsv_v_tol

    @hsv_v_tol.setter
    def hsv_v_tol(self, value: int) -> None:
        self.active_layer().hsv_v_tol = int(value)

    @property
    def palette(self) -> List[PaletteColor]:
        return self.active_layer().palette

    @palette.setter
    def palette(self, value: List[PaletteColor]) -> None:
        self.active_layer().palette = value

    @property
    def mask_feather_radius(self) -> int:
        return self.active_layer().mask_feather_radius

    @mask_feather_radius.setter
    def mask_feather_radius(self, value: int) -> None:
        self.active_layer().mask_feather_radius = int(value)

    @property
    def mask_grow_shrink(self) -> int:
        return self.active_layer().mask_grow_shrink

    @mask_grow_shrink.setter
    def mask_grow_shrink(self, value: int) -> None:
        self.active_layer().mask_grow_shrink = int(value)

    @property
    def remove_islands_min_size(self) -> int:
        return self.active_layer().remove_islands_min_size

    @remove_islands_min_size.setter
    def remove_islands_min_size(self, value: int) -> None:
        self.active_layer().remove_islands_min_size = int(value)

    @property
    def opacity(self) -> float:
        return self.active_layer().opacity

    @opacity.setter
    def opacity(self, value: float) -> None:
        self.active_layer().opacity = float(value)

    @property
    def brightness(self) -> float:
        return self.active_layer().brightness

    @brightness.setter
    def brightness(self, value: float) -> None:
        self.active_layer().brightness = float(value)

    @property
    def contrast(self) -> float:
        return self.active_layer().contrast

    @contrast.setter
    def contrast(self, value: float) -> None:
        self.active_layer().contrast = float(value)

    @property
    def saturation(self) -> float:
        return self.active_layer().saturation

    @saturation.setter
    def saturation(self, value: float) -> None:
        self.active_layer().saturation = float(value)

    @property
    def gamma(self) -> float:
        return self.active_layer().gamma

    @gamma.setter
    def gamma(self, value: float) -> None:
        self.active_layer().gamma = float(value)

    @property
    def vibrance(self) -> float:
        return self.active_layer().vibrance

    @vibrance.setter
    def vibrance(self, value: float) -> None:
        self.active_layer().vibrance = float(value)

    @property
    def temperature(self) -> int:
        return self.active_layer().temperature

    @temperature.setter
    def temperature(self, value: int) -> None:
        self.active_layer().temperature = int(value)

    def enabled_palette_rgbs(self) -> List[Tuple[int, int, int]]:
        return self.active_layer().enabled_palette_rgbs()
