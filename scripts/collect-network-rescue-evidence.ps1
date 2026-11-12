<#
.SYNOPSIS
Records one stage of a physical Network Rescue acceptance run as JSON.

.DESCRIPTION
Run it on the machine under test before the rescue (missing driver), after the driver install and
after any restart. It reads PCI/USB network devices, the bound driver, address and gateway state,
then optionally tries DNS and HTTPS. It does not install, remove or disable anything.

Privacy: no MAC address, IP address, SSID, host name, user name, serial number or device instance
ID is written. USB instance IDs can contain serial numbers, so only hardware IDs are kept.
Runs on Windows PowerShell 5.1 so it works on a clean Windows 10 or 11 install.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('baseline', 'after-install', 'after-restart')]
    [string]$Stage,

    # Free text such as "win11-home-wifi-running-os"; keep customer data out of it.
    [Parameter(Mandatory)]
    [ValidatePattern('^[A-Za-z0-9._-]{1,64}$')]
    [string]$Scenario,

    [string]$OutputDirectory = (Get-Location).Path,

    [string]$DnsName = 'www.microsoft.com',

    [string]$ProbeUrl = 'https://www.microsoft.com/',

    [switch]$SkipConnectivity
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0

# Same limit the desktop speed test uses for a single request.
$PROBE_TIMEOUT_MS = 15000
$SCHEMA_VERSION = 1
$PROBLEM_CODE_NOT_INSTALLED = 28

function Test-NetworkHardware([string[]]$HardwareIds, [string[]]$CompatibleIds, [string]$SetupClass, [int]$ProblemCode) {
    $ids = @($HardwareIds) + @($CompatibleIds)
    $isPci = @($HardwareIds | Where-Object { $_ -like 'PCI\VEN_*' }).Count -gt 0
    if ($isPci) {
        # PCI base class 02: 0200 Ethernet, 0280 other network (Wi-Fi).
        return @($ids | Where-Object { $_ -match '(?i)^PCI\\(.*&)?CC_02(00|80)' }).Count -gt 0
    }

    $isUsb = @($HardwareIds | Where-Object { $_ -match '(?i)^USB\\VID_[0-9A-F]{4}&PID_' }).Count -gt 0
    if (!$isUsb) { return $false }
    if ($SetupClass -eq 'Net') { return $true }
    return $ProblemCode -eq $PROBLEM_CODE_NOT_INSTALLED -and ([string]::IsNullOrEmpty($SetupClass) -or $SetupClass -eq 'Unknown')
}

function Get-AddressKind([string]$Address) {
    if ($Address -like '169.254.*') { return 'ipv4-link-local' }
    if ($Address -match '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.|100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.)') {
        return 'ipv4-private'
    }
    if ($Address -match '^\d+\.\d+\.\d+\.\d+$') { return 'ipv4-public' }
    if ($Address -like 'fe80:*') { return 'ipv6-link-local' }
    if ($Address -match '^(?i)f[cd]') { return 'ipv6-unique-local' }
    return 'ipv6-global'
}

function Get-AdapterState([string]$PnpDeviceId) {
    # One device can own stale "Not Present" interfaces and hidden Wi-Fi Direct ones; prefer the live one.
    $adapter = Get-NetAdapter -ErrorAction SilentlyContinue |
        Where-Object { $_.PnPDeviceID -eq $PnpDeviceId } |
        Sort-Object @{ Expression = { $_.Status -eq 'Up' }; Descending = $true },
            @{ Expression = { $_.Status -ne 'Not Present' }; Descending = $true } |
        Select-Object -First 1
    if ($null -eq $adapter) { return $null }

    $addresses = @(Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -ErrorAction SilentlyContinue |
        ForEach-Object { Get-AddressKind $_.IPAddress } | Sort-Object -Unique)
    $routes = @(Get-NetRoute -InterfaceIndex $adapter.ifIndex -ErrorAction SilentlyContinue |
        Where-Object { $_.DestinationPrefix -in @('0.0.0.0/0', '::/0') })
    $dnsServerCount = @(Get-DnsClientServerAddress -InterfaceIndex $adapter.ifIndex -ErrorAction SilentlyContinue |
        ForEach-Object { $_.ServerAddresses }).Count

    [ordered]@{
        status            = [string]$adapter.Status
        mediaType         = [string]$adapter.PhysicalMediaType
        linkSpeed         = [string]$adapter.LinkSpeed
        addressKinds      = $addresses
        hasIpv4Gateway    = @($routes | Where-Object { $_.DestinationPrefix -eq '0.0.0.0/0' }).Count -gt 0
        hasIpv6Gateway    = @($routes | Where-Object { $_.DestinationPrefix -eq '::/0' }).Count -gt 0
        dnsServerCount    = $dnsServerCount
    }
}

