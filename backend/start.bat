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
    REM spaCy's model is not a PyPI package. It is fetched through spaCy's own
    REM downloader rather than pinned in requirements.txt as a GitHub URL,
    REM because that URL fails the whole install when the connection drops.
    .venv\Scripts\python.exe -m spacy download en_core_web_sm
)

echo [Zaram] Launching server...
cd backend
..\.venv\Scripts\python.exe main.py

pause
