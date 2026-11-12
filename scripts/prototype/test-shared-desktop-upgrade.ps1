# Real different-version upgrade evidence for the shared desktop prototype. Builds two payloads with different
# assembly/file versions, installs them as different host versions, and checks the Run value migration.
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$script:RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$script:RegistryPath = 'HKCU:\Software\Akikazu\SharedDesktop'
$script:UninstallRoot = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall'
$script:RunKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$script:StartupValueName = 'AkikazuHardwareCheck'
$script:SettingsPath = Join-Path (Join-Path $env:LOCALAPPDATA 'AkikazuHardwareCheck') 'settings.json'
$script:Failures = @()
$script:Root = Join-Path $env:TEMP ('AkikazuSharedDesktopUpgrade-' + [guid]::NewGuid().ToString('N'))
$script:PayloadRoot = Join-Path $env:TEMP ('AkikazuSharedDesktopPayloads-' + [guid]::NewGuid().ToString('N'))
$script:SettingsBackup = $null
$script:SettingsExisted = $false
$script:SettingsWritten = $false
$script:RunBackup = $null
$script:RunExisted = $false
$script:RunCaptured = $false

function Check {
    param([bool]$Condition, [string]$Message)
    if ($Condition) {
        Write-Host "PASS $Message"
    } else {
        Write-Host "FAIL $Message" -ForegroundColor Red
        $script:Failures += $Message
    }
}

function Get-LanguageText {
    param([string]$Key)
    if ($null -eq $script:Language) {
        $path = Join-Path $script:RepoRoot 'src\AkikazuHardwareCheck.Core\Localization\zh-CN.json'
        $script:Language = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
    }

    return [string]$script:Language.$Key
}

function Get-TestProcesses {
    return @(Get-Process -Name AkikazuHardwareCheck -ErrorAction SilentlyContinue | Where-Object {
        $_.Path -and $_.Path.StartsWith($script:Root, [System.StringComparison]::OrdinalIgnoreCase)
    })
}

function Stop-TestApps {
    foreach ($process in (Get-TestProcesses)) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }

    Start-Sleep -Milliseconds 600
}

function Wait-Window {
    param([string]$TitlePrefix, [int]$TimeoutSeconds = 30)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        foreach ($process in (Get-TestProcesses)) {
            if ($process.MainWindowHandle -ne 0 -and $process.MainWindowTitle.StartsWith($TitlePrefix)) {
                return $process
            }
        }

        Start-Sleep -Milliseconds 250
    }

    throw "Window '$TitlePrefix' did not appear."
}

function Start-TestApp {
    param([string]$App, [switch]$Tray)

    $state = Get-SharedState -Root $script:Root
    $module = @($state.Modules | Where-Object { $_.Id -eq $App }) | Select-Object -First 1
    if ($null -eq $module) {
        throw "Module $App is not registered."
    }

    $arguments = @('--module', $App, '--no-elevate')
    if ($Tray) {
        $arguments += '--tray'
    }

    return Start-Process -FilePath $module.HostPath -ArgumentList $arguments -PassThru
}

function Get-InstalledHostPath {
    param([string]$App)

    $state = Get-SharedState -Root $script:Root
    $module = @($state.Modules | Where-Object { $_.Id -eq $App }) | Select-Object -First 1
    if ($null -eq $module) {
        return $null
    }

    return [string]$module.HostPath
}

function Get-TestAutostart {
    return (Get-ItemProperty -Path $script:RunKey -Name $script:StartupValueName -ErrorAction SilentlyContinue).$script:StartupValueName
}

function Set-TestAutostart {
    param([string]$HostPath)
    Set-ItemProperty -Path $script:RunKey -Name $script:StartupValueName -Value ('"' + $HostPath + '" --tray') -Type String
}

function Assert-AutostartHost {
    param([string]$ExpectedHostPath, [string]$Message)
    $expected = '"' + $ExpectedHostPath + '" --tray'
    Check ([string](Get-TestAutostart) -eq $expected) $Message
    Check (Test-Path -LiteralPath $ExpectedHostPath) "$Message (target host exists)"
}

function Assert-NoAutostart {
    param([string]$Message)
    Check ([string]::IsNullOrWhiteSpace([string](Get-TestAutostart))) $Message
}

function Cleanup {
    foreach ($app in @('hardware-check', 'network-rescue')) {
        $identity = $null
        try {
            $identity = Get-SharedIdentity -App $app
        } catch {
            continue
        }

        $manifest = Get-PrototypeManifest
        Uninstall-SharedApp -Id $identity.Id -UninstallKey $identity.UninstallKey -ShortcutName $identity.ShortcutName -ShortcutFolder ([string]$manifest.ShortcutFolder) -DisplayName $identity.DisplayName -Root $script:Root -Quiet
    }

    Remove-Item -LiteralPath $script:RegistryPath -Recurse -Force -ErrorAction SilentlyContinue
    foreach ($key in @('Akikazu.HardwareCheck', 'Akikazu.NetworkRescue')) {
        Remove-Item -LiteralPath (Join-Path $script:UninstallRoot $key) -Recurse -Force -ErrorAction SilentlyContinue
    }

    $manifest = Get-PrototypeManifest
    $shortcutFolder = Join-Path ([Environment]::GetFolderPath('Programs')) ([string]$manifest.ShortcutFolder)
    if (Test-Path -LiteralPath $shortcutFolder) {
        if (@(Get-ChildItem -LiteralPath $shortcutFolder -Force).Count -eq 0) {
            Remove-Item -LiteralPath $shortcutFolder -Force -ErrorAction SilentlyContinue
        }
    }

    Remove-Item -LiteralPath $script:Root -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $script:PayloadRoot -Recurse -Force -ErrorAction SilentlyContinue
}

try {
    Import-Module (Join-Path $PSScriptRoot 'SharedDesktopPrototype.psm1') -Force

    if (Test-Path -LiteralPath $script:RegistryPath) {
        throw "Refusing to run: $script:RegistryPath already exists."
    }

    foreach ($key in @('Akikazu.HardwareCheck', 'Akikazu.NetworkRescue')) {
        if (Test-Path -LiteralPath (Join-Path $script:UninstallRoot $key)) {
            throw "Refusing to run: uninstall entry $key already exists."
        }
    }

    if (@(Get-Process -Name AkikazuHardwareCheck -ErrorAction SilentlyContinue).Count -gt 0) {
        throw 'Refusing to run: an AkikazuHardwareCheck process is already running.'
    }

    if (Test-Path -LiteralPath $script:SettingsPath) {
        $script:SettingsBackup = Get-Content -LiteralPath $script:SettingsPath -Raw
        $script:SettingsExisted = $true
    }

    New-Item -ItemType Directory -Path (Split-Path -Parent $script:SettingsPath) -Force | Out-Null
    $testSettings = '{"Language":"zh-CN","ShowTrayIcon":true,"CloseToTray":true,"FloatingEnabled":false,"CrosshairEnabled":false,"RulerEnabled":false,"HudEnabled":false}'
    Set-Content -LiteralPath $script:SettingsPath -Value $testSettings -Encoding UTF8
    $script:SettingsWritten = $true

    $script:RunBackup = Get-TestAutostart
    $script:RunExisted = -not [string]::IsNullOrWhiteSpace([string]$script:RunBackup)
    $script:RunCaptured = $true
    Remove-ItemProperty -Path $script:RunKey -Name $script:StartupValueName -ErrorAction SilentlyContinue

    New-Item -ItemType Directory -Path (Join-Path $script:PayloadRoot '0.2.0') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $script:PayloadRoot '0.2.1') -Force | Out-Null

    dotnet build (Join-Path $script:RepoRoot 'AkikazuHardwareCheck.slnx') -c Release -p:Version=0.2.0 --no-incremental --nologo -v q
    if ($LASTEXITCODE -ne 0) {
        throw "0.2.0 build failed with exit code $LASTEXITCODE"
    }

    Copy-Item -Path (Join-Path $script:RepoRoot 'src\AkikazuHardwareCheck.App\bin\Release\net10.0-windows\win-x64\*') -Destination (Join-Path $script:PayloadRoot '0.2.0') -Recurse -Force
    dotnet build (Join-Path $script:RepoRoot 'AkikazuHardwareCheck.slnx') -c Release -p:Version=0.2.1 --no-incremental --nologo -v q
    if ($LASTEXITCODE -ne 0) {
        throw "0.2.1 build failed with exit code $LASTEXITCODE"
    }

    Copy-Item -Path (Join-Path $script:RepoRoot 'src\AkikazuHardwareCheck.App\bin\Release\net10.0-windows\win-x64\*') -Destination (Join-Path $script:PayloadRoot '0.2.1') -Recurse -Force

    $oldPayloadExecutable = Join-Path $script:PayloadRoot '0.2.0\AkikazuHardwareCheck.exe'
    $newPayloadExecutable = Join-Path $script:PayloadRoot '0.2.1\AkikazuHardwareCheck.exe'
    $oldFileVersion = (Get-Item -LiteralPath $oldPayloadExecutable).VersionInfo.FileVersion
    $newFileVersion = (Get-Item -LiteralPath $newPayloadExecutable).VersionInfo.FileVersion
    Check ($oldFileVersion -like '0.2.0*') "0.2.0 payload has file version $oldFileVersion"
    Check ($newFileVersion -like '0.2.1*') "0.2.1 payload has file version $newFileVersion"
    Check ($oldFileVersion -ne $newFileVersion) 'the two payloads are genuinely different binaries'

    $hardwareTitle = (Get-LanguageText 'ui.appName') + ' v'
    $rescueTitle = (Get-LanguageText 'module.rescue') + ' v'

    Install-SharedApp -App 'hardware-check' -Version '0.2.0' -HostVersion '0.2.0' -PayloadPath (Join-Path $script:PayloadRoot '0.2.0') -Root $script:Root | Out-Null
    Install-SharedApp -App 'network-rescue' -Version '0.1.0' -HostVersion '0.2.0' -PayloadPath (Join-Path $script:PayloadRoot '0.2.0') -Root $script:Root | Out-Null
    $oldHardwareHost = Get-InstalledHostPath 'hardware-check'
    $oldRescueHost = Get-InstalledHostPath 'network-rescue'
    Check ((Get-Item -LiteralPath $oldHardwareHost).VersionInfo.FileVersion -like '0.2.0*') 'installed hardware host is the real 0.2.0 binary'
    Set-TestAutostart $oldHardwareHost

    Install-SharedApp -App 'hardware-check' -Version '0.2.1' -HostVersion '0.2.1' -PayloadPath (Join-Path $script:PayloadRoot '0.2.1') -Root $script:Root | Out-Null
    $newHardwareHost = Get-InstalledHostPath 'hardware-check'
    Check ((Get-Item -LiteralPath $newHardwareHost).VersionInfo.FileVersion -like '0.2.1*') 'upgraded hardware host is the real 0.2.1 binary'
    Check ((Get-InstalledHostPath 'network-rescue') -eq $oldRescueHost) 'rescue keeps its real 0.2.0 host'
    Assert-AutostartHost $newHardwareHost 'upgrade rewrites autostart to the real 0.2.1 hardware host'

    $hardwareProcess = Start-TestApp -App 'hardware-check'
    $window = Wait-Window -TitlePrefix ($hardwareTitle + '0.2.1')
    Check ($window.Id -eq $hardwareProcess.Id) 'the real 0.2.1 hardware host opens with its module version'
    Stop-TestApps

    $rescueProcess = Start-TestApp -App 'network-rescue'
    $window = Wait-Window -TitlePrefix ($rescueTitle + '0.1.0')
    Check ($window.Id -eq $rescueProcess.Id) 'the unchanged rescue host still opens'
    Stop-TestApps

    $hardwareIdentity = Get-SharedIdentity -App 'hardware-check'
    $manifest = Get-PrototypeManifest
    Uninstall-SharedApp -Id $hardwareIdentity.Id -UninstallKey $hardwareIdentity.UninstallKey -ShortcutName $hardwareIdentity.ShortcutName -ShortcutFolder ([string]$manifest.ShortcutFolder) -DisplayName $hardwareIdentity.DisplayName -Root $script:Root -Quiet
    Assert-AutostartHost $oldRescueHost 'uninstalling the upgraded hardware host moves autostart to rescue'
    $rescueProcess = Start-TestApp -App 'network-rescue'
    $window = Wait-Window -TitlePrefix ($rescueTitle + '0.1.0')
    Check ($window.Id -eq $rescueProcess.Id) 'rescue is launchable after the hardware uninstall'
    Stop-TestApps

    $rescueIdentity = Get-SharedIdentity -App 'network-rescue'
    Uninstall-SharedApp -Id $rescueIdentity.Id -UninstallKey $rescueIdentity.UninstallKey -ShortcutName $rescueIdentity.ShortcutName -ShortcutFolder ([string]$manifest.ShortcutFolder) -DisplayName $rescueIdentity.DisplayName -Root $script:Root -Quiet
    Assert-NoAutostart 'uninstalling the last module removes autostart'
    Check (-not (Test-Path -LiteralPath $script:Root)) 'real-version upgrade test removes its root'
}
catch {
    Write-Host "ERROR $($_.Exception.Message)" -ForegroundColor Red
    $script:Failures += $_.Exception.Message
}
finally {
    Stop-TestApps
    try {
        Cleanup
    } catch {
        Write-Host "cleanup warning: $($_.Exception.Message)" -ForegroundColor Yellow
    }

    if ($script:SettingsExisted) {
        Set-Content -LiteralPath $script:SettingsPath -Value $script:SettingsBackup -Encoding UTF8
    } elseif ($script:SettingsWritten -and (Test-Path -LiteralPath $script:SettingsPath)) {
        Remove-Item -LiteralPath $script:SettingsPath -Force -ErrorAction SilentlyContinue
    }

    if ($script:RunCaptured) {
        if ($script:RunExisted) {
            Set-ItemProperty -Path $script:RunKey -Name $script:StartupValueName -Value $script:RunBackup -Type String
        } else {
            Remove-ItemProperty -Path $script:RunKey -Name $script:StartupValueName -ErrorAction SilentlyContinue
        }
    }

    dotnet build (Join-Path $script:RepoRoot 'AkikazuHardwareCheck.slnx') -c Release --nologo -v q | Out-Null
}

if ($script:Failures.Count -gt 0) {
    Write-Host ''
    Write-Host "FAILED $($script:Failures.Count) check(s):" -ForegroundColor Red
    foreach ($failure in $script:Failures) {
        Write-Host " - $failure" -ForegroundColor Red
    }

    exit 1
}

Write-Host ''
Write-Host 'All real different-version upgrade checks passed.'
exit 0