function Get-NetworkDevices {
    $signed = @{}
    Get-CimInstance Win32_PnPSignedDriver -ErrorAction SilentlyContinue | Where-Object { $_.DeviceID } |
        ForEach-Object { $signed[$_.DeviceID] = $_ }

    foreach ($entity in Get-CimInstance Win32_PnPEntity -Filter 'Present = TRUE') {
        $hardwareIds = @($entity.HardwareID | Where-Object { $_ })
        $compatibleIds = @($entity.CompatibleID | Where-Object { $_ })
        $problemCode = [int]$entity.ConfigManagerErrorCode
        if (!(Test-NetworkHardware $hardwareIds $compatibleIds $entity.PNPClass $problemCode)) { continue }

        $driver = $signed[$entity.PNPDeviceID]
        $driverInfo = $null
        if ($null -ne $driver -and $driver.InfName) {
            $driverInfo = [ordered]@{
                infName  = [string]$driver.InfName
                version  = [string]$driver.DriverVersion
                provider = [string]$driver.DriverProviderName
                isSigned = [bool]$driver.IsSigned
                signer   = [string]$driver.Signer
            }
        }

        [ordered]@{
            name          = [string]$entity.Name
            setupClass    = [string]$entity.PNPClass
            service       = [string]$entity.Service
            problemCode   = $problemCode
            hardwareIds   = $hardwareIds
            compatibleIds = @($compatibleIds | Where-Object { $_ -like 'PCI\VEN_*' -or $_ -like 'USB\*' })
            driver        = $driverInfo
            adapter       = Get-AdapterState $entity.PNPDeviceID
        }
    }
}

function Test-Connectivity {
    $result = [ordered]@{ dnsName = $DnsName; dnsResolved = $false; probeUrl = $ProbeUrl; httpsStatus = $null; error = $null }
    try {
        $result.dnsResolved = @(Resolve-DnsName -Name $DnsName -DnsOnly -QuickTimeout -ErrorAction Stop).Count -gt 0
    } catch {
        $result.error = 'dns: ' + $_.Exception.GetType().Name
        return $result
    }

    try {
        # Windows PowerShell 5.1 may default to TLS 1.0 on older Windows 10 builds.
        $protocol = [Net.ServicePointManager]::SecurityProtocol
        if ($protocol -ne [Net.SecurityProtocolType]::SystemDefault -and !($protocol -band [Net.SecurityProtocolType]::Tls12)) {
            [Net.ServicePointManager]::SecurityProtocol = $protocol -bor [Net.SecurityProtocolType]::Tls12
        }
        $request = [Net.HttpWebRequest]::Create($ProbeUrl)
        $request.Method = 'GET'
        # Some sites answer 403 to requests without a user agent.
        $request.UserAgent = 'NetworkRescueEvidence/1'
        $request.Timeout = $PROBE_TIMEOUT_MS
        $request.AllowAutoRedirect = $false
        $response = $request.GetResponse()
        try { $result.httpsStatus = [int]$response.StatusCode } finally { $response.Close() }
    } catch [Net.WebException] {
        if ($null -ne $_.Exception.Response) {
            $result.httpsStatus = [int]$_.Exception.Response.StatusCode
        } else {
            $result.error = 'https: ' + [string]$_.Exception.Status
        }
    }
    return $result
}

$os = Get-CimInstance Win32_OperatingSystem
$version = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
$ubr = $null
if ($version.PSObject.Properties.Name -contains 'UBR') { $ubr = [int]$version.UBR }
$connectivity = $null
if (!$SkipConnectivity) { $connectivity = Test-Connectivity }

$report = [ordered]@{
    schemaVersion = $SCHEMA_VERSION
    stage         = $Stage
    scenario      = $Scenario
    recordedAtUtc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    windows       = [ordered]@{
        caption      = [string]$os.Caption
        editionId    = [string]$version.EditionID
        displayVersion = [string]$version.DisplayVersion
        build        = [int]$os.BuildNumber
        ubr          = $ubr
        architecture = [string]$os.OSArchitecture
        isWinPE      = Test-Path 'HKLM:\SYSTEM\CurrentControlSet\Control\MiniNT'
    }
    devices       = @(Get-NetworkDevices)
    connectivity  = $connectivity
}

$OutputDirectory = (Resolve-Path -LiteralPath $OutputDirectory).Path
$fileName = 'network-rescue-evidence-{0}-{1}-{2}.json' -f $Scenario, $Stage, (Get-Date -Format 'yyyyMMdd-HHmmss')
$path = Join-Path $OutputDirectory $fileName
$json = $report | ConvertTo-Json -Depth 6
[IO.File]::WriteAllText($path, $json, (New-Object Text.UTF8Encoding($false)))
Write-Output $path
