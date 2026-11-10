# LIVE 사전 점검. 프로세스를 종료하거나 스택을 띄우지 않는다.
$ErrorActionPreference = "Stop"
if (Test-Path variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Failures = New-Object System.Collections.Generic.List[string]

function Write-Check([string]$State, [string]$Message) {
    Write-Host "[$State] $Message"
    if ($State -eq "실패") {
        $script:Failures.Add($Message)
    }
}

function Test-ListenPort([int]$Port) {
    try {
        $rows = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    } catch {
        Write-Check "안내" "127.0.0.1:${Port} 점유를 확인하지 못했습니다. 프로세스는 종료하지 않습니다."
        return
    }
    if ($rows.Count -eq 0) {
        Write-Check "통과" "127.0.0.1:${Port} 은 대기 중이 아닙니다."
        return
    }
    $owners = @()
    foreach ($row in $rows) {
        $name = "pid $($row.OwningProcess)"
        try {
            $proc = Get-Process -Id $row.OwningProcess -ErrorAction Stop
            $name = "$($proc.ProcessName) pid $($row.OwningProcess)"
        } catch {
            $name = "pid $($row.OwningProcess)"
        }
        $owners += $name
    }
    $unique = ($owners | Select-Object -Unique) -join ", "
    Write-Check "안내" "포트 ${Port} 이 이미 대기 중입니다: $unique. 프로세스는 종료하지 않습니다. Compose가 같은 포트를 열지 못하면 이 프로세스를 확인하세요."
}

Write-Host "MaidOps Lab LIVE 점검"
Write-Host "저장소: $Root"

$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    Write-Check "실패" "docker 명령이 없습니다. Docker Desktop 또는 Docker Engine을 설치한 뒤 다시 실행하세요."
} else {
    Write-Check "통과" "docker 명령: $($docker.Source)"
    & docker compose version | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Check "실패" "docker compose 플러그인을 실행하지 못했습니다."
    } else {
        Write-Check "통과" "docker compose 플러그인이 있습니다."
    }
    & docker info --format "{{.ServerVersion}}" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Check "실패" "Docker 데몬에 연결하지 못했습니다. Docker Desktop이 실행 중인지 확인하세요. 스택은 시작하지 않았습니다."
    } else {
        Write-Check "통과" "Docker 데몬에 연결했습니다."
    }
}

Test-ListenPort 5432
Test-ListenPort 8080

& py -3.11 -c "import sys; print(sys.version)"
if ($LASTEXITCODE -ne 0) {
    Write-Check "실패" "py -3.11 을 실행하지 못했습니다. DEMO와 LIVE TUI에는 Python 3.11이 필요합니다."
} else {
    Write-Check "통과" "py -3.11 을 실행했습니다."
}

$venvPython = Join-Path $Root "tui\.venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPython) {
    Write-Check "통과" "TUI 가상환경: $venvPython"
} else {
    Write-Check "실패" "tui\.venv 가 없습니다. README의 DEMO 설치를 tui 디렉터리에서 먼저 실행하세요."
}

$jdkHome = $env:JAVA_HOME
$jdkNote = "호스트에서 backend를 직접 실행할 때만 JDK 21이 필요합니다. Compose만 쓰면 이미지 안의 JDK를 사용합니다."
if ([string]::IsNullOrWhiteSpace($jdkHome)) {
    Write-Check "안내" "JAVA_HOME 이 비어 있습니다. $jdkNote"
} else {
    $javaExe = Join-Path $jdkHome "bin\java.exe"
    if (-not (Test-Path -LiteralPath $javaExe)) {
        Write-Check "안내" "JAVA_HOME=$jdkHome 에 java.exe 가 없습니다. $jdkNote"
    } else {
        $versionText = cmd /c "`"$javaExe`" -version 2>&1" | Out-String
        if ($versionText -match 'version "(?<major>\d+)') {
            $major = [int]$Matches.major
            if ($major -eq 21) {
                Write-Check "통과" "호스트 JDK 21: $jdkHome"
            } else {
                Write-Check "안내" "호스트 JAVA_HOME 은 JDK $major 입니다. Compose 기동에는 필수가 아닙니다. $jdkNote"
            }
        } else {
            Write-Check "안내" "JAVA_HOME 의 Java 버전을 읽지 못했습니다. $jdkNote"
        }
    }
}

$healthUrl = "http://127.0.0.1:8080/api/v1/health"
try {
    $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 5
    $database = [string]$health.database
    $worker = [string]$health.worker
    $trainer = [string]$health.trainer
    Write-Check "통과" "health 응답: database=$database worker=$worker trainer=$trainer authentication=$($health.authentication)"
    if ($database -ne "UP") {
        Write-Check "안내" "database 가 UP 이 아닙니다. postgres 컨테이너 또는 호스트의 5432 연결을 확인하세요."
    }
    if ($worker -eq "CONNECTED") {
        Write-Check "통과" "worker 는 최근 heartbeat 로 CONNECTED 입니다."
    } else {
        Write-Check "안내" "worker=NOT_CONNECTED. 백엔드만 켜 둔 경우에는 정상입니다. Compose 풀스택이면 worker 컨테이너와 heartbeat를 확인하세요."
    }
    if ($trainer -eq "CONNECTED") {
        Write-Check "통과" "trainer 는 최근 heartbeat 로 CONNECTED 입니다."
    } elseif ([string]::IsNullOrWhiteSpace($trainer)) {
        Write-Check "안내" "health 에 trainer 필드가 없습니다. 기동 중인 backend 가 이전 빌드일 수 있습니다."
    } else {
        Write-Check "안내" "trainer=NOT_CONNECTED. 백엔드만 켜 둔 경우에는 정상입니다. Compose 풀스택이면 trainer 컨테이너와 heartbeat를 확인하세요."
    }
    Write-Check "안내" "Compose healthcheck 는 컨테이너 안 alive 파일이고, 이 API 상태는 DB heartbeat 입니다."
} catch {
    Write-Check "안내" "health 에 연결하지 못했습니다 ($healthUrl). 스택이 아직 없으면 정상입니다. 기동은 .\scripts\run-live.ps1 입니다."
}

Write-Host ""
if ($Failures.Count -eq 0) {
    Write-Host "요약: 실패 0. 위 안내는 프로세스를 종료하지 않았습니다."
    exit 0
}
Write-Host "요약: 실패 $($Failures.Count)"
foreach ($item in $Failures) {
    Write-Host " - $item"
}
exit 1
