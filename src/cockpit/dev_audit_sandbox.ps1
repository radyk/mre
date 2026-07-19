#Requires -Version 5
# dev_audit_sandbox.ps1 - make a throwaway, gitignored copy of the committed
# glass_box dataset for sabotage work, so the committed set is NEVER dirtied.
#
# The sabotage menu says "work on a copy"; this is the mechanism that makes that
# true. Copy once, then serve or gate the COPY:
#
#   .\src\cockpit\dev_audit_sandbox.ps1
#   .\src\cockpit\dev_api.ps1 -DatasetPath _sandbox\glass_box_audit   # cockpit
#   python -m mre.gate _sandbox\glass_box_audit                       # terminal
#
# Edit the CSVs under _sandbox\glass_box_audit\ per SABOTAGE_MENU.md; the tracked
# datasets/glass_box stays clean, so test_glass_box stays green throughout.
# Run it from anywhere - it resolves the repo root from its own location.
param(
    # The sandbox copy's name under _sandbox/ (keep several audits side by side).
    [string]$Name = 'glass_box_audit',
    # Overwrite an existing sandbox of this name (you will lose its edits).
    [switch]$Force
)
$ErrorActionPreference = 'Stop'

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$src = Join-Path $repo 'datasets\glass_box'
$dst = Join-Path $repo "_sandbox\$Name"

if (-not (Test-Path $src)) { throw "glass_box dataset not found at $src" }
if (Test-Path $dst) {
    if (-not $Force) {
        throw "sandbox already exists: _sandbox\$Name - pass -Force to overwrite (you will lose its sabotage edits)"
    }
    Remove-Item -Recurse -Force $dst
}
New-Item -ItemType Directory -Force -Path $dst | Out-Null
# Copy the whole folder (CSVs + manifest + cost_model AND the companion .md docs)
# so the menu/walkthrough sit next to the editable files. dev_api.ps1 serves only
# the .csv/.json; the docs are just for reference.
Copy-Item -Path (Join-Path $src '*') -Destination $dst -Recurse

Write-Host "[audit] sandbox ready: _sandbox\$Name  (gitignored - safe to sabotage)"
Write-Host "[audit] edit the CSVs there per SABOTAGE_MENU.md, then:"
Write-Host "[audit]   cockpit:  .\src\cockpit\dev_api.ps1 -DatasetPath _sandbox\$Name"
Write-Host "[audit]   terminal: python -m mre.gate _sandbox\$Name"
Write-Host "[audit] the committed datasets/glass_box stays clean throughout."
