from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select, update
from sqlalchemy.engine import Engine

from weedlab.api.app import box_coverage, create_app
from weedlab.api.db import (
    Base,
    ClassCount,
    DetectionImage,
    DetectionRecord,
    make_engine,
    make_session_factory,
)
from weedlab.api.settings import Settings
from weedlab.inference import Detection

HEADER = "X-Visitor-Id"
VISITOR_A = "visitor-aaaaaaaaaaaaaaaa"
VISITOR_B = "visitor-bbbbbbbbbbbbbbbb"


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


def make_parts(**overrides: Any) -> tuple[FastAPI, FakeDetector, Engine]:
    """The app, its fake detector and its engine. Cleanup is off unless a test turns it on."""
    fake = FakeDetector()
    engine = make_engine(os.environ.get("WEEDLAB_TEST_DATABASE_URL", "sqlite://"))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    overrides.setdefault("retention_days", 0)
    settings = Settings(metrics_path=None, **overrides)
    return create_app(settings, fake, engine), fake, engine


def make_client(
    visitor: str | None = VISITOR_A, **overrides: Any
) -> tuple[TestClient, FakeDetector]:
    """A client that sends visitor A's id by default. Pass visitor=None to send none."""
    app, fake, _ = make_parts(**overrides)
    headers = {HEADER: visitor} if visitor is not None else None
    return TestClient(app, headers=headers), fake


def post(client: TestClient, data: bytes, *, as_visitor: str | None = None, **params: Any) -> Any:
    files = {"file": ("a.jpg", data, "image/jpeg")}
    headers = {HEADER: as_visitor} if as_visitor is not None else None
    return client.post("/v1/detect", files=files, params=params, headers=headers)


def age_detection(engine: Engine, detection_id: int, days: float) -> None:
    """Back-date one saved detection, to test the cleanup."""
    with make_session_factory(engine)() as session:
        session.execute(
            update(DetectionRecord)
            .where(DetectionRecord.id == detection_id)
            .values(created_at=datetime.now(UTC) - timedelta(days=days))
        )
        session.commit()


def set_required_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    model = tmp_path / "m.onnx"
    model.write_bytes(b"x")
    monkeypatch.setenv("WEEDLAB_MODEL_PATH", str(model))
    monkeypatch.setenv("WEEDLAB_DATABASE_URL", "sqlite://")


def test_health() -> None:
    client, _ = make_client(visitor=None)
    assert client.get("/health").json() == {"status": "ok", "model_loaded": True}


def test_model_info_lists_classes() -> None:
    client, _ = make_client(visitor=None)
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
    client, _ = make_client(visitor=None, cors_origins=("http://localhost:5173",))
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
    set_required_env(monkeypatch, tmp_path)
    monkeypatch.setenv("WEEDLAB_CORS_ORIGINS", "*")
    with pytest.raises(RuntimeError):
        Settings.from_env()


def test_settings_read_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    set_required_env(monkeypatch, tmp_path)
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


def test_retention_defaults_to_seven_days(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    set_required_env(monkeypatch, tmp_path)
    monkeypatch.delenv("WEEDLAB_RETENTION_DAYS", raising=False)
    assert Settings.from_env().retention_days == 7


@pytest.mark.parametrize(("value", "expected"), [("3", 3), ("0", 0)])
def test_retention_is_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str, expected: int
) -> None:
    set_required_env(monkeypatch, tmp_path)
    monkeypatch.setenv("WEEDLAB_RETENTION_DAYS", value)
    assert Settings.from_env().retention_days == expected


