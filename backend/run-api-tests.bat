@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [hunter] Create backend\.venv and run: pip install -e ".[dev]"
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python run_tests_and_report.py %*
pause
