<#
.SYNOPSIS
    Build the NovoTree Windows installer (novotree-X.Y.Z-setup.exe).

.DESCRIPTION
    Full packaging pipeline -- run this once to produce a distributable installer:

      Step 1  python version.py
              Reads __version__ from version.py and writes two build artifacts:
                installer/version.iss        -- Inno Setup version #define
                installer/version_info.txt   -- Windows VERSIONINFO resource
                                               (embedded in the .exe by PyInstaller)

      Step 2  npm run build  (in frontend/)
              Vite produces the SPA bundle at frontend/dist/.  PyInstaller
              packs this folder into the exe so the FastAPI backend can serve
              the UI as static files when running in local mode.

      Step 3  pyinstaller installer\novotree.spec
              Bundles the Python app + all dependencies (FastAPI, uvicorn,
              SQLAlchemy, pywebview, ...) plus the frontend/dist/ tree into a
              self-contained folder.  Build artifacts are kept under installer/
              so the repo root stays clean:
                installer/build/   -- intermediate files (cached for re-runs)
                installer/dist/novotree/novotree.exe

      Step 4  iscc installer\novotree.iss
              Inno Setup Compiler packages installer/dist/novotree/ into a
              single installer executable:
                installer/Output/novotree-X.Y.Z-setup.exe

.PREREQUISITES
    pip install pyinstaller pywebview platformdirs
    Node.js 20+ (for `npm run build`)

    Inno Setup 6.7.1 -- the --location flag is required; without it winget installs
    to a path that cannot be resolved by scripts:

        winget install --id JRSoftware.InnoSetup `
            --location "C:\Program Files\Inno Setup 6" `
            --accept-package-agreements --accept-source-agreements

    Installs ISCC.exe to: C:\Program Files\Inno Setup 6\ISCC.exe
    This script auto-discovers that path -- no PATH changes needed.

.USAGE
    From the repo root in PowerShell:
        .\installer\build.ps1

    Skip the frontend rebuild when only backend changed:
        .\installer\build.ps1 -SkipFrontend

    Skip PyInstaller too when only the .iss script changed:
        .\installer\build.ps1 -SkipFrontend -SkipPyInstaller
#>

param(
    [switch]$SkipFrontend,
    [switch]$SkipPyInstaller
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# -- Locate repo root (one level up from this script) -------------------------
$RepoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $RepoRoot

# -- Pin the Python interpreter to venv-win\Scripts\python.exe ---------------
# Resolved via absolute path, NOT through PATH. This matters because:
#   1. If the user runs build.ps1 without activating the venv, `python` /
#      `pyinstaller` from PATH may be the system / Microsoft Store Python
#      with a DIFFERENT (often older) PyInstaller installed in its user-site.
#      We saw a 6.11.1 leak from MSIX Python's user-site that produced bundles
#      crashing with "PyiFrozenImporter has no attribute …" at runtime.
#   2. By calling the venv python directly and using `-m PyInstaller`, we
#      bypass any PATH lookup entirely.
#   3. PYTHONNOUSERSITE=1 plugs the second leakage path: even the venv python
#      reads the base interpreter's user-site by default, and we don't want
#      a stray `pip install --user pyinstaller` to corrupt our build.
$VenvPython = Join-Path $RepoRoot "venv-win\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Error @"

venv-win not found at:
  $VenvPython

Create it once with (run from $RepoRoot):
  python -m venv venv-win
  .\venv-win\Scripts\Activate.ps1
  pip install -r requirements.txt
  pip install pyinstaller

"@
}
$env:PYTHONNOUSERSITE = "1"

# -- Locate iscc.exe (Inno Setup Compiler) ------------------------------------
$IsccCandidates = @(
    "$env:ProgramFiles\Inno Setup 6\iscc.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\iscc.exe"
)
$Iscc = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) {
    Write-Error "Inno Setup 6 not found.  Install it with:  winget install JRSoftware.InnoSetup"
}

# -- Helper: run a command and stop on failure --------------------------------
function Invoke-Step {
    param([string]$Label, [scriptblock]$Command)
    Write-Host ""
    Write-Host "--- $Label ---" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Error "$Label failed (exit code $LASTEXITCODE)."
    }
}

# -- Step 1: generate version artifacts ---------------------------------------
Invoke-Step "Step 1/4 -- Generate version artifacts" {
    & $VenvPython version.py
}

# Read the version back for the final summary message
$Version = (& $VenvPython -c "from version import __version__; print(__version__)")

# -- Step 2: Frontend build ---------------------------------------------------
if (-not $SkipFrontend) {
    Invoke-Step "Step 2/4 -- Frontend build (Vite)" {
        Push-Location frontend
        try {
            # Build-time flags baked into the SPA bundle:
            # - VITE_NOVOTREE_APP_MODE=admin : single-user, auth bypassed, no
            #   login screen. Pinned defensively in case the build host has it
            #   set to "public" for web deployments.
            # - VITE_NOVOTREE_INSTALLER=true : reveals desktop-app-only UI
            #   (Donate ♥ button in the header, future "Move data folder…"
            #   dialog). The web/VM build leaves it unset so this UI never
            #   appears at novospace.cz.
            # Scoped to this command only — the user's shell is not mutated.
            $env:VITE_NOVOTREE_APP_MODE = "admin"
            $env:VITE_NOVOTREE_INSTALLER = "true"
            npm run build
        } finally {
            Pop-Location
        }
    }
} else {
    Write-Host ""
    Write-Host "--- Step 2/4 -- Frontend build  [skipped via -SkipFrontend] ---" -ForegroundColor DarkGray
}

# -- Step 3: PyInstaller -------------------------------------------------------
# --workpath / --distpath keep all build artifacts under installer/ instead of
# polluting the repo root with dist/ and build/ folders.
# We invoke PyInstaller as a module of the venv python (`python -m PyInstaller`)
# rather than via the `pyinstaller` shim from PATH — see the comment at the top
# of this script for why that matters.
if (-not $SkipPyInstaller) {
    Invoke-Step "Step 3/4 -- PyInstaller (bundle app)" {
        & $VenvPython -m PyInstaller installer\novotree.spec --noconfirm `
            --workpath installer\build `
            --distpath installer\dist
    }
} else {
    Write-Host ""
    Write-Host "--- Step 3/4 -- PyInstaller  [skipped via -SkipPyInstaller] ---" -ForegroundColor DarkGray
}

# -- Step 4: Inno Setup -------------------------------------------------------
Invoke-Step "Step 4/4 -- Inno Setup (create installer)" {
    & $Iscc "installer\novotree.iss"
}

# -- Cleanup ------------------------------------------------------------------
# Drop the PyInstaller --onefile output (a single .exe) once it's been packaged
# into setup.exe. We keep installer\build\ around so subsequent rebuilds can
# reuse the cache.
Remove-Item -Force "installer\dist\novotree.exe" -ErrorAction SilentlyContinue

# -- Done ---------------------------------------------------------------------
$Output = "installer\Output\novotree-$Version-setup.exe"
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Done!  ->  $Output" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
