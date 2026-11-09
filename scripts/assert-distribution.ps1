param(
    [Parameter(Mandatory = $true)]
    [string]$AssemblyPath,

    [Parameter(Mandatory = $true)]
    [ValidateSet('Website', 'Store')]
    [string]$ExpectedChannel,

    [Parameter(Mandatory = $true)]
    [ValidateSet('Present', 'Absent')]
    [string]$ExpectedPawnIo
)

$ErrorActionPreference = 'Stop'

$assembly = [System.Reflection.Assembly]::LoadFile((Resolve-Path $AssemblyPath).Path)
$resources = $assembly.GetManifestResourceNames()
$hasPawnIo = $resources -contains 'pawnio.setup.exe'
$pawnIoExpected = $ExpectedPawnIo -eq 'Present'
if ($hasPawnIo -ne $pawnIoExpected) {
    throw "PawnIO resource mismatch. Expected=$pawnIoExpected Actual=$hasPawnIo"
}

$channel = $assembly.GetCustomAttributesData() |
    Where-Object { $_.AttributeType.Name -eq 'AssemblyMetadataAttribute' } |
    Where-Object { $_.ConstructorArguments[0].Value -eq 'DistributionChannel' } |
    ForEach-Object { $_.ConstructorArguments[1].Value }
if ($channel -ne $ExpectedChannel) {
    throw "Unexpected distribution channel: $channel"
}

Write-Output "Distribution assertion: $channel, PawnIO=$hasPawnIo"
