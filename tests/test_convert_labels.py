from weedlab.convert_labels import region_to_box


def test_region_to_box_converts_pixels_to_yolo() -> None:
    region = {
        "shape_attributes": {"name": "rect", "x": 0, "y": 0, "width": 50, "height": 100},
        "region_attributes": {"CottonWeed": {"Waterhemp": True}},
    }
    assert region_to_box(region, 100, 200) == (0, 0.25, 0.25, 0.5, 0.5)


def test_region_to_box_rejects_unknown_species() -> None:
    region = {
        "shape_attributes": {"name": "rect", "x": 0, "y": 0, "width": 50, "height": 100},
        "region_attributes": {"CottonWeed": {"NotAWeed": True}},
    }
    assert region_to_box(region, 100, 200) is None
