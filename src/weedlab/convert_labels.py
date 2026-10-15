"""Build training labels from the VGG JSON annotations (the trusted source)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image

from weedlab.audit import IMG_EXTS, Box, parse_label_file
from weedlab.verify_classes import json_regions, region_species

SPECIES_TO_ID = {
    "Waterhemp": 0,
    "MorningGlory": 1,
    "Purslane": 2,
    "SpottedSpurge": 3,
    "Carpetweed": 4,
    "Ragweed": 5,
    "Eclipta": 6,
    "PricklySida": 7,
    "PalmerAmaranth": 8,
    "Sicklepod": 9,
    "Goosegrass": 10,
    "CutleafGroundcherry": 11,
}


def region_to_box(region: dict[str, Any], width: int, height: int) -> Box | None:
    species = region_species(region)
    if len(species) != 1 or species[0] not in SPECIES_TO_ID:
        return None
    shape = region.get("shape_attributes", {})
    if shape.get("name") != "rect":
        return None
    x0 = max(0.0, float(shape["x"]))
    y0 = max(0.0, float(shape["y"]))
    x1 = min(float(width), float(shape["x"]) + float(shape["width"]))
    y1 = min(float(height), float(shape["y"]) + float(shape["height"]))
    if x1 <= x0 or y1 <= y0:
        return None
    return (
        SPECIES_TO_ID[species[0]],
        (x0 + x1) / 2 / width,
        (y0 + y1) / 2 / height,
        (x1 - x0) / width,
        (y1 - y0) / height,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("data/processed/labels"))
    args = ap.parse_args()

    img_dir: Path = args.root / "weedImages"
    json_dir: Path = args.root / "annotation_VGG_json"
    yolo_dir: Path = args.root / "annotation_YOLO_txt"
    images = {p.stem: p for p in img_dir.iterdir() if p.suffix.lower() in IMG_EXTS}
    args.out.mkdir(parents=True, exist_ok=True)

    skipped = 0
    written = 0
    total_boxes = 0
    differs: list[str] = []

    for jpath in sorted(json_dir.glob("*.json")):
        stem = jpath.stem
        with Image.open(images[stem]) as im:
            width, height = im.size
        data: dict[str, Any] = json.loads(jpath.read_text())
        boxes: list[Box] = []
        for region in json_regions(data):
            box = region_to_box(region, width, height)
            if box is None:
                skipped += 1
            else:
                boxes.append(box)

        lines = [f"{c} {x:.6f} {y:.6f} {w:.6f} {h:.6f}" for c, x, y, w, h in boxes]
        (args.out / f"{stem}.txt").write_text("\n".join(lines) + "\n")
        written += 1
        total_boxes += len(boxes)

        old, _ = parse_label_file(yolo_dir / f"{stem}.txt")
        if sorted(b[0] for b in old) != sorted(b[0] for b in boxes):
            differs.append(stem)

    print(f"label files written: {written}")
    print(f"total boxes: {total_boxes}")
    print(f"regions skipped (unknown species, bad shape): {skipped}")
    print(f"images whose classes differ from shipped YOLO files: {len(differs)}")
    for s in differs:
        print(f"  {s}")


if __name__ == "__main__":
    main()
