@echo off
cd /d "%~dp0"
echo [Zaram] Starting backend...

if not exist venv (
    echo [Zaram] Creating virtual environment...
    py -3.11 -m venv venv
)

echo [Zaram] Installing dependencies...
venv\Scripts\python.exe -m pip install -q -r requirements.txt

echo [Zaram] Launching server...
venv\Scripts\python.exe main.py

pause
