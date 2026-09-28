@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo [Anubis] Python 3 was not found on PATH. Please install Python 3.10+ from https://www.python.org/downloads/windows/
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [Anubis] Creating virtual environment ...
    py -3 -m venv .venv || python -m venv .venv
    if errorlevel 1 (
        echo [Anubis] Failed to create a virtual environment.
        exit /b 1
    )

    echo [Anubis] Installing dependencies ...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    if errorlevel 1 (
        echo [Anubis] Failed to upgrade pip.
        exit /b 1
    )

    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [Anubis] Dependency installation failed. Review the error output above and try again.
        exit /b 1
    )
)

if exist ".env.example" if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo [Anubis] Created .env from .env.example. Update it with your API keys if needed.
)

echo [Anubis] Starting Anubis Forensics GUI...
".venv\Scripts\python.exe" main.py
