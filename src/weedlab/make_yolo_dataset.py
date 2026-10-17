"""Build a YOLO-layout dataset (resized images plus labels) from the frozen split."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from PIL import Image


def resize_long_side(im: Image.Image, long_side: int) -> Image.Image:
    w, h = im.size
    scale = long_side / max(w, h)
    if scale >= 1:
        return im
    return im.resize((round(w * scale), round(h * scale)), Image.Resampling.LANCZOS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--labels", type=Path, default=Path("data/processed/labels"))
    ap.add_argument("--manifest", type=Path, default=Path("configs/split_v1.json"))
    ap.add_argument("--out", type=Path, default=Path("data/yolo"))
    ap.add_argument("--long-side", type=int, default=1024)
    ap.add_argument("--quality", type=int, default=90)
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text())
    images = {p.stem: p for p in (args.root / "weedImages").iterdir()}

    for split, stems in manifest["images"].items():
        img_out = args.out / "images" / split
        lbl_out = args.out / "labels" / split
        img_out.mkdir(parents=True, exist_ok=True)
        lbl_out.mkdir(parents=True, exist_ok=True)
        for n, stem in enumerate(stems, start=1):
            with Image.open(images[stem]) as raw:
                im = resize_long_side(raw.convert("RGB"), args.long_side)
                im.save(img_out / f"{stem}.jpg", quality=args.quality)
            shutil.copyfile(args.labels / f"{stem}.txt", lbl_out / f"{stem}.txt")
            if n % 500 == 0:
                print(f"  {split}: {n}/{len(stems)}", flush=True)
        print(f"{split}: {len(stems)} images written", flush=True)


if __name__ == "__main__":
    main()
