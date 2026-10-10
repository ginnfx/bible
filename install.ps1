# Installs the latest `bible` on Windows 10/11 - no Python, no admin rights.
#
#   irm https://raw.githubusercontent.com/ginnfx/bible/main/install.ps1 | iex
#
# Downloads the same installer the Releases page offers and runs it
# silently, so both routes end up identical: bible.exe in
# %LOCALAPPDATA%\Programs\Bible, on your PATH, in the Start menu, and
# removable from Settings > Apps.

# Wrapped in a script block so `iex` doesn't leave these preferences and
# variables behind in the caller's session.
& {
    $ErrorActionPreference = "Stop"
    $ProgressPreference = "SilentlyContinue"  # Invoke-WebRequest is far slower with the progress bar

    $repo = "ginnfx/bible"
    $asset = "bible-windows-x86_64-setup.exe"
    $url = "https://github.com/$repo/releases/latest/download/$asset"

    if (-not [Environment]::Is64BitOperatingSystem) {
        Write-Host "bible needs 64-bit Windows." -ForegroundColor Red
        return
    }

    # Windows PowerShell 5.1 can default to TLS 1.0, which GitHub refuses.
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

    $installer = Join-Path $env:TEMP $asset
    Write-Host "Downloading bible..."
    try {
        Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
    } catch {
        Write-Host "Couldn't download $url - check https://github.com/$repo/releases ($_)" -ForegroundColor Red
        return
    }

    Write-Host "Installing..."
    $process = Start-Process -FilePath $installer -Wait -PassThru `
        -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"
    Remove-Item $installer -ErrorAction SilentlyContinue
    if ($process.ExitCode -ne 0) {
        Write-Host "The installer exited with code $($process.ExitCode)." -ForegroundColor Red
        return
    }

    # The installer updates the user PATH for new terminals; make `bible` work
    # in this one too without reopening it.
    $installDir = Join-Path $env:LOCALAPPDATA "Programs\Bible"
    if (($env:Path -split ";") -notcontains $installDir) {
        $env:Path = "$env:Path;$installDir"
    }

    Write-Host ""
    Write-Host "Installed. Run: bible   (or open 'Bible' from the Start menu)"
}
