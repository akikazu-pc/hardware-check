$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$project = Join-Path $root 'tests/AkikazuHardwareCheck.App.SmokeTests/AkikazuHardwareCheck.App.SmokeTests.csproj'
$runner = Join-Path $root 'tests/AkikazuHardwareCheck.App.SmokeTests/bin/Release/net10.0-windows/win-x64/AkikazuHardwareCheck.App.SmokeTests.exe'

dotnet build $project -c Release -p:DistributionChannel=Store --nologo
if ($LASTEXITCODE -ne 0) {
    throw "Store smoke build failed with exit code $LASTEXITCODE"
}

& $runner
if ($LASTEXITCODE -ne 0) {
    throw "Store smoke tests failed with exit code $LASTEXITCODE"
}
