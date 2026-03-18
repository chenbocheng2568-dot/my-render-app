from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

import numpy as np


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float
    visibility: float | None = None


def calculate_angle(a: Point2D, b: Point2D, c: Point2D) -> float | None:
    """Returns the angle ABC in degrees on a 2D plane."""
    ba = np.array([a.x - b.x, a.y - b.y], dtype=float)
    bc = np.array([c.x - b.x, c.y - b.y], dtype=float)
    ba_norm = np.linalg.norm(ba)
    bc_norm = np.linalg.norm(bc)
    if ba_norm == 0 or bc_norm == 0:
        return None
    cosine = np.clip(np.dot(ba, bc) / (ba_norm * bc_norm), -1.0, 1.0)
    return float(np.degrees(np.arccos(cosine)))


def calculate_segment_angle(start: Point2D, end: Point2D) -> float | None:
    """Angle of a segment against the positive horizontal axis."""
    dx = end.x - start.x
    dy = end.y - start.y
    if dx == 0 and dy == 0:
        return None
    return float(np.degrees(np.arctan2(dy, dx)))


def visibility_ok(points: Iterable[Point2D | None], threshold: float) -> bool:
    for point in points:
        if point is None:
            return False
        if point.visibility is not None and point.visibility < threshold:
            return False
    return True


def midpoint(a: Point2D, b: Point2D) -> Point2D:
    return Point2D(x=(a.x + b.x) / 2.0, y=(a.y + b.y) / 2.0)


def compute_joint_angles(landmarks: Dict[str, Point2D], visibility_threshold: float) -> Dict[str, float | None]:
    results: Dict[str, float | None] = {}

    triplets: Dict[str, Tuple[str, str, str]] = {
        "left_elbow_angle_deg": ("left_shoulder", "left_elbow", "left_wrist"),
        "right_elbow_angle_deg": ("right_shoulder", "right_elbow", "right_wrist"),
        "left_shoulder_angle_deg": ("left_hip", "left_shoulder", "left_elbow"),
        "right_shoulder_angle_deg": ("right_hip", "right_shoulder", "right_elbow"),
        "left_hip_angle_deg": ("left_shoulder", "left_hip", "left_knee"),
        "right_hip_angle_deg": ("right_shoulder", "right_hip", "right_knee"),
        "left_knee_angle_deg": ("left_hip", "left_knee", "left_ankle"),
        "right_knee_angle_deg": ("right_hip", "right_knee", "right_ankle"),
        "left_ankle_angle_deg": ("left_knee", "left_ankle", "left_foot_index"),
        "right_ankle_angle_deg": ("right_knee", "right_ankle", "right_foot_index"),
    }

    for metric_name, keys in triplets.items():
        points = [landmarks.get(key) for key in keys]
        if visibility_ok(points, visibility_threshold):
            results[metric_name] = calculate_angle(points[0], points[1], points[2])
        else:
            results[metric_name] = None

    if visibility_ok(
        [landmarks.get("left_hip"), landmarks.get("right_hip"), landmarks.get("left_shoulder"), landmarks.get("right_shoulder")],
        visibility_threshold,
    ):
        hip_mid = midpoint(landmarks["left_hip"], landmarks["right_hip"])
        shoulder_mid = midpoint(landmarks["left_shoulder"], landmarks["right_shoulder"])
        results["trunk_angle_deg"] = calculate_segment_angle(hip_mid, shoulder_mid)
    else:
        results["trunk_angle_deg"] = None

    segment_pairs: Dict[str, Tuple[str, str]] = {
        "left_thigh_angle_deg": ("left_hip", "left_knee"),
        "right_thigh_angle_deg": ("right_hip", "right_knee"),
        "left_shank_angle_deg": ("left_knee", "left_ankle"),
        "right_shank_angle_deg": ("right_knee", "right_ankle"),
        "left_foot_angle_deg": ("left_heel", "left_foot_index"),
        "right_foot_angle_deg": ("right_heel", "right_foot_index"),
        "left_upper_arm_angle_deg": ("left_shoulder", "left_elbow"),
        "right_upper_arm_angle_deg": ("right_shoulder", "right_elbow"),
        "left_forearm_angle_deg": ("left_elbow", "left_wrist"),
        "right_forearm_angle_deg": ("right_elbow", "right_wrist"),
    }
    for metric_name, keys in segment_pairs.items():
        points = [landmarks.get(key) for key in keys]
        if visibility_ok(points, visibility_threshold):
            results[metric_name] = calculate_segment_angle(points[0], points[1])
        else:
            results[metric_name] = None

    return results


def safe_nanmean(values: Iterable[float | None]) -> float | None:
    arr = np.array([np.nan if value is None else value for value in values], dtype=float)
    if np.isnan(arr).all():
        return None
    return float(np.nanmean(arr))


def safe_nanmax(values: Iterable[float | None]) -> float | None:
    arr = np.array([np.nan if value is None else value for value in values], dtype=float)
    if np.isnan(arr).all():
        return None
    return float(np.nanmax(arr))


def safe_nanmin(values: Iterable[float | None]) -> float | None:
    arr = np.array([np.nan if value is None else value for value in values], dtype=float)
    if np.isnan(arr).all():
        return None
    return float(np.nanmin(arr))
