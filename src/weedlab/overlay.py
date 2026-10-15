"""Draw YOLO boxes on a few random images for a visual sanity check."""

from __future__ import annotations

import argparse
import random
from pathlib import Path

from PIL import Image, ImageDraw

from weedlab.audit import parse_label_file

# Verified against species names in annotation_VGG_json.
CLASS_NAMES = [
    "Amaranthus tuberculatus",
    "Ipomoea indica",
    "Portulaca oleracea",
    "Euphorbia maculata",
    "Mollugo verticillata",
    "Ambrosia artemisiifolia",
    "Eclipta",
    "Sida rhombifolia",
    "Amaranthus palmeri",
    "Senna obtusifolia",
    "Eleusine indica",
    "Physalis angulata",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("reports/overlays"))
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--stems", nargs="*", default=None)
    args = ap.parse_args()

    img_dir: Path = args.root / "weedImages"
    lbl_dir: Path = args.root / "annotation_YOLO_txt"
    images = {p.stem: p for p in img_dir.iterdir()}
    stems = sorted(p.stem for p in lbl_dir.glob("*.txt"))
    picks = args.stems or random.Random(0).sample(stems, args.n)
    args.out.mkdir(parents=True, exist_ok=True)

    for stem in picks:
        boxes, _ = parse_label_file(lbl_dir / f"{stem}.txt")
        with Image.open(images[stem]) as raw:
            im = raw.convert("RGB")
        im.thumbnail((1200, 1200))
        w, h = im.size
        draw = ImageDraw.Draw(im)
        for cls, x, y, bw, bh in boxes:
            x0, y0 = (x - bw / 2) * w, (y - bh / 2) * h
            x1, y1 = (x + bw / 2) * w, (y + bh / 2) * h
            draw.rectangle((x0, y0, x1, y1), outline=(255, 0, 0), width=3)
            draw.text((x0 + 4, y0 + 4), f"{cls} {CLASS_NAMES[cls]}", fill=(255, 255, 0))
        im.save(args.out / f"{stem}.jpg")
        print("wrote", stem)


if __name__ == "__main__":
    main()
