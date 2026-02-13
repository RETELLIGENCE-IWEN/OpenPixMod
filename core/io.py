from __future__ import annotations
from PIL import Image

def load_image_rgba(path: str) -> Image.Image:
    img = Image.open(path)
    # Convert to RGBA for consistent alpha work
    return img.convert("RGBA")

def save_image(path: str, img_rgba: Image.Image) -> None:
    # Saving as PNG preserves alpha
    img_rgba.save(path)
