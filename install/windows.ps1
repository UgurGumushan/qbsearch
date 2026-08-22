$ErrorActionPreference = "Stop"

# Install the complete qBittorrent nova3 engine collection from this checkout
# or release archive. This script intentionally has no command-line options.

$repoRoot = Split-Path -Parent $PSScriptRoot
$pluginDirectory = Join-Path $repoRoot "plugins"
$iconDirectory = Join-Path $repoRoot "icons"

$localAppData = $env:LOCALAPPDATA
if ([string]::IsNullOrWhiteSpace($localAppData)) {
    $localAppData = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
}
if ([string]::IsNullOrWhiteSpace($localAppData)) {
    throw "LOCALAPPDATA is not set and the Windows local application-data directory could not be determined."
}

$destination = Join-Path $localAppData "qBittorrent"
$destination = Join-Path $destination "nova3"
$destination = Join-Path $destination "engines"

if (-not (Test-Path -LiteralPath $pluginDirectory -PathType Container) -or
    -not (Test-Path -LiteralPath $iconDirectory -PathType Container)) {
    throw "Could not find the plugins and icons directories next to this installer."
}

$plugins = @(Get-ChildItem -LiteralPath $pluginDirectory -Filter "*.py" -File | Sort-Object Name)
if ($plugins.Count -eq 0) {
    throw "No plugin files were found."
}

$items = New-Object 'System.Collections.Generic.List[object]'
foreach ($plugin in $plugins) {
    $null = $items.Add([PSCustomObject]@{
        Source = $plugin.FullName
        Target = Join-Path $destination $plugin.Name
        Label = $plugin.Name
        Preserve = $false
    })

    $iconPath = Join-Path $iconDirectory ($plugin.BaseName + ".ico")
    if (Test-Path -LiteralPath $iconPath -PathType Leaf) {
        $null = $items.Add([PSCustomObject]@{
            Source = $iconPath
            Target = Join-Path $destination ($plugin.BaseName + ".ico")
            Label = $plugin.BaseName + ".ico"
            Preserve = $false
        })
    }
}

$supportFiles = @(Get-ChildItem -LiteralPath $pluginDirectory -Filter "*.json" -File | Sort-Object Name)
foreach ($supportFile in $supportFiles) {
    $null = $items.Add([PSCustomObject]@{
        Source = $supportFile.FullName
        Target = Join-Path $destination $supportFile.Name
        Label = $supportFile.Name
        Preserve = $true
    })
}

$null = New-Item -ItemType Directory -Path $destination -Force
$total = $items.Count
$interactive = (-not [Console]::IsOutputRedirected) -and [string]::IsNullOrEmpty($env:CI)

function Show-InstallProgress {
    param(
        [int]$Current,
        [int]$Total,
        [string]$Message
    )

    if ($script:interactive) {
        $percent = [int](($Current * 100) / [Math]::Max($Total, 1))
        Write-Progress -Activity "Installing qBittorrent plugins" -Status $Message -PercentComplete $percent
    }
    else {
        Write-Output ("[{0}/{1}] {2}" -f $Current, $Total, $Message)
    }
}

Write-Output ("Installing {0} plugin(s) into {1}" -f $plugins.Count, $destination)
$current = 0
foreach ($item in $items) {
    $current++
    if ($item.Preserve -and (Test-Path -LiteralPath $item.Target)) {
        Show-InstallProgress $current $total ("preserved " + $item.Label)
        continue
    }

    Copy-Item -LiteralPath $item.Source -Destination $item.Target -Force
    Show-InstallProgress $current $total $item.Label
}

if ($interactive) {
    Write-Progress -Activity "Installing qBittorrent plugins" -Completed
}
Write-Output ("Installed {0} file(s) into {1}" -f $total, $destination)
Write-Output "Done. Quit and relaunch qBittorrent if it was running."