@pytest.mark.parametrize("value", ["-1", "abc", "1.5"])
def test_settings_reject_bad_retention(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str
) -> None:
    set_required_env(monkeypatch, tmp_path)
    monkeypatch.setenv("WEEDLAB_RETENTION_DAYS", value)
    with pytest.raises(RuntimeError, match="RETENTION"):
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
    app = create_app(Settings(metrics_path=None, retention_days=0), FakeDetector(), engine)
    client = TestClient(app, headers={HEADER: VISITOR_A})
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
    set_required_env(monkeypatch, tmp_path)
    monkeypatch.setenv("WEEDLAB_RATE_LIMIT_PER_MINUTE", value)
    with pytest.raises(RuntimeError, match="RATE_LIMIT"):
        Settings.from_env()


def test_saved_openapi_spec_matches_the_app() -> None:
    client, _ = make_client(visitor=None)
    spec_file = Path(__file__).resolve().parents[1] / "frontend" / "openapi.json"
    saved = json.loads(spec_file.read_text(encoding="utf-8"))
    assert client.get("/openapi.json").json() == saved, (
        "frontend/openapi.json is out of date. Regenerate it from the running API, "
        "then run npm run gen-api in frontend/"
    )


def test_detect_stores_a_thumbnail_and_serves_it() -> None:
    client, _ = make_client()
    created = post(client, image_bytes(size=(2000, 1000))).json()
    response = client.get(f"/v1/detections/{created['id']}/image")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "private, max-age=3600"
    assert Image.open(BytesIO(response.content)).size == (640, 320)


def test_small_photo_thumbnail_is_not_enlarged() -> None:
    client, _ = make_client()
    created = post(client, image_bytes(size=(200, 100))).json()
    response = client.get(f"/v1/detections/{created['id']}/image")
    assert Image.open(BytesIO(response.content)).size == (200, 100)


def test_thumbnail_for_missing_or_invalid_id() -> None:
    client, _ = make_client()
    assert client.get("/v1/detections/999/image").status_code == 404
    assert client.get("/v1/detections/0/image").status_code == 422


def test_delete_removes_detection_and_its_photo() -> None:
    client, _ = make_client()
    first = post(client, image_bytes()).json()["id"]
    second = post(client, image_bytes()).json()["id"]
    response = client.delete(f"/v1/detections/{first}")
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/v1/detections/{first}").status_code == 404
    assert client.get(f"/v1/detections/{first}/image").status_code == 404
    assert client.get(f"/v1/detections/{second}/image").status_code == 200
    assert client.get("/v1/detections").json()["total"] == 1
    assert client.get("/v1/stats").json()["detections"] == 1


def test_delete_missing_or_invalid_id() -> None:
    client, _ = make_client()
    assert client.delete("/v1/detections/999").status_code == 404
    assert client.delete("/v1/detections/0").status_code == 422


def test_cors_preflight_for_delete_only_from_listed_origin() -> None:
    client, _ = make_client(visitor=None, cors_origins=("http://localhost:5173",))
    ok = client.options(
        "/v1/detections/1",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "DELETE"},
    )
    assert ok.status_code == 200
    assert "DELETE" in ok.headers["access-control-allow-methods"]
    other = client.options(
        "/v1/detections/1",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "DELETE"},
    )
    assert other.status_code == 400


def test_cors_preflight_allows_the_visitor_header_and_nothing_else() -> None:
    client, _ = make_client(visitor=None, cors_origins=("http://localhost:5173",))
    base = {"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"}
    ok = client.options(
        "/v1/detect", headers={**base, "Access-Control-Request-Headers": "x-visitor-id"}
    )
    assert ok.status_code == 200
    assert "x-visitor-id" in ok.headers["access-control-allow-headers"].lower()
    other = client.options(
        "/v1/detect", headers={**base, "Access-Control-Request-Headers": "x-something-else"}
    )
    assert other.status_code == 400


def test_daily_stats_on_empty_history() -> None:
    client, _ = make_client()
    assert client.get("/v1/stats/daily").json()["days"] == []


