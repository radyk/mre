#Requires -Version 5
# dev_cockpit.ps1 — terminal 2 of the cockpit dev-startup recipe (see README.md).
#
# Submits + solves a multi_route_distinct schedule (sync + deterministic), builds
# its priced forced-alternative ghosts, prints the cockpit URL, then runs the Vite
# dev server proxied at the API. Requires dev_api.ps1 to be running first. Run it
# from anywhere — it resolves the repo root from its own location.
param(
    # Reuse the schedule from the previous run (cached in _data/.last_schedule)
    # and skip the submit → solve → alternatives steps — a fast restart of just
    # the Vite dev server against an already-solved board. Falls back to a full
    # run if no cached schedule exists or it is no longer reachable.
    [switch]$Resume
)
$ErrorActionPreference = 'Stop'

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$api  = if ($env:MRE_API) { $env:MRE_API } else { 'http://localhost:8000' }
$json = 'application/json'
$lastFile = Join-Path $repo '_data\.last_schedule'

# JSON bodies are built as hashtables piped through ConvertTo-Json so PowerShell
# handles the quoting (and, for the Windows submission path, the backslashes)
# rather than us. Invoke-RestMethod auto-parses the {api_version, data} envelope.

try {
    Invoke-RestMethod -Uri "$api/health" -TimeoutSec 5 | Out-Null
} catch {
    throw "API not reachable at $api - start dev_api.ps1 in another terminal first."
}

# -Resume: reuse the last solved schedule (cached below) and skip the slow
# submit → solve → alternatives steps, as long as it is still reachable.
$sch = $null
if ($Resume -and (Test-Path $lastFile)) {
    $cached = (Get-Content $lastFile -Raw).Trim()
    try {
        Invoke-RestMethod -Uri "$api/schedules/$cached/meta" -TimeoutSec 5 | Out-Null
        $sch = $cached
        Write-Host "[dev_cockpit] -Resume: reusing schedule_id=$sch (skipping submit/solve/alternatives)"
    } catch {
        Write-Host "[dev_cockpit] -Resume: cached schedule $cached not reachable - running a full solve"
    }
}

if (-not $sch) {
    $subDir = (Join-Path $repo '_data\mrd')
    if (-not (Test-Path $subDir)) { throw "submission not found at $subDir - run dev_api.ps1 first." }

    Write-Host "[dev_cockpit] submitting $subDir"
    $sub = (Invoke-RestMethod -Method Post -Uri "$api/submissions" -ContentType $json -Body (@{ path = $subDir } | ConvertTo-Json)).data.submission_id
    Write-Host "[dev_cockpit] submission_id=$sub"

    Write-Host "[dev_cockpit] solving (sync, deterministic) - this may take a moment..."
    $run = (Invoke-RestMethod -Method Post -Uri "$api/submissions/$sub/solve" -ContentType $json -Body (@{ sync = $true; deterministic = $true } | ConvertTo-Json) -TimeoutSec 180).data.run_id
    $sch = (Invoke-RestMethod -Uri "$api/runs/$run").data.result.schedule_id
    Write-Host "[dev_cockpit] schedule_id=$sch"

    # budget=8 (over the service default of 4) so the lively busy_board fixture
    # surfaces a full set of priced roads-not-taken for the cockpit to render.
    Write-Host "[dev_cockpit] building forced-alternative ghosts (the priced roads not taken)"
    Invoke-RestMethod -Method Post -Uri "$api/schedules/$sch/alternatives" -ContentType $json -Body (@{ sync = $true; budget = 8 } | ConvertTo-Json) -TimeoutSec 300 | Out-Null

    # Cache the schedule id so a later -Resume can skip straight to Vite.
    Set-Content -Path $lastFile -Value $sch -Encoding UTF8
}

Write-Host ""
Write-Host "  cockpit URL:  http://localhost:5175/?schedule=$sch"
Write-Host ""

# Run the Vite dev server, proxying the API (dev build => the CU6 feel tuning
# panel mounts; it is stripped from `npm run build`).
$env:MRE_API = $api
Set-Location (Join-Path $repo 'src\cockpit')
if (-not (Test-Path 'node_modules')) {
    Write-Host "[dev_cockpit] installing npm deps (first run)"
    npm install
}
Write-Host "[dev_cockpit] starting Vite dev server (proxy -> $api)"
npm run dev
