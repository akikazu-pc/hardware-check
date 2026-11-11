# Prototype per-user installer for the shared desktop identities. This is deliberately not an MSI: the real MSI
# projects need Advanced Installer, which is not available in this environment. The registry contract, module
# discovery, shortcuts and uninstall entries are the same ones the application reads.
$ErrorActionPreference = 'Stop'

$script:RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$script:ManifestPath = Join-Path (Join-Path $script:RepoRoot 'packaging') 'shared-desktop\app-identities.json'
$script:DefaultRegistryPath = 'HKCU:\Software\Akikazu\SharedDesktop'
$script:UninstallRoot = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall'

function Get-PrototypeManifest {
    if (-not (Test-Path -LiteralPath $script:ManifestPath)) {
        throw "Identity manifest not found: $script:ManifestPath"
    }

    return Get-Content -LiteralPath $script:ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Get-SharedIdentity {
    param([Parameter(Mandatory = $true)][string]$App)

    $manifest = Get-PrototypeManifest
    $identity = @($manifest.Modules | Where-Object { $_.Id -eq $App }) | Select-Object -First 1
    if ($null -eq $identity) {
        throw "Unknown application identity: $App"
    }

    return $identity
}

function Get-ProductVersion {
    $props = [xml](Get-Content -LiteralPath (Join-Path $script:RepoRoot 'Directory.Build.props'))
    return [string]$props.Project.PropertyGroup.Version
}

function Get-ShortcutPath {
    param(
        [Parameter(Mandatory = $true)][string]$ShortcutName,
        [Parameter(Mandatory = $true)][string]$ShortcutFolder
    )

    $programs = [Environment]::GetFolderPath('Programs')
    return Join-Path (Join-Path $programs $ShortcutFolder) ($ShortcutName + '.lnk')
}

function Copy-SharedPayload {
    param(
        [Parameter(Mandatory = $true)][string]$PayloadPath,
        [Parameter(Mandatory = $true)][string]$HostDirectory,
        [Parameter(Mandatory = $true)][string]$PayloadExecutable
    )

    $hostExecutable = Join-Path $HostDirectory $PayloadExecutable
    if (Test-Path -LiteralPath $hostExecutable) {
        return $hostExecutable
    }

    New-Item -ItemType Directory -Path $HostDirectory -Force | Out-Null
    Copy-Item -Path (Join-Path $PayloadPath '*') -Destination $HostDirectory -Recurse -Force
    if (-not (Test-Path -LiteralPath $hostExecutable)) {
        throw "The shared host was not copied to $hostExecutable"
    }

    return $hostExecutable
}

function Write-ModuleFiles {
    param(
        [Parameter(Mandatory = $true)]$Identity,
        [Parameter(Mandatory = $true)][string]$ModuleDirectory,
        [Parameter(Mandatory = $true)][string]$Version,
        [Parameter(Mandatory = $true)][string]$HostVersion,
        [Parameter(Mandatory = $true)][string]$HostPath,
        [Parameter(Mandatory = $true)][string]$RegistryPath,
        [Parameter(Mandatory = $true)][string]$ShortcutFolder
    )

    New-Item -ItemType Directory -Path $ModuleDirectory -Force | Out-Null
    $moduleRecord = [ordered]@{
        SchemaVersion = 1
        Id = $Identity.Id
        Version = $Version
        MinHostInterface = 1
        HostVersion = $HostVersion
        InstallRoot = $ModuleDirectory
        HostPath = $HostPath
        EntryArguments = $Identity.EntryArguments
        InstallIdentity = $Identity.InstallIdentity
        UninstallKey = $Identity.UninstallKey
        InstalledAt = (Get-Date).ToString('o')
    }
    $moduleRecord | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $ModuleDirectory 'module.json') -Encoding UTF8

    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'SharedDesktopPrototype.psm1') -Destination $ModuleDirectory -Force
    $quote = {
        param([string]$value)
        return "'" + $value.Replace("'", "''") + "'"
    }
    $uninstallScript = @'
