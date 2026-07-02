# TeamsX build script (ASCII only - PS 5.1 safe)
param(
    [switch]$PortableOnly,
    [switch]$SkipEnv,
    [string]$IsccPath
)

function Find-InnoIscc {
    param([string]$Override)

    if ($Override -and (Test-Path -LiteralPath $Override)) {
        return (Resolve-Path -LiteralPath $Override).Path
    }

    if ($env:INNO_SETUP_PATH) {
        $fromEnv = Join-Path $env:INNO_SETUP_PATH "ISCC.exe"
        if (Test-Path -LiteralPath $fromEnv) {
            return (Resolve-Path -LiteralPath $fromEnv).Path
        }
    }

    $cmd = Get-Command iscc -ErrorAction SilentlyContinue
    if ($cmd -and (Test-Path -LiteralPath $cmd.Source)) {
        return $cmd.Source
    }

    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:LocalAppData "Programs\Inno Setup 6\ISCC.exe")
    )
    foreach ($p in $candidates) {
        if (Test-Path -LiteralPath $p) {
            return (Resolve-Path -LiteralPath $p).Path
        }
    }

    $regRoots = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )
    foreach ($regRoot in $regRoots) {
        try {
            $items = Get-ItemProperty $regRoot -ErrorAction SilentlyContinue |
                Where-Object { $_.DisplayName -match "Inno Setup 6" }
            foreach ($item in $items) {
                if ($item.InstallLocation) {
                    $c = Join-Path $item.InstallLocation.TrimEnd("\") "ISCC.exe"
                    if (Test-Path -LiteralPath $c) {
                        return (Resolve-Path -LiteralPath $c).Path
                    }
                }
                if ($item.UninstallString) {
                    $dir = Split-Path ($item.UninstallString -replace '"', "") -Parent
                    $c = Join-Path $dir "ISCC.exe"
                    if (Test-Path -LiteralPath $c) {
                        return (Resolve-Path -LiteralPath $c).Path
                    }
                }
            }
        }
        catch {
        }
    }

    return $null
}

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$LogFile = Join-Path $Root "build.log"
$script:TranscriptOn = $false
try {
    if (Test-Path -LiteralPath $LogFile) {
        Remove-Item -LiteralPath $LogFile -Force -ErrorAction SilentlyContinue
    }
    Start-Transcript -Path $LogFile -Force -ErrorAction Stop | Out-Null
    $script:TranscriptOn = $true
}
catch {
    Write-Host "Note: build.log transcript skipped (continuing build)."
}

# folder name: TeamsX_纯净版 (built from char codes, no UTF-8 in this file)
$PortableSuffix = -join ([char]0x7EAF, [char]0x51C0, [char]0x7248)
$PortableFolder = "TeamsX_" + $PortableSuffix

$Venv = Join-Path $Root ".venv-build"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$Spec = Join-Path $Root "TeamsX.spec"
$Dist = Join-Path $Root "dist\TeamsX"
$Release = Join-Path $Root "release"
$PortableOut = Join-Path $Release $PortableFolder

if (-not (Test-Path -LiteralPath (Join-Path $Root "logo.ico"))) {
    throw "Missing icon: $Root\logo.ico"
}

$AudioDir = Join-Path $Root "audio"
$NotifyMp3 = Join-Path $AudioDir "teams_notify_official.mp3"
$CallMp3 = Join-Path $AudioDir "video.mp3"
if (-not (Test-Path -LiteralPath $NotifyMp3)) {
    throw "Missing notify sound: $NotifyMp3 (create audio folder before build)"
}
if (-not (Test-Path -LiteralPath $CallMp3)) {
    throw "Missing call notify sound: $CallMp3 (place video.mp3 in audio folder)"
}

if (-not $SkipEnv) {
    & (Join-Path $Root "setup_build_env.ps1")
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Build venv python not found. Run setup_build_env.ps1 first."
}

Write-Host "=== PyInstaller ==="
$buildDir = Join-Path $Root "build"
$distDir = Join-Path $Root "dist"
if (Test-Path -LiteralPath $buildDir) {
    Remove-Item -LiteralPath $buildDir -Recurse -Force
}
if (Test-Path -LiteralPath $distDir) {
    Remove-Item -LiteralPath $distDir -Recurse -Force
}

# PyInstaller logs to stderr; with ErrorActionPreference=Stop that would abort the build.
# Relax it for this call and rely on the exit code instead.
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $VenvPython -m PyInstaller $Spec --noconfirm --clean 2>&1 | Out-Host
$piExit = $LASTEXITCODE
$ErrorActionPreference = $prevEAP
if ($piExit -ne 0) {
    throw "PyInstaller exited with code $piExit"
}
$builtExe = Join-Path $Dist "TeamsX.exe"
if (-not (Test-Path -LiteralPath $builtExe)) {
    throw "Build failed: dist\TeamsX\TeamsX.exe was not created."
}

Write-Host "=== Bundle audio (next to TeamsX.exe) ==="
$DistAudio = Join-Path $Dist "audio"
if (Test-Path -LiteralPath $DistAudio) {
    Remove-Item -LiteralPath $DistAudio -Recurse -Force
}
Copy-Item -LiteralPath $AudioDir -Destination $DistAudio -Recurse -Force
Write-Host "Audio: $DistAudio"

$LogoIco = Join-Path $Root "logo.ico"
if (Test-Path -LiteralPath $LogoIco) {
    Copy-Item -LiteralPath $LogoIco -Destination (Join-Path $Dist "logo.ico") -Force
    Write-Host "Icon: $(Join-Path $Dist 'logo.ico')"
}
else {
    Write-Warning "Missing logo.ico — tray icon may fall back to default."
}

Write-Host "=== Portable package ==="
if (Test-Path -LiteralPath $PortableOut) {
    Remove-Item -LiteralPath $PortableOut -Recurse -Force
}
New-Item -ItemType Directory -Path $Release -Force | Out-Null
Copy-Item -LiteralPath $Dist -Destination $PortableOut -Recurse
Write-Host "Portable: $PortableOut"

if ($PortableOnly) {
    Write-Host "Done (portable only)."
    if ($script:TranscriptOn) { Stop-Transcript | Out-Null }
    exit 0
}

Write-Host "=== Inno Setup 6 installer ==="
$Iscc = Find-InnoIscc -Override $IsccPath
if (-not $Iscc) {
    throw "ISCC.exe not found. Install Inno Setup 6 or use -IsccPath."
}

Write-Host "Inno Setup: $Iscc"
$Iss = Join-Path $Root "TeamsX_setup.iss"
& $Iscc $Iss
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE"
}

$Setup = Get-ChildItem -Path $Release -Filter "TeamsX_Setup_*.exe" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if ($Setup) {
    Write-Host "Installer: $($Setup.FullName)"
}
else {
    Write-Warning "Inno Setup finished but TeamsX_Setup_*.exe was not found in release."
}

Write-Host ""
Write-Host "All done."
Write-Host "  Portable: $PortableOut"
if ($Setup) {
    Write-Host "  Installer: $($Setup.FullName)"
}
if ($script:TranscriptOn) { Stop-Transcript | Out-Null }
if (Test-Path -LiteralPath $LogFile) {
    Write-Host "  Log: $LogFile"
}
