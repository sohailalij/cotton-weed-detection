"""Small JPEG copies of uploaded photos, for the history page."""

from __future__ import annotations

from io import BytesIO

from PIL import Image

THUMB_MAX_SIDE = 640
THUMB_QUALITY = 80


def make_thumbnail(
    image: Image.Image, max_side: int = THUMB_MAX_SIDE, quality: int = THUMB_QUALITY
) -> bytes:
    """Downscale to at most max_side on the long side (never upscale) and encode as JPEG."""
    small = image.convert("RGB")
    small.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    small.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()
