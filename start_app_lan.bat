@echo off
setlocal
cd /d "%~dp0"

echo Starting 2D Motion Analyzer for LAN access...
echo Keep this window open while using the app on your iPhone.
python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true --browser.gatherUsageStats false