param([switch]$Quiet)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Import-Module (Join-Path $here 'SharedDesktopPrototype.psm1') -Force
Uninstall-SharedApp -Id {0} -UninstallKey {1} -ShortcutName {2} -ShortcutFolder {3} -DisplayName {4} -Root {5} -RegistryPath {6} -Quiet:$Quiet
'@ -f (& $quote $Identity.Id), (& $quote $Identity.UninstallKey), (& $quote $Identity.ShortcutName), (& $quote $ShortcutFolder), (& $quote $Identity.DisplayName), (& $quote (Split-Path -Parent (Split-Path -Parent $ModuleDirectory))), (& $quote $RegistryPath)
    [System.IO.File]::WriteAllText((Join-Path $ModuleDirectory 'uninstall.ps1'), $uninstallScript, (New-Object System.Text.UTF8Encoding($true)))
}

function Write-ModuleRegistration {
    param(
        [Parameter(Mandatory = $true)]$Identity,
        [Parameter(Mandatory = $true)][string]$ModuleDirectory,
        [Parameter(Mandatory = $true)][string]$Version,
        [Parameter(Mandatory = $true)][string]$HostVersion,
        [Parameter(Mandatory = $true)][string]$HostPath,
        [Parameter(Mandatory = $true)][string]$RegistryPath
    )

    if (-not (Test-Path -LiteralPath $RegistryPath)) {
        New-Item -Path $RegistryPath -Force | Out-Null
    }

    Set-ItemProperty -Path $RegistryPath -Name 'SchemaVersion' -Value 1 -Type DWord
    Set-ItemProperty -Path $RegistryPath -Name 'HostInterfaceVersion' -Value 1 -Type DWord

    $modulesKey = Join-Path $RegistryPath 'Modules'
    if (-not (Test-Path -LiteralPath $modulesKey)) {
        New-Item -Path $modulesKey -Force | Out-Null
    }

    $moduleKey = Join-Path $modulesKey $Identity.Id
    New-Item -Path $moduleKey -Force | Out-Null
    Set-ItemProperty -Path $moduleKey -Name 'SchemaVersion' -Value 1 -Type DWord
    Set-ItemProperty -Path $moduleKey -Name 'Id' -Value $Identity.Id -Type String
    Set-ItemProperty -Path $moduleKey -Name 'Version' -Value $Version -Type String
    Set-ItemProperty -Path $moduleKey -Name 'MinHostInterface' -Value 1 -Type DWord
    Set-ItemProperty -Path $moduleKey -Name 'HostVersion' -Value $HostVersion -Type String
    Set-ItemProperty -Path $moduleKey -Name 'InstallRoot' -Value $ModuleDirectory -Type String
    Set-ItemProperty -Path $moduleKey -Name 'HostPath' -Value $HostPath -Type String
    Set-ItemProperty -Path $moduleKey -Name 'EntryArguments' -Value $Identity.EntryArguments -Type String
    Set-ItemProperty -Path $moduleKey -Name 'InstallIdentity' -Value $Identity.InstallIdentity -Type String
    Set-ItemProperty -Path $moduleKey -Name 'UninstallKey' -Value $Identity.UninstallKey -Type String
}

