"""FastAPI service around the ONNX weed detector."""

from __future__ import annotations

import json
import math
from collections import Counter
from io import BytesIO
from pathlib import Path
from typing import Annotated, Protocol

import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps, UnidentifiedImageError

from weedlab.api.schemas import (
    Box,
    DetectionOut,
    DetectResponse,
    Health,
    HeldOutMetrics,
    ModelInfo,
)
from weedlab.api.settings import Settings
from weedlab.inference import Detection, Detector

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class DetectorLike(Protocol):
    names: dict[int, str]
    imgsz: int

    def detect(
        self,
        image: Image.Image,
        conf: float = ...,
        iou: float = ...,
        max_det: int = ...,
    ) -> list[Detection]: ...


def box_coverage(boxes: list[tuple[float, float, float, float]], width: int, height: int) -> float:
    """Share of the image covered by the union of the boxes, on a grid of at most 512 px."""
    if not boxes:
        return 0.0
    scale = min(1.0, 512 / max(width, height))
    grid_w, grid_h = max(1, round(width * scale)), max(1, round(height * scale))
    mask = np.zeros((grid_h, grid_w), dtype=bool)
    for x1, y1, x2, y2 in boxes:
        mask[int(y1 * scale) : math.ceil(y2 * scale), int(x1 * scale) : math.ceil(x2 * scale)] = (
            True
        )
    return float(mask.mean())


def read_image(data: bytes, max_pixels: int) -> Image.Image:
    """Decode an upload. The header sent by the client is never trusted."""
    try:
        image = Image.open(BytesIO(data))
    except Image.DecompressionBombError as exc:
        raise HTTPException(status_code=413, detail="image has too many pixels") from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="file is not a readable image") from exc
    if image.format not in ALLOWED_FORMATS:
        raise HTTPException(
            status_code=415,
            detail=f"unsupported image format {image.format}; use JPEG, PNG or WEBP",
        )
    if image.width * image.height > max_pixels:
        raise HTTPException(status_code=413, detail="image has too many pixels")
    try:
        image.load()
    except (OSError, SyntaxError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="file is not a readable image") from exc
    upright = ImageOps.exif_transpose(image)
    return (upright or image).convert("RGB")


def load_metrics(path: Path | None) -> HeldOutMetrics | None:
    if path is None or not path.is_file():
        return None
    raw = json.loads(path.read_text())
    return HeldOutMetrics(
        map50=raw["map50"],
        map50_95=raw["map50_95"],
        precision=raw["precision"],
        recall=raw["recall"],
    )


def create_app(settings: Settings | None = None, detector: DetectorLike | None = None) -> FastAPI:
    cfg = settings or (Settings() if detector is not None else Settings.from_env())
    if detector is None:
        if cfg.model_path is None:
            raise RuntimeError("no model path configured")
        detector = Detector(cfg.model_path, imgsz=cfg.imgsz)
    model: DetectorLike = detector
    metrics = load_metrics(cfg.metrics_path)

    app = FastAPI(title="Weed detection API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cfg.cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health", response_model=Health)
    def health() -> Health:
        return Health(status="ok", model_loaded=True)

    @app.get("/v1/model", response_model=ModelInfo)
    def model_info() -> ModelInfo:
        return ModelInfo(
            name=cfg.model_name,
            imgsz=model.imgsz,
            default_conf=cfg.default_conf,
            classes=dict(model.names),
            test_metrics=metrics,
        )

    @app.post("/v1/detect", response_model=DetectResponse)
    def detect(
        file: Annotated[UploadFile, File(description="JPEG, PNG or WEBP image")],
        conf: Annotated[float | None, Query(ge=0.01, le=0.99)] = None,
    ) -> DetectResponse:
        data = file.file.read(cfg.max_upload_bytes + 1)
        if len(data) > cfg.max_upload_bytes:
            raise HTTPException(status_code=413, detail="upload is too large")
        if not data:
            raise HTTPException(status_code=400, detail="empty upload")
        image = read_image(data, cfg.max_pixels)
        used = cfg.default_conf if conf is None else conf
        found = model.detect(image, conf=used)
        return DetectResponse(
            image_width=image.width,
            image_height=image.height,
            conf_used=used,
            count=len(found),
            counts_by_class=dict(Counter(d.class_name for d in found)),
            box_coverage=box_coverage([d.box for d in found], image.width, image.height),
            detections=[
                DetectionOut(
                    box=Box(
                        x1=round(d.box[0], 1),
                        y1=round(d.box[1], 1),
                        x2=round(d.box[2], 1),
                        y2=round(d.box[3], 1),
                    ),
                    confidence=round(d.score, 4),
                    class_id=d.class_id,
                    class_name=d.class_name,
                )
                for d in found
            ],
        )

    return app
