$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\backend")
$Jdk21 = "C:\Program Files\Java\jdk-21"
if (Test-Path $Jdk21) {
    $env:JAVA_HOME = $Jdk21
    $env:Path = "$env:JAVA_HOME\bin;" + $env:Path
}
Push-Location $Root
try {
    & .\mvnw.cmd -B test
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