function Write-UninstallRegistration {
    param(
        [Parameter(Mandatory = $true)]$Identity,
        [Parameter(Mandatory = $true)][string]$Version,
        [Parameter(Mandatory = $true)][string]$HostPath,
        [Parameter(Mandatory = $true)][string]$ModuleDirectory,
        [Parameter(Mandatory = $true)][string]$Publisher,
        [Parameter(Mandatory = $true)][string]$UrlInfoAbout
    )

    $key = Join-Path $script:UninstallRoot $Identity.UninstallKey
    New-Item -Path $key -Force | Out-Null
    $powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $uninstallScript = Join-Path $ModuleDirectory 'uninstall.ps1'
    $uninstallString = '"{0}" -NoProfile -ExecutionPolicy Bypass -File "{1}"' -f $powershell, $uninstallScript
    $size = 0
    try {
        $size = [int][math]::Ceiling((Get-ChildItem -LiteralPath (Split-Path -Parent $HostPath) -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1KB)
    } catch {
        $size = 0
    }

    Set-ItemProperty -Path $key -Name 'DisplayName' -Value $Identity.DisplayName -Type String
    Set-ItemProperty -Path $key -Name 'DisplayVersion' -Value $Version -Type String
    Set-ItemProperty -Path $key -Name 'Publisher' -Value $Publisher -Type String
    Set-ItemProperty -Path $key -Name 'InstallLocation' -Value $ModuleDirectory -Type String
    Set-ItemProperty -Path $key -Name 'DisplayIcon' -Value $HostPath -Type String
    Set-ItemProperty -Path $key -Name 'UninstallString' -Value $uninstallString -Type String
    Set-ItemProperty -Path $key -Name 'QuietUninstallString' -Value ($uninstallString + ' -Quiet') -Type String
    Set-ItemProperty -Path $key -Name 'InstallDate' -Value (Get-Date).ToString('yyyyMMdd') -Type String
    Set-ItemProperty -Path $key -Name 'URLInfoAbout' -Value $UrlInfoAbout -Type String
    Set-ItemProperty -Path $key -Name 'NoModify' -Value 1 -Type DWord
    Set-ItemProperty -Path $key -Name 'NoRepair' -Value 1 -Type DWord
    if ($size -gt 0) {
        Set-ItemProperty -Path $key -Name 'EstimatedSize' -Value $size -Type DWord
    }
}

function Write-LaunchShortcut {
    param(
        [Parameter(Mandatory = $true)]$Identity,
        [Parameter(Mandatory = $true)][string]$HostPath,
        [Parameter(Mandatory = $true)][string]$HostDirectory,
        [Parameter(Mandatory = $true)][string]$ShortcutFolder
    )

    $shortcutPath = Get-ShortcutPath -ShortcutName $Identity.ShortcutName -ShortcutFolder $ShortcutFolder
    New-Item -ItemType Directory -Path (Split-Path -Parent $shortcutPath) -Force | Out-Null
    if (Test-Path -LiteralPath $shortcutPath) {
        Remove-Item -LiteralPath $shortcutPath -Force
    }

    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($shortcutPath)
    $link.TargetPath = $HostPath
    $link.Arguments = $Identity.EntryArguments
    $link.WorkingDirectory = $HostDirectory
    $link.IconLocation = $HostPath + ',0'
    $link.Description = $Identity.DisplayName
    $link.Save()
    return $shortcutPath
}

function Get-ReferencedHostVersions {
    param(
        [Parameter(Mandatory = $true)][string]$RegistryPath
    )

    $versions = @{}
    $modulesKey = Join-Path $RegistryPath 'Modules'
    if (Test-Path -LiteralPath $modulesKey) {
        foreach ($key in @(Get-ChildItem -Path $modulesKey -ErrorAction SilentlyContinue)) {
            $value = (Get-ItemProperty -Path $key.PSPath -Name 'HostVersion' -ErrorAction SilentlyContinue).HostVersion
            if (-not [string]::IsNullOrWhiteSpace([string]$value)) {
                $versions[[string]$value] = $true
            }
        }
    }

    return $versions
}

function Remove-OrphanedHostDirectories {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$RegistryPath
    )

    $hostRoot = Join-Path $Root 'host'
    if (-not (Test-Path -LiteralPath $hostRoot)) {
        return
    }

    $referenced = Get-ReferencedHostVersions -RegistryPath $RegistryPath
    foreach ($directory in @(Get-ChildItem -LiteralPath $hostRoot -Directory -ErrorAction SilentlyContinue)) {
        $parsed = $null
        if (-not [version]::TryParse($directory.Name, [ref]$parsed)) {
            continue
        }

        if (-not $referenced.ContainsKey($directory.Name)) {
            try {
                Remove-Item -LiteralPath $directory.FullName -Recurse -Force
            } catch {
                # The running host may still hold its files. Leaving it is safer than failing the uninstall.
            }
        }
    }
}

function Remove-EmptyDirectory {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        $children = @(Get-ChildItem -LiteralPath $Path -Force -ErrorAction SilentlyContinue)
        if ($children.Count -eq 0) {
            Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
        }
    }
}

