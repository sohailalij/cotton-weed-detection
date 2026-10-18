from weedlab.errors import iou, match_image, size_bucket, yolo_to_pixels


def test_iou_identical_and_disjoint() -> None:
    a = (0.0, 0.0, 10.0, 10.0)
    assert iou(a, a) == 1.0
    assert iou(a, (20.0, 20.0, 30.0, 30.0)) == 0.0


def test_yolo_to_pixels() -> None:
    assert yolo_to_pixels(0.5, 0.5, 0.5, 0.5, 100, 200) == (25.0, 50.0, 75.0, 150.0)


def test_match_image_produces_every_event_type() -> None:
    gt = [
        (0, (0.0, 0.0, 10.0, 10.0)),
        (1, (50.0, 50.0, 60.0, 60.0)),
        (2, (100.0, 100.0, 110.0, 110.0)),
    ]
    preds = [
        (0, 0.9, (0.0, 0.0, 10.0, 10.0)),
        (3, 0.8, (50.0, 50.0, 60.0, 60.0)),
        (4, 0.7, (200.0, 200.0, 210.0, 210.0)),
    ]
    kinds = sorted(e["type"] for e in match_image(gt, preds, 0.5))
    assert kinds == ["confused", "false_positive", "missed", "ok"]


def test_each_real_box_is_matched_only_once() -> None:
    gt = [(0, (0.0, 0.0, 10.0, 10.0))]
    preds = [
        (0, 0.9, (0.0, 0.0, 10.0, 10.0)),
        (0, 0.8, (0.0, 0.0, 10.0, 10.0)),
    ]
    kinds = sorted(e["type"] for e in match_image(gt, preds, 0.5))
    assert kinds == ["false_positive", "ok"]


def test_size_bucket() -> None:
    assert size_bucket(10) == "<32px"
    assert size_bucket(32) == "32-64px"
    assert size_bucket(64) == ">=64px"
