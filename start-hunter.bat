@echo off
setlocal
cd /d "%~dp0"

echo.
echo  Hunter — starting API and frontend in separate windows.
echo  Close each window to stop that process (Ctrl+C then close, or close the window).
echo.

if not exist "backend\.venv\Scripts\activate.bat" (
  echo [hunter] Backend virtualenv not found.
  echo.
  echo  From the backend folder run:
  echo    python -m venv .venv
  echo    .venv\Scripts\activate.bat
  echo    pip install -e ".[dev]"
  echo.
  pause
  exit /b 1
)

if not exist "frontend\package.json" (
  echo [hunter] frontend\package.json not found.
  pause
  exit /b 1
)

start "Hunter API :8000" "%~dp0scripts\run-backend.bat"
timeout /t 2 /nobreak >nul
start "Hunter UI :5173" "%~dp0scripts\run-frontend.bat"
timeout /t 4 /nobreak >nul

start "" "http://localhost:5173" 2>nul

echo [hunter] Opened API and UI windows. Browser should open http://localhost:5173
echo.
pause
