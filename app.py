from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from motion_analyzer.pose_analyzer import AnalysisConfig, PoseVideoAnalyzer


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("APP_DATA_DIR", BASE_DIR))
OUTPUT_DIR = DATA_DIR / "outputs"
UPLOAD_DIR = DATA_DIR / "uploads"


def slugify(name: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_\u4e00-\u9fff-]+", "_", name)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or datetime.now().strftime("task_%Y%m%d_%H%M%S")


def load_bytes(path: Path) -> bytes:
    return path.read_bytes()


def make_long_table(df: pd.DataFrame, selected_metrics: list[str]) -> pd.DataFrame:
    table = df[["time_s", *selected_metrics]].melt(id_vars="time_s", var_name="metric", value_name="value_deg")
    return table.dropna(subset=["value_deg"])


st.set_page_config(page_title="2D Motion Analyzer", layout="wide")
st.title("二维人体运动学分析软件")
st.caption("上传视频后，自动完成关键点识别、骨架可视化、关节角度计算与结果导出。")

with st.sidebar:
    st.header("分析参数")
    min_detection_confidence = st.slider("最小检测置信度", 0.1, 1.0, 0.5, 0.05)
    min_tracking_confidence = st.slider("最小跟踪置信度", 0.1, 1.0, 0.5, 0.05)
    visibility_threshold = st.slider("关键点可见性阈值", 0.1, 1.0, 0.5, 0.05)
    model_complexity = st.selectbox("模型复杂度", options=[0, 1, 2], index=2)
    draw_angles = st.toggle("在视频上叠加角度文本", value=True)


uploaded_file = st.file_uploader("上传待分析视频", type=["mp4", "mov", "avi", "m4v"])

if uploaded_file is None:
    st.info("请选择一个单人运动视频。建议固定机位、侧面拍摄、主体完整入镜，以获得更稳定的二维运动学结果。")
    st.stop()

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

task_name = slugify(f"{Path(uploaded_file.name).stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
video_path = UPLOAD_DIR / f"{task_name}{Path(uploaded_file.name).suffix}"
video_path.write_bytes(uploaded_file.read())

st.video(load_bytes(video_path))

if st.button("开始分析", type="primary", use_container_width=True):
    analyzer = PoseVideoAnalyzer(output_root=OUTPUT_DIR)
    config = AnalysisConfig(
        min_detection_confidence=min_detection_confidence,
        min_tracking_confidence=min_tracking_confidence,
        model_complexity=model_complexity,
        visibility_threshold=visibility_threshold,
        draw_angles=draw_angles,
    )

    with st.spinner("正在识别关键点并计算运动学数据，这可能需要一些时间..."):
        artifacts = analyzer.analyze_video(video_path=video_path, task_name=task_name, config=config)

    st.success("分析完成。")

    summary = artifacts.summary
    summary_cols = st.columns(4)
    summary_cols[0].metric("视频时长", f"{summary['video']['duration_s']:.2f} s" if summary["video"]["duration_s"] else "-")
    summary_cols[1].metric("帧率", f"{summary['video']['fps']:.2f}")
    summary_cols[2].metric("检测帧占比", f"{summary['analysis']['detection_rate'] * 100:.1f}%")
    summary_cols[3].metric("逐帧记录", f"{summary['analysis']['kinematic_rows']}")

    left, right = st.columns([1.1, 1])
    with left:
        st.subheader("标记点与人体模型可视化")
        st.video(load_bytes(artifacts.annotated_video_path), format="video/mp4")
    with right:
        st.subheader("首帧预览")
        if artifacts.preview_frame_bytes is not None:
            st.image(artifacts.preview_frame_bytes, use_container_width=True)
        else:
            st.info("首帧预览生成失败，但分析数据已保留。")

    if artifacts.sample_frame_bytes:
        st.subheader("分析抽帧预览")
        sample_cols = st.columns(min(3, len(artifacts.sample_frame_bytes)))
        for idx, frame_bytes in enumerate(artifacts.sample_frame_bytes):
            sample_cols[idx % len(sample_cols)].image(
                frame_bytes,
                caption=f"样本帧 {idx + 1}",
                use_container_width=True,
            )

    angle_columns = [col for col in artifacts.kinematics_df.columns if col.endswith("_deg")]
    default_metrics = [col for col in angle_columns if "knee" in col or "hip" in col][:4]
    selected_metrics = st.multiselect(
        "选择需要绘制的运动学指标",
        options=angle_columns,
        default=default_metrics or angle_columns[:4],
    )

    if selected_metrics:
        plot_df = make_long_table(artifacts.kinematics_df, selected_metrics)
        fig = px.line(
            plot_df,
            x="time_s",
            y="value_deg",
            color="metric",
            labels={"time_s": "时间 (s)", "value_deg": "角度 (deg)", "metric": "指标"},
            title="运动学时间序列",
        )
        fig.update_layout(height=520, legend_title_text="")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("关键结果摘要")
    st.json(summary, expanded=False)

    st.subheader("数据预览")
    tabs = st.tabs(["运动学数据", "关键点数据"])
    with tabs[0]:
        st.dataframe(artifacts.kinematics_df.head(200), use_container_width=True)
    with tabs[1]:
        st.dataframe(artifacts.landmarks_df.head(200), use_container_width=True)

    download_cols = st.columns(4)
    download_cols[0].download_button(
        "下载标注视频",
        data=load_bytes(artifacts.annotated_video_path),
        file_name=artifacts.annotated_video_path.name,
        mime="video/mp4",
        use_container_width=True,
    )
    download_cols[1].download_button(
        "下载关键点 CSV",
        data=load_bytes(artifacts.landmarks_csv_path),
        file_name=artifacts.landmarks_csv_path.name,
        mime="text/csv",
        use_container_width=True,
    )
    download_cols[2].download_button(
        "下载运动学 CSV",
        data=load_bytes(artifacts.kinematics_csv_path),
        file_name=artifacts.kinematics_csv_path.name,
        mime="text/csv",
        use_container_width=True,
    )
    download_cols[3].download_button(
        "下载摘要 JSON",
        data=load_bytes(artifacts.summary_json_path),
        file_name=artifacts.summary_json_path.name,
        mime="application/json",
        use_container_width=True,
    )
