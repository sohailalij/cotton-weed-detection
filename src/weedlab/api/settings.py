"""API settings, read from environment variables. The service refuses to start on bad ones."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ORIGINS = ("http://localhost:5173",)
DEFAULT_METRICS = Path("reports/test_eval/yolo11s_v1_960_best/metrics.json")


@dataclass(frozen=True)
class Settings:
    model_path: Path | None = None
    metrics_path: Path | None = DEFAULT_METRICS
    imgsz: int = 960
    default_conf: float = 0.58
    max_upload_bytes: int = 15 * 1024 * 1024
    max_pixels: int = 50_000_000
    cors_origins: tuple[str, ...] = DEFAULT_ORIGINS

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
        raw_origins = os.environ.get("WEEDLAB_CORS_ORIGINS")
        origins = (
            tuple(o.strip() for o in raw_origins.split(",") if o.strip())
            if raw_origins
            else DEFAULT_ORIGINS
        )
        if "*" in origins:
            raise RuntimeError("WEEDLAB_CORS_ORIGINS must list origins, not '*'")
        max_mb = float(os.environ.get("WEEDLAB_MAX_UPLOAD_MB", "15"))
        return cls(
            model_path=model_path,
            max_upload_bytes=int(max_mb * 1024 * 1024),
            cors_origins=origins,
        )
