param(
    [ValidateSet('host','target','electronics','mechanical','render','all')][string]$Action = 'all',
    [Parameter(Mandatory=$true)][string]$BuildRoot
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
if (!(Test-Path -LiteralPath "$root/.venv/Scripts/python.exe")) { throw 'Run uv venv --python 3.12, then uv sync --frozen first.' }
if ($Action -in @('host','all') -and !(Get-Command cl.exe -ErrorAction SilentlyContinue)) {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    $vs = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if (!$vs) { throw 'Install Visual Studio C++ tools or run in its developer PowerShell.' }
    & (Join-Path $vs 'Common7/Tools/Launch-VsDevShell.ps1') -Arch amd64 -HostArch amd64 | Out-Null
}
& "$root/.venv/Scripts/python.exe" -X utf8 "$PSScriptRoot/engineering.py" $Action --build-root $BuildRoot
if ($LASTEXITCODE -ne 0) { throw "Engineering validation failed with exit code $LASTEXITCODE" }
