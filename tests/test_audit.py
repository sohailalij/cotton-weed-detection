from pathlib import Path

from weedlab.audit import parse_label_file


def test_parse_valid_label(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("3 0.5 0.5 0.2 0.3\n")
    boxes, problems = parse_label_file(f)
    assert boxes == [(3, 0.5, 0.5, 0.2, 0.3)]
    assert problems == []


def test_parse_bad_label(tmp_path: Path) -> None:
    f = tmp_path / "b.txt"
    f.write_text("3 1.5 0.5 0.2 0.3\n1 0.5\n")
    boxes, problems = parse_label_file(f)
    assert boxes == []
    assert len(problems) == 2
