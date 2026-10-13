# worker 자신의 .venv만 사용한다. TUI 가상환경으로 대체하지 않는다.
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\worker")
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "worker\.venv 가 없습니다. 기존 환경을 지우지 말고, 현재 Python으로 새 환경을 만든 뒤 worker 의존성을 설치해야 합니다."
    Write-Host "예: py -3.11 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -e `".[dev]`""
    exit 2
}

Push-Location $Root
try {
    & $Python -c "import sys; print(sys.executable); print(sys.version)"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "worker .venv의 기준 인터프리터를 실행하지 못했습니다. 이 환경을 정상으로 보지 않으며 TUI venv로 대체하지 않습니다."
        exit 2
    }
    & $Python -m pytest
    if ($null -eq $LASTEXITCODE) {
        exit 1
    }
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
