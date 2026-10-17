@echo off
cd /d "%~dp0backend"

python -c "import fastapi, uvicorn, pydantic" 2>nul
if %errorlevel% neq 0 (
    echo Dependencies not found in global Python. Checking virtual environment...
    if not exist .venv (
        echo Creating Python virtual environment...
        python -m venv .venv || py -m venv .venv
    )
    if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
    echo Installing backend requirements...
    pip install -r requirements.txt
)

echo Starting FastAPI Backend on http://127.0.0.1:8000 ...
python -m uvicorn app.main:app --reload --port 8000

