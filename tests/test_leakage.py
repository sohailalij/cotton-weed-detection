from pathlib import Path

from PIL import Image, ImageOps

from weedlab.leakage import dhash, hamming


def test_identical_images_have_same_hash(tmp_path: Path) -> None:
    im = Image.linear_gradient("L").rotate(90)
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    im.save(a)
    im.save(b)
    assert hamming(dhash(a), dhash(b)) == 0


def test_mirrored_gradient_is_far_apart(tmp_path: Path) -> None:
    im = Image.linear_gradient("L").rotate(90)
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    im.save(a)
    ImageOps.mirror(im).save(b)
    assert hamming(dhash(a), dhash(b)) > 32
