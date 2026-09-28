$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Show-ErrorAndExit($message) {
    Write-Host "[Anubis] $message" -ForegroundColor Red
    exit 1
}

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Show-ErrorAndExit "Python 3 was not found on PATH. Install Python 3.10+ from https://www.python.org/downloads/windows/"
    }
    $pythonCommand = "python"
} else {
    $pythonCommand = "py"
}

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "[Anubis] Creating virtual environment ..."
    & $pythonCommand -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Show-ErrorAndExit "Failed to create the virtual environment."
    }

    Write-Host "[Anubis] Installing dependencies ..."
    & ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        Show-ErrorAndExit "Failed to upgrade pip."
    }

    & ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Show-ErrorAndExit "Dependency installation failed. Review the error output above and try again."
    }
}

if ((Test-Path ".env.example") -and (-not (Test-Path ".env"))) {
    Copy-Item ".env.example" ".env"
    Write-Host "[Anubis] Created .env from .env.example. Update it with your API keys if needed."
}

Write-Host "[Anubis] Starting Anubis Forensics GUI..."
& ".\.venv\Scripts\python.exe" main.py