def test_daily_stats_add_up_over_saved_detections() -> None:
    client, _ = make_client()
    post(client, image_bytes())
    post(client, image_bytes())
    days = client.get("/v1/stats/daily").json()["days"]
    assert len(days) == 1
    assert days[0]["detections"] == 2
    assert days[0]["weeds_found"] == 4
    assert days[0]["counts_by_class"] == {"waterhemp": 2, "ragweed": 2}
    assert days[0]["mean_box_coverage"] == pytest.approx(0.405)


def test_daily_stats_respect_the_date_range() -> None:
    client, _ = make_client()
    post(client, image_bytes())
    since = client.get("/v1/stats/daily", params={"start": "2000-01-01T00:00:00Z"}).json()
    assert len(since["days"]) == 1
    future = client.get("/v1/stats/daily", params={"start": "2999-01-01T00:00:00Z"}).json()
    assert future["days"] == []
    until = client.get("/v1/stats/daily", params={"end": "2000-01-01T00:00:00Z"}).json()
    assert until["days"] == []


def test_daily_stats_reject_start_after_end() -> None:
    client, _ = make_client()
    params = {"start": "2030-01-01T00:00:00Z", "end": "2020-01-01T00:00:00Z"}
    assert client.get("/v1/stats/daily", params=params).status_code == 422


# --- Visitor scoping ---------------------------------------------------------------------

VISITOR_ROUTES = [
    ("GET", "/v1/detections"),
    ("GET", "/v1/detections/1"),
    ("GET", "/v1/detections/1/image"),
    ("DELETE", "/v1/detections/1"),
    ("GET", "/v1/stats"),
    ("GET", "/v1/stats/daily"),
]

BAD_VISITOR_IDS = [
    "",
    "short",
    "x" * 65,
    "has spaces in it 1234",
    "semi;colon;12345678",
    "dots.are.not.allowed.1",
    "slash/not/allowed/123",
]


@pytest.mark.parametrize(("method", "path"), VISITOR_ROUTES)
def test_visitor_id_is_required(method: str, path: str) -> None:
    client, _ = make_client(visitor=None)
    assert client.request(method, path).status_code == 400


def test_detect_requires_a_visitor_id_and_saves_nothing() -> None:
    client, _ = make_client(visitor=None)
    assert post(client, image_bytes()).status_code == 400
    mine = client.get("/v1/detections", headers={HEADER: VISITOR_A}).json()
    assert mine["total"] == 0


@pytest.mark.parametrize("bad", BAD_VISITOR_IDS)
def test_malformed_visitor_ids_are_rejected(bad: str) -> None:
    client, _ = make_client(visitor=bad)
    assert client.get("/v1/detections").status_code == 400
    assert post(client, image_bytes()).status_code == 400


def test_a_valid_id_at_the_length_limits_is_accepted() -> None:
    for visitor in ("a" * 16, "Z" * 64, "ab_-" * 8):
        client, _ = make_client(visitor=visitor)
        assert client.get("/v1/detections").status_code == 200


def test_each_visitor_sees_only_their_own_history_and_stats() -> None:
    client, _ = make_client()
    post(client, image_bytes())
    post(client, image_bytes())
    post(client, image_bytes(), as_visitor=VISITOR_B)
    other = {HEADER: VISITOR_B}

    mine = client.get("/v1/detections").json()
    theirs = client.get("/v1/detections", headers=other).json()
    assert (mine["total"], [i["id"] for i in mine["items"]]) == (2, [2, 1])
    assert (theirs["total"], [i["id"] for i in theirs["items"]]) == (1, [3])

    assert client.get("/v1/stats").json()["detections"] == 2
    assert client.get("/v1/stats", headers=other).json()["detections"] == 1
    assert client.get("/v1/stats", headers=other).json()["weeds_found"] == 2
    assert client.get("/v1/stats/daily").json()["days"][0]["detections"] == 2
    assert client.get("/v1/stats/daily", headers=other).json()["days"][0]["detections"] == 1


