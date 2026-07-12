#Requires -Version 5
# dev_api.ps1 — terminal 1 of the cockpit dev-startup recipe (see README.md).
#
# Generates a multi_route_distinct submission and starts the MRE API over a
# persistent data root. Leave this running, then run dev_cockpit.ps1 in a
# second terminal. Run it from anywhere — it resolves the repo root from its
# own location.
$ErrorActionPreference = 'Stop'

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $repo

# The API's data root, the PowerShell way. The registry, run dirs and schedule
# documents live here; dev_cockpit.ps1 submits the dataset generated below.
$env:MRE_DATA_ROOT = './_data'

Write-Host "[dev_api] repo root:      $repo"
Write-Host "[dev_api] MRE_DATA_ROOT:  $env:MRE_DATA_ROOT"
Write-Host "[dev_api] generating multi_route_distinct submission -> _data/mrd"
python tools/generate_erp_dataset.py --scenario multi_route_distinct --out _data/mrd
if ($LASTEXITCODE -ne 0) { throw "dataset generation failed (exit $LASTEXITCODE)" }

Write-Host "[dev_api] starting API on http://localhost:8000  (leave this running)"
Write-Host "[dev_api] then run dev_cockpit.ps1 in another terminal"
python -m uvicorn mre.api.app:create_app --factory --app-dir src --port 8000
