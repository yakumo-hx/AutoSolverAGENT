$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not $env:DEEPSEEK_API_KEY) {
  Write-Host "DEEPSEEK_API_KEY is not set. Workbench will run in mock mode."
}

Write-Host "Open http://localhost:8027/frontend/index.html"
python backend/web_server.py
