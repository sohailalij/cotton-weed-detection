"""Compare the ONNX detector with the PyTorch checkpoint it was exported from."""

from __future__ import annotations

import argparse
import statistics
import time
from pathlib import Path
from typing import Any

from PIL import Image
from ultralytics import YOLO

from weedlab.inference import Detection, Detector


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def torch_detections(result: Any, names: dict[int, str]) -> list[Detection]:
    out: list[Detection] = []
    for b, c, k in zip(
        result.boxes.xyxy.tolist(),
        result.boxes.conf.tolist(),
        result.boxes.cls.tolist(),
        strict=True,
    ):
        box = (float(b[0]), float(b[1]), float(b[2]), float(b[3]))
        out.append(Detection(box, float(c), int(k), names[int(k)]))
    return out


def match(a: list[Detection], b: list[Detection], thr: float) -> tuple[int, float]:
    """Count detections in a that have a same-class detection in b with IoU >= thr."""
    used: set[int] = set()
    matched = 0
    max_diff = 0.0
    for det in a:
        best, best_iou = -1, thr
        for j, other in enumerate(b):
            if j in used or other.class_id != det.class_id:
                continue
            value = iou(det.box, other.box)
            if value >= best_iou:
                best, best_iou = j, value
        if best >= 0:
            used.add(best)
            matched += 1
            max_diff = max(max_diff, abs(det.score - b[best].score))
    return matched, max_diff


def p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=Path, required=True)
    ap.add_argument("--onnx", type=Path, required=True)
    ap.add_argument("--images", type=Path, default=Path("data/yolo/images/test"))
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--n", type=int, default=50)
    args = ap.parse_args()

    paths = sorted(args.images.glob("*.jpg"))
    paths = paths[:: max(1, len(paths) // args.n)][: args.n]
    torch_model = YOLO(str(args.pt))
    names: dict[int, str] = dict(torch_model.names)
    detector = Detector(args.onnx, imgsz=args.imgsz)

    def run_torch(path: Path) -> list[Detection]:
        result = torch_model.predict(
            str(path), imgsz=args.imgsz, conf=args.conf, iou=0.7, device="cpu", verbose=False
        )[0]
        return torch_detections(result, names)

    def run_onnx(path: Path) -> list[Detection]:
        with Image.open(path) as image:
            return detector.detect(image, conf=args.conf)

    for path in paths[:3]:  # warm-up, not timed
        run_torch(path)
        run_onnx(path)

    t_torch: list[float] = []
    t_onnx: list[float] = []
    n_torch = n_onnx = n_match = n_match_rev = 0
    worst = 0.0
    for path in paths:
        start = time.perf_counter()
        a = run_torch(path)
        t_torch.append((time.perf_counter() - start) * 1000)
        start = time.perf_counter()
        b = run_onnx(path)
        t_onnx.append((time.perf_counter() - start) * 1000)
        m, diff = match(a, b, 0.9)
        n_torch, n_onnx, n_match = n_torch + len(a), n_onnx + len(b), n_match + m
        n_match_rev += match(b, a, 0.9)[0]
        worst = max(worst, diff)

    print(f"images: {len(paths)}  imgsz: {args.imgsz}  conf: {args.conf}")
    print(f"detections: torch {n_torch}, onnx {n_onnx}")
    print(f"torch detections with an onnx match (same class, IoU>=0.9): {n_match}")
    print(f"onnx detections with a torch match: {n_match_rev}")
    print(f"largest confidence difference among matches: {worst:.4f}")
    t, o = statistics.median(t_torch), statistics.median(t_onnx)
    print(f"torch  median {t:.1f} ms, p95 {p95(t_torch):.1f} ms")
    print(f"onnx   median {o:.1f} ms, p95 {p95(t_onnx):.1f} ms  (speed-up x{t / o:.2f})")


if __name__ == "__main__":
    main()
