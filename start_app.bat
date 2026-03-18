@echo off
setlocal
cd /d "%~dp0"

echo Starting 2D Motion Analyzer...
start "Motion Analyzer Server" cmd /k "cd /d %~dp0 && python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true --browser.gatherUsageStats false"
timeout /t 6 /nobreak >nul
start "" http://localhost:8501
