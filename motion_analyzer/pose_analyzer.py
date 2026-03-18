from __future__ import annotations

import json
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import cv2
import mediapipe as mp
import numpy as np
import pandas as pd

from .kinematics import Point2D, compute_joint_angles, safe_nanmax, safe_nanmean, safe_nanmin


try:
    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils
except AttributeError:
    # Some hosted environments expose the solutions modules under mediapipe.python.
    from mediapipe.python.solutions import drawing_utils as mp_drawing
    from mediapipe.python.solutions import pose as mp_pose


POSE_LANDMARKS = mp_pose.PoseLandmark
POSE_CONNECTIONS = mp_pose.POSE_CONNECTIONS

LANDMARK_NAME_MAP = {
    landmark.value: landmark.name.lower()
    for landmark in POSE_LANDMARKS
}


@dataclass
class AnalysisConfig:
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    model_complexity: int = 2
    visibility_threshold: float = 0.5
    draw_angles: bool = True


@dataclass
class AnalysisArtifacts:
    task_dir: Path
    annotated_video_path: Path
    landmarks_csv_path: Path
    kinematics_csv_path: Path
    summary_json_path: Path
    preview_frame_path: Path
    summary: dict
    landmarks_df: pd.DataFrame
    kinematics_df: pd.DataFrame
    preview_frame_bytes: bytes | None
    sample_frame_bytes: List[bytes]


