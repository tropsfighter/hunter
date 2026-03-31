@echo off
setlocal
rem Run from backend root so pytest.ini and package imports resolve correctly
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
  echo [hunter] Missing backend\.venv — create it and install dev deps:
  echo   cd backend
  echo   python -m venv .venv
  echo   .venv\Scripts\activate.bat
  echo   pip install -e ".[dev]"
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat
echo [hunter] Running pytest tests...
python -m pytest tests %*
set "EXIT=%ERRORLEVEL%"
if not "%EXIT%"=="0" (
  echo.
  echo [hunter] Tests finished with errors ^(exit %EXIT%^).
) else (
  echo.
  echo [hunter] All tests passed.
)
pause
exit /b %EXIT%
