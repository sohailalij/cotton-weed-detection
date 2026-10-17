from PIL import Image

from weedlab.make_yolo_dataset import resize_long_side


def test_resize_shrinks_long_side() -> None:
    im = Image.new("RGB", (4000, 3000))
    out = resize_long_side(im, 1024)
    assert out.size == (1024, 768)


def test_resize_never_enlarges() -> None:
    im = Image.new("RGB", (800, 600))
    assert resize_long_side(im, 1024).size == (800, 600)
