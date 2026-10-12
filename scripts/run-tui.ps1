$ErrorActionPreference = "Stop"
$Python = Join-Path $PSScriptRoot "..\tui\.venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "가상환경이 없습니다. README의 설치 명령을 tui 디렉터리에서 먼저 실행하세요."
}
& $Python -m maidops_tui
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
