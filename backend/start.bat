@echo off
REM Zaram backend launcher.
REM
REM Uses the repository-root .venv. There was a second environment at
REM backend\venv; this script created and installed into it on every launch,
REM which is how two environments came to exist and drift apart. Deleted.
REM
REM Dependencies install only when the environment is first created. The old
REM version ran pip install on every start, which on a slow connection turned
REM every launch into a several-minute wait for a no-op.
cd /d "%~dp0.."
echo [Zaram] Starting backend...

if not exist .venv (
    echo [Zaram] Creating virtual environment...
    py -3.11 -m venv .venv
    echo [Zaram] Installing dependencies ^(first run only^)...
    .venv\Scripts\python.exe -m pip install -r backend\requirements.txt
    REM Voice is deliberately NOT installed here. It pulls torch, transformers
    REM and the spaCy stack - roughly 830 MB against a ~200 MB base - for a
    REM feature that is out of scope for v1. Speech reports itself unavailable
    REM in Settings, with the command to enable it. See requirements-voice.txt.
)

echo [Zaram] Launching server...
cd backend
..\.venv\Scripts\python.exe main.py

pause
