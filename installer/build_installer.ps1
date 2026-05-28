<#
.SYNOPSIS
    Builds the portable .exe and the Inno Setup installer .exe.

.DESCRIPTION
    End-to-end pipeline:
      1. (Re)create the local Python virtualenv if missing.
      2. pip install -r requirements.txt.
      3. PyInstaller produces UsageMonitorForClaude.exe (the portable build).
      4. Stage payload (EXE + LICENSE) into the Inno Setup payload folder.
      5. ISCC compiles setup.iss into the installer .exe.
      6. Print SHA-256 + size for both artifacts and where to find them.

    The build workspace lives OUTSIDE the repo (default: ~/Apps/UsageMonitorForClaude-build)
    so build artefacts never pollute the source tree.

    From the produced artifacts, upload to GitHub Releases manually:
        portable:  UsageMonitorForClaude.exe
        installer: UsageMonitorForClaude-Setup-v<version>.exe

.PARAMETER BuildDir
    Override the local build workspace path.

.PARAMETER SkipPyInstaller
    Reuse the existing portable EXE in the build workspace and only
    re-run Inno Setup.  Useful when only the .iss or branding changed.

.PARAMETER Iscc
    Override the path to ISCC.exe.  Default: auto-detect.

.EXAMPLE
    .\build_installer.ps1
        Full build from source.

.EXAMPLE
    .\build_installer.ps1 -SkipPyInstaller
        Skip Python build, only rebuild the installer.
#>
[CmdletBinding()]
param(
    [string]$BuildDir = "$env:USERPROFILE\Apps\UsageMonitorForClaude-build",
    [switch]$SkipPyInstaller,
    [string]$Iscc
)

$ErrorActionPreference = 'Stop'

$scriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$projectDir  = Split-Path -Parent $scriptDir

$venvDir     = Join-Path $BuildDir '.venv'
$pyExe       = Join-Path $venvDir  'Scripts\python.exe'
$piBuildDir  = Join-Path $BuildDir 'pyinstaller-build'
$piDistDir   = Join-Path $BuildDir 'pyinstaller-dist'
$portableExe = Join-Path $piDistDir 'UsageMonitorForClaude.exe'
$payloadDir  = Join-Path $BuildDir 'installer-payload'
$outputDir   = Join-Path $BuildDir 'installer-output'

$specFile    = Join-Path $projectDir 'usage_monitor_for_claude.spec'
$reqFile     = Join-Path $projectDir 'requirements.txt'
$licenseFile = Join-Path $projectDir 'LICENSE'
$issFile     = Join-Path $scriptDir  'setup.iss'

function Write-Section([string]$msg) {
    Write-Host ''
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Find-Iscc {
    if ($Iscc) {
        if (-not (Test-Path $Iscc)) { throw "ISCC override not found: $Iscc" }
        return $Iscc
    }
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }
    throw 'ISCC.exe not found. Install Inno Setup 6 first: winget install JRSoftware.InnoSetup'
}

function Ensure-Dir([string]$path) {
    if (-not (Test-Path $path)) { New-Item -ItemType Directory -Path $path -Force | Out-Null }
}

# -------------------- Main --------------------

Write-Section 'Build paths'
Write-Host "  Source:        $projectDir"
Write-Host "  Build dir:     $BuildDir"
Write-Host "  Portable EXE:  $portableExe"
Write-Host "  Installer EXE: $outputDir\UsageMonitorForClaude-Setup-v<version>.exe"

Ensure-Dir $BuildDir
Ensure-Dir $payloadDir
Ensure-Dir $outputDir

if (-not $SkipPyInstaller) {
    Write-Section 'Ensuring local virtualenv'
    if (-not (Test-Path $pyExe)) {
        Write-Host '  .venv missing, creating it now.'
        $py = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($py) {
            & $py.Source -3 -m venv $venvDir
        } else {
            $sysPy = Get-Command python.exe -ErrorAction SilentlyContinue
            if (-not $sysPy) { throw 'No Python found on PATH. Install Python 3.11 or newer first.' }
            & $sysPy.Source -m venv $venvDir
        }
    } else {
        Write-Host '  .venv exists, reusing.'
    }

    Write-Section 'Installing dependencies'
    & $pyExe -m pip install --upgrade pip --disable-pip-version-check -q
    & $pyExe -m pip install -r $reqFile --disable-pip-version-check -q

    Write-Section 'PyInstaller (portable EXE)'
    Push-Location $projectDir
    try {
        & $pyExe -m PyInstaller $specFile `
            --workpath $piBuildDir `
            --distpath $piDistDir  `
            --clean --noconfirm
    } finally {
        Pop-Location
    }
    if (-not (Test-Path $portableExe)) { throw "PyInstaller failed: $portableExe was not created." }
}

if (-not (Test-Path $portableExe)) {
    throw "Portable EXE not found at $portableExe. Re-run without -SkipPyInstaller."
}

Write-Section 'Staging payload for Inno Setup'
Copy-Item -Path $portableExe -Destination $payloadDir -Force
Copy-Item -Path $licenseFile -Destination (Join-Path $payloadDir 'LICENSE.txt') -Force

Write-Section 'Compiling setup.iss'
$iscc = Find-Iscc
Write-Host "  ISCC: $iscc"
& $iscc `
    "/DPayloadDir=$payloadDir" `
    "/DOutputDirOverride=$outputDir" `
    $issFile

$installer = Get-ChildItem -Path $outputDir -Filter 'UsageMonitorForClaude-Setup-v*.exe' -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $installer) { throw "No installer EXE found in $outputDir" }

# -------------------- Summary --------------------

Write-Section 'Build artifacts'
$portableInfo = Get-Item $portableExe
$portableHash = (Get-FileHash $portableExe -Algorithm SHA256).Hash
$installerHash = (Get-FileHash $installer.FullName -Algorithm SHA256).Hash

[PSCustomObject]@{
    Artifact = 'Portable EXE'
    Path     = $portableExe
    SizeMB   = [Math]::Round($portableInfo.Length / 1MB, 2)
    SHA256   = $portableHash
} | Format-List

[PSCustomObject]@{
    Artifact = 'Installer EXE'
    Path     = $installer.FullName
    SizeMB   = [Math]::Round($installer.Length / 1MB, 2)
    SHA256   = $installerHash
} | Format-List

Write-Host 'Both artifacts are ready.  Upload them to a GitHub Releases tag manually,' -ForegroundColor Green
Write-Host 'either through the web UI or with: gh release create v<version> ...'      -ForegroundColor Green
