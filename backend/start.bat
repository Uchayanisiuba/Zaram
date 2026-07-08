@echo off
cd /d "%~dp0"
echo [Zaram] Starting Zaram Backend v3.0...

if not exist venv (
    echo [Zaram] Creating virtual environment...
    py -3.11 -m venv venv
)

echo [Zaram] Installing dependencies...
venv\Scripts\python.exe -m pip install -q -r requirements.txt

echo [Zaram] Starting server...
venv\Scripts\python.exe main.py

pause
