#Requires -Version 5
# dev_api.ps1 — terminal 1 of the cockpit dev-startup recipe (see README.md).
#
# Generates a submission (the busy_board FEEL fixture by default) and starts the
# MRE API over a persistent data root. Leave this running, then run
# dev_cockpit.ps1 in a second terminal. Run it from anywhere — it resolves the
# repo root from its own location.
param(
    # Generator scenario for the dev submission. Defaults to busy_board — the
    # lively, multi-eligible, loaded FEEL fixture built for gesture-surface
    # feel-iteration. Pass any generator scenario, e.g.
    #   .\src\cockpit\dev_api.ps1 -Scenario multi_route_distinct
    [string]$Scenario = 'busy_board'
)
$ErrorActionPreference = 'Stop'

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $repo

# .env.local (repo root, gitignored) — the dev secret/config file. KEY=VALUE
# per line, '#' comments and blank lines ignored, surrounding quotes stripped.
# This is where ANTHROPIC_API_KEY lives so the DEV cockpit's fail-closed LLM
# renderer has a key without exporting it by hand. Existing environment wins
# (an already-set var is never overwritten).
$envLocal = Join-Path $repo '.env.local'
if (Test-Path $envLocal) {
    Write-Host "[dev_api] loading .env.local"
    foreach ($line in Get-Content $envLocal) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith('#') -or ($t -notmatch '=')) { continue }
        $k, $v = $t.Split('=', 2)
        $k = $k.Trim(); $v = $v.Trim().Trim('"').Trim("'")
        if ($k -and -not [Environment]::GetEnvironmentVariable($k, 'Process')) {
            Set-Item -Path "env:$k" -Value $v
        }
    }
}

# The API's data root, the PowerShell way. The registry, run dirs and schedule
# documents live here; dev_cockpit.ps1 submits the dataset generated below.
$env:MRE_DATA_ROOT = './_data'

# Dev default: MRE_DEV on unless already set. It gates the dev-only surfaces
# (the /ledger/refusals route, the fail-closed LLM renderer wiring) that the
# production build never exposes. Override with $env:MRE_DEV='' before running.
if ($null -eq [Environment]::GetEnvironmentVariable('MRE_DEV', 'Process')) {
    $env:MRE_DEV = '1'
}

Write-Host "[dev_api] repo root:      $repo"
Write-Host "[dev_api] MRE_DATA_ROOT:  $env:MRE_DATA_ROOT"
Write-Host "[dev_api] MRE_DEV:        $env:MRE_DEV"
Write-Host "[dev_api] generating $Scenario submission -> _data/mrd"
python tools/generate_erp_dataset.py --scenario $Scenario --out _data/mrd
if ($LASTEXITCODE -ne 0) { throw "dataset generation failed (exit $LASTEXITCODE)" }

Write-Host "[dev_api] starting API on http://localhost:8000  (leave this running)"
Write-Host "[dev_api] then run dev_cockpit.ps1 in another terminal"
python -m uvicorn mre.api.app:create_app --factory --app-dir src --port 8000
