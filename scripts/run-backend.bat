@echo off
setlocal
title Hunter API (uvicorn :8000)
cd /d "%~dp0..\backend"

if not exist ".venv\Scripts\activate.bat" (
  echo [hunter] Missing backend\.venv
  echo Create it from the repo root:
  echo   cd backend
  echo   python -m venv .venv
  echo   .venv\Scripts\activate.bat
  echo   pip install -e ".[dev]"
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat
if errorlevel 1 (
  echo [hunter] Failed to activate virtual environment.
  pause
  exit /b 1
)

echo [hunter] Starting API at http://127.0.0.1:8000
uvicorn hunter.api.main:app --reload --port 8000
pause
