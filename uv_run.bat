@echo off
setlocal enabledelayedexpansion

rem Load variables from .env
for /f "usebackq tokens=1,2 delims==" %%a in (".env") do (
    set %%a=%%b
)

rem Default PORT if not set
if "%PORT%"=="" set PORT=8000


cd app
uv run uvicorn main:app --host 127.0.0.1 --port %PORT% --reload