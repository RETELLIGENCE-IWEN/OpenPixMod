# Advanced Brush Tools Implementation Plan

This plan expands OpenPixMod's paint/retouch direction into a production-ready advanced brush system while keeping delivery incremental.

## 1) Product goals and scope

### Target users
- Pixel artists doing cleanup and selective touchups.
- Digital illustrators who need texture, blending, and expressive strokes.
- Background-removal users who need quick mask correction tools.

### Priority workflows (v1)
1. **Mask cleanup**: precise erase/restore with soft edges.
2. **Detail painting**: textured and scatter brushes for surface variation.
3. **Blend touchup**: smudge/mixer for seam and transition cleanup.

### Success metrics
- Brush-stroke latency remains interactive on common canvas sizes.
- Users can switch tools and presets in under two clicks.
- Brush presets are persistent and portable across projects.

## 2) Brush architecture

Introduce a unified brush engine API in core paint modules:

- `BrushPreset`: static parameters (shape, spacing, hardness, blend mode, jitter bounds).
- `BrushDynamics`: input-driven modulation (pressure size/opacity/flow, tilt angle/roundness).
- `StrokeSample`: pointer sample (`x`, `y`, `pressure`, `tilt`, timestamp).
- `StrokeRenderer`: interpolation + stamp application + compositing.

### Pipeline
1. Collect pointer events into stroke samples.
2. Resample path using spacing policy.
3. Resolve dynamic values per stamp (size, flow, angle, scatter offset).
4. Stamp to active target map (alpha mask or paint bitmap).
5. Commit stroke command to undo/redo stack.

## 3) Initial advanced brush pack

Ship a focused first pack:

- **Soft Round** (baseline)
- **Textured Round**
- **Scatter Dots**
- **Calligraphy Flat**
- **Smudge**
- **Mixer**
- **Symmetry Brush** (X/Y mirrored)
- **Eraser variants** (hard, soft, textured)

### Acceptance criteria (per brush)
- Preview appears correctly in UI.
- Stroke output is deterministic with same seed/settings.
- Undo/redo restores canvas exactly.

## 4) UI/UX plan

Add a dedicated **Brushes** dock:

- Brush library list with category filters.
- Preset favorites and recently used section.
- Contextual settings panel:
  - size, hardness, spacing, flow, opacity
  - jitter controls (size/angle/scatter)
  - blend mode and symmetry toggles
- Live brush tip preview.
- Beginner/advanced toggle to reduce visual clutter.

## 5) Input device support

### Input matrix
- Mouse: full support except pressure/tilt.
- Tablet pen: pressure in v1; tilt in v1.1.
- Touch/stylus: basic support with smoothing fallback.

### Behavior rules
- Missing pressure defaults to 1.0.
- Missing tilt disables tilt dynamics without errors.
- Configurable smoothing per device type.

## 6) Performance strategy

- Path chunking for long strokes.
- Dirty-rect rendering updates instead of full-canvas redraw.
- Stroke stamp caching for repeated brush tips.
- Async low-priority preview updates where possible.
- Memory budget guardrails for texture-heavy presets.

### Performance targets
- Typical stroke segment processing under ~16ms on mid-range hardware.
- No unbounded memory growth during extended paint sessions.

## 7) Persistence and versioning

Persist brush system in project and preset files:

- `brush_engine_version`
- `active_brush_id`
- `custom_presets[]`
- `tool_mode` (paint, erase, smudge, mixer)

### Import/export
- JSON brush preset bundles (`.opmbrush`).
- Backward-compatible parser with default-fallback values.
- Migration path for schema upgrades.

## 8) QA strategy

### Automated
- Golden-image tests for known stroke sequences.
- Serialization round-trip tests for presets.
- Performance micro-benchmarks for heavy brush scenarios.

### Manual
- Cross-platform interaction checks (Windows/Linux/macOS where available).
- Tablet sanity checks (pressure curve and line smoothness).
- Undo/redo reliability under long paint sessions.

## 9) Rollout strategy

### Milestones
1. **Alpha**: architecture + soft round/textured/scatter/eraser.
2. **Beta**: smudge/mixer + preset import/export + performance tuning.
3. **Stable**: symmetry, polish, docs/tutorials, defaults tuning.

### Release controls
- Feature flag for advanced brushes.
- Optional telemetry counters (brush type usage, latency buckets).
- In-app onboarding snippets and short tutorial examples.

## Suggested implementation sequence (engineering)

1. Add brush/preset schema and project-IO persistence.
2. Add stroke renderer with round + eraser baseline.
3. Add brush dock UI and preset switching.
4. Add textured/scatter/calligraphy dynamics.
5. Add smudge/mixer and symmetry.
6. Benchmark, optimize, and finalize migration logic.
