---
title: 2D Motion Analyzer
emoji: 🏃
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
suggested_hardware: cpu-basic
---

# 2D Motion Kinematics Analyzer

本项目是一个本地运行的二维人体运动学分析工具。用户上传视频后，系统会自动识别人身体关键点，建立二维骨架模型，计算关节角度与关键点轨迹，并导出分析结果。

## 功能

- 上传单人运动视频并自动分析
- 基于 AI 自动识别人体关键点
- 在视频上叠加关键点、骨架与主要关节角度
- 导出逐帧关键点数据与运动学数据 CSV
- 在网页中查看运动学曲线和分析摘要

## 技术路线

- 姿态估计: MediaPipe Pose
- 视频处理: OpenCV
- 数据分析: NumPy / Pandas
- 可视化与界面: Streamlit / Plotly

## 运行

### 方式 1: 双击启动

直接双击项目根目录下的 `start_app.bat`。
会先弹出一个服务窗口，几秒后浏览器会自动打开。

### iPhone 局域网访问

1. 电脑和 iPhone 连接到同一个 Wi-Fi。
2. 双击 `start_app_lan.bat`。
3. 在服务窗口中查看 `Network URL`，通常类似 `http://192.168.x.x:8501`。
4. 在 iPhone Safari 中打开这个地址。
5. 首次使用如果打不开，允许 Windows 防火墙放行 Python 的专用网络访问。

### iPhone 外网访问

如果 iPhone 和电脑不在同一个局域网，可以使用 Cloudflare Tunnel。

1. 双击 `start_app_public.bat`。
2. 会打开两个窗口：
   - 一个是 Streamlit 服务窗口
   - 一个是 Cloudflare Tunnel 窗口
3. 在 Cloudflare Tunnel 窗口中找到 `https://...trycloudflare.com` 公网地址。
4. 在 iPhone Safari 中打开这个公网地址。
5. 使用结束后，关闭这两个窗口即可停止外网访问。

注意：

- 只要窗口开着，这个公网地址就可访问。
- Quick Tunnel 地址是临时的，重启后通常会变化。
- 为了安全，建议只在你使用时开启。

## 部署到 Render

本项目已经包含：

- `Dockerfile`
- `render.yaml`

推荐部署方式：

1. 将本项目推送到 GitHub 仓库。
2. 在 Render 中创建 `Web Service`。
3. 选择该 GitHub 仓库。
4. Render 会自动识别 `Dockerfile` 并构建部署。
5. 部署成功后，使用 Render 分配的 `https://<service>.onrender.com` 地址访问。

说明：

- Render Web Service 需要绑定 `0.0.0.0`，并监听 `PORT` 环境变量指定端口。当前项目已兼容。
- 本项目默认将上传与分析输出写入 `APP_DATA_DIR`，在容器中默认为 `/app/data`。
- Render 默认文件系统是临时的。如果希望重启后仍保留上传视频和分析结果，需要在 Render 控制台为服务挂载 `Persistent Disk`。

相关官方文档：

- [Render Web Services](https://render.com/docs/web-services)
- [Render Docker 部署](https://render.com/docs/docker)
- [Render Persistent Disks](https://render.com/docs/disks)

## 部署到 Streamlit Community Cloud

本项目已补充：

- `runtime.txt` 固定 Python 3.11
- `packages.txt` 安装 OpenCV / MediaPipe 运行所需系统库

如果在 Streamlit Community Cloud 上部署失败，优先检查：

- 是否正确识别 `app.py` 为入口文件
- 构建日志中是否出现 Python 版本不匹配
- `requirements.txt` 中依赖是否成功安装

## 部署到 Hugging Face Spaces

推荐使用 Docker Space。Hugging Face 官方说明，Docker Space 需要在仓库根目录的 `README.md` 顶部加入 YAML 配置，并通过 `Dockerfile` 启动服务；默认对外端口可通过 `app_port` 配置，例如 `7860`。

当前项目已适配：

- `sdk: docker`
- `app_port: 7860`
- 容器内默认数据目录为 `/data/app`

部署步骤：

1. 在 Hugging Face 创建一个新 Space。
2. SDK 选择 `Docker`。
3. 将 Space 仓库关联到当前 GitHub 仓库，或将当前仓库内容上传到该 Space。
4. 等待 Hugging Face 自动构建镜像并启动。
5. 启动后直接通过 Hugging Face 提供的网址访问。

参考：

- [Docker Spaces](https://huggingface.co/docs/hub/spaces-sdks-docker)
- [Spaces 配置参考](https://huggingface.co/docs/hub/en/spaces-config-reference)

### 方式 2: 命令行启动

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

如果 `streamlit` 命令不可用，也可以用：

```bash
python -m streamlit run app.py
```

## 输出文件

分析完成后，程序会生成：

- `outputs/<任务名>/annotated_video.mp4`
- `outputs/<任务名>/landmarks.csv`
- `outputs/<任务名>/kinematics.csv`
- `outputs/<任务名>/summary.json`
