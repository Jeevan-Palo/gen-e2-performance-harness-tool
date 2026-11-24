# One-time setup for Windows: creates .venv, installs requirements.txt, runs the doctor.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
if (-not (Test-Path .venv)) { & $py -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
& .\.venv\Scripts\python.exe -m pip install --quiet -r requirements.txt
& .\.venv\Scripts\python.exe tools\doctor.py
Write-Host ""
Write-Host "Done. In VS Code choose the interpreter .venv\Scripts\python.exe, open Copilot Chat in Agent mode and type /run-end-to-end."
