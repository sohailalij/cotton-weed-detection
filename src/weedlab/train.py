"""Train a YOLO model from a committed config file."""

from __future__ import annotations

import argparse
import json
import platform
from importlib.metadata import version
from pathlib import Path
from typing import Any

import yaml

CLASS_NAMES = [
    "waterhemp",
    "morning_glory",
    "purslane",
    "spotted_spurge",
    "carpetweed",
    "ragweed",
    "eclipta",
    "prickly_sida",
    "palmer_amaranth",
    "sicklepod",
    "goosegrass",
    "cutleaf_groundcherry",
]

REQUIRED_KEYS = ("model", "name", "seed")


def load_config(path: Path) -> dict[str, Any]:
    with path.open() as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise TypeError(f"{path} must contain a mapping")
    for key in REQUIRED_KEYS:
        if key not in cfg:
            raise ValueError(f"{path} is missing required key '{key}'")
    return cfg


def write_data_yaml(data_root: Path, out: Path) -> Path:
    cfg = {
        "path": str(data_root),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": dict(enumerate(CLASS_NAMES)),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)
    return out


def write_versions(out: Path) -> None:
    info = {
        "python": platform.python_version(),
        "ultralytics": version("ultralytics"),
        "torch": version("torch"),
    }
    out.write_text(json.dumps(info, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--name", default=None, help="override the run name")
    args = ap.parse_args()

    cfg = load_config(args.config)
    model_name = str(cfg.pop("model"))
    config_name = str(cfg.pop("name"))
    run_name = str(args.name or config_name)
    data_yaml = write_data_yaml(args.data_root, args.project / "data.yaml")

    from ultralytics import YOLO

    model = YOLO(model_name)
    model.train(data=str(data_yaml), project=str(args.project), name=run_name, **cfg)
    write_versions(Path(model.trainer.save_dir) / "versions.json")


if __name__ == "__main__":
    main()
