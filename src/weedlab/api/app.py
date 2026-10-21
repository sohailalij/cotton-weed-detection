"""FastAPI service around the ONNX weed detector."""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Annotated, Protocol

import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi import Path as PathParam
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from weedlab.api.db import make_engine, make_session_factory
from weedlab.api.ratelimit import RateLimiter
from weedlab.api.schemas import (
    Box,
    DetectionDetail,
    DetectionOut,
    DetectionPage,
    DetectResponse,
    Health,
    HeldOutMetrics,
    ModelInfo,
    Stats,
)
from weedlab.api.settings import Settings
from weedlab.api.store import (
    as_utc,
    compute_stats,
    get_detection,
    list_detections,
    save_detection,
)
from weedlab.inference import Detection, Detector

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_ID = 2_147_483_647


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


def create_app(
    settings: Settings | None = None,
    detector: DetectorLike | None = None,
    engine: Engine | None = None,
    limiter: RateLimiter | None = None,
) -> FastAPI:
    cfg = settings or (Settings() if detector is not None else Settings.from_env())
    if detector is None:
        if cfg.model_path is None:
            raise RuntimeError("no model path configured")
        detector = Detector(cfg.model_path, imgsz=cfg.imgsz)
    if engine is None:
        if cfg.database_url is None:
            raise RuntimeError("no database configured")
        engine = make_engine(cfg.database_url)
    model: DetectorLike = detector
    sessions = make_session_factory(engine)
    metrics = load_metrics(cfg.metrics_path)
    rate_limiter: RateLimiter = limiter or RateLimiter(cfg.rate_limit_per_minute)

    app = FastAPI(title="Weed detection API", version="0.2.0")
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
        request: Request,
        file: Annotated[UploadFile, File(description="JPEG, PNG or WEBP image")],
        conf: Annotated[float | None, Query(ge=0.01, le=0.99)] = None,
    ) -> DetectResponse:
        client_key = request.client.host if request.client else "unknown"
        wait = rate_limiter.check(client_key)
        if wait is not None:
            raise HTTPException(
                status_code=429,
                detail="rate limit exceeded",
                headers={"Retry-After": str(math.ceil(wait))},
            )
        data = file.file.read(cfg.max_upload_bytes + 1)
        if len(data) > cfg.max_upload_bytes:
            raise HTTPException(status_code=413, detail="upload is too large")
        if not data:
            raise HTTPException(status_code=400, detail="empty upload")
        image = read_image(data, cfg.max_pixels)
        used = cfg.default_conf if conf is None else conf
        found = model.detect(image, conf=used)
        out = [
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
        ]
        coverage = box_coverage([d.box for d in found], image.width, image.height)
        try:
            with sessions() as session:
                new_id = save_detection(
                    session,
                    model_name=cfg.model_name,
                    width=image.width,
                    height=image.height,
                    conf=used,
                    coverage=coverage,
                    detections=out,
                )
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="could not save the result") from exc
        return DetectResponse(
            id=new_id,
            image_width=image.width,
            image_height=image.height,
            conf_used=used,
            count=len(found),
            counts_by_class=dict(Counter(d.class_name for d in found)),
            box_coverage=coverage,
            detections=out,
        )

    @app.get("/v1/detections", response_model=DetectionPage)
    def detections(
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> DetectionPage:
        with sessions() as session:
            return list_detections(session, limit, offset)

    @app.get("/v1/detections/{detection_id}", response_model=DetectionDetail)
    def detection(detection_id: Annotated[int, PathParam(ge=1, le=MAX_ID)]) -> DetectionDetail:
        with sessions() as session:
            found = get_detection(session, detection_id)
        if found is None:
            raise HTTPException(status_code=404, detail="detection not found")
        return found

    @app.get("/v1/stats", response_model=Stats)
    def stats(start: datetime | None = None, end: datetime | None = None) -> Stats:
        if start is not None and end is not None and as_utc(start) > as_utc(end):
            raise HTTPException(status_code=422, detail="start must not be after end")
        with sessions() as session:
            return compute_stats(session, start, end)

    return app
