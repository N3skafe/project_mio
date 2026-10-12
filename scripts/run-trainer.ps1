$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $Root "trainer\.venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "가상환경이 없습니다. trainer\README.md의 설치 명령을 먼저 실행하세요."
}
$env:MAIDOPS_CODE_ROOT = $Root
if (-not $env:MAIDOPS_MODEL_DIR) {
    $env:MAIDOPS_MODEL_DIR = Join-Path $Root "data\models"
}
if (-not $env:MAIDOPS_BACKEND_URL) {
    $env:MAIDOPS_BACKEND_URL = "http://127.0.0.1:8080"
}
if (-not $env:MAIDOPS_TRAIN_DEVICE) {
    $env:MAIDOPS_TRAIN_DEVICE = "auto"
}
& $Python -m maidops_trainer
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