def test_a_visitor_cannot_read_another_visitors_detection_or_photo() -> None:
    client, _ = make_client()
    mine = post(client, image_bytes()).json()["id"]
    other = {HEADER: VISITOR_B}
    assert client.get(f"/v1/detections/{mine}", headers=other).status_code == 404
    assert client.get(f"/v1/detections/{mine}/image", headers=other).status_code == 404
    assert client.get("/v1/detections", headers=other).json()["items"] == []
    assert client.get("/v1/stats", headers=other).json()["detections"] == 0
    assert client.get("/v1/stats/daily", headers=other).json()["days"] == []
    assert client.get(f"/v1/detections/{mine}").status_code == 200


def test_a_visitor_cannot_delete_another_visitors_detection() -> None:
    client, _ = make_client()
    mine = post(client, image_bytes()).json()["id"]
    response = client.delete(f"/v1/detections/{mine}", headers={HEADER: VISITOR_B})
    assert response.status_code == 404
    assert client.get(f"/v1/detections/{mine}").status_code == 200
    assert client.get(f"/v1/detections/{mine}/image").status_code == 200


def test_another_visitors_row_looks_exactly_like_a_missing_one() -> None:
    client, _ = make_client()
    mine = post(client, image_bytes()).json()["id"]
    other = {HEADER: VISITOR_B}
    foreign = client.get(f"/v1/detections/{mine}", headers=other)
    missing = client.get("/v1/detections/999", headers=other)
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()
    foreign_image = client.get(f"/v1/detections/{mine}/image", headers=other)
    missing_image = client.get("/v1/detections/999/image", headers=other)
    assert foreign_image.status_code == missing_image.status_code == 404
    assert foreign_image.json() == missing_image.json()


def test_image_route_accepts_the_visitor_as_a_query_parameter() -> None:
    client, _ = make_client(visitor=None)
    created = post(client, image_bytes(), as_visitor=VISITOR_A).json()
    url = f"/v1/detections/{created['id']}/image"
    assert client.get(url, params={"visitor": VISITOR_A}).status_code == 200
    assert client.get(url, params={"visitor": VISITOR_B}).status_code == 404
    assert client.get(url).status_code == 400
    assert client.get(url, params={"visitor": "short"}).status_code == 400


def test_the_header_wins_over_the_query_parameter_on_the_image_route() -> None:
    client, _ = make_client()
    created = post(client, image_bytes()).json()
    url = f"/v1/detections/{created['id']}/image"
    response = client.get(url, params={"visitor": VISITOR_A}, headers={HEADER: VISITOR_B})
    assert response.status_code == 404


def test_other_routes_do_not_accept_the_visitor_as_a_query_parameter() -> None:
    client, _ = make_client(visitor=None)
    assert client.get("/v1/detections", params={"visitor": VISITOR_A}).status_code == 400
    assert client.get("/v1/stats", params={"visitor": VISITOR_A}).status_code == 400


# --- Automatic deletion of old detections -------------------------------------------------


def test_purge_removes_expired_rows_of_every_visitor_and_keeps_recent_ones() -> None:
    app, _, engine = make_parts(retention_days=7)
    client = TestClient(app, headers={HEADER: VISITOR_A})
    old_a = post(client, image_bytes()).json()["id"]
    old_b = post(client, image_bytes(), as_visitor=VISITOR_B).json()["id"]
    recent = post(client, image_bytes()).json()["id"]
    fresh = post(client, image_bytes()).json()["id"]
    age_detection(engine, old_a, 8)
    age_detection(engine, old_b, 8)
    age_detection(engine, recent, 6)

    assert app.state.run_purge() == 2

    assert client.get(f"/v1/detections/{old_a}").status_code == 404
    assert client.get(f"/v1/detections/{old_a}/image").status_code == 404
    other = {HEADER: VISITOR_B}
    assert client.get(f"/v1/detections/{old_b}", headers=other).status_code == 404
    for kept in (recent, fresh):
        assert client.get(f"/v1/detections/{kept}").status_code == 200
        assert client.get(f"/v1/detections/{kept}/image").status_code == 200
    assert client.get("/v1/detections").json()["total"] == 2