function Install-SharedApp {
    param(
        [Parameter(Mandatory = $true)][string]$App,
        [string]$Version,
        [string]$HostVersion,
        [string]$PayloadPath,
        [string]$Root,
        [switch]$NoShortcut
    )

    $identity = Get-SharedIdentity -App $App
    $manifest = Get-PrototypeManifest
    $shortcutFolder = [string]$manifest.ShortcutFolder
    if ([string]::IsNullOrWhiteSpace($shortcutFolder)) {
        throw 'The identity manifest does not define ShortcutFolder.'
    }

    $productVersion = Get-ProductVersion
    if ([string]::IsNullOrWhiteSpace($Version)) {
        $Version = [string]$identity.DefaultVersion
        if ([string]::IsNullOrWhiteSpace($Version)) {
            $Version = $productVersion
        }
    }

    if ([string]::IsNullOrWhiteSpace($HostVersion)) {
        $HostVersion = $productVersion
    }

    $parsedVersion = $null
    if (-not [version]::TryParse($Version, [ref]$parsedVersion)) {
        throw "Version is not a valid version number: $Version"
    }

    if (-not [version]::TryParse($HostVersion, [ref]$parsedVersion)) {
        throw "HostVersion is not a valid version number: $HostVersion"
    }

    if ([string]::IsNullOrWhiteSpace($Root)) {
        $Root = Join-Path $env:LOCALAPPDATA 'Akikazu\SharedDesktop'
    }

    if ([string]::IsNullOrWhiteSpace($PayloadPath)) {
        $PayloadPath = Join-Path $script:RepoRoot 'src\AkikazuHardwareCheck.App\bin\Release\net10.0-windows\win-x64'
    }

    $payload = (Resolve-Path -LiteralPath $PayloadPath).Path
    $payloadExecutable = Join-Path $payload $identity.PayloadExecutable
    if (-not (Test-Path -LiteralPath $payloadExecutable)) {
        throw "Payload executable not found: $payloadExecutable"
    }

    $hostDirectory = Join-Path (Join-Path $Root 'host') $HostVersion
    $hostPath = Copy-SharedPayload -PayloadPath $payload -HostDirectory $hostDirectory -PayloadExecutable $identity.PayloadExecutable
    $moduleDirectory = Join-Path (Join-Path $Root 'modules') $identity.Id
    Write-ModuleFiles -Identity $identity -ModuleDirectory $moduleDirectory -Version $Version -HostVersion $HostVersion -HostPath $hostPath -RegistryPath $script:DefaultRegistryPath -ShortcutFolder $shortcutFolder
    Write-ModuleRegistration -Identity $identity -ModuleDirectory $moduleDirectory -Version $Version -HostVersion $HostVersion -HostPath $hostPath -RegistryPath $script:DefaultRegistryPath
    Write-UninstallRegistration -Identity $identity -Version $Version -HostPath $hostPath -ModuleDirectory $moduleDirectory -Publisher ([string]$manifest.Publisher) -UrlInfoAbout ([string]$manifest.URLInfoAbout)

    $shortcutPath = $null
    if (-not $NoShortcut) {
        $shortcutPath = Write-LaunchShortcut -Identity $identity -HostPath $hostPath -HostDirectory $hostDirectory -ShortcutFolder $shortcutFolder
    }

    Remove-OrphanedHostDirectories -Root $Root -RegistryPath $script:DefaultRegistryPath

    return [pscustomobject]@{
        App = $identity.Id
        DisplayName = $identity.DisplayName
        Version = $Version
        HostVersion = $HostVersion
        HostPath = $hostPath
        ModuleDirectory = $moduleDirectory
        ShortcutPath = $shortcutPath
        UninstallKey = $identity.UninstallKey
        Root = $Root
    }
}

