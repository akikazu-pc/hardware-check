# Verifies the shared desktop prototype through the real install/uninstall entries. Run with:
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/prototype/test-shared-desktop.ps1
# It refuses to run when a shared-desktop registration already exists, and removes only its own test state.
[CmdletBinding()]
param(
    [switch]$SkipBuild,
    [string]$Root,
    [string]$PayloadPath
)

$ErrorActionPreference = 'Stop'
$script:Failures = @()
$script:RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$script:RegistryPath = 'HKCU:\Software\Akikazu\SharedDesktop'
$script:UninstallRoot = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall'
$script:SettingsPath = Join-Path (Join-Path $env:LOCALAPPDATA 'AkikazuHardwareCheck') 'settings.json'
$script:SettingsBackup = $null
$script:SettingsExisted = $false
$script:SettingsWritten = $false
$script:Root = $Root
$script:PayloadPath = $PayloadPath

function Check {
    param([bool]$Condition, [string]$Message)
    if ($Condition) {
        Write-Host "PASS $Message"
    } else {
        Write-Host "FAIL $Message" -ForegroundColor Red
        $script:Failures += $Message
    }
}

function Get-LocalizedText {
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
        try {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        } catch {
            # Already gone.
        }
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

    $titles = @((Get-TestProcesses) | ForEach-Object { $_.MainWindowTitle }) -join ' | '
    throw "Window '$TitlePrefix' did not appear. Current titles: $titles"
}

function Wait-ProcessCount {
    param([int]$Expected, [int]$TimeoutSeconds = 10)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ((Get-TestProcesses).Count -eq $Expected) {
            return
        }

        Start-Sleep -Milliseconds 250
    }

    Check ((Get-TestProcesses).Count -eq $Expected) "exactly $Expected shared host process remains"
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

function Start-TestShortcut {
    param([string]$App)

    $identity = Get-SharedIdentity -App $App
    $manifest = Get-PrototypeManifest
    $path = Get-ShortcutPath -ShortcutName $identity.ShortcutName -ShortcutFolder ([string]$manifest.ShortcutFolder)
    return Start-Process -FilePath $path -PassThru
}

function Install-TestApp {
    param([string]$App, [string]$Version, [string]$HostVersion)

    $arguments = @{
        App = $App
        Root = $script:Root
        PayloadPath = $script:PayloadPath
    }
    if (-not [string]::IsNullOrWhiteSpace($Version)) {
        $arguments.Version = $Version
    }
    if (-not [string]::IsNullOrWhiteSpace($HostVersion)) {
        $arguments.HostVersion = $HostVersion
    }

    return Install-SharedApp @arguments
}

function Uninstall-TestApp {
    param([string]$App)

    $identity = Get-SharedIdentity -App $App
    $manifest = Get-PrototypeManifest
    Uninstall-SharedApp `
        -Id $identity.Id `
        -UninstallKey $identity.UninstallKey `
        -ShortcutName $identity.ShortcutName `
        -ShortcutFolder ([string]$manifest.ShortcutFolder) `
        -DisplayName $identity.DisplayName `
        -Root $script:Root `
        -RegistryPath $script:RegistryPath `
        -Quiet
}

function Get-InstalledVersion {
    param([string]$App)

    $state = Get-SharedState -Root $script:Root
    $module = @($state.Modules | Where-Object { $_.Id -eq $App }) | Select-Object -First 1
    if ($null -eq $module) {
        return $null
    }

    return [string]$module.Version
}

function Get-InstalledHostVersion {
    param([string]$App)

    $state = Get-SharedState -Root $script:Root
    $module = @($state.Modules | Where-Object { $_.Id -eq $App }) | Select-Object -First 1
    if ($null -eq $module) {
        return $null
    }

    return [string]$module.HostVersion
}

function Assert-Shortcut {
    param([string]$App, [string]$ExpectedArguments)

    $identity = Get-SharedIdentity -App $App
    $manifest = Get-PrototypeManifest
    $path = Get-ShortcutPath -ShortcutName $identity.ShortcutName -ShortcutFolder ([string]$manifest.ShortcutFolder)
    Check (Test-Path -LiteralPath $path) "$App shortcut exists"

    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($path)
    Check ($link.TargetPath -like (Join-Path $script:Root 'host\*\AkikazuHardwareCheck.exe')) "$App shortcut points at the shared host"
    Check ($link.Arguments -eq $ExpectedArguments) "$App shortcut passes its module entry"
}

