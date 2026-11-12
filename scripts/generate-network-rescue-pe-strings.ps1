param([Parameter(Mandatory)] [string]$Destination)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$languages = 'en-US', 'ja-JP', 'zh-CN', 'zh-TW'
$translations = foreach ($language in $languages) {
    $path = Join-Path $root "src/AkikazuHardwareCheck.Core/Localization/$language.json"
    Get-Content -LiteralPath $path -Raw | ConvertFrom-Json -AsHashtable
}
$prefix = 'rescue.pe.'
$version = ([xml](Get-Content (Join-Path $root 'Directory.Build.props') -Raw)).Project.PropertyGroup.Version
$keys = [ordered]@{
    homeTitle = 'rescue.heading'
    homeNetwork = 'rescue.network'
    homeScan = 'rescue.refresh'
    homeHelp = 'ui.menuHelp'
    homeGuide = 'ui.guide'
    homeAbout = 'ui.about'
}
foreach ($key in $translations[0].Keys | Where-Object { $_.StartsWith($prefix) }) {
    $keys.Add($key.Substring($prefix.Length), $key)
}
@(
    'static constexpr wchar_t peVersion[] = L"' + $version + '";'
    'struct PeText {'
    foreach ($field in $keys.Keys) { "    const wchar_t* $field;" }
    '};'
    'static constexpr PeText peText[] = {'
    foreach ($translation in $translations) {
        '    {'
        foreach ($key in $keys.Values) {
            if (!$translation.Contains($key)) { throw "Missing PE translation: $key" }
            '        L' + (ConvertTo-Json -InputObject $translation[$key] -Compress) + ','
        }
        '    },'
    }
    '};'
) | Set-Content -LiteralPath $Destination -Encoding utf8
