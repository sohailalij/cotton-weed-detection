from pathlib import Path

import pytest
import yaml

from weedlab.train import CLASS_NAMES, load_config, write_data_yaml

ROOT = Path(__file__).resolve().parents[1]

RUNS = [
    ("configs/train_yolo11n.yaml", "reports/runs/yolo11n_e50/args.yaml"),
    ("configs/train_yolo11s.yaml", "reports/runs/yolo11s_e50/args.yaml"),
]


def test_load_config_requires_keys(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("model: yolo11n.pt\n")
    with pytest.raises(ValueError):
        load_config(bad)


def test_write_data_yaml(tmp_path: Path) -> None:
    out = write_data_yaml(tmp_path / "data", tmp_path / "data.yaml")
    data = yaml.safe_load(out.read_text())
    assert len(CLASS_NAMES) == 12
    assert data["names"] == dict(enumerate(CLASS_NAMES))


@pytest.mark.parametrize(("config", "args_file"), RUNS)
def test_config_matches_recorded_run(config: str, args_file: str) -> None:
    cfg = load_config(ROOT / config)
    recorded = yaml.safe_load((ROOT / args_file).read_text())
    for key, value in cfg.items():
        assert recorded[key] == value, f"{key}: config {value!r} vs run {recorded[key]!r}"