function Assert-UninstallEntry {
    param([string]$App, [string]$ExpectedVersion)

    $identity = Get-SharedIdentity -App $App
    $key = Join-Path $script:UninstallRoot $identity.UninstallKey
    Check (Test-Path -LiteralPath $key) "$App uninstall entry exists"
    if (Test-Path -LiteralPath $key) {
        $values = Get-ItemProperty -Path $key
        Check ($values.DisplayVersion -eq $ExpectedVersion) "$App uninstall entry reports $ExpectedVersion"
        Check (-not [string]::IsNullOrWhiteSpace($values.UninstallString)) "$App uninstall command exists"
    }
}

function Remove-TestState {
    foreach ($app in @('hardware-check', 'network-rescue')) {
        try {
            Uninstall-TestApp -App $app
        } catch {
            # Best effort during cleanup.
        }
    }

    if (Test-Path -LiteralPath $script:RegistryPath) {
        Remove-Item -LiteralPath $script:RegistryPath -Recurse -Force -ErrorAction SilentlyContinue
    }

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

    if (Test-Path -LiteralPath $script:Root) {
        Remove-Item -LiteralPath $script:Root -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$identityManifest = $null
$settingsDirectory = Split-Path -Parent $script:SettingsPath
try {
    Import-Module (Join-Path $PSScriptRoot 'SharedDesktopPrototype.psm1') -Force
    $identityManifest = Get-PrototypeManifest

    if (Test-Path -LiteralPath $script:RegistryPath) {
        throw "Refusing to run: $script:RegistryPath already exists. Remove the existing shared-desktop install first."
    }

    foreach ($key in @('Akikazu.HardwareCheck', 'Akikazu.NetworkRescue')) {
        if (Test-Path -LiteralPath (Join-Path $script:UninstallRoot $key)) {
            throw "Refusing to run: uninstall entry $key already exists."
        }
    }

    if ([string]::IsNullOrWhiteSpace($script:Root)) {
        $script:Root = Join-Path $env:TEMP ('AkikazuSharedDesktopTest-' + [guid]::NewGuid().ToString('N'))
    } elseif (Test-Path -LiteralPath $script:Root) {
        if (@(Get-ChildItem -LiteralPath $script:Root -Force).Count -gt 0) {
            throw "Refusing to run: the supplied test root is not empty: $script:Root"
        }
    }

    if ([string]::IsNullOrWhiteSpace($script:PayloadPath)) {
        $script:PayloadPath = Join-Path $script:RepoRoot 'src\AkikazuHardwareCheck.App\bin\Release\net10.0-windows\win-x64'
    }

    if (-not $SkipBuild) {
        dotnet build (Join-Path $script:RepoRoot 'AkikazuHardwareCheck.slnx') -c Release --nologo -v q
        if ($LASTEXITCODE -ne 0) {
            throw "dotnet build failed with exit code $LASTEXITCODE"
        }
    }

    if ($null -eq $identityManifest) {
        throw 'The identity manifest could not be read.'
    }

    if (Test-Path -LiteralPath $script:SettingsPath) {
        $script:SettingsBackup = Get-Content -LiteralPath $script:SettingsPath -Raw
        $script:SettingsExisted = $true
    }

    New-Item -ItemType Directory -Path $settingsDirectory -Force | Out-Null
    $testSettings = '{"Language":"zh-CN","ShowTrayIcon":true,"CloseToTray":true,"FloatingEnabled":false,"CrosshairEnabled":false,"RulerEnabled":false,"HudEnabled":false}'
    Set-Content -LiteralPath $script:SettingsPath -Value $testSettings -Encoding UTF8
    $script:SettingsWritten = $true

    $hardwareVersion = '0.2.0'
    $rescueVersion = '0.1.0'
    $hardwareTitle = (Get-LocalizedText 'ui.appName') + ' v'
    $rescueTitle = (Get-LocalizedText 'module.rescue') + ' v'

    Write-Host "Test root: $script:Root"
    Write-Host '--- single install: hardware only ---'
    Install-TestApp -App 'hardware-check' -Version $hardwareVersion | Out-Null
    Check ((Get-InstalledVersion 'hardware-check') -eq $hardwareVersion) 'hardware module is registered'
    Check ($null -eq (Get-InstalledVersion 'network-rescue')) 'rescue module is not registered'
    Assert-Shortcut -App 'hardware-check' -ExpectedArguments '--module hardware-check'
    Assert-UninstallEntry -App 'hardware-check' -ExpectedVersion $hardwareVersion
    $hardwareProcess = Start-TestApp -App 'hardware-check'
    $window = Wait-Window -TitlePrefix ($hardwareTitle + $hardwareVersion)
    Check ($window.Id -eq $hardwareProcess.Id) 'hardware entry opens the shared window'
    Wait-ProcessCount -Expected 1
    Stop-TestApps

    Write-Host '--- uninstall through the registered uninstall command ---'
    $hardwareIdentity = Get-SharedIdentity -App 'hardware-check'
    $uninstallKey = Join-Path $script:UninstallRoot $hardwareIdentity.UninstallKey
    $quietUninstall = (Get-ItemProperty -Path $uninstallKey).QuietUninstallString
    $uninstallProcess = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', ('"' + $quietUninstall + '"') -Wait -PassThru -WindowStyle Hidden
    Check ($uninstallProcess.ExitCode -eq 0) 'registered uninstall command exits successfully'
    Check ((Get-SharedState -Root $script:Root).Modules.Count -eq 0) 'hardware uninstall leaves no module registration'
    Check (-not (Test-Path -LiteralPath $script:Root)) 'hardware uninstall removes the now-unused shared root'
    Check (-not (Test-Path -LiteralPath (Join-Path $script:UninstallRoot $hardwareIdentity.UninstallKey))) 'hardware uninstall removes its uninstall entry'

    Write-Host '--- single install: rescue only ---'
    Install-TestApp -App 'network-rescue' -Version $rescueVersion | Out-Null
    Check ((Get-InstalledVersion 'network-rescue') -eq $rescueVersion) 'rescue module is registered'
    Check ($null -eq (Get-InstalledVersion 'hardware-check')) 'hardware module is absent'
    Start-TestShortcut -App 'network-rescue' | Out-Null
    $window = Wait-Window -TitlePrefix ($rescueTitle + $rescueVersion)
    Check ($null -ne $window) 'the rescue Start Menu shortcut opens the shared window on the rescue page'
    Wait-ProcessCount -Expected 1
    Stop-TestApps

    Write-Host '--- install order: rescue then hardware ---'
    Install-TestApp -App 'hardware-check' -Version $hardwareVersion | Out-Null
    Check ((Get-InstalledVersion 'hardware-check') -eq $hardwareVersion) 'hardware can be added after rescue'
    $hardwareProcess = Start-TestApp -App 'hardware-check'
    $window = Wait-Window -TitlePrefix ($hardwareTitle + $hardwareVersion)
    Check ($window.Id -eq $hardwareProcess.Id) 'hardware entry opens the shared window'
    $second = Start-TestApp -App 'network-rescue'
    $second.WaitForExit(10000) | Out-Null
    Check ($second.HasExited) 'second entry exits after asking the shared host to navigate'
    Wait-ProcessCount -Expected 1
    $window = Wait-Window -TitlePrefix ($rescueTitle + $rescueVersion)
    Check ($window.Id -eq $hardwareProcess.Id) 'second entry navigates the existing shared window'
    Stop-TestApps

    Write-Host '--- uninstall one leaves the other usable ---'
    Uninstall-TestApp -App 'hardware-check'
    Check ($null -eq (Get-InstalledVersion 'hardware-check')) 'hardware registration is removed'
    Check ((Get-InstalledVersion 'network-rescue') -eq $rescueVersion) 'rescue registration remains'
    Check (Test-Path -LiteralPath (Join-Path $script:Root 'host\0.2.0\AkikazuHardwareCheck.exe')) 'shared host is retained for the remaining module'
    $rescueProcess = Start-TestApp -App 'network-rescue'
    $window = Wait-Window -TitlePrefix ($rescueTitle + $rescueVersion)
    Check ($window.Id -eq $rescueProcess.Id) 'remaining rescue entry still opens'
    Stop-TestApps

    Write-Host '--- independent upgrade: rescue host moves, hardware stays ---'
    Install-TestApp -App 'hardware-check' -Version $hardwareVersion | Out-Null
    Install-TestApp -App 'network-rescue' -Version '0.1.1' -HostVersion '0.2.1' | Out-Null
    Check ((Get-InstalledVersion 'hardware-check') -eq $hardwareVersion) 'hardware module version is unchanged by the rescue upgrade'
    Check ((Get-InstalledHostVersion 'hardware-check') -eq '0.2.0') 'hardware keeps its host version'
    Check ((Get-InstalledVersion 'network-rescue') -eq '0.1.1') 'rescue module version is upgraded'
    Check ((Get-InstalledHostVersion 'network-rescue') -eq '0.2.1') 'rescue points at the upgraded host'
    Check ((Test-Path -LiteralPath (Join-Path $script:Root 'host\0.2.0\AkikazuHardwareCheck.exe'))) 'old host is retained for hardware'
    Check ((Test-Path -LiteralPath (Join-Path $script:Root 'host\0.2.1\AkikazuHardwareCheck.exe'))) 'new host is installed for rescue'
    $rescueProcess = Start-TestApp -App 'network-rescue'
    $window = Wait-Window -TitlePrefix ($rescueTitle + '0.1.1')
    Check ($window.Id -eq $rescueProcess.Id) 'upgraded rescue entry opens'
    Stop-TestApps
    $hardwareProcess = Start-TestApp -App 'hardware-check'
    $window = Wait-Window -TitlePrefix ($hardwareTitle + $hardwareVersion)
    Check ($window.Id -eq $hardwareProcess.Id) 'unchanged hardware entry still opens'
    Stop-TestApps

    Write-Host '--- independent upgrade: hardware host moves, rescue stays ---'
    Install-TestApp -App 'hardware-check' -Version '0.2.1' -HostVersion '0.2.2' | Out-Null
    Check ((Get-InstalledVersion 'hardware-check') -eq '0.2.1') 'hardware module version is upgraded'
    Check ((Get-InstalledHostVersion 'hardware-check') -eq '0.2.2') 'hardware points at the upgraded host'
    Check ((Get-InstalledVersion 'network-rescue') -eq '0.1.1') 'rescue module version is unchanged by the hardware upgrade'
    Check ((Get-InstalledHostVersion 'network-rescue') -eq '0.2.1') 'rescue keeps its host version'
    Check ((Test-Path -LiteralPath (Join-Path $script:Root 'host\0.2.2\AkikazuHardwareCheck.exe'))) 'new hardware host is installed'
    Check ((Test-Path -LiteralPath (Join-Path $script:Root 'host\0.2.1\AkikazuHardwareCheck.exe'))) 'rescue host is retained'
    Check (-not (Test-Path -LiteralPath (Join-Path $script:Root 'host\0.2.0'))) 'hardware old host is removed when nothing references it'
    $hardwareProcess = Start-TestApp -App 'hardware-check'
    $window = Wait-Window -TitlePrefix ($hardwareTitle + '0.2.1')
    Check ($window.Id -eq $hardwareProcess.Id) 'upgraded hardware entry opens'
    Stop-TestApps
    $rescueProcess = Start-TestApp -App 'network-rescue'
    $window = Wait-Window -TitlePrefix ($rescueTitle + '0.1.1')
    Check ($window.Id -eq $rescueProcess.Id) 'unchanged rescue entry still opens'
    Stop-TestApps

    Write-Host '--- uninstall upgraded rescue leaves hardware and its host ---'
    Uninstall-TestApp -App 'network-rescue'
    Check ((Get-InstalledVersion 'hardware-check') -eq '0.2.1') 'hardware registration survives the rescue uninstall'
    Check (-not (Test-Path -LiteralPath (Join-Path $script:Root 'host\0.2.1'))) 'unreferenced upgraded host is removed'
    Check ((Test-Path -LiteralPath (Join-Path $script:Root 'host\0.2.2\AkikazuHardwareCheck.exe'))) 'host used by hardware is retained'
    $hardwareProcess = Start-TestApp -App 'hardware-check'
    $window = Wait-Window -TitlePrefix ($hardwareTitle + '0.2.1')
    Check ($window.Id -eq $hardwareProcess.Id) 'hardware entry still opens after the rescue uninstall'
    Stop-TestApps

    Write-Host '--- final uninstall leaves a clean root ---'
    Uninstall-TestApp -App 'hardware-check'
    Check ((Get-SharedState -Root $script:Root).Modules.Count -eq 0) 'no module registration remains'
    Check (-not (Test-Path -LiteralPath $script:Root)) 'shared root is removed after the last module'
    Check (-not (Test-Path -LiteralPath $script:RegistryPath)) 'shared registry root is removed after the last module'

    Write-Host '--- concurrent launch and reverse install order ---'
    Install-TestApp -App 'network-rescue' -Version $rescueVersion | Out-Null
    Install-TestApp -App 'hardware-check' -Version $hardwareVersion | Out-Null
    $first = Start-TestApp -App 'hardware-check'
    $second = Start-TestApp -App 'network-rescue'
    Start-Sleep -Seconds 4
    Check ((Get-TestProcesses).Count -eq 1) 'concurrent launch keeps exactly one shared host process'
    $window = Get-TestProcesses | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
    Check ($null -ne $window) 'concurrent launch produces one window'
    if ($null -ne $window) {
        $other = if ($window.MainWindowTitle.StartsWith($hardwareTitle)) { 'network-rescue' } else { 'hardware-check' }
        $otherProcess = Start-TestApp -App $other
        $otherProcess.WaitForExit(10000) | Out-Null
        Check ($otherProcess.HasExited) 'navigation entry exits after the concurrent launch'
        Wait-ProcessCount -Expected 1
        $expectedPrefix = if ($other -eq 'hardware-check') { $hardwareTitle + $hardwareVersion } else { $rescueTitle + $rescueVersion }
        $window = Wait-Window -TitlePrefix $expectedPrefix
        Check ($null -ne $window) 'the surviving window follows the navigation entry'
    }

    Stop-TestApps

    Write-Host '--- tray-hidden launch is restored by a second entry ---'
    Uninstall-TestApp -App 'hardware-check'
    $hidden = Start-TestApp -App 'network-rescue' -Tray
    Start-Sleep -Seconds 2
    $hidden.Refresh()
    Check ((Get-TestProcesses).Count -eq 1) 'tray launch keeps one shared host process'
    Check ($hidden.MainWindowHandle -eq 0) 'tray launch starts without a visible main window'
    $second = Start-TestApp -App 'network-rescue'
    $second.WaitForExit(10000) | Out-Null
    Check ($second.HasExited) 'restore entry exits after signalling'
    $window = Wait-Window -TitlePrefix ($rescueTitle + $rescueVersion)
    Check ($null -ne $window) 'restore entry returns the hidden window'
    Wait-ProcessCount -Expected 1
    Stop-TestApps

    Write-Host '--- offline-simulated rescue launch ---'
    $oldProxy = @{
        HTTP_PROXY = $env:HTTP_PROXY
        HTTPS_PROXY = $env:HTTPS_PROXY
        ALL_PROXY = $env:ALL_PROXY
        NO_PROXY = $env:NO_PROXY
    }
    try {
        $env:HTTP_PROXY = 'http://127.0.0.1:1'
        $env:HTTPS_PROXY = 'http://127.0.0.1:1'
        $env:ALL_PROXY = 'http://127.0.0.1:1'
        $env:NO_PROXY = ''
        $offlineProcess = Start-TestApp -App 'network-rescue'
        $window = Wait-Window -TitlePrefix ($rescueTitle + $rescueVersion) -TimeoutSeconds 15
        Check ($window.Id -eq $offlineProcess.Id) 'rescue page starts with outbound HTTP proxied to a dead endpoint'
        Wait-ProcessCount -Expected 1
    } finally {
        $env:HTTP_PROXY = $oldProxy.HTTP_PROXY
        $env:HTTPS_PROXY = $oldProxy.HTTPS_PROXY
        $env:ALL_PROXY = $oldProxy.ALL_PROXY
        $env:NO_PROXY = $oldProxy.NO_PROXY
    }

    Stop-TestApps

    Write-Host '--- cleanup ---'
    Uninstall-TestApp -App 'network-rescue'
    Check ((Get-SharedState -Root $script:Root).Modules.Count -eq 0) 'all registrations removed'
    Check (-not (Test-Path -LiteralPath $script:Root)) 'test root removed'
}
catch {
    Write-Host "ERROR $($_.Exception.Message)" -ForegroundColor Red
    $script:Failures += $_.Exception.Message
}
finally {
    Stop-TestApps
    try {
        Remove-TestState
    } catch {
        Write-Host "cleanup warning: $($_.Exception.Message)" -ForegroundColor Yellow
    }

    if ($script:SettingsExisted) {
        Set-Content -LiteralPath $script:SettingsPath -Value $script:SettingsBackup -Encoding UTF8
    } elseif ($script:SettingsWritten -and (Test-Path -LiteralPath $script:SettingsPath)) {
        Remove-Item -LiteralPath $script:SettingsPath -Force -ErrorAction SilentlyContinue
    }
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
Write-Host 'All shared desktop prototype checks passed.'
exit 0
