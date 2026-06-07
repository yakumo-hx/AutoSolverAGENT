$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
python backend/demo_runner.py --case data/sample_case.tsv --out demo/trace.generated.json

