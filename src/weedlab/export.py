"""Export a trained YOLO checkpoint to ONNX and show what the exported model expects."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import onnxruntime as ort
from ultralytics import YOLO


def export_onnx(weights: Path, out: Path, imgsz: int) -> Path:
    """Export with dynamic height and width, move the result to `out`."""
    exported = Path(
        YOLO(str(weights)).export(format="onnx", imgsz=imgsz, dynamic=True, simplify=True)
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(exported), out)
    return out


def describe(path: Path) -> None:
    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    for item in session.get_inputs():
        print("input ", item.name, item.shape, item.type)
    for item in session.get_outputs():
        print("output", item.name, item.shape, item.type)
    meta = session.get_modelmeta().custom_metadata_map
    for key in ("imgsz", "stride", "batch", "names"):
        print(f"meta   {key}: {meta.get(key)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--imgsz", type=int, default=640)
    args = ap.parse_args()

    path = export_onnx(args.weights, args.out, args.imgsz)
    size_mb = path.stat().st_size / 1e6
    print(f"saved {path} ({size_mb:.1f} MB)")
    describe(path)


if __name__ == "__main__":
    main()
