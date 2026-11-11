# Elevation and non-elevation entry evidence for the shared desktop prototype. The hardware entry follows the
# product's existing auto-elevation policy; the rescue entry must stay non-elevated. This script temporarily writes
# settings, cleans up its test install, and restores the user's settings and Run value.
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$script:RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$script:RegistryPath = 'HKCU:\Software\Akikazu\SharedDesktop'
$script:UninstallRoot = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall'
$script:RunKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$script:StartupValueName = 'AkikazuHardwareCheck'
$script:SettingsPath = Join-Path (Join-Path $env:LOCALAPPDATA 'AkikazuHardwareCheck') 'settings.json'
$script:Root = Join-Path $env:TEMP ('AkikazuSharedDesktopElevation-' + [guid]::NewGuid().ToString('N'))
$script:Failures = @()
$script:SettingsBackup = $null
$script:SettingsExisted = $false
$script:SettingsWritten = $false
$script:RunBackup = $null
$script:RunExisted = $false
$script:RunCaptured = $false
$script:Language = $null

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class ElevationProbe
{
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr OpenProcess(uint access, bool inherit, uint pid);

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool OpenProcessToken(IntPtr process, uint access, out IntPtr token);

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern bool GetTokenInformation(IntPtr token, int infoClass, out int info, int length, out int returnLength);

    [DllImport("kernel32.dll")]
    private static extern bool CloseHandle(IntPtr handle);

    // 1 elevated, 0 not elevated, -1 could not query.
    public static int GetElevation(int pid)
    {
        IntPtr process = OpenProcess(0x1000, false, (uint)pid);
        if (process == IntPtr.Zero)
        {
            return -1;
        }

        try
        {
            IntPtr token;
            if (!OpenProcessToken(process, 0x0008, out token))
            {
                return -1;
            }

            try
            {
                int elevated;
                int returned;
                if (!GetTokenInformation(token, 20, out elevated, 4, out returned))
                {
                    return -1;
                }

                return elevated != 0 ? 1 : 0;
            }
            finally
            {
                CloseHandle(token);
            }
        }
        finally
        {
            CloseHandle(process);
        }
    }
}
'@

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
    # The elevated process does not expose Path or CommandLine to this medium-integrity test process, so use the
    # process name; the script refuses to start when any other instance is already running.
    return @(Get-Process -Name AkikazuHardwareCheck -ErrorAction SilentlyContinue)
}

function Stop-TestApps {
    foreach ($process in (Get-TestProcesses)) {
        $elevation = [ElevationProbe]::GetElevation($process.Id)
        if ($elevation -eq 1) {
            Start-Process -FilePath (Join-Path $env:SystemRoot 'System32\taskkill.exe') -ArgumentList @('/PID', $process.Id, '/F') -Verb RunAs -Wait -WindowStyle Hidden
        } else {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }

    Start-Sleep -Milliseconds 800
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
    param([string]$App)

    $state = Get-SharedState -Root $script:Root
    $module = @($state.Modules | Where-Object { $_.Id -eq $App }) | Select-Object -First 1
    if ($null -eq $module) {
        throw "Module $App is not registered."
    }

    return Start-Process -FilePath $module.HostPath -ArgumentList @('--module', $App) -PassThru
}

function Install-TestApp {
    param([string]$App, [string]$Version)
    Install-SharedApp -App $App -Version $Version -Root $script:Root -PayloadPath $script:PayloadPath | Out-Null
}

function Uninstall-TestApp {
    param([string]$App)
    $identity = Get-SharedIdentity -App $App
    $manifest = Get-PrototypeManifest
    Uninstall-SharedApp -Id $identity.Id -UninstallKey $identity.UninstallKey -ShortcutName $identity.ShortcutName -ShortcutFolder ([string]$manifest.ShortcutFolder) -DisplayName $identity.DisplayName -Root $script:Root -Quiet
}

function Get-TestAutostart {
    return (Get-ItemProperty -Path $script:RunKey -Name $script:StartupValueName -ErrorAction SilentlyContinue).$script:StartupValueName
}

function Cleanup {
    foreach ($app in @('hardware-check', 'network-rescue')) {
        try {
            Uninstall-TestApp -App $app
        } catch {
            # Best effort.
        }
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
}

try {
    Import-Module (Join-Path $PSScriptRoot 'SharedDesktopPrototype.psm1') -Force
    $script:PayloadPath = Join-Path $script:RepoRoot 'src\AkikazuHardwareCheck.App\bin\Release\net10.0-windows\win-x64'

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

    if (-not (Get-Service -Name 'PawnIO' -ErrorAction SilentlyContinue)) {
        throw 'Refusing to run: PawnIO is not installed, so the elevated hardware launch would install a driver. Run this test only on a machine where PawnIO is already installed.'
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

    $hardwareTitle = (Get-LanguageText 'ui.appName') + ' v'
    $rescueTitle = (Get-LanguageText 'module.rescue') + ' v'

    Write-Host '--- hardware entry: auto-elevation ---'
    Install-TestApp -App 'hardware-check' -Version '0.2.0'
    $launcher = Start-TestApp -App 'hardware-check'
    $window = Wait-Window -TitlePrefix ($hardwareTitle + '0.2.0')
    $elevated = [ElevationProbe]::GetElevation($window.Id)
    Check ($elevated -eq 1) 'hardware entry runs in an elevated process'
    Check (@(Get-TestProcesses).Count -eq 1) 'elevated hardware entry leaves one shared host process'
    Stop-TestApps
    $launcher.WaitForExit(10000) | Out-Null
    Check ($launcher.HasExited) 'the non-elevated launcher exits after starting the elevated copy'

    Write-Host '--- rescue entry: non-elevated ---'
    Uninstall-TestApp -App 'hardware-check'
    Install-TestApp -App 'network-rescue' -Version '0.1.0'
    $launcher = Start-TestApp -App 'network-rescue'
    $window = Wait-Window -TitlePrefix ($rescueTitle + '0.1.0')
    $elevated = [ElevationProbe]::GetElevation($window.Id)
    Check ($elevated -eq 0) 'rescue entry runs in a non-elevated process'
    Check (@(Get-TestProcesses).Count -eq 1) 'rescue entry leaves one shared host process'
    Stop-TestApps
    $launcher.WaitForExit(10000) | Out-Null

    Write-Host '--- mixed entries: rescue first, then hardware ---'
    Install-TestApp -App 'hardware-check' -Version '0.2.0'
    $rescueLauncher = Start-TestApp -App 'network-rescue'
    $window = Wait-Window -TitlePrefix ($rescueTitle + '0.1.0')
    Check ([ElevationProbe]::GetElevation($window.Id) -eq 0) 'the first rescue window is non-elevated'
    $hardwareLauncher = Start-TestApp -App 'hardware-check'
    $window = Wait-Window -TitlePrefix ($hardwareTitle + '0.2.0')
    Check (@(Get-TestProcesses).Count -eq 1) 'mixed entries keep one shared host process'
    Check ([ElevationProbe]::GetElevation($window.Id) -eq 0) 'the existing non-elevated window keeps the hardware page; it does not become elevated'
    Stop-TestApps
    $hardwareLauncher.WaitForExit(10000) | Out-Null
    $rescueLauncher.WaitForExit(10000) | Out-Null

    Uninstall-TestApp -App 'hardware-check'
    Uninstall-TestApp -App 'network-rescue'
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
Write-Host 'All elevation / non-elevation entry checks passed.'
exit 0