def test_purge_leaves_no_orphan_rows_behind() -> None:
    app, _, engine = make_parts(retention_days=7)
    client = TestClient(app, headers={HEADER: VISITOR_A})
    old = post(client, image_bytes()).json()["id"]
    post(client, image_bytes())
    age_detection(engine, old, 30)

    assert app.state.run_purge() == 1

    with make_session_factory(engine)() as session:
        assert session.scalar(select(func.count()).select_from(DetectionRecord)) == 1
        assert session.scalar(select(func.count()).select_from(ClassCount)) == 2
        assert session.scalar(select(func.count()).select_from(DetectionImage)) == 1


def test_purge_with_nothing_expired_removes_nothing() -> None:
    app, _, _ = make_parts(retention_days=7)
    client = TestClient(app, headers={HEADER: VISITOR_A})
    post(client, image_bytes())
    assert app.state.run_purge() == 0
    assert client.get("/v1/detections").json()["total"] == 1


def test_purge_survives_a_database_error() -> None:
    engine = make_engine("sqlite://")  # no tables, so every query fails
    app = create_app(Settings(metrics_path=None, retention_days=7), FakeDetector(), engine)
    assert app.state.run_purge() == 0


def test_app_starts_and_stops_with_cleanup_enabled() -> None:
    app, _, _ = make_parts(retention_days=1)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200


def _upload(client: TestClient, forwarded: str | None = None) -> int:
    headers = {"X-Forwarded-For": forwarded} if forwarded else {}
    response = client.post(
        "/v1/detect",
        files={"file": ("a.jpg", image_bytes(), "image/jpeg")},
        headers=headers,
    )
    return response.status_code


def test_visitors_behind_a_trusted_proxy_get_separate_limits() -> None:
    app, _, _ = make_parts(rate_limit_per_minute=2, trusted_proxy_hops=1)
    alice = TestClient(app, headers={HEADER: VISITOR_A})
    bob = TestClient(app, headers={HEADER: VISITOR_B})
    assert _upload(alice, "203.0.113.1") == 200
    assert _upload(alice, "203.0.113.1") == 200
    assert _upload(alice, "203.0.113.1") == 429
    assert _upload(bob, "203.0.113.2") == 200


def test_a_forged_forwarded_header_does_not_dodge_the_limit() -> None:
    app, _, _ = make_parts(rate_limit_per_minute=2, trusted_proxy_hops=1)
    client = TestClient(app, headers={HEADER: VISITOR_A})
    assert _upload(client, "6.6.6.1, 203.0.113.1") == 200
    assert _upload(client, "6.6.6.2, 203.0.113.1") == 200
    assert _upload(client, "6.6.6.3, 203.0.113.1") == 429


def test_forwarded_header_is_ignored_when_no_proxy_is_trusted() -> None:
    app, _, _ = make_parts(rate_limit_per_minute=2)
    client = TestClient(app, headers={HEADER: VISITOR_A})
    assert _upload(client, "6.6.6.1") == 200
    assert _upload(client, "6.6.6.2") == 200
    assert _upload(client, "6.6.6.3") == 429


@pytest.mark.parametrize("value", ["-1", "6", "abc"])
def test_settings_reject_bad_trusted_proxy_hops(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str
) -> None:
    set_required_env(monkeypatch, tmp_path)
    monkeypatch.setenv("WEEDLAB_TRUSTED_PROXY_HOPS", value)
    with pytest.raises(RuntimeError, match="TRUSTED_PROXY_HOPS"):
        Settings.from_env()


def test_trusted_proxy_hops_defaults_to_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    set_required_env(monkeypatch, tmp_path)
    monkeypatch.delenv("WEEDLAB_TRUSTED_PROXY_HOPS", raising=False)
    assert Settings.from_env().trusted_proxy_hops == 0
