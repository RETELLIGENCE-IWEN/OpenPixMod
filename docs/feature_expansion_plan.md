# OpenPixMod Feature Expansion Plan

This document proposes a pragmatic path to add:

1. Multi-layer editing
2. Paint/retouch tools
3. A richer adjustment/filter stack

The plan is intentionally incremental so the app remains stable and shippable after each phase.

## Current baseline (summary)

OpenPixMod currently has a single-source compositing model (`src_path` + one image in memory), color-key/mask refinement, selection masks, transform controls, and a compact adjustment set (opacity, brightness, contrast, saturation, gamma).

## Phase 1 — Data model + backward compatibility (multi-layer foundation)

### Goals
- Keep existing projects opening exactly as before.
- Introduce a layer schema in project state and project files.
- Keep rendering behavior identical while only one layer exists.

### Changes
- Add `LayerState` dataclass:
  - `name`, `src_path`, `visible`, `opacity`, `blend_mode`
  - per-layer transform: `img_scale`, `img_off_x`, `img_off_y`, `rotation_deg`
  - optional per-layer mask/retouch map references
- Add to `ProjectState`:
  - `layers: list[LayerState]`
  - `active_layer_index: int`
- Project IO:
  - When loading old files without `layers`, synthesize a single `LayerState` from old fields.
  - When saving, write both the new layer list and (temporarily) legacy fields to keep downgrade compatibility.

### Acceptance criteria
- Existing `.opm/.json` projects load unchanged.
- New projects save/load with `layers`.

## Phase 2 — Renderer upgrade (composite multiple layers)

### Goals
- Move from one-source composition to ordered layer compositing.
- Preserve current masking/keying behavior per layer.

### Changes
- Add `composite_layers_to_canvas(layers=..., out_size=...)` in `core/compositor.py`.
- For each visible layer:
  - load/cache source image
  - apply layer-local keying/mask/refine/adjustments
  - apply blend mode + opacity onto canvas
- Keep a compatibility wrapper that maps old single-image calls to one layer.

### Blend modes (initial set)
- `normal`
- `multiply`
- `screen`
- `overlay`

### Acceptance criteria
- Two-layer test projects render in correct order.
- Single-layer renders are pixel-identical (or within small tolerance) to previous output.

## Phase 3 — Layer UI/UX

### Goals
- Make layers discoverable and usable from the main window.

### Changes
- New “Layers” dock:
  - layer list with visibility toggle
  - add/remove/duplicate/reorder
  - active-layer selection
  - per-layer opacity + blend mode controls
- Update undo/redo snapshots to include layer stack + active layer + per-layer masks.

### Acceptance criteria
- Basic layer operations are undoable.
- User can stack and reorder at least 5 layers.

## Phase 4 — Paint/retouch MVP

### Goals
- Provide practical pixel editing for mask cleanup and touch-ups.

### Tools (MVP)
- Brush
- Eraser
- Clone stamp (optional in MVP, otherwise phase 4.5)

### Technical approach
- Add per-layer editable maps:
  - `alpha_paint_mask` (for non-destructive transparency painting)
  - optional `retouch_bitmap` for destructive paint mode
- In `CanvasWidget`, add stroke handling with:
  - brush size/hardness/flow
  - cursor preview
  - tablet pressure support later
- Apply strokes in source-space for the active layer (map canvas → layer image coords).

### Acceptance criteria
- User can erase/restore transparency with brush strokes.
- Strokes persist in project save/load.
- Brush strokes participate in undo/redo.

## Phase 5 — Rich adjustment/filter stack

### Goals
- Move from fixed global controls to a stack-based non-destructive pipeline.

### Filter model
Each filter node should include:
- `type` (e.g., levels, curves, hue_sat, white_balance, blur, sharpen)
- `enabled`
- parameter payload (typed dict)
- optional mask/selection target

### Suggested initial filters
- Tonal/color:
  - Levels
  - Curves (RGB + per-channel)
  - Hue/Saturation
  - White balance (temperature/tint)
  - Vibrance
- Detail/effects:
  - Gaussian blur
  - Unsharp mask
  - Noise reduction (basic)

### Rendering order
For each layer:
1. Source decode
2. Keying/mask operations
3. Retouch maps
4. Adjustment/filter stack (ordered)
5. Layer blend into canvas

### Acceptance criteria
- Reorderable filter list per layer.
- Toggle visibility of each filter.
- No destructive writes to source image files.

## Recommended implementation order

1. Phase 1 + project compatibility tests
2. Phase 2 compositor + pixel parity checks
3. Phase 3 layer dock
4. Phase 4 brush/eraser
5. Phase 5 filter stack

## Risks and mitigations

- **Performance regressions**: add image cache + tiled updates + preview resolution modes.
- **Undo memory growth**: switch to command-based undo for brush strokes and delta encoding.
- **Complexity creep**: keep strict MVP scope for each phase and defer advanced tools until baseline is stable.

## Test strategy

- Unit tests:
  - project load/save migration paths
  - blend mode math
  - filter parameter validation
- Golden-image tests:
  - known projects rendered to expected PNG outputs
- UI smoke tests:
  - add/reorder layers, apply filter, paint stroke, undo/redo

## First practical milestone (2–3 sessions)

- Introduce `LayerState` and migration in project IO.
- Add a minimal Layers dock with list + visibility + reorder.
- Render multiple visible layers with `normal` blend mode only.

This gives immediate user-facing value while keeping risk controlled.
