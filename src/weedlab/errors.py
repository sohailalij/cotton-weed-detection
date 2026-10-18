"""Match predictions to ground truth on the test split and list every failure."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from weedlab.audit import parse_label_file
from weedlab.train import CLASS_NAMES

PixBox = tuple[float, float, float, float]
GtList = list[tuple[int, PixBox]]
PredList = list[tuple[int, float, PixBox]]


def iou(a: PixBox, b: PixBox) -> float:
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def yolo_to_pixels(x: float, y: float, w: float, h: float, img_w: int, img_h: int) -> PixBox:
    return (
        (x - w / 2) * img_w,
        (y - h / 2) * img_h,
        (x + w / 2) * img_w,
        (y + h / 2) * img_h,
    )


def match_image(gt: GtList, preds: PredList, iou_thr: float) -> list[dict[str, Any]]:
    """Greedy matching, highest confidence first. Each real box is used once."""
    events: list[dict[str, Any]] = []
    used: set[int] = set()
    for pcls, conf, pbox in sorted(preds, key=lambda p: -p[1]):
        best, best_iou = -1, 0.0
        for gi, (_, gbox) in enumerate(gt):
            if gi in used:
                continue
            value = iou(pbox, gbox)
            if value > best_iou:
                best, best_iou = gi, value
        if best >= 0 and best_iou >= iou_thr:
            used.add(best)
            gcls, gbox = gt[best]
            kind = "ok" if gcls == pcls else "confused"
            events.append(
                {
                    "type": kind,
                    "gt_class": gcls,
                    "pred_class": pcls,
                    "conf": conf,
                    "iou": best_iou,
                    "box": gbox,
                }
            )
        else:
            events.append(
                {
                    "type": "false_positive",
                    "gt_class": None,
                    "pred_class": pcls,
                    "conf": conf,
                    "iou": best_iou,
                    "box": pbox,
                }
            )
    for gi, (gcls, gbox) in enumerate(gt):
        if gi not in used:
            events.append(
                {
                    "type": "missed",
                    "gt_class": gcls,
                    "pred_class": None,
                    "conf": None,
                    "iou": None,
                    "box": gbox,
                }
            )
    return events


def size_bucket(short_px: float) -> str:
    if short_px < 32:
        return "<32px"
    if short_px < 64:
        return "32-64px"
    return ">=64px"


def draw_overlay(path: Path, gt: GtList, preds: PredList, out: Path) -> None:
    with Image.open(path) as raw:
        im = raw.convert("RGB")
    draw = ImageDraw.Draw(im)
    font = ImageFont.load_default(size=20)
    for cls, box in gt:
        draw.rectangle(box, outline=(0, 200, 0), width=4)
        draw.text((box[0] + 4, box[1] + 4), f"GT {CLASS_NAMES[cls]}", fill=(0, 255, 0), font=font)
    for cls, conf, box in preds:
        draw.rectangle(box, outline=(255, 0, 0), width=3)
        draw.text(
            (box[0] + 4, box[3] - 26),
            f"{CLASS_NAMES[cls]} {conf:.2f}",
            fill=(255, 255, 0),
            font=font,
        )
    im.save(out, quality=85)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--data-root", type=Path, default=Path("data/yolo"))
    ap.add_argument("--out", type=Path, default=Path("reports/error_analysis"))
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--match-iou", type=float, default=0.5)
    ap.add_argument("--top", type=int, default=40)
    args = ap.parse_args()

    from ultralytics import YOLO

    model = YOLO(str(args.model))
    out_dir = args.out / args.model.stem
    (out_dir / "worst").mkdir(parents=True, exist_ok=True)
    images = sorted((args.data_root / "images" / "test").glob("*.jpg"))

    rows: list[dict[str, Any]] = []
    totals: Counter[str] = Counter()
    all_gt_by_size: Counter[str] = Counter()
    per_image: Counter[str] = Counter()
    detail: dict[str, tuple[GtList, PredList]] = {}

    results = model.predict(
        source=[str(p) for p in images],
        conf=args.conf,
        imgsz=640,
        device="cpu",
        stream=True,
        verbose=False,
    )
    for n, (path, res) in enumerate(zip(images, results, strict=True), start=1):
        img_h, img_w = res.orig_shape
        label_boxes, _ = parse_label_file(args.data_root / "labels" / "test" / f"{path.stem}.txt")
        gt: GtList = [
            (c, yolo_to_pixels(x, y, w, h, img_w, img_h)) for c, x, y, w, h in label_boxes
        ]
        xyxy = res.boxes.xyxy.tolist()
        confs = res.boxes.conf.tolist()
        clss = res.boxes.cls.tolist()
        preds: PredList = [
            (int(c), float(cf), (b[0], b[1], b[2], b[3]))
            for b, cf, c in zip(xyxy, confs, clss, strict=True)
        ]
        detail[path.stem] = (gt, preds)

        scale = 640 / max(img_w, img_h)
        totals["gt_boxes"] += len(gt)
        for _, gt_box in gt:
            short = min(gt_box[2] - gt_box[0], gt_box[3] - gt_box[1]) * scale
            all_gt_by_size[size_bucket(short)] += 1

        for ev in match_image(gt, preds, args.match_iou):
            totals[ev["type"]] += 1
            if ev["type"] == "ok":
                continue
            box: PixBox = ev["box"]
            short = min(box[2] - box[0], box[3] - box[1]) * scale
            rows.append(
                {
                    "image": path.stem,
                    "type": ev["type"],
                    "gt_class": CLASS_NAMES[ev["gt_class"]] if ev["gt_class"] is not None else "",
                    "pred_class": (
                        CLASS_NAMES[ev["pred_class"]] if ev["pred_class"] is not None else ""
                    ),
                    "conf": round(ev["conf"], 3) if ev["conf"] is not None else "",
                    "iou": round(ev["iou"], 3) if ev["iou"] is not None else "",
                    "area_frac": round((box[2] - box[0]) * (box[3] - box[1]) / (img_w * img_h), 4),
                    "short_px_640": round(short, 1),
                }
            )
            per_image[path.stem] += 1
        if n % 100 == 0:
            print(f"  processed {n}/{len(images)}", flush=True)

    with (out_dir / "failures.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    gt_failures = [r for r in rows if r["type"] in ("missed", "confused")]
    summary: dict[str, Any] = {
        "model": args.model.name,
        "conf": args.conf,
        "match_iou": args.match_iou,
        "images": len(images),
        "gt_boxes": totals["gt_boxes"],
        "ok": totals["ok"],
        "confused": totals["confused"],
        "missed": totals["missed"],
        "false_positive": totals["false_positive"],
        "failures_by_gt_class": dict(Counter(r["gt_class"] for r in gt_failures)),
        "top_confusions": [
            [a, b, count]
            for (a, b), count in Counter(
                (r["gt_class"], r["pred_class"]) for r in rows if r["type"] == "confused"
            ).most_common(10)
        ],
        "all_gt_by_size": dict(all_gt_by_size),
        "gt_failures_by_size": dict(Counter(size_bucket(r["short_px_640"]) for r in gt_failures)),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1))

    for rank, (stem, count) in enumerate(per_image.most_common(args.top), start=1):
        gt, preds = detail[stem]
        draw_overlay(
            args.data_root / "images" / "test" / f"{stem}.jpg",
            gt,
            preds,
            out_dir / "worst" / f"{rank:02d}_{count}err_{stem}.jpg",
        )

    print(json.dumps(summary, indent=1))
    print(f"\nsaved to {out_dir}")


if __name__ == "__main__":
    main()
