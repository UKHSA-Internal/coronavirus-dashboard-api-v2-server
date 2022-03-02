[cmdletbinding()]
param(
    $TaskList = "compose",
    $Version = "0.0.1",
    $Instance = "ci"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Module psake -ListAvailable -ErrorAction SilentlyContinue)) {
    Install-Module -Name psake -RequiredVersion 4.9.0 -Force
}

Invoke-psake -TaskList $TaskList -Parameters @{ SolutionRoot = $(Get-Location); Version = $Version; Configuration = "Release"; Instance = $Instance} -Verbose:$VerbosePreference

if ($psake.build_success -eq $False) { exit 1 } else { exit 0 }
