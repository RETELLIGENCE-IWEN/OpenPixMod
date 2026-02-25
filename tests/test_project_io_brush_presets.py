from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.project_io import save_project, load_project
from core.state import ProjectState, BrushPreset


class ProjectIOBrushPresetTests(unittest.TestCase):
    def test_brush_fields_round_trip(self) -> None:
        state = ProjectState()
        state.brush_engine_version = 3
        state.active_brush_id = "textured_round"
        state.layers[0].alpha_paint_mask_data = "maskdata"
        state.custom_brush_presets = [
            BrushPreset(
                preset_id="textured_round",
                name="Textured Round",
                tool_mode="paint",
                size=48.0,
                hardness=0.65,
                spacing=0.2,
                flow=0.78,
                opacity=0.92,
                jitter_size=0.1,
                jitter_angle=0.35,
                jitter_scatter=0.4,
                blend_mode="multiply",
                symmetry_x=True,
                symmetry_y=False,
            )
        ]

        with TemporaryDirectory() as td:
            path = Path(td) / "brushes.opm"
            save_project(str(path), state)
            loaded = load_project(str(path))

        self.assertEqual(loaded.brush_engine_version, 3)
        self.assertEqual(loaded.active_brush_id, "textured_round")
        self.assertEqual(loaded.layers[0].alpha_paint_mask_data, "maskdata")
        self.assertEqual(len(loaded.custom_brush_presets), 1)
        preset = loaded.custom_brush_presets[0]
        self.assertEqual(preset.preset_id, "textured_round")
        self.assertEqual(preset.name, "Textured Round")
        self.assertEqual(preset.tool_mode, "paint")
        self.assertEqual(preset.blend_mode, "multiply")
        self.assertTrue(preset.symmetry_x)
        self.assertFalse(preset.symmetry_y)

    def test_brush_defaults_for_legacy_project(self) -> None:
        with TemporaryDirectory() as td:
            path = Path(td) / "legacy.json"
            path.write_text('{"state": {"out_w": 100, "out_h": 120}}', encoding="utf-8")
            loaded = load_project(str(path))

        self.assertEqual(loaded.brush_engine_version, 1)
        self.assertEqual(loaded.active_brush_id, "soft_round")
        self.assertEqual(loaded.custom_brush_presets, [])


if __name__ == "__main__":
    unittest.main()
