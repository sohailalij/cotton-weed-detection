from __future__ import annotations

import json
import os
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from weedlab.api.app import box_coverage, create_app
from weedlab.api.db import Base, make_engine
from weedlab.api.settings import Settings
from weedlab.inference import Detection


class FakeDetector:
    def __init__(self) -> None:
        self.names = {0: "waterhemp", 5: "ragweed"}
        self.imgsz = 960
        self.last_conf: float | None = None

    def detect(
        self,
        image: Image.Image,
        conf: float = 0.25,
        iou: float = 0.7,
        max_det: int = 300,
    ) -> list[Detection]:
        self.last_conf = conf
        return [
            Detection((10.0, 10.0, 60.0, 60.0), 0.9, 0, "waterhemp"),
            Detection((100.0, 20.0, 180.0, 90.0), 0.8, 5, "ragweed"),
        ]


def image_bytes(fmt: str = "JPEG", size: tuple[int, int] = (200, 100)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, (10, 200, 10)).save(buf, format=fmt)
    return buf.getvalue()


def make_client(**overrides: Any) -> tuple[TestClient, FakeDetector]:
    fake = FakeDetector()
    engine = make_engine(os.environ.get("WEEDLAB_TEST_DATABASE_URL", "sqlite://"))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    settings = Settings(metrics_path=None, **overrides)
    return TestClient(create_app(settings, fake, engine)), fake


def post(client: TestClient, data: bytes, **params: Any) -> Any:
    files = {"file": ("a.jpg", data, "image/jpeg")}
    return client.post("/v1/detect", files=files, params=params)


def test_health() -> None:
    client, _ = make_client()
    assert client.get("/health").json() == {"status": "ok", "model_loaded": True}


def test_model_info_lists_classes() -> None:
    client, _ = make_client()
    body = client.get("/v1/model").json()
    assert body["imgsz"] == 960
    assert body["default_conf"] == 0.58
    assert body["classes"] == {"0": "waterhemp", "5": "ragweed"}
    assert body["test_metrics"] is None


def test_detect_returns_boxes_and_summary() -> None:
    client, _ = make_client()
    response = post(client, image_bytes())
    assert response.status_code == 200
    body = response.json()
    assert (body["image_width"], body["image_height"]) == (200, 100)
    assert body["count"] == 2
    assert body["counts_by_class"] == {"waterhemp": 1, "ragweed": 1}
    assert body["box_coverage"] == pytest.approx(0.405)
    assert body["detections"][0]["class_name"] == "waterhemp"
    assert body["detections"][0]["box"] == {"x1": 10.0, "y1": 10.0, "x2": 60.0, "y2": 60.0}


def test_conf_defaults_to_setting_and_can_be_overridden() -> None:
    client, fake = make_client()
    post(client, image_bytes())
    assert fake.last_conf == 0.58
    response = post(client, image_bytes(), conf=0.3)
    assert response.json()["conf_used"] == 0.3
    assert fake.last_conf == 0.3


def test_conf_out_of_range_is_rejected() -> None:
    client, _ = make_client()
    assert post(client, image_bytes(), conf=0.0).status_code == 422
    assert post(client, image_bytes(), conf=1.5).status_code == 422


def test_text_file_with_image_header_is_rejected() -> None:
    client, _ = make_client()
    assert post(client, b"this is not an image").status_code == 400


def test_unsupported_format_is_rejected() -> None:
    client, _ = make_client()
    assert post(client, image_bytes("GIF")).status_code == 415


def test_large_upload_is_rejected() -> None:
    client, _ = make_client(max_upload_bytes=100)
    assert post(client, image_bytes()).status_code == 413


def test_image_with_too_many_pixels_is_rejected() -> None:
    client, _ = make_client(max_pixels=1000)
    assert post(client, image_bytes()).status_code == 413


def test_cors_allows_only_listed_origins() -> None:
    client, _ = make_client(cors_origins=("http://localhost:5173",))
    ok = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert ok.headers["access-control-allow-origin"] == "http://localhost:5173"
    other = client.get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in other.headers


def test_box_coverage_counts_overlap_once() -> None:
    assert box_coverage([(0, 0, 50, 50), (25, 25, 75, 75)], 100, 100) == pytest.approx(0.4375)


def test_box_coverage_of_no_boxes_is_zero() -> None:
    assert box_coverage([], 100, 100) == 0.0


def test_settings_require_a_model_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WEEDLAB_MODEL_PATH", raising=False)
    with pytest.raises(RuntimeError):
        Settings.from_env()


def test_settings_refuse_wildcard_cors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    model = tmp_path / "m.onnx"
    model.write_bytes(b"x")
    monkeypatch.setenv("WEEDLAB_MODEL_PATH", str(model))
    monkeypatch.setenv("WEEDLAB_DATABASE_URL", "sqlite://")
    monkeypatch.setenv("WEEDLAB_CORS_ORIGINS", "*")
    with pytest.raises(RuntimeError):
        Settings.from_env()


def test_settings_read_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    model = tmp_path / "m.onnx"
    model.write_bytes(b"x")
    monkeypatch.setenv("WEEDLAB_MODEL_PATH", str(model))
    monkeypatch.setenv("WEEDLAB_DATABASE_URL", "sqlite://")
    monkeypatch.setenv("WEEDLAB_CORS_ORIGINS", "https://a.example, https://b.example")
    monkeypatch.setenv("WEEDLAB_MAX_UPLOAD_MB", "2")
    cfg = Settings.from_env()
    assert cfg.cors_origins == ("https://a.example", "https://b.example")
    assert cfg.max_upload_bytes == 2 * 1024 * 1024


