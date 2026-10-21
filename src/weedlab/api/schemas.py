"""Response schemas for the weed detection API."""

from __future__ import annotations

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
