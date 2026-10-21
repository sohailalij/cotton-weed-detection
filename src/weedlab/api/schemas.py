"""Response schemas for the weed detection API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Box(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class DetectionOut(BaseModel):
    box: Box
    confidence: float = Field(ge=0, le=1)
    class_id: int
    class_name: str


class DetectResponse(BaseModel):
    id: int
    image_width: int
    image_height: int
    conf_used: float
    count: int
    counts_by_class: dict[str, int]
    box_coverage: float = Field(
        ge=0, le=1, description="Share of the image covered by the union of the boxes"
    )
    detections: list[DetectionOut]


class HeldOutMetrics(BaseModel):
    map50: float
    map50_95: float
    precision: float
    recall: float


class ModelInfo(BaseModel):
    name: str
    imgsz: int
    default_conf: float
    classes: dict[int, str]
    test_metrics: HeldOutMetrics | None


class Health(BaseModel):
    status: str
    model_loaded: bool


class DetectionSummary(BaseModel):
    id: int
    created_at: datetime
    model_name: str
    image_width: int
    image_height: int
    conf_used: float
    count: int
    box_coverage: float
    counts_by_class: dict[str, int]


class DetectionDetail(DetectionSummary):
    detections: list[DetectionOut]


class DetectionPage(BaseModel):
    items: list[DetectionSummary]
    total: int
    limit: int
    offset: int


class Stats(BaseModel):
    start: datetime | None
    end: datetime | None
    detections: int
    weeds_found: int
    mean_box_coverage: float | None
    counts_by_class: dict[str, int]
