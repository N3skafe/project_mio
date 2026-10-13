# JDK 21을 고른 뒤 Maven Wrapper로 백엔드 테스트를 실행한다.
# JAVA_HOME과 PATH는 이 프로세스에서만 바꾸고, 끝나면 되돌린다.
param(
    [string]$JavaHome,
    [switch]$ResolveOnly
)

$ErrorActionPreference = "Stop"
if (Test-Path variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\backend")
$SavedJavaHome = $env:JAVA_HOME
$SavedPath = $env:Path
$ExitCode = 0

function Get-ToolMajor([string]$Executable) {
    $output = cmd /c "`"$Executable`" -version 2>&1" | Out-String
    if ($output -match 'version "(?<major>\d+)') {
        $major = [int]$Matches.major
        if ($major -eq 1 -and $output -match 'version "1\.(?<legacy>\d+)') {
            return [int]$Matches.legacy
        }
        return $major
    }
    if ($output -match '(?m)^javac\s+(?<major>\d+)') {
        return [int]$Matches.major
    }
    return 0
}

function Test-Jdk21([string]$JdkRoot) {
    if ([string]::IsNullOrWhiteSpace($JdkRoot) -or -not (Test-Path -LiteralPath $JdkRoot)) {
        return $false
    }
    $java = Join-Path $JdkRoot "bin\java.exe"
    $javac = Join-Path $JdkRoot "bin\javac.exe"
    if (-not (Test-Path -LiteralPath $java) -or -not (Test-Path -LiteralPath $javac)) {
        return $false
    }
    return (Get-ToolMajor $java) -eq 21 -and (Get-ToolMajor $javac) -eq 21
}

function Get-JdkCandidates {
    $candidates = New-Object System.Collections.Generic.List[string]
    if (-not [string]::IsNullOrWhiteSpace($env:JAVA_HOME)) {
        $candidates.Add($env:JAVA_HOME)
    }
    $javaCommand = Get-Command java.exe -ErrorAction SilentlyContinue
    $javacCommand = Get-Command javac.exe -ErrorAction SilentlyContinue
    if ($javaCommand -and $javacCommand) {
        $javaBin = Split-Path -Parent $javaCommand.Source
        $javacBin = Split-Path -Parent $javacCommand.Source
        if ($javaBin -eq $javacBin) {
            $candidates.Add((Resolve-Path (Join-Path $javaBin "..")).Path)
        }
    }
    $scanRoots = @(
        (Join-Path $env:ProgramFiles "Java"),
        (Join-Path ${env:ProgramFiles(x86)} "Java"),
        (Join-Path $env:ProgramFiles "Eclipse Adoptium"),
        (Join-Path $env:ProgramFiles "Microsoft")
    )
    foreach ($scanRoot in $scanRoots) {
        if ([string]::IsNullOrWhiteSpace($scanRoot) -or -not (Test-Path -LiteralPath $scanRoot)) {
            continue
        }
        Get-ChildItem -LiteralPath $scanRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object {
            $candidates.Add($_.FullName)
        }
    }
    return $candidates
}

function Resolve-Jdk21 {
    if (-not [string]::IsNullOrWhiteSpace($JavaHome)) {
        if (Test-Jdk21 $JavaHome) {
            return (Resolve-Path -LiteralPath $JavaHome).Path
        }
        throw "지정한 JavaHome이 JDK 21이 아닙니다: $JavaHome"
    }
    $seen = @{}
    foreach ($candidate in Get-JdkCandidates) {
        if ([string]::IsNullOrWhiteSpace($candidate) -or $seen.ContainsKey($candidate)) {
            continue
        }
        $seen[$candidate] = $true
        if (Test-Jdk21 $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    throw "java와 javac가 모두 21인 JDK를 JavaHome, JAVA_HOME, PATH, Program Files에서 찾지 못했습니다."
}

try {
    $resolved = Resolve-Jdk21
    Write-Host "JDK 21: $resolved"
    if ($ResolveOnly) {
        $ExitCode = 0
    } else {
        $env:JAVA_HOME = $resolved
        $env:Path = "$(Join-Path $resolved "bin");$SavedPath"
        Push-Location $Root
        try {
            & .\mvnw.cmd -B test
            if ($null -eq $LASTEXITCODE) {
                $ExitCode = 1
            } else {
                $ExitCode = $LASTEXITCODE
            }
        } finally {
            Pop-Location
        }
    }
} catch {
    Write-Host $_.Exception.Message
    $ExitCode = 2
} finally {
    if ($null -eq $SavedJavaHome) {
        Remove-Item Env:JAVA_HOME -ErrorAction SilentlyContinue
    } else {
        $env:JAVA_HOME = $SavedJavaHome
    }
    $env:Path = $SavedPath
    Write-Host "복원 JAVA_HOME=$($env:JAVA_HOME)"
}

exit $ExitCode
