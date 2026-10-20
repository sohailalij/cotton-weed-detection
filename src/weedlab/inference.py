"""ONNX Runtime inference for the weed detector: preprocessing, forward pass, NMS."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
from numpy.typing import NDArray
from PIL import Image

STRIDE = 32
PAD_VALUE = 114
CLASS_OFFSET = 4096.0  # shifts boxes by class so one NMS pass never suppresses across classes


@dataclass(frozen=True)
class Detection:
    box: tuple[float, float, float, float]  # x1, y1, x2, y2 in original-image pixels
    score: float
    class_id: int
    class_name: str


def letterbox(image: Image.Image, imgsz: int) -> tuple[NDArray[Any], float, int, int]:
    """Resize so the long side is imgsz, then pad to a multiple of STRIDE with grey.

    Returns the NCHW float32 tensor (0..1), the scale, and the left and top padding.
    """
    width, height = image.size
    scale = min(imgsz / height, imgsz / width)
    new_w, new_h = round(width * scale), round(height * scale)
    pad_w = (imgsz - new_w) % STRIDE
    pad_h = (imgsz - new_h) % STRIDE
    left = round(pad_w / 2 - 0.1)
    top = round(pad_h / 2 - 0.1)
    if (new_w, new_h) != (width, height):
        image = image.resize((new_w, new_h), Image.Resampling.BILINEAR)
    canvas = np.full((new_h + pad_h, new_w + pad_w, 3), PAD_VALUE, dtype=np.uint8)
    canvas[top : top + new_h, left : left + new_w] = np.asarray(image)
    tensor = np.ascontiguousarray(canvas.transpose(2, 0, 1)[None], dtype=np.float32) / 255.0
    return tensor, scale, left, top


def nms(boxes: NDArray[Any], scores: NDArray[Any], iou_thres: float) -> list[int]:
    """Greedy non-maximum suppression. Returns kept indices, best score first."""
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        rest = order[1:]
        if rest.size == 0:
            break
        x1 = np.maximum(boxes[i, 0], boxes[rest, 0])
        y1 = np.maximum(boxes[i, 1], boxes[rest, 1])
        x2 = np.minimum(boxes[i, 2], boxes[rest, 2])
        y2 = np.minimum(boxes[i, 3], boxes[rest, 3])
        inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
        area_i = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
        area_r = (boxes[rest, 2] - boxes[rest, 0]) * (boxes[rest, 3] - boxes[rest, 1])
        iou = inter / (area_i + area_r - inter + 1e-9)
        order = rest[iou <= iou_thres]
    return keep


def postprocess(
    output: NDArray[Any],
    scale: float,
    left: int,
    top: int,
    size: tuple[int, int],
    names: dict[int, str],
    conf: float,
    iou: float,
    max_det: int,
) -> list[Detection]:
    """Turn the raw [1, 4 + classes, anchors] output into detections in original pixels."""
    preds = output[0].T
    class_scores = preds[:, 4:]
    class_ids = class_scores.argmax(axis=1)
    scores = class_scores[np.arange(len(preds)), class_ids]
    keep_mask = scores > conf
    preds, class_ids, scores = preds[keep_mask], class_ids[keep_mask], scores[keep_mask]
    if len(preds) == 0:
        return []
    cx, cy, bw, bh = preds[:, 0], preds[:, 1], preds[:, 2], preds[:, 3]
    boxes = np.stack([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], axis=1)
    kept = nms(boxes + class_ids[:, None] * CLASS_OFFSET, scores, iou)[:max_det]
    width, height = size
    detections: list[Detection] = []
    for i in kept:
        x1 = float(np.clip((boxes[i, 0] - left) / scale, 0, width))
        y1 = float(np.clip((boxes[i, 1] - top) / scale, 0, height))
        x2 = float(np.clip((boxes[i, 2] - left) / scale, 0, width))
        y2 = float(np.clip((boxes[i, 3] - top) / scale, 0, height))
        cid = int(class_ids[i])
        detections.append(Detection((x1, y1, x2, y2), float(scores[i]), cid, names[cid]))
    return detections


class Detector:
    """Loads the ONNX model once and runs detection on PIL images."""

    def __init__(self, model_path: Path, imgsz: int = 960, intra_threads: int | None = None):
        options = ort.SessionOptions()
        if intra_threads is not None:
            options.intra_op_num_threads = intra_threads
        self.session = ort.InferenceSession(
            str(model_path), sess_options=options, providers=["CPUExecutionProvider"]
        )
        self.input_name: str = self.session.get_inputs()[0].name
        meta = self.session.get_modelmeta().custom_metadata_map
        self.names: dict[int, str] = ast.literal_eval(meta["names"])
        self.imgsz = imgsz

    def detect(
        self,
        image: Image.Image,
        conf: float = 0.25,
        iou: float = 0.7,
        max_det: int = 300,
    ) -> list[Detection]:
        rgb = image.convert("RGB")
        tensor, scale, left, top = letterbox(rgb, self.imgsz)
        output = self.session.run(None, {self.input_name: tensor})[0]
        return postprocess(output, scale, left, top, rgb.size, self.names, conf, iou, max_det)
