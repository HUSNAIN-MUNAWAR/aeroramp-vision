from aeroramp.vision.geometry import (
    angle_difference,
    bbox_intersection_ratio,
    closest_point_of_approach,
    estimate_speed,
    line_crossed,
    point_in_polygon,
    valid_polygon,
)


def test_polygon_operations() -> None:
    polygon = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert valid_polygon(polygon)
    assert point_in_polygon((5, 5), polygon)
    assert not point_in_polygon((12, 5), polygon)
    assert bbox_intersection_ratio((5, 5, 15, 15), polygon) == 0.25


def test_line_speed_and_direction() -> None:
    assert line_crossed((0, 0), (10, 10), [[0, 10], [10, 0]])
    assert estimate_speed((0, 0), (10, 0), 2, 0.5) == 2.5
    assert estimate_speed((0, 0), (10, 0), 2, None) is None
    assert angle_difference(350, 10) == 20


def test_closest_point_of_approach() -> None:
    result = closest_point_of_approach((0, 0), (1, 0), (10, 0), (-1, 0))
    assert result.distance < 1e-6
    assert result.time_to_closest == 5
