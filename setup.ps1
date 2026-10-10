# Sets up bible from source on Windows - the PowerShell twin of setup.sh.
#
#   powershell -ExecutionPolicy Bypass -File setup.ps1
#
# Most people want install.ps1 or the installer from the Releases page
# instead; this is for running (and hacking on) the code itself.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Native commands don't throw on failure, even with ErrorActionPreference
# set, so every one goes through here.
function Invoke-Checked {
    param([string]$Command, [string[]]$Arguments)
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "'$Command $($Arguments -join ' ')' failed with exit code $LASTEXITCODE"
    }
}

function Find-Python {
    # The `py` launcher is what python.org installs; `python` may instead be
    # the Microsoft Store stub, which the version check below rejects.
    $candidates = @(
        @{ Command = "py"; Prefix = @("-3") },
        @{ Command = "python"; Prefix = @() }
    )
    # Windows PowerShell turns a native command's stderr into a terminating
    # error under "Stop", and the Store stub writes to stderr.
    $ErrorActionPreference = "Continue"
    foreach ($candidate in $candidates) {
        if (-not (Get-Command $candidate.Command -ErrorAction SilentlyContinue)) { continue }
        $prefix = $candidate.Prefix
        & $candidate.Command @prefix -c "import sys; sys.exit(sys.version_info < (3, 11))" 2>$null
        if ($LASTEXITCODE -eq 0) { return $candidate }
    }
    return $null
}

Write-Host "Setting up bible...."

$python = Find-Python
if ($null -eq $python) {
    Write-Error "Python 3.11 or newer is required: https://www.python.org/downloads/windows/"
    exit 1
}
$pythonArgs = $python.Prefix
$version = & $python.Command @pythonArgs -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"
Write-Host "Python $version found"

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    Invoke-Checked $python.Command ($pythonArgs + @("-m", "venv", ".venv"))
}

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
Invoke-Checked $venvPython @("-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel")
Invoke-Checked $venvPython @("-m", "pip", "install", "-r", "requirements.txt")
Invoke-Checked $venvPython @("-m", "pip", "install", "-e", ".")

$database = Join-Path $env:APPDATA "bible-tui\bible.db"
if (-not (Test-Path $database)) {
    Write-Host "Importing Bible data (this may take a minute)..."
    Invoke-Checked $venvPython @("scripts\import_data.py")
} else {
    Write-Host "Bible data already exists at $database"
}

Write-Host ""
Write-Host "Setup complete."
Write-Host ""
Write-Host "To run the app:"
Write-Host "  1. Activate the virtual environment: .venv\Scripts\Activate.ps1"
Write-Host "  2. Launch: bible"
Write-Host ""
Write-Host "Other commands:"
Write-Host "  bible read `"John 3:16`"        # read a verse, range, or chapter"
Write-Host "  bible search `"love one another`""
Write-Host "  bible today                   # verse of the day"
Write-Host "  bible --help"
Write-Host ""
