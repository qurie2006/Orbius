@echo off
cd /d "%~dp0"
echo ========================================================
echo   Starting Orbius - Multi-Agent BRD Studio
echo ========================================================
echo.
start "Orbius Backend (FastAPI)" cmd /k call "%~dp0start-backend.bat"
start "Orbius Frontend (Vite)" cmd /k call "%~dp0start-frontend.bat"
echo.
echo [!] Backend: http://127.0.0.1:8000
echo [!] Frontend: http://localhost:5173
echo.
echo Both services are starting in dedicated terminal windows.
echo ========================================================
