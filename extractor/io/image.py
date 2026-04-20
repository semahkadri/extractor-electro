from __future__ import annotations

import io
from pathlib import Path
from typing import NamedTuple

from PIL import Image, ImageEnhance

from ..models.exceptions import ImageError

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".jfif", ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
)


class CropBox(NamedTuple):
    """Percentage-based crop coordinates (0.0-1.0)."""
    x1: float
    y1: float
    x2: float
    y2: float


# Calibrated crop regions for the AQUILLA panel layout.
CROP_PUISSANCE = CropBox(0.02, 0.25, 0.45, 0.55)
CROP_ACCELERATEURS = CropBox(0.38, 0.25, 0.75, 0.55)
CROP_GLOBAL = CropBox(0.30, 0.48, 0.80, 0.72)


def validate_path(path: str | Path) -> Path:
    """Validate that *path* exists and is a supported format."""
    p = Path(path)
    if not p.exists():
        raise ImageError(f"Image not found: {p}")
    if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ImageError(f"Unsupported format '{p.suffix}'.")
    return p


def load_and_enhance(path: str | Path, contrast: float = 1.4, sharpness: float = 1.8) -> Image.Image:
    """Load image, convert to RGB, enhance contrast + sharpness."""
    p = validate_path(path)
    img = Image.open(p).convert("RGB")
    img = ImageEnhance.Contrast(img).enhance(contrast)
    img = ImageEnhance.Sharpness(img).enhance(sharpness)
    return img


def crop_percent(img: Image.Image, box: CropBox) -> Image.Image:
    """Crop using percentage-based coordinates."""
    w, h = img.size
    return img.crop((int(w * box.x1), int(h * box.y1), int(w * box.x2), int(h * box.y2)))


def to_png_bytes(img: Image.Image) -> bytes:
    """Encode PIL Image as PNG bytes."""
    buf = io.BytesIO()
    img.save(buf, format="PNG", quality=95)
    return buf.getvalue()
