$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
Write-Host "Open http://localhost:8026/frontend/index.html"
python -m http.server 8026
