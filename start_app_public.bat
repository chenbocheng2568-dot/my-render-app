@echo off
setlocal
cd /d "%~dp0"

if not exist "tools\cloudflared.exe" (
  echo cloudflared not found. Please make sure tools\cloudflared.exe exists.
  pause
  exit /b 1
)

echo Starting 2D Motion Analyzer for public internet access...
echo Keep both windows open while accessing the app from your iPhone.

start "Motion Analyzer Server" cmd /k "cd /d %~dp0 && python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false"
timeout /t 6 /nobreak >nul
start "Cloudflare Tunnel" cmd /k "cd /d %~dp0 && tools\cloudflared.exe tunnel --url http://127.0.0.1:8501"

echo.
echo Wait for the Cloudflare Tunnel window to show a public https://*.trycloudflare.com URL.
echo Open that URL on your iPhone.
pause