function Uninstall-SharedApp {
    param(
        [Parameter(Mandatory = $true)][string]$Id,
        [Parameter(Mandatory = $true)][string]$UninstallKey,
        [Parameter(Mandatory = $true)][string]$ShortcutName,
        [Parameter(Mandatory = $true)][string]$ShortcutFolder,
        [Parameter(Mandatory = $true)][string]$DisplayName,
        [string]$Root,
        [string]$RegistryPath,
        [switch]$Quiet
    )

    if ([string]::IsNullOrWhiteSpace($Root)) {
        $Root = Join-Path $env:LOCALAPPDATA 'Akikazu\SharedDesktop'
    }

    if ([string]::IsNullOrWhiteSpace($RegistryPath)) {
        $RegistryPath = $script:DefaultRegistryPath
    }

    $moduleKey = Join-Path (Join-Path $RegistryPath 'Modules') $Id
    Remove-Item -LiteralPath $moduleKey -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $script:UninstallRoot $UninstallKey) -Recurse -Force -ErrorAction SilentlyContinue

    $shortcutPath = Get-ShortcutPath -ShortcutName $ShortcutName -ShortcutFolder $ShortcutFolder
    if (Test-Path -LiteralPath $shortcutPath) {
        Remove-Item -LiteralPath $shortcutPath -Force -ErrorAction SilentlyContinue
    }

    $shortcutDirectory = Split-Path -Parent $shortcutPath
    Remove-EmptyDirectory -Path $shortcutDirectory

    $moduleDirectory = Join-Path (Join-Path $Root 'modules') $Id
    Remove-Item -LiteralPath $moduleDirectory -Recurse -Force -ErrorAction SilentlyContinue
    Remove-OrphanedHostDirectories -Root $Root -RegistryPath $RegistryPath

    $modulesKey = Join-Path $RegistryPath 'Modules'
    $remaining = @(Get-ChildItem -Path $modulesKey -ErrorAction SilentlyContinue)
    if ($remaining.Count -eq 0) {
        Remove-EmptyDirectory -Path (Join-Path $Root 'modules')
        Remove-EmptyDirectory -Path (Join-Path $Root 'host')
        Remove-EmptyDirectory -Path $Root
        Remove-Item -LiteralPath $RegistryPath -Recurse -Force -ErrorAction SilentlyContinue
    }

    if (-not $Quiet) {
        Write-Output "Uninstalled $DisplayName."
    }
}

function Get-SharedState {
    param(
        [string]$Root,
        [string]$RegistryPath
    )

    if ([string]::IsNullOrWhiteSpace($Root)) {
        $Root = Join-Path $env:LOCALAPPDATA 'Akikazu\SharedDesktop'
    }

    if ([string]::IsNullOrWhiteSpace($RegistryPath)) {
        $RegistryPath = $script:DefaultRegistryPath
    }

    $modules = @()
    $modulesKey = Join-Path $RegistryPath 'Modules'
    if (Test-Path -LiteralPath $modulesKey) {
        foreach ($key in @(Get-ChildItem -Path $modulesKey -ErrorAction SilentlyContinue)) {
            $values = Get-ItemProperty -Path $key.PSPath -ErrorAction SilentlyContinue
            $modules += [pscustomobject]@{
                Id = $key.PSChildName
                Version = $values.Version
                HostVersion = $values.HostVersion
                HostPath = $values.HostPath
                InstallRoot = $values.InstallRoot
            }
        }
    }

    $hostVersions = @()
    $hostRoot = Join-Path $Root 'host'
    if (Test-Path -LiteralPath $hostRoot) {
        $hostVersions = @(Get-ChildItem -LiteralPath $hostRoot -Directory -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name)
    }

    $shortcuts = @()
    $manifest = Get-PrototypeManifest
    foreach ($identity in @($manifest.Modules)) {
        $path = Get-ShortcutPath -ShortcutName $identity.ShortcutName -ShortcutFolder ([string]$manifest.ShortcutFolder)
        if (Test-Path -LiteralPath $path) {
            $shortcuts += $path
        }
    }

    return [pscustomobject]@{
        Modules = $modules
        HostVersions = $hostVersions
        Shortcuts = $shortcuts
        RootExists = (Test-Path -LiteralPath $Root)
        RegistryExists = (Test-Path -LiteralPath $RegistryPath)
    }
}

Export-ModuleMember -Function Install-SharedApp, Uninstall-SharedApp, Get-SharedState, Get-SharedIdentity, Get-PrototypeManifest, Get-ShortcutPath, Get-ProductVersion
