from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from weedlab.api.app import box_coverage, create_app
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
    settings = Settings(metrics_path=None, **overrides)
    return TestClient(create_app(settings, fake)), fake


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
    monkeypatch.setenv("WEEDLAB_CORS_ORIGINS", "*")
    with pytest.raises(RuntimeError):
        Settings.from_env()


def test_settings_read_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    model = tmp_path / "m.onnx"
    model.write_bytes(b"x")
    monkeypatch.setenv("WEEDLAB_MODEL_PATH", str(model))
    monkeypatch.setenv("WEEDLAB_CORS_ORIGINS", "https://a.example, https://b.example")
    monkeypatch.setenv("WEEDLAB_MAX_UPLOAD_MB", "2")
    cfg = Settings.from_env()
    assert cfg.cors_origins == ("https://a.example", "https://b.example")
    assert cfg.max_upload_bytes == 2 * 1024 * 1024