class PoseVideoAnalyzer:
    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.drawer = mp_drawing

    def analyze_video(self, video_path: Path, task_name: str, config: AnalysisConfig) -> AnalysisArtifacts:
        task_dir = self.output_root / task_name
        task_dir.mkdir(parents=True, exist_ok=True)

        annotated_video_path = task_dir / "annotated_video.mp4"
        landmarks_csv_path = task_dir / "landmarks.csv"
        kinematics_csv_path = task_dir / "kinematics.csv"
        summary_json_path = task_dir / "summary.json"
        preview_frame_path = task_dir / "preview_frame.jpg"

        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise RuntimeError(f"无法打开视频: {video_path}")

        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(annotated_video_path), fourcc, fps, (width, height))

        landmark_rows: List[dict] = []
        kinematic_rows: List[dict] = []
        preview_written = False
        sample_frame_bytes: List[bytes] = []
        sample_indices = self._build_sample_indices(total_frames)

        with mp_pose.Pose(
            static_image_mode=False,
            model_complexity=config.model_complexity,
            smooth_landmarks=True,
            enable_segmentation=False,
            min_detection_confidence=config.min_detection_confidence,
            min_tracking_confidence=config.min_tracking_confidence,
        ) as pose:
            frame_index = 0
            while True:
                ok, frame_bgr = capture.read()
                if not ok:
                    break

                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                result = pose.process(frame_rgb)

                time_s = frame_index / fps if fps else 0.0
                per_frame_landmarks: Dict[str, Point2D] = {}

                if result.pose_landmarks:
                    for idx, landmark in enumerate(result.pose_landmarks.landmark):
                        landmark_name = LANDMARK_NAME_MAP[idx]
                        x_px = landmark.x * width
                        y_px = landmark.y * height
                        per_frame_landmarks[landmark_name] = Point2D(
                            x=float(x_px),
                            y=float(y_px),
                            visibility=float(getattr(landmark, "visibility", 1.0)),
                        )
                        landmark_rows.append(
                            {
                                "frame": frame_index,
                                "time_s": time_s,
                                "landmark": landmark_name,
                                "x_px": float(x_px),
                                "y_px": float(y_px),
                                "z_norm": float(landmark.z),
                                "visibility": float(getattr(landmark, "visibility", 1.0)),
                            }
                        )

                    kinematics = compute_joint_angles(per_frame_landmarks, config.visibility_threshold)
                    kinematics["frame"] = frame_index
                    kinematics["time_s"] = time_s
                    kinematic_rows.append(kinematics)

                    annotated = frame_bgr.copy()
                    self.drawer.draw_landmarks(
                        annotated,
                        result.pose_landmarks,
                        POSE_CONNECTIONS,
                        self.drawer.DrawingSpec(color=(0, 255, 255), thickness=2, circle_radius=2),
                        self.drawer.DrawingSpec(color=(0, 128, 255), thickness=2, circle_radius=1),
                    )
                    if config.draw_angles:
                        self._draw_selected_angles(annotated, per_frame_landmarks, kinematics)
                else:
                    annotated = frame_bgr.copy()
                    kinematic_rows.append({"frame": frame_index, "time_s": time_s})

                if not preview_written:
                    preview_bytes = self._encode_image_bytes(annotated)
                    if preview_bytes is not None:
                        preview_frame_path.write_bytes(preview_bytes)
                        preview_written = True

                if frame_index in sample_indices:
                    sample_bytes = self._encode_image_bytes(annotated)
                    if sample_bytes is not None:
                        sample_frame_bytes.append(sample_bytes)

                writer.write(annotated)
                frame_index += 1

        capture.release()
        writer.release()

        landmarks_df = pd.DataFrame(landmark_rows)
        kinematics_df = pd.DataFrame(kinematic_rows).sort_values(by="frame").reset_index(drop=True)

        landmarks_df.to_csv(landmarks_csv_path, index=False, encoding="utf-8-sig")
        kinematics_df.to_csv(kinematics_csv_path, index=False, encoding="utf-8-sig")

        summary = self._build_summary(
            total_frames=total_frames,
            fps=fps,
            width=width,
            height=height,
            landmarks_df=landmarks_df,
            kinematics_df=kinematics_df,
        )
        summary_json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

        return AnalysisArtifacts(
            task_dir=task_dir,
            annotated_video_path=annotated_video_path,
            landmarks_csv_path=landmarks_csv_path,
            kinematics_csv_path=kinematics_csv_path,
            summary_json_path=summary_json_path,
            preview_frame_path=preview_frame_path,
            summary=summary,
            landmarks_df=landmarks_df,
            kinematics_df=kinematics_df,
            preview_frame_bytes=preview_frame_path.read_bytes() if preview_frame_path.exists() else None,
            sample_frame_bytes=sample_frame_bytes,
        )

    def _build_summary(
        self,
        total_frames: int,
        fps: float,
        width: int,
        height: int,
        landmarks_df: pd.DataFrame,
        kinematics_df: pd.DataFrame,
    ) -> dict:
        detected_frames = int(kinematics_df.dropna(how="all", subset=[col for col in kinematics_df.columns if col.endswith("_deg")]).shape[0])
        detection_rate = detected_frames / total_frames if total_frames else 0.0

        metrics = {}
        for column in [col for col in kinematics_df.columns if col.endswith("_deg")]:
            values = kinematics_df[column].tolist()
            metrics[column] = {
                "mean": safe_nanmean(values),
                "min": safe_nanmin(values),
                "max": safe_nanmax(values),
            }

        return {
            "video": {
                "total_frames": total_frames,
                "fps": fps,
                "width": width,
                "height": height,
                "duration_s": total_frames / fps if fps else None,
            },
            "analysis": {
                "detected_frames": detected_frames,
                "detection_rate": detection_rate,
                "landmark_rows": int(len(landmarks_df)),
                "kinematic_rows": int(len(kinematics_df)),
            },
            "metrics": metrics,
        }

    def _draw_selected_angles(self, frame: np.ndarray, landmarks: Dict[str, Point2D], kinematics: dict) -> None:
        labels = [
            ("left_knee", "LK", kinematics.get("left_knee_angle_deg")),
            ("right_knee", "RK", kinematics.get("right_knee_angle_deg")),
            ("left_hip", "LH", kinematics.get("left_hip_angle_deg")),
            ("right_hip", "RH", kinematics.get("right_hip_angle_deg")),
            ("left_elbow", "LE", kinematics.get("left_elbow_angle_deg")),
            ("right_elbow", "RE", kinematics.get("right_elbow_angle_deg")),
        ]
        for landmark_name, prefix, value in labels:
            point = landmarks.get(landmark_name)
            if point is None or value is None:
                continue
            cv2.putText(
                frame,
                f"{prefix}:{value:.1f}",
                (int(point.x) + 8, int(point.y) - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                f"{prefix}:{value:.1f}",
                (int(point.x) + 8, int(point.y) - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (20, 20, 20),
                1,
                cv2.LINE_AA,
            )

    def _encode_image_bytes(self, frame: np.ndarray) -> bytes | None:
        ok, encoded = cv2.imencode(".jpg", frame)
        if not ok:
            return None
        return encoded.tobytes()

    def _build_sample_indices(self, total_frames: int, count: int = 6) -> set[int]:
        if total_frames <= 0:
            return set()
        if total_frames <= count:
            return set(range(total_frames))
        values = np.linspace(0, total_frames - 1, num=count, dtype=int)
        return {int(v) for v in values}
