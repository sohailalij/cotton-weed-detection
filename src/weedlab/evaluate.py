"""Evaluate trained models once on the frozen test split (CPU only)."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

from weedlab.train import CLASS_NAMES, write_data_yaml


def per_class_rows(results: Any) -> list[dict[str, Any]]:
    box = results.box
    rows: list[dict[str, Any]] = []
    for i, cls in enumerate(box.ap_class_index):
        c = int(cls)
        rows.append(
            {
                "class": CLASS_NAMES[c],
                "images": int(results.nt_per_image[c]),
                "boxes": int(results.nt_per_class[c]),
                "precision": round(float(box.p[i]), 4),
                "recall": round(float(box.r[i]), 4),
                "map50": round(float(box.ap50[i]), 4),
                "map50_95": round(float(box.ap[i]), 4),
            }
        )
    return rows


def markdown_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Class | Images | Boxes | P | R | mAP50 | mAP50-95 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['class']} | {r['images']} | {r['boxes']} | {r['precision']:.3f} "
            f"| {r['recall']:.3f} | {r['map50']:.3f} | {r['map50_95']:.3f} |"
        )
    return "\n".join(lines)


def cpu_latency(
    model: Any, images: list[Path], warmup: int = 5, imgsz: int = 640
) -> dict[str, float]:
    """Wall time of one predict() call per image, including decode and postprocess."""
    for path in images[:warmup]:
        model.predict(str(path), imgsz=imgsz, device="cpu", verbose=False)
    times: list[float] = []
    for path in images[warmup:]:
        start = time.perf_counter()
        model.predict(str(path), imgsz=imgsz, device="cpu", verbose=False)
        times.append((time.perf_counter() - start) * 1000)
    times.sort()
    return {
        "n_images": float(len(times)),
        "median_ms": round(statistics.median(times), 1),
        "p95_ms": round(times[int(0.95 * (len(times) - 1))], 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", type=Path, nargs="+", required=True)
    ap.add_argument("--data-root", type=Path, default=Path("data/yolo"))
    ap.add_argument("--out", type=Path, default=Path("reports/test_eval"))
    ap.add_argument("--latency-images", type=int, default=50)
    ap.add_argument("--imgsz", type=int, default=640)
    args = ap.parse_args()

    from ultralytics import YOLO

    data_yaml = write_data_yaml(args.data_root.resolve(), Path("data/processed/data_eval.yaml"))
    test_images = sorted((args.data_root / "images" / "test").glob("*.jpg"))
    latency_set = test_images[: args.latency_images + 5]

    for model_path in args.models:
        model = YOLO(str(model_path))
        results = model.val(
            data=str(data_yaml),
            split="test",
            imgsz=args.imgsz,
            batch=16,
            device="cpu",
            workers=0,
            plots=True,
            project=str(args.out.resolve()),
            name=model_path.stem,
            exist_ok=True,
            verbose=False,
        )
        rows = per_class_rows(results)
        report = {
            "model_file": model_path.name,
            "split": "test",
            "map50": round(float(results.box.map50), 4),
            "map50_95": round(float(results.box.map), 4),
            "precision": round(float(results.box.mp), 4),
            "recall": round(float(results.box.mr), 4),
            "per_class": rows,
            "cpu_latency": cpu_latency(model, latency_set, imgsz=args.imgsz),
            "versions": {
                "python": platform.python_version(),
                "ultralytics": version("ultralytics"),
                "torch": version("torch"),
                "cpu": platform.processor(),
            },
        }
        save_dir = Path(results.save_dir)
        (save_dir / "metrics.json").write_text(json.dumps(report, indent=1))
        print(f"\n== {model_path.name} (test split) ==")
        print(
            f"mAP50 {report['map50']}  mAP50-95 {report['map50_95']}  "
            f"P {report['precision']}  R {report['recall']}"
        )
        print(f"CPU latency: {report['cpu_latency']}")
        print(markdown_table(rows))
        print(f"saved to {save_dir}")


if __name__ == "__main__":
    main()
