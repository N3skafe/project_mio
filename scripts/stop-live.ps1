# LIVE Compose 를 내린다. 볼륨은 -Volumes 를 준 경우에만 삭제한다.
param(
    [switch]$Volumes
)

$ErrorActionPreference = "Stop"
if (Test-Path variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$ComposeFile = Join-Path $Root "infra\docker-compose.yml"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "docker 명령이 없습니다. 내릴 스택을 확인하지 못했습니다."
    exit 1
}

if ($Volumes) {
    Write-Host "요청한 -Volumes 로 컨테이너와 볼륨을 삭제합니다. 로컬 DB와 모델 볼륨이 지워집니다."
    & docker compose -f $ComposeFile down -v
} else {
    & docker compose -f $ComposeFile down
    Write-Host "스택을 내렸습니다. 볼륨은 유지했습니다."
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "docker compose down 이 실패했습니다. 파일: $ComposeFile"
    exit $LASTEXITCODE
}
