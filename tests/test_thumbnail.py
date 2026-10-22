from io import BytesIO

from PIL import Image

from weedlab.api.thumbnail import make_thumbnail


def size_of(data: bytes) -> tuple[int, int]:
    return Image.open(BytesIO(data)).size


def test_downscales_long_side_and_keeps_aspect() -> None:
    data = make_thumbnail(Image.new("RGB", (4000, 3000), (10, 200, 10)))
    assert size_of(data) == (640, 480)
    assert Image.open(BytesIO(data)).format == "JPEG"
    assert len(data) < 30_000


def test_portrait_photo_and_no_upscaling() -> None:
    assert size_of(make_thumbnail(Image.new("RGB", (900, 1600)))) == (360, 640)
    assert size_of(make_thumbnail(Image.new("RGB", (200, 100)))) == (200, 100)


def test_transparent_image_is_flattened_to_rgb() -> None:
    data = make_thumbnail(Image.new("RGBA", (50, 50), (0, 0, 0, 0)))
    assert Image.open(BytesIO(data)).mode == "RGB"
