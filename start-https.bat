@echo off
cd /d "%~dp0"

echo ==========================================
echo   MoringRead - Start HTTPS Server
echo ==========================================
echo.

if not exist "server/cert/key.pem" (
    echo [ERROR] Certificate not found!
    echo.
    echo Please run first:
    echo   uv run python server/cert/simple_cert.py
    echo.
    pause
    exit /b 1
)

echo [INFO] Starting HTTPS server...
echo.
echo Access URLs:
echo   Local: https://localhost:5003/tingli2
echo   LAN:   https://192.168.0.109:5003/tingli2
echo.
echo NOTE: You will see a security warning in the browser
echo       Click "Advanced" - "Proceed to..."
echo.

uv run uvicorn server:app --reload --host 0.0.0.0 --port 5003 --app-dir server --ssl-keyfile server/cert/key.pem --ssl-certfile server/cert/cert.pem

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start!
    pause
    exit /b 1
)

echo.
echo Service stopped.
pause
