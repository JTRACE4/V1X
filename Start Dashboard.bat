@echo off
title Kalshi Dashboard
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed yet.
  echo Install it from https://www.python.org/downloads/ - and TICK "Add Python to PATH" in the installer.
  echo Then double-click this file again.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo First-time setup - one minute, please wait...
  python -m venv .venv
  if errorlevel 1 ( echo Could not create the Python environment. & pause & exit /b 1 )
  ".venv\Scripts\python.exe" -m pip install -q --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
  if errorlevel 1 ( echo Install failed - check your internet connection and try again. & rmdir /s /q .venv & pause & exit /b 1 )
)
echo Starting the dashboard... your browser will open in a few seconds.
echo To stop it: close this window (or press Ctrl+C).
start "" /b cmd /c "timeout /t 12 /nobreak >nul & start http://127.0.0.1:8765"
".venv\Scripts\python.exe" kalshi_web_dashboard.py
pause
