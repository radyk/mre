#Requires -Version 5
# ci_local.ps1 -- reproduce the standing image-as-shipped CI gate LOCALLY.
#
# SOURCE OF TRUTH: .github/workflows/ci.yml (job `image-build-and-test`). This
# script mirrors that job's sequence EXACTLY so a developer can run the same
# green-on-the-shipped-image check before pushing -- the stale-install
# false-green lesson (docs/04 2026-07-21 Session 2.4b): the fast suite must run
# INSIDE a container built FROM the runtime image, not against the checkout.
#
#   1. build the runtime target (the shipped image, no test tooling)
#   2. build the test target (FROM runtime + dev deps + suites)
#   3. run the fast suite INSIDE the built test image
#   4. boot the runtime image and poll /health
#
# The `secret-scan` (gitleaks) job in ci.yml is a SEPARATE concern and is NOT
# reproduced here (run gitleaks directly if needed). Requires a running Docker
# engine. Run it from anywhere -- it resolves the repo root from its own location.
param(
    # Skip the two image builds and reuse existing tags (fast re-run of the
    # in-container suite + health check only).
    [switch]$NoBuild
)
$ErrorActionPreference = 'Stop'

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $repo

$RUNTIME_TAG = 'mre-api:ci-local'
$TEST_TAG    = 'mre-api:citest-local'
$HEALTH_NAME = 'mre_ci_local_health'

function Invoke-Step([string]$label, [scriptblock]$body) {
    Write-Host "[ci_local] $label" -ForegroundColor Cyan
    & $body
    if ($LASTEXITCODE -ne 0) { throw "$label FAILED (exit $LASTEXITCODE)" }
}

# Preflight: Docker must be reachable (mirrors the CI runner having an engine).
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker engine not reachable - start Docker Desktop and retry." }

Write-Host "[ci_local] repo root: $repo"

if (-not $NoBuild) {
    # 1. runtime target (as shipped -- must build on its own, no test tooling).
    Invoke-Step "build runtime image ($RUNTIME_TAG, target=runtime)" {
        docker build --target runtime -t $RUNTIME_TAG $repo
    }
    # 2. test target -- FROM runtime, so `import mre` resolves to the SHIPPED venv.
    Invoke-Step "build test image ($TEST_TAG, target=test)" {
        docker build --target test -t $TEST_TAG $repo
    }
} else {
    Write-Host "[ci_local] -NoBuild: reusing existing $RUNTIME_TAG / $TEST_TAG"
}

# 3. run the fast suite INSIDE the built image (the image as shipped).
Invoke-Step "run fast suite inside the built test image" {
    docker run --rm $TEST_TAG pytest -q -m "not slow"
}

# 4. smoke the runtime image /health -- boot it, poll, then always clean up.
Write-Host "[ci_local] smoke the runtime image /health" -ForegroundColor Cyan
docker rm -f $HEALTH_NAME *> $null
docker run -d --name $HEALTH_NAME -p 8000:8000 $RUNTIME_TAG | Out-Null
$ok = $false
try {
    foreach ($i in 1..30) {
        try {
            $resp = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 `
                        -Uri 'http://localhost:8000/health'
            if ($resp.StatusCode -eq 200) {
                Write-Host "[ci_local] /health -> $($resp.Content)"
                $ok = $true; break
            }
        } catch { Start-Sleep -Seconds 2 }
    }
    if (-not $ok) { docker logs $HEALTH_NAME }
} finally {
    docker rm -f $HEALTH_NAME *> $null
}
if (-not $ok) { throw "runtime image /health never responded 200" }

Write-Host "[ci_local] ALL GREEN - image builds, fast suite passes in-container, /health OK." -ForegroundColor Green
