from __future__ import annotations

import unittest


class CompositorAlphaPaintMaskTests(unittest.TestCase):
    def test_alpha_paint_mask_applies_to_layer_alpha(self) -> None:
        try:
            import numpy as np
            from PIL import Image
            from core.compositor import LayerRenderInput, composite_layers_to_canvas
        except Exception as exc:  # pragma: no cover - environment dependency
            self.skipTest(f"missing runtime dependency: {exc}")

        src = Image.new("RGBA", (2, 2), (255, 0, 0, 255))
        mask = np.array([[255, 0], [128, 255]], dtype=np.uint8)
        out = composite_layers_to_canvas(
            layers=[
                LayerRenderInput(
                    src_rgba_pil=src,
                    alpha_paint_mask=mask,
                    palette_rgbs=[],
                    tolerance=0,
                )
            ],
            out_size=(2, 2),
            high_quality=False,
            nearest_neighbor=True,
        )
        arr = np.array(out.convert("RGBA"), dtype=np.uint8)
        self.assertEqual(int(arr[0, 0, 3]), 255)
        self.assertEqual(int(arr[0, 1, 3]), 0)
        self.assertLess(abs(int(arr[1, 0, 3]) - 128), 2)


if __name__ == "__main__":
    unittest.main()
