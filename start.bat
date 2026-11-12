@echo off
rem Issuer Intelligence Hub: double-click to start (Windows). Opens http://127.0.0.1:8600 in the browser.
rem Needs: Python 3, the data\ folder (from the team's OneDrive) and, for the AI, the .env file (sent privately).
cd /d "%~dp0"
if not exist data\daily_features.parquet (
  echo The data folder is missing. Copy it from the team's OneDrive into: %cd%\data
  pause & exit /b 1
)
if not exist .env echo No .env file: the app runs, but the AI uses fixed-rule answers (template mode).
if not exist .venv\Scripts\python.exe (
  echo First start: installing the Python packages ^(needs internet, about 1-2 minutes^) ...
  py -3 -m venv .venv || python -m venv .venv
  .venv\Scripts\python.exe -m pip install -q -r requirements.txt || (echo Installation failed. & pause & exit /b 1)
)
start "" cmd /c "timeout /t 6 >nul & start http://127.0.0.1:8600"
echo Starting ... the browser opens by itself. Keep this window open during the demo; close it to stop.
.venv\Scripts\python.exe web\server.py %*
