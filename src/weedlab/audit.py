"""Audit CottonWeedDet12: label validity, image sizes, EXIF orientation."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from PIL import Image

IMG_EXTS = {".jpg", ".jpeg", ".png"}
EXIF_ORIENTATION = 274

Box = tuple[int, float, float, float, float]


def parse_label_file(path: Path) -> tuple[list[Box], list[str]]:
    boxes: list[Box] = []
    problems: list[str] = []
    text = path.read_text().strip()
    if not text:
        return boxes, ["empty label file"]
    for i, line in enumerate(text.splitlines(), start=1):
        parts = line.split()
        if len(parts) != 5:
            problems.append(f"line {i}: expected 5 fields, got {len(parts)}")
            continue
        try:
            cls = int(parts[0])
            x, y, w, h = (float(p) for p in parts[1:])
        except ValueError:
            problems.append(f"line {i}: non-numeric value")
            continue
        if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
            problems.append(f"line {i}: values out of range")
            continue
        boxes.append((cls, x, y, w, h))
    return boxes, problems


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("reports/image_audit.csv"))
    args = ap.parse_args()

    img_dir: Path = args.root / "weedImages"
    lbl_dir: Path = args.root / "annotation_YOLO_txt"
    images = {p.stem: p for p in img_dir.iterdir() if p.suffix.lower() in IMG_EXTS}
    labels = {p.stem: p for p in lbl_dir.glob("*.txt")}

    print(f"images: {len(images)}  labels: {len(labels)}")
    print(f"images without label: {len(set(images) - set(labels))}")
    print(f"labels without image: {len(set(labels) - set(images))}")

    rows: list[dict[str, object]] = []
    class_boxes: Counter[int] = Counter()
    class_images: Counter[int] = Counter()
    sizes: Counter[tuple[int, int]] = Counter()
    orientations: Counter[int] = Counter()
    groups: Counter[str] = Counter()
    bad_files = 0

    for stem, img_path in sorted(images.items()):
        with Image.open(img_path) as im:
            width, height = im.size
            orient = int(im.getexif().get(EXIF_ORIENTATION, 1))
        boxes: list[Box] = []
        problems: list[str] = []
        if stem in labels:
            boxes, problems = parse_label_file(labels[stem])
        if problems:
            bad_files += 1

        parts = stem.split("_")
        date, device = (parts[0], parts[1]) if len(parts) >= 4 else ("unknown", "unknown")
        classes = sorted({b[0] for b in boxes})
        for b in boxes:
            class_boxes[b[0]] += 1
        for c in classes:
            class_images[c] += 1
        sizes[(width, height)] += 1
        orientations[orient] += 1
        groups[f"{date}_{device}"] += 1

        rows.append(
            {
                "stem": stem,
                "date": date,
                "device": device,
                "width": width,
                "height": height,
                "exif_orientation": orient,
                "n_boxes": len(boxes),
                "classes": ";".join(str(c) for c in classes),
                "problems": " | ".join(problems),
            }
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nfiles with label problems: {bad_files}")
    print(f"total boxes: {sum(class_boxes.values())}")
    print("\nclass id: images / boxes")
    for c in sorted(class_boxes):
        print(f"  {c}: {class_images[c]} / {class_boxes[c]}")
    print("\nimage sizes (top 5):", sizes.most_common(5))
    print("EXIF orientations:", dict(orientations))
    print("\ndate_device groups:", len(groups))
    for g, n in groups.most_common(10):
        print(f"  {g}: {n}")
    print(f"\nreport written to {args.out}")


if __name__ == "__main__":
    main()
