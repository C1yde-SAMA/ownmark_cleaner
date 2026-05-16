import pytest

from ownmark_cleaner.detection import Box, merge_nearby_boxes, mask_from_boxes, parse_rect


def test_parse_rect_ok():
    assert parse_rect("1,2,300,40") == (1, 2, 300, 40)


def test_parse_rect_strips_spaces():
    assert parse_rect(" 1, 2, 3, 4 ") == (1, 2, 3, 4)


def test_parse_rect_rejects_bad_count():
    with pytest.raises(ValueError):
        parse_rect("1,2,3")


def test_parse_rect_rejects_non_integer():
    with pytest.raises(ValueError):
        parse_rect("1,2,x,4")


def test_parse_rect_rejects_negative_size():
    with pytest.raises(ValueError):
        parse_rect("1,2,-3,4")


def test_merge_nearby_boxes_merges_close_boxes():
    boxes = [Box(10, 10, 10, 10, 100), Box(25, 12, 10, 10, 100)]
    merged = merge_nearby_boxes(boxes, gap=8, width=100, height=100)
    assert len(merged) == 1
    assert merged[0].x == 10
    assert merged[0].w == 25


def test_mask_from_boxes_fills_with_padding():
    mask = mask_from_boxes(20, 20, [Box(5, 5, 4, 4, 16)], padding=2)
    assert mask[3:11, 3:11].all()
    assert mask[0, 0] == 0
