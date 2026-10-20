import numpy as np
from PIL import Image

from weedlab.inference import letterbox, nms, postprocess

NAMES = {i: f"c{i}" for i in range(12)}


def test_letterbox_pads_to_multiple_of_stride_with_grey() -> None:
    image = Image.new("RGB", (1024, 768), (0, 0, 0))
    tensor, scale, left, top = letterbox(image, 960)
    assert tensor.shape == (1, 3, 736, 960)
    assert tensor.dtype == np.float32
    assert scale == 0.9375
    assert (left, top) == (0, 8)
    assert np.isclose(tensor[0, 0, 0, 0], 114 / 255)  # padding row
    assert tensor[0, 0, 8, 0] == 0.0  # first image row


def test_letterbox_needs_no_padding_when_already_aligned() -> None:
    tensor, _, left, top = letterbox(Image.new("RGB", (1024, 683)), 960)
    assert tensor.shape == (1, 3, 640, 960)
    assert (left, top) == (0, 0)


def test_nms_keeps_best_of_overlapping_boxes() -> None:
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], dtype=np.float32)
    scores = np.array([0.8, 0.9, 0.7], dtype=np.float32)
    # IoU of the first two boxes is about 0.68
    assert nms(boxes, scores, 0.5) == [1, 2]  # suppressed above 0.5
    assert nms(boxes, scores, 0.7) == [1, 0, 2]  # kept below 0.7


def _output(rows: list[tuple[float, float, float, float, int, float]]) -> np.ndarray:
    out = np.zeros((1, 16, len(rows)), dtype=np.float32)
    for i, (cx, cy, w, h, cls, score) in enumerate(rows):
        out[0, :4, i] = (cx, cy, w, h)
        out[0, 4 + cls, i] = score
    return out


def test_postprocess_maps_back_to_original_pixels_and_filters() -> None:
    out = _output(
        [
            (100, 100, 50, 50, 4, 0.9),
            (101, 101, 50, 50, 4, 0.8),  # duplicate of the first, same class
            (100, 100, 50, 50, 5, 0.7),  # same place, other class, must survive
            (300, 300, 20, 20, 2, 0.1),  # below the confidence cutoff
        ]
    )
    dets = postprocess(out, 0.5, 10, 20, (2000, 2000), NAMES, conf=0.25, iou=0.7, max_det=300)
    assert [d.class_id for d in dets] == [4, 5]
    assert dets[0].class_name == "c4"
    assert np.allclose(dets[0].box, (130, 110, 230, 210))
    assert np.isclose(dets[0].score, 0.9)


def test_postprocess_clips_to_image_and_returns_empty_list() -> None:
    out = _output([(5, 5, 50, 50, 0, 0.9)])
    dets = postprocess(out, 1.0, 0, 0, (100, 100), NAMES, conf=0.25, iou=0.7, max_det=300)
    assert dets[0].box[0] == 0.0 and dets[0].box[1] == 0.0
    empty = postprocess(out, 1.0, 0, 0, (100, 100), NAMES, conf=0.95, iou=0.7, max_det=300)
    assert empty == []


def test_postprocess_respects_max_det() -> None:
    rows = [(100.0 + 200 * i, 100.0, 50.0, 50.0, 0, 0.9) for i in range(5)]
    dets = postprocess(_output(rows), 1.0, 0, 0, (2000, 2000), NAMES, 0.25, 0.7, max_det=3)
    assert len(dets) == 3
