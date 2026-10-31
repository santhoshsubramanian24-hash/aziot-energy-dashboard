@echo off
title AZIOT Smart MCB Energy Dashboard
cd /d "%~dp0backend"

echo ========================================================
echo        AZIOT Smart MCB - Energy & Bill Analyzer
echo ========================================================
echo.

set "PY_EXE=%USERPROFILE%\tradingsetup\venv\Scripts\python.exe"
if not exist "%PY_EXE%" (
    set "PY_EXE=python"
)

echo Starting Server on port 5050...
start "" http://localhost:5050

"%PY_EXE%" -m uvicorn app:app --host 0.0.0.0 --port 5050
pause