def test_settings_require_a_database_url(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    model = tmp_path / "m.onnx"
    model.write_bytes(b"x")
    monkeypatch.setenv("WEEDLAB_MODEL_PATH", str(model))
    monkeypatch.delenv("WEEDLAB_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="WEEDLAB_DATABASE_URL"):
        Settings.from_env()


def test_detect_saves_result_and_returns_id() -> None:
    client, _ = make_client()
    created = post(client, image_bytes()).json()
    assert created["id"] == 1
    stored = client.get("/v1/detections/1").json()
    assert stored["id"] == 1
    assert stored["count"] == 2
    assert stored["counts_by_class"] == {"waterhemp": 1, "ragweed": 1}
    assert stored["model_name"] == "unknown"
    assert stored["detections"] == created["detections"]


def test_history_is_newest_first_and_paginated() -> None:
    client, _ = make_client()
    for _ in range(3):
        post(client, image_bytes())
    page = client.get("/v1/detections").json()
    assert page["total"] == 3
    assert [i["id"] for i in page["items"]] == [3, 2, 1]
    first = client.get("/v1/detections", params={"limit": 2}).json()
    assert [i["id"] for i in first["items"]] == [3, 2]
    last = client.get("/v1/detections", params={"limit": 2, "offset": 2}).json()
    assert [i["id"] for i in last["items"]] == [1]
    beyond = client.get("/v1/detections", params={"offset": 10}).json()
    assert beyond["items"] == []
    assert beyond["total"] == 3


def test_pagination_bounds_are_validated() -> None:
    client, _ = make_client()
    assert client.get("/v1/detections", params={"limit": 0}).status_code == 422
    assert client.get("/v1/detections", params={"limit": 101}).status_code == 422
    assert client.get("/v1/detections", params={"offset": -1}).status_code == 422


def test_missing_detection_is_404_and_bad_id_is_422() -> None:
    client, _ = make_client()
    assert client.get("/v1/detections/999").status_code == 404
    assert client.get("/v1/detections/abc").status_code == 422
    assert client.get("/v1/detections/0").status_code == 422


def test_stats_on_empty_history() -> None:
    client, _ = make_client()
    body = client.get("/v1/stats").json()
    assert body["detections"] == 0
    assert body["weeds_found"] == 0
    assert body["mean_box_coverage"] is None
    assert body["counts_by_class"] == {}


def test_stats_add_up_over_saved_detections() -> None:
    client, _ = make_client()
    post(client, image_bytes())
    post(client, image_bytes())
    body = client.get("/v1/stats").json()
    assert body["detections"] == 2
    assert body["weeds_found"] == 4
    assert body["counts_by_class"] == {"waterhemp": 2, "ragweed": 2}
    assert body["mean_box_coverage"] == pytest.approx(0.405)


def test_stats_respect_the_date_range() -> None:
    client, _ = make_client()
    post(client, image_bytes())
    post(client, image_bytes())
    since = client.get("/v1/stats", params={"start": "2000-01-01T00:00:00Z"}).json()
    assert since["detections"] == 2
    future = client.get("/v1/stats", params={"start": "2999-01-01T00:00:00Z"}).json()
    assert future["detections"] == 0
    until = client.get("/v1/stats", params={"end": "2000-01-01T00:00:00Z"}).json()
    assert until["detections"] == 0


def test_stats_reject_start_after_end() -> None:
    client, _ = make_client()
    params = {"start": "2030-01-01T00:00:00Z", "end": "2020-01-01T00:00:00Z"}
    assert client.get("/v1/stats", params=params).status_code == 422


def test_detect_returns_503_when_the_database_is_unavailable() -> None:
    engine = make_engine("sqlite://")  # no tables created, so saving fails
    client = TestClient(create_app(Settings(metrics_path=None), FakeDetector(), engine))
    assert post(client, image_bytes()).status_code == 503


def test_detect_is_rate_limited_per_client() -> None:
    client, _ = make_client(rate_limit_per_minute=2)
    assert post(client, image_bytes()).status_code == 200
    assert post(client, image_bytes()).status_code == 200
    blocked = post(client, image_bytes())
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    assert client.get("/health").status_code == 200
    assert client.get("/v1/detections").status_code == 200


@pytest.mark.parametrize("value", ["0", "-3", "abc"])
def test_settings_reject_bad_rate_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str
) -> None:
    model = tmp_path / "m.onnx"
    model.write_bytes(b"x")
    monkeypatch.setenv("WEEDLAB_MODEL_PATH", str(model))
    monkeypatch.setenv("WEEDLAB_DATABASE_URL", "sqlite://")
    monkeypatch.setenv("WEEDLAB_RATE_LIMIT_PER_MINUTE", value)
    with pytest.raises(RuntimeError, match="RATE_LIMIT"):
        Settings.from_env()


def test_saved_openapi_spec_matches_the_app() -> None:
    client, _ = make_client()
    spec_file = Path(__file__).resolve().parents[1] / "frontend" / "openapi.json"
    saved = json.loads(spec_file.read_text(encoding="utf-8"))
    assert client.get("/openapi.json").json() == saved, (
        "frontend/openapi.json is out of date. Regenerate it from the running API, "
        "then run npm run gen-api in frontend/"
    )
