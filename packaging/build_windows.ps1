# Builds the standalone Windows `bible.exe`, natively, on a Windows machine -
# and, if Inno Setup is installed, the double-click installer around it.
#
#   powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
#
# Uses Nuitka, same as build_macos.sh. Nuitka needs a C compiler; with
# --assume-yes-for-downloads it fetches one itself if Visual Studio's
# isn't installed.

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

function Invoke-Checked {
    param([string]$Command, [string[]]$Arguments)
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "'$Command' failed with exit code $LASTEXITCODE"
    }
}

if (-not (Test-Path ".venv")) {
    Invoke-Checked "py" @("-3", "-m", "venv", ".venv")
}
$venvPython = ".venv\Scripts\python.exe"
Invoke-Checked $venvPython @("-m", "pip", "install", "--quiet", "-e", ".[packaging]")

Write-Host "Building seed database (content only - your reading data is stripped)..."
Invoke-Checked $venvPython @("scripts\build_seed_db.py")

Invoke-Checked $venvPython @(
    "-m", "nuitka",
    "--onefile",
    "--output-dir=dist\windows",
    "--output-filename=bible.exe",
    "--include-data-file=bible_tui/data/schema.sql=bible_tui/data/schema.sql",
    "--include-data-file=bible_tui/ui/themes.tcss=bible_tui/ui/themes.tcss",
    "--include-data-file=packaging/seed/bible.db=seed/bible.db",
    "--assume-yes-for-downloads",
    "--remove-output",
    "packaging/entry_point.py"
)
Write-Host "Windows build: dist\windows\bible.exe"

$iscc = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
if (Test-Path $iscc) {
    Invoke-Checked $iscc @("packaging\windows\bible.iss")
    Write-Host "Windows installer: dist\windows\bible-windows-x86_64-setup.exe"
} else {
    Write-Host "Inno Setup 6 not found - skipping the installer (winget install JRSoftware.InnoSetup)."
}
