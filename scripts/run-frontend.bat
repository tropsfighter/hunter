@echo off
setlocal
title Hunter UI (Vite :5173)
cd /d "%~dp0..\frontend"

if not exist "package.json" (
  echo [hunter] frontend\package.json not found.
  pause
  exit /b 1
)

if not exist "node_modules\" (
  echo [hunter] node_modules missing. Running npm install...
  call npm install
  if errorlevel 1 (
    echo [hunter] npm install failed.
    pause
    exit /b 1
  )
)

echo [hunter] Starting dev server at http://localhost:5173
call npm run dev
pause
