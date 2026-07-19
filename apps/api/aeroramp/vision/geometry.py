from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from shapely.geometry import LineString, Point, Polygon, box


@dataclass(slots=True)
class ClosestApproach:
    distance: float
    time_to_closest: float


def valid_polygon(points: list[list[float]]) -> bool:
    if len(points) < 3:
        return False
    polygon = Polygon(points)
    return polygon.is_valid and polygon.area > 0


def point_in_polygon(point: tuple[float, float], polygon: list[list[float]]) -> bool:
    return Polygon(polygon).covers(Point(point))


def bbox_intersection_ratio(
    bbox_xyxy: tuple[float, float, float, float], polygon: list[list[float]]
) -> float:
    bbox_shape = box(*bbox_xyxy)
    if bbox_shape.area == 0:
        return 0.0
    return float(bbox_shape.intersection(Polygon(polygon)).area / bbox_shape.area)


def line_crossed(
    previous: tuple[float, float], current: tuple[float, float], line: list[list[float]]
) -> bool:
    return LineString([previous, current]).crosses(LineString(line))


def estimate_speed(
    previous: tuple[float, float], current: tuple[float, float], delta_seconds: float, scale: float | None
) -> float | None:
    if scale is None or delta_seconds <= 0:
        return None
    return math.dist(previous, current) * scale / delta_seconds


def direction_angle(previous: tuple[float, float], current: tuple[float, float]) -> float:
    return math.degrees(math.atan2(current[1] - previous[1], current[0] - previous[0]))


def angle_difference(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def closest_point_of_approach(
    p1: tuple[float, float], v1: tuple[float, float], p2: tuple[float, float], v2: tuple[float, float]
) -> ClosestApproach:
    relative_position = np.array(p1, dtype=float) - np.array(p2, dtype=float)
    relative_velocity = np.array(v1, dtype=float) - np.array(v2, dtype=float)
    speed_sq = float(np.dot(relative_velocity, relative_velocity))
    if speed_sq < 1e-9:
        return ClosestApproach(float(np.linalg.norm(relative_position)), 0.0)
    time_to_closest = max(0.0, -float(np.dot(relative_position, relative_velocity)) / speed_sq)
    closest = relative_position + relative_velocity * time_to_closest
    return ClosestApproach(float(np.linalg.norm(closest)), time_to_closest)


def apply_homography(point: tuple[float, float], matrix: list[list[float]]) -> tuple[float, float]:
    src = np.array([[[point[0], point[1]]]], dtype=np.float32)
    transformed = np.array(matrix, dtype=np.float64)
    result = __import__("cv2").perspectiveTransform(src, transformed)[0][0]
    return float(result[0]), float(result[1])
