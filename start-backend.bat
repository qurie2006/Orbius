@echo off
cd /d "%~dp0backend"

if not exist .venv (
    echo Creating Python virtual environment...
    python -m venv .venv || py -m venv .venv
)

if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe -c "import fastapi, uvicorn, pydantic, sse_starlette" 2>nul
    if errorlevel 1 (
        echo Installing backend requirements into virtual environment...
        .venv\Scripts\pip.exe install -r requirements.txt
    )
    echo Starting FastAPI Backend on http://127.0.0.1:8000 ...
    .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
) else (
    echo Starting FastAPI Backend on http://127.0.0.1:8000 ...
    python -m uvicorn app.main:app --reload --port 8000
)

