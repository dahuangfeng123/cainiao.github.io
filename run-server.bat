@echo off
cd /d "%~dp0"

echo ==========================================
echo   MoringRead - Start Learning Service
echo ==========================================
echo.

REM Check if uv is available
where uv >nul 2>&1
if errorlevel 1 (
    echo [ERROR] uv command not found!
    echo.
    echo Please install uv:
    echo   pip install uv
    echo.
    echo Or download from:
    echo   https://github.com/astral-sh/uv
    echo.
    pause
    exit /b 1
)

echo Starting server.py (FastAPI Unified Service)...
echo.

:uv run server/server.py
uv run uvicorn server:app --reload --port 5003 --app-dir server

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start!
    echo Please check:
    echo   1. Python environment is configured
    echo   2. server/server.py exists
    echo   3. Dependencies are installed
    echo.
    pause
    exit /b 1
)

echo.
echo Service stopped.
pause
