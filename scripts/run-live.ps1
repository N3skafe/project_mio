# LIVE 스택을 한 번에 띄운다. 사용자 입력을 셸 문자열로 실행하지 않는다.
param(
    [switch]$WithTui,
    [int]$TimeoutSeconds = 240
)

$ErrorActionPreference = "Stop"
if (Test-Path variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$ComposeFile = Join-Path $Root "infra\docker-compose.yml"
$HealthUrl = "http://127.0.0.1:8080/api/v1/health"

function Fail([string]$Message) {
    Write-Host $Message
    exit 1
}

if (-not (Test-Path -LiteralPath $ComposeFile)) {
    Fail "Compose 파일이 없습니다: $ComposeFile"
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fail "docker 명령이 없습니다. Docker를 설치한 뒤 .\scripts\doctor-live.ps1 로 다시 확인하세요. 스택은 시작하지 않았습니다."
}
& docker compose version | Out-Null
if ($LASTEXITCODE -ne 0) {
    Fail "docker compose 플러그인을 실행하지 못했습니다. 스택은 시작하지 않았습니다."
}
& docker info --format "{{.ServerVersion}}" | Out-Null
if ($LASTEXITCODE -ne 0) {
    Fail "Docker 데몬에 연결하지 못했습니다. Docker Desktop이 실행 중인지 확인하세요. 스택은 시작하지 않았습니다."
}

Write-Host "postgres, backend, worker, trainer 를 빌드하고 백그라운드로 시작합니다."
Write-Host "파일: $ComposeFile"
& docker compose -f $ComposeFile up --build -d
if ($LASTEXITCODE -ne 0) {
    Fail "docker compose up 이 실패했습니다. 5432 또는 8080 점유, 이미지 빌드, postgres/backend/worker/trainer 중 하나를 .\scripts\doctor-live.ps1 과 docker compose logs 로 확인하세요."
}

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$health = $null
Write-Host "health 를 기다립니다. 제한 시간은 ${TimeoutSeconds}초입니다."
while ((Get-Date) -lt $deadline) {
    try {
        $health = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 5
    } catch {
        $health = $null
        Write-Host "아직 health 에 연결하지 못했습니다. postgres 또는 backend 가 준비 중일 수 있습니다."
        Start-Sleep -Seconds 5
        continue
    }
    $database = [string]$health.database
    $worker = [string]$health.worker
    $trainer = [string]$health.trainer
    Write-Host "health: database=$database worker=$worker trainer=$trainer"
    if ($database -eq "UP" -and $worker -eq "CONNECTED" -and $trainer -eq "CONNECTED") {
        break
    }
    if ($database -ne "UP") {
        Write-Host "database 가 아직 UP 이 아닙니다. postgres 를 기다립니다."
    } elseif ($worker -ne "CONNECTED") {
        Write-Host "worker heartbeat 를 기다립니다. 백엔드만 준비된 상태입니다."
    } elseif ($trainer -ne "CONNECTED") {
        Write-Host "trainer heartbeat 를 기다립니다. worker 는 연결되었습니다."
    }
    Start-Sleep -Seconds 5
}

if ($null -eq $health -or [string]$health.database -ne "UP" -or [string]$health.worker -ne "CONNECTED" -or [string]$health.trainer -ne "CONNECTED") {
    Write-Host "제한 시간 안에 풀스택이 준비되지 않았습니다."
    if ($null -eq $health) {
        Write-Host "문제: backend health ($HealthUrl) 가 응답하지 않았습니다. postgres 또는 backend 포트 8080 을 확인하세요."
    } else {
        Write-Host "마지막 health: database=$($health.database) worker=$($health.worker) trainer=$($health.trainer)"
        if ([string]$health.database -ne "UP") {
            Write-Host "문제 서비스: postgres. database 가 UP 이 아닙니다."
        }
        if ([string]$health.worker -ne "CONNECTED") {
            Write-Host "문제 서비스: worker. heartbeat 가 없습니다. 컨테이너는 떠 있어도 API 는 NOT_CONNECTED 입니다."
        }
        if ([string]$health.trainer -ne "CONNECTED") {
            Write-Host "문제 서비스: trainer. heartbeat 가 없습니다. 컨테이너는 떠 있어도 API 는 NOT_CONNECTED 입니다."
        }
    }
    & docker compose -f $ComposeFile ps
    exit 1
}

Write-Host ""
Write-Host "LIVE 스택이 준비되었습니다."
Write-Host "health: database=$($health.database) worker=$($health.worker) trainer=$($health.trainer)"
Write-Host "백엔드: $HealthUrl"
Write-Host ""
Write-Host "다음 명령"
Write-Host '  $env:MAIDOPS_MODE = "LIVE"'
Write-Host '  $env:MAIDOPS_BACKEND_URL = "http://127.0.0.1:8080"'
Write-Host "  .\scripts\run-tui.ps1"
Write-Host "TUI 안에서 샘플 1건:"
Write-Host "  /project list"
Write-Host "  /project select trusted-sample"
Write-Host "  /test"
Write-Host "또는 실행 없이 로그 1건:"
Write-Host "  /import-log trusted-sample Connection to localhost:5432 refused"
Write-Host "중지: .\scripts\stop-live.ps1"
Write-Host "볼륨은 유지됩니다. 볼륨까지 지우려면 .\scripts\stop-live.ps1 -Volumes"

if ($WithTui) {
    $venvPython = Join-Path $Root "tui\.venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $venvPython)) {
        Fail "TUI 가상환경이 없습니다. 스택은 띄운 상태입니다. README의 DEMO 설치 뒤 .\scripts\run-tui.ps1 을 실행하세요."
    }
    $env:MAIDOPS_MODE = "LIVE"
    $env:MAIDOPS_BACKEND_URL = "http://127.0.0.1:8080"
    Write-Host "TUI LIVE 를 시작합니다."
    & (Join-Path $PSScriptRoot "run-tui.ps1")
    exit $LASTEXITCODE
}
