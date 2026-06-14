@echo off
title ChatMoney Launcher
echo ============================================
echo            Starting ChatMoney...
echo ============================================
echo.

REM --- Start the backend (FastAPI) in its own window, using the project's venv ---
start "ChatMoney Backend" cmd /k "cd /d C:\Users\user\Documents\ChatMoney\backend && C:\Users\user\Documents\ChatMoney\venv\Scripts\python.exe -m uvicorn main:app --reload"

REM --- Start the frontend (Next.js dev server) in its own window ---
start "ChatMoney Frontend" cmd /k "cd /d C:\Users\user\Documents\ChatMoney\frontend && npm run dev"

REM --- Give both servers a few seconds to boot, then open the browser ---
echo Waiting for the servers to start...
timeout /t 10 /nobreak >nul
start "" http://localhost:3000

echo.
echo ChatMoney is opening in your browser at http://localhost:3000
echo.
echo Two server windows have opened (Backend + Frontend).
echo Closing those windows stops the app.
timeout /t 5 /nobreak >nul
exit
