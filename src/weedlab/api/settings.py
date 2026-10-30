"""API settings, read from environment variables. The service refuses to start on bad ones."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ORIGINS = ("http://localhost:5173",)
DEFAULT_METRICS = Path("reports/test_eval/yolo11s_v1_960_best/metrics.json")
DEFAULT_RETENTION_DAYS = 7


@dataclass(frozen=True)
class Settings:
    model_path: Path | None = None
    metrics_path: Path | None = DEFAULT_METRICS
    imgsz: int = 960
    default_conf: float = 0.58
    max_upload_bytes: int = 15 * 1024 * 1024
    max_pixels: int = 50_000_000
    cors_origins: tuple[str, ...] = DEFAULT_ORIGINS
    database_url: str | None = None
    rate_limit_per_minute: int = 10
    retention_days: int = DEFAULT_RETENTION_DAYS
    trusted_proxy_hops: int = 0

    @property
    def model_name(self) -> str:
        return self.model_path.stem if self.model_path else "unknown"

    @classmethod
    def from_env(cls) -> Settings:
        raw_path = os.environ.get("WEEDLAB_MODEL_PATH")
        if not raw_path:
            raise RuntimeError("WEEDLAB_MODEL_PATH is not set")
        model_path = Path(raw_path)
        if not model_path.is_file():
            raise RuntimeError(f"model file not found: {model_path}")
        database_url = os.environ.get("WEEDLAB_DATABASE_URL")
        if not database_url:
            raise RuntimeError("WEEDLAB_DATABASE_URL is not set")
        raw_origins = os.environ.get("WEEDLAB_CORS_ORIGINS")
        origins = (
            tuple(o.strip() for o in raw_origins.split(",") if o.strip())
            if raw_origins
            else DEFAULT_ORIGINS
        )
        if "*" in origins:
            raise RuntimeError("WEEDLAB_CORS_ORIGINS must list origins, not '*'")
        max_mb = float(os.environ.get("WEEDLAB_MAX_UPLOAD_MB", "15"))
        raw_rate = os.environ.get("WEEDLAB_RATE_LIMIT_PER_MINUTE", "10")
        try:
            rate = int(raw_rate)
        except ValueError:
            rate = 0
        if rate < 1:
            raise RuntimeError("WEEDLAB_RATE_LIMIT_PER_MINUTE must be a positive integer")
        raw_retention = os.environ.get("WEEDLAB_RETENTION_DAYS", str(DEFAULT_RETENTION_DAYS))
        try:
            retention = int(raw_retention)
        except ValueError:
            retention = -1
        if retention < 0:
            raise RuntimeError(
                "WEEDLAB_RETENTION_DAYS must be a whole number of days, or 0 to keep everything"
            )
        raw_hops = os.environ.get("WEEDLAB_TRUSTED_PROXY_HOPS", "0")
        try:
            hops = int(raw_hops)
        except ValueError:
            hops = -1
        if not 0 <= hops <= 5:
            raise RuntimeError("WEEDLAB_TRUSTED_PROXY_HOPS must be a whole number from 0 to 5")
        return cls(
            model_path=model_path,
            max_upload_bytes=int(max_mb * 1024 * 1024),
            cors_origins=origins,
            database_url=database_url,
            rate_limit_per_minute=rate,
            retention_days=retention,
            trusted_proxy_hops=hops,
        )
