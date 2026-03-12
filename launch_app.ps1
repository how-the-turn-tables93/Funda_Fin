$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$pythonCmd = $null

if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py -3"
} elseif (Test-Path "C:\Users\aksha\AppData\Local\Programs\Python\Python313\python.exe") {
    $pythonCmd = "C:\Users\aksha\AppData\Local\Programs\Python\Python313\python.exe"
}

if (-not $pythonCmd) {
    Write-Host "Could not find Python. Please install Python or add it to PATH." -ForegroundColor Red
    exit 1
}

Write-Host "Starting CAS Mutual Fund Analyzer..." -ForegroundColor Cyan

try {
    Invoke-Expression "$pythonCmd -m streamlit run .\streamlit_app.py"
} catch {
    Write-Host "Streamlit launch failed. Installing required packages and retrying..." -ForegroundColor Yellow
    Invoke-Expression "$pythonCmd -m pip install -r .\requirements.txt"
    Invoke-Expression "$pythonCmd -m streamlit run .\streamlit_app.py"
}
