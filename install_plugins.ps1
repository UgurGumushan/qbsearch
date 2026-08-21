$ErrorActionPreference = "Stop"
$repoDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonCommand = Get-Command py -ErrorAction SilentlyContinue
if ($null -eq $pythonCommand) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
}
if ($null -eq $pythonCommand) {
    throw "Python 3 was not found. Install Python 3.9 or newer, then run this script again."
}
& $pythonCommand.Source "$repoDir\scripts\install_plugins.py" @args
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
