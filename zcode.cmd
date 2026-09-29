@echo off
REM ZCode - the Spine from a terminal.
REM
REM Finds the bundled interpreter, changes to backend\, runs -m cli.
REM Put this folder on PATH and `zcode recall "..."` works anywhere.
setlocal
set "ZCODE_HOME=%~dp0backend"
set "ZCODE_PYTHON=%ZCODE_HOME%\venv\Scripts\python.exe"
if not exist "%ZCODE_PYTHON%" set "ZCODE_PYTHON=python"
pushd "%ZCODE_HOME%"
"%ZCODE_PYTHON%" -m cli %*
set "ZCODE_EXIT=%ERRORLEVEL%"
popd
exit /b %ZCODE_EXIT%
