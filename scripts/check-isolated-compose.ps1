# 격리 Compose 설정을 렌더링만 한다. pull, build, up, down 은 호출하지 않는다.
$ErrorActionPreference = "Stop"
$ComposeFile = Resolve-Path (Join-Path $PSScriptRoot "..\infra\isolated\docker-compose.yml")
$IsolatedRoot = Resolve-Path (Join-Path $PSScriptRoot "..\infra\isolated")
$ProjectName = "maidops-isolated"

if ($args -match '^(up|down|pull|build|start|stop|restart)$') {
    Write-Host "이 스크립트는 스택을 시작하거나 내리지 않습니다."
    exit 2
}

$raw = Get-Content -LiteralPath $ComposeFile -Raw
if ($raw -match '(?m)^\s*container_name\s*:') {
    Write-Host "격리 설정에 container_name 이 있습니다. 기존 컨테이너와 이름이 겹칠 수 있어 중단합니다."
    exit 2
}
if ($raw -match '(?m)^\s*external\s*:\s*true\s*$') {
    Write-Host "격리 설정이 external volume 을 사용합니다. 기존 볼륨과 분리되지 않아 중단합니다."
    exit 2
}

$configArgs = @(
    "compose",
    "--project-name", $ProjectName,
    "-f", $ComposeFile,
    "config",
    "--format", "json"
)
$rendered = & docker @configArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "docker compose config 가 실패했습니다. 스택은 시작하지 않았습니다."
    exit $(if ($null -eq $LASTEXITCODE) { 1 } else { $LASTEXITCODE })
}

$document = $rendered | ConvertFrom-Json
$failures = New-Object System.Collections.Generic.List[string]
if ($document.name -and $document.name -ne $ProjectName) {
    $failures.Add("project name 이 $ProjectName 이 아닙니다: $($document.name)")
}

$allowedPublished = @{ "55432" = $true; "18080" = $true }
foreach ($serviceProp in $document.services.PSObject.Properties) {
    $service = $serviceProp.Value
    $serviceName = $serviceProp.Name
    if ($service.container_name) {
        $failures.Add("$serviceName 에 container_name 이 있습니다.")
    }
    foreach ($port in @($service.ports)) {
        if (-not $port) { continue }
        $published = [string]$port.published
        $hostIp = [string]$port.host_ip
        if (-not $allowedPublished.ContainsKey($published)) {
            $failures.Add("$serviceName 호스트 포트 $published 는 55432 또는 18080 이 아닙니다.")
        }
        if ($published -eq "5432" -or $published -eq "8080") {
            $failures.Add("$serviceName 이 기존 호스트 포트 $published 를 엽니다.")
        }
        if ($hostIp -ne "127.0.0.1") {
            $failures.Add("$serviceName 호스트 주소가 127.0.0.1 이 아닙니다: $hostIp")
        }
    }
    $environment = $service.environment
    if ($environment) {
        foreach ($envProp in $environment.PSObject.Properties) {
            $value = [string]$envProp.Value
            if ($value -match '127\.0\.0\.1:(5432|8080)\b') {
                $failures.Add("$serviceName $($envProp.Name) 이 기존 호스트 포트를 가리킵니다.")
            }
        }
    }
    foreach ($volume in @($service.volumes)) {
        if (-not $volume) { continue }
        if ($volume.type -eq "bind") {
            $source = [string]$volume.source
            $full = [System.IO.Path]::GetFullPath($source)
            $root = $IsolatedRoot.Path.TrimEnd('\')
            $prefix = $root + '\'
            $inside = $full.Equals($root, [System.StringComparison]::OrdinalIgnoreCase) -or
                $full.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)
            if (-not $inside) {
                $failures.Add("$serviceName bind mount 가 격리 디렉터리 밖입니다: $full")
            }
        }
    }
}

foreach ($volumeProp in $document.volumes.PSObject.Properties) {
    $volume = $volumeProp.Value
    if ($volume.external -eq $true) {
        $failures.Add("volume $($volumeProp.Name) 이 external 입니다.")
    }
    $volumeName = [string]$volume.name
    if ($volumeName -notlike "$ProjectName*") {
        $failures.Add("volume $($volumeProp.Name) 이 격리 프로젝트 이름이 아닙니다: $volumeName")
    }
    if ($volumeName -eq "maidops-models" -or $volumeName -eq "maidops_maidops-models") {
        $failures.Add("기존 모델 볼륨 이름과 같습니다: $volumeName")
    }
}

function Hide-Secrets([string]$Text) {
    return [regex]::Replace(
        $Text,
        '(?i)(PASSWORD"\s*:\s*")([^"]*)(")',
        '${1}[REDACTED]${3}'
    )
}

$renderedText = $rendered | Out-String
if ($failures.Count -gt 0) {
    foreach ($failure in $failures) {
        Write-Host $failure
    }
    Write-Host (Hide-Secrets $renderedText)
    exit 2
}

Write-Host "격리 Compose config 확인: project=$ProjectName postgres=127.0.0.1:55432 api=127.0.0.1:18080"
Write-Host "pull, build, up, down 은 실행하지 않았습니다."
exit 0
