"""FastAPI service around the ONNX weed detector."""

from __future__ import annotations

import json
import logging
import math
import re
import threading
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Annotated, Protocol

import numpy as np
from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi import Path as PathParam
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from weedlab.api.clientip import client_key as resolve_client_key
from weedlab.api.db import make_engine, make_session_factory
from weedlab.api.ratelimit import RateLimiter
from weedlab.api.schemas import (
    Box,
    DailySeries,
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
    compute_daily,
    compute_stats,
    delete_detection,
    get_detection,
    get_thumbnail,
    list_detections,
    purge_older_than,
    save_detection,
)
from weedlab.api.thumbnail import make_thumbnail
from weedlab.inference import Detection, Detector

logger = logging.getLogger(__name__)

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_ID = 2_147_483_647
VISITOR_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,64}")
PURGE_INTERVAL_SECONDS = 3600


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


def check_visitor_id(value: str | None) -> str:
    """Accept only a well-formed visitor id. Anything else is a 400."""
    if value is None or VISITOR_ID_PATTERN.fullmatch(value) is None:
        raise HTTPException(status_code=400, detail="missing or malformed visitor id")
    return value


def visitor_from_header(x_visitor_id: Annotated[str | None, Header()] = None) -> str:
    return check_visitor_id(x_visitor_id)


def visitor_from_header_or_query(
    x_visitor_id: Annotated[str | None, Header()] = None,
    visitor: Annotated[str | None, Query()] = None,
) -> str:
    """For the image route: an <img> tag cannot send headers, so a query parameter works too."""
    return check_visitor_id(x_visitor_id if x_visitor_id is not None else visitor)


Visitor = Annotated[str, Depends(visitor_from_header)]
ImageVisitor = Annotated[str, Depends(visitor_from_header_or_query)]


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

    def run_purge() -> int:
        """Delete detections older than the retention period. Never raises."""
        cutoff = datetime.now(UTC) - timedelta(days=cfg.retention_days)
        try:
            with sessions() as session:
                removed = purge_older_than(session, cutoff)
        except SQLAlchemyError:
            logger.exception("could not delete expired detections")
            return 0
        if removed:
            logger.info("deleted %d detections older than %d days", removed, cfg.retention_days)
        return removed

    def purge_loop(stop: threading.Event) -> None:
        while True:
            run_purge()
            if stop.wait(PURGE_INTERVAL_SECONDS):
                return

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        stop = threading.Event()
        worker: threading.Thread | None = None
        if cfg.retention_days > 0:
            worker = threading.Thread(
                target=purge_loop, args=(stop,), name="purge-expired", daemon=True
            )
            worker.start()
        try:
            yield
        finally:
            stop.set()
            if worker is not None:
                worker.join(timeout=5)

    app = FastAPI(title="Weed detection API", version="0.4.0", lifespan=lifespan)
    app.state.run_purge = run_purge
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cfg.cors_origins),
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-Visitor-Id"],
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
        visitor_id: Visitor,
        file: Annotated[UploadFile, File(description="JPEG, PNG or WEBP image")],
        conf: Annotated[float | None, Query(ge=0.01, le=0.99)] = None,
    ) -> DetectResponse:
        client_key = resolve_client_key(
            request.client.host if request.client else None,
            request.headers,
            cfg.trusted_proxy_hops,
        )
        logger.warning(
            "DEBUG-IP peer=%s xff=%r hops=%d key=%s",
            request.client.host if request.client else None,
            request.headers.get("x-forwarded-for"),
            cfg.trusted_proxy_hops,
            client_key,
        )
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
        thumbnail = make_thumbnail(image)
        try:
            with sessions() as session:
                new_id = save_detection(
                    session,
                    visitor_id=visitor_id,
                    model_name=cfg.model_name,
                    width=image.width,
                    height=image.height,
                    conf=used,
                    coverage=coverage,
                    detections=out,
                    thumbnail=thumbnail,
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
        visitor_id: Visitor,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> DetectionPage:
        with sessions() as session:
            return list_detections(session, visitor_id, limit, offset)

    @app.get("/v1/detections/{detection_id}", response_model=DetectionDetail)
    def detection(
        visitor_id: Visitor,
        detection_id: Annotated[int, PathParam(ge=1, le=MAX_ID)],
    ) -> DetectionDetail:
        with sessions() as session:
            found = get_detection(session, visitor_id, detection_id)
        if found is None:
            raise HTTPException(status_code=404, detail="detection not found")
        return found

    @app.get(
        "/v1/detections/{detection_id}/image",
        response_class=Response,
        responses={200: {"content": {"image/jpeg": {}}, "description": "JPEG thumbnail"}},
    )
    def detection_image(
        visitor_id: ImageVisitor,
        detection_id: Annotated[int, PathParam(ge=1, le=MAX_ID)],
    ) -> Response:
        with sessions() as session:
            jpeg = get_thumbnail(session, visitor_id, detection_id)
        if jpeg is None:
            raise HTTPException(status_code=404, detail="image not found")
        return Response(
            content=jpeg,
            media_type="image/jpeg",
            headers={"Cache-Control": "private, max-age=3600"},
        )

    @app.delete("/v1/detections/{detection_id}", status_code=204, response_class=Response)
    def remove_detection(
        visitor_id: Visitor,
        detection_id: Annotated[int, PathParam(ge=1, le=MAX_ID)],
    ) -> Response:
        with sessions() as session:
            found = delete_detection(session, visitor_id, detection_id)
        if not found:
            raise HTTPException(status_code=404, detail="detection not found")
        return Response(status_code=204)

    @app.get("/v1/stats", response_model=Stats)
    def stats(
        visitor_id: Visitor,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Stats:
        if start is not None and end is not None and as_utc(start) > as_utc(end):
            raise HTTPException(status_code=422, detail="start must not be after end")
        with sessions() as session:
            return compute_stats(session, visitor_id, start, end)

    @app.get("/v1/stats/daily", response_model=DailySeries)
    def stats_daily(
        visitor_id: Visitor,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> DailySeries:
        if start is not None and end is not None and as_utc(start) > as_utc(end):
            raise HTTPException(status_code=422, detail="start must not be after end")
        with sessions() as session:
            return compute_daily(session, visitor_id, start, end)

    return app
