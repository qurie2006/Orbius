@echo off
cd /d %~dp0backend
if not exist .venv (
    echo Creating Python virtual environment...
    python -m venv .venv || py -m venv .venv
)
call .venv\Scripts\activate.bat
echo Installing backend requirements...
pip install -r requirements.txt
echo Starting FastAPI Backend on http://127.0.0.1:8000 ...
python -m uvicorn app.main:app --reload --port 8000
