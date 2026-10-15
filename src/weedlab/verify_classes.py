"""Verify YOLO class ids against species names in the VGG JSON files."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from weedlab.audit import parse_label_file


def json_regions(data: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in data.values():
        regions = entry.get("regions", {})
        if isinstance(regions, dict):
            if "shape_attributes" in regions:
                out.append(regions)
            else:
                out.extend(r for r in regions.values() if isinstance(r, dict))
        elif isinstance(regions, list):
            out.extend(r for r in regions if isinstance(r, dict))
    return out


def region_species(region: dict[str, Any]) -> list[str]:
    attrs = region.get("region_attributes", {}).get("CottonWeed", {})
    if isinstance(attrs, dict):
        return [str(name) for name, on in attrs.items() if on]
    if isinstance(attrs, str) and attrs:
        return [attrs]
    return []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()

    lbl_dir: Path = args.root / "annotation_YOLO_txt"
    json_dir: Path = args.root / "annotation_VGG_json"

    pairs: dict[int, Counter[str]] = defaultdict(Counter)
    missing_json = 0
    yolo_total = 0
    json_total = 0
    mismatched: list[tuple[str, int, int]] = []

    for lbl in sorted(lbl_dir.glob("*.txt")):
        stem = lbl.stem
        boxes, _ = parse_label_file(lbl)
        yolo_total += len(boxes)
        jpath = json_dir / f"{stem}.json"
        if not jpath.exists():
            missing_json += 1
            continue
        data: dict[str, Any] = json.loads(jpath.read_text())
        regions = json_regions(data)
        json_total += len(regions)
        if len(regions) != len(boxes):
            mismatched.append((stem, len(boxes), len(regions)))

        names = [n for r in regions for n in region_species(r)]
        classes = {b[0] for b in boxes}
        if len(classes) == 1 and len(set(names)) == 1:
            pairs[next(iter(classes))][names[0]] += 1

    print(f"YOLO json files missing: {missing_json}")
    print(f"total boxes: YOLO {yolo_total}, JSON {json_total}")
    print(f"images where box counts differ: {len(mismatched)}")
    for stem, n_yolo, n_json in mismatched[:10]:
        print(f"  {stem}: YOLO {n_yolo}, JSON {n_json}")

    print("\nclass id -> species name (from single-class images)")
    for cls in sorted(pairs):
        total = sum(pairs[cls].values())
        name, count = pairs[cls].most_common(1)[0]
        print(f"  {cls}: {name}  ({count}/{total} images agree)")


if __name__ == "__main__":
    main()
