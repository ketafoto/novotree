<#
.SYNOPSIS
  Create or reset the first Owner/admin account (Windows wrapper).
.DESCRIPTION
  Forwards all arguments to tools.ops.signups.signup_owner, run from the project
  root with the project venv if present.
.EXAMPLE
  tools\ops\signups\signup_owner.ps1 --email me@example.com
.EXAMPLE
  tools\ops\signups\signup_owner.ps1 --email me@example.com --password 'S3cret!!' --force
#>

$ErrorActionPreference = 'Stop'

# Project root = three levels up from this script (tools\ops\signups\ -> root).
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptDir '..\..\..')).Path
Set-Location $ProjectRoot

# Pick a Python: project venv first, then PATH.
if (Test-Path 'venv-win\Scripts\python.exe') {
    $Py = 'venv-win\Scripts\python.exe'
} elseif (Test-Path 'venv\Scripts\python.exe') {
    $Py = 'venv\Scripts\python.exe'
} else {
    $Py = 'python'
}

& $Py -m tools.ops.signups.signup_owner @args
exit $LASTEXITCODE
