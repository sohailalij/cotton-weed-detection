from types import SimpleNamespace

from weedlab.evaluate import markdown_table, per_class_rows


def fake_results() -> SimpleNamespace:
    box = SimpleNamespace(
        ap_class_index=[0, 4],
        p=[0.9, 0.5],
        r=[0.8, 0.4],
        ap50=[0.95, 0.55],
        ap=[0.9, 0.45],
    )
    return SimpleNamespace(
        box=box,
        nt_per_image=list(range(12)),
        nt_per_class=[10 * i for i in range(12)],
    )


def test_per_class_rows_uses_class_ids() -> None:
    rows = per_class_rows(fake_results())
    assert [r["class"] for r in rows] == ["waterhemp", "carpetweed"]
    assert rows[1]["images"] == 4
    assert rows[1]["boxes"] == 40
    assert rows[1]["precision"] == 0.5


def test_markdown_table_shape() -> None:
    table = markdown_table(per_class_rows(fake_results()))
    lines = table.splitlines()
    assert len(lines) == 4
    assert "carpetweed" in lines[3]
