@echo off
REM ZCode - the Spine from a terminal.
REM
REM One script, two layouts, because it ships in the installer and also sits
REM at the root of a checkout:
REM
REM   installed   <install>\zcode.cmd
REM               python   <install>\resources\runtime\python.exe
REM               backend  <install>\resources\app.asar.unpacked\backend
REM
REM   checkout    <repo>\zcode.cmd
REM               python   <repo>\backend\venv\Scripts\python.exe
REM               backend  <repo>\backend
REM
REM The layout is decided by looking for the backend, not by a flag somebody
REM has to set - the same way electron\backend\backendLauncher.js resolves its
REM interpreter, and in the same order: ZARAM_PYTHON first, then the bundled
REM runtime, then a development venv.
REM
REM **PATH is deliberately not a fallback.** Finding some other Python is worse
REM than finding none: it will not have Zaram's dependencies, and the failure
REM arrives later wearing the costume of a broken product. That reasoning is
REM backendLauncher.js's, quoted here so the two cannot drift apart silently.
REM
REM The data directory needs no argument. `core.paths.is_packaged()` reads
REM sys.executable, and the bundled interpreter lives under `resources`, so an
REM installed ZCode resolves to %APPDATA%\Zaram - the same Spine the app uses.
setlocal

set "ZCODE_ROOT=%~dp0"

if exist "%ZCODE_ROOT%resources\app.asar.unpacked\backend\cli.py" (
  set "ZCODE_HOME=%ZCODE_ROOT%resources\app.asar.unpacked\backend"
  set "ZCODE_DEFAULT_PY=%ZCODE_ROOT%resources\runtime\python.exe"
) else (
  set "ZCODE_HOME=%ZCODE_ROOT%backend"
  set "ZCODE_DEFAULT_PY=%ZCODE_ROOT%backend\venv\Scripts\python.exe"
)

if defined ZARAM_PYTHON (
  set "ZCODE_PYTHON=%ZARAM_PYTHON%"
) else (
  set "ZCODE_PYTHON=%ZCODE_DEFAULT_PY%"
)

if not exist "%ZCODE_HOME%\cli.py" (
  echo zcode: Zaram's backend is not beside this script.>&2
  echo        Looked in "%ZCODE_HOME%".>&2
  exit /b 9009
)

if not exist "%ZCODE_PYTHON%" (
  echo zcode: Zaram's Python runtime is missing.>&2
  echo        Looked for "%ZCODE_PYTHON%".>&2
  echo        Set ZARAM_PYTHON to name an interpreter yourself.>&2
  exit /b 9009
)

pushd "%ZCODE_HOME%"
"%ZCODE_PYTHON%" -m cli %*
set "ZCODE_EXIT=%ERRORLEVEL%"
popd
exit /b %ZCODE_EXIT%
