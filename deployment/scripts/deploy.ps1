<#
.SYNOPSIS
    PowerShell wrapper for Zero-Downtime Blue-Green Deployment Controller.
.PARAMETER Version
    Target application release version (e.g. 'v1.1.0').
.PARAMETER SimulateRuntime
    Runs deployment using runtime simulation mode.
.PARAMETER SimulateFailure
    Injects readiness check failure to demonstrate automated rollback.
.EXAMPLE
    .\deployment\scripts\deploy.ps1 -Version "v1.1.0" -SimulateRuntime
.EXAMPLE
    .\deployment\scripts\deploy.ps1 -Version "v2.0.0-broken" -SimulateRuntime -SimulateFailure
#>
param(
    [string]$Version = "v1.1.0",
    [switch]$SimulateRuntime,
    [switch]$SimulateFailure
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$controller = Join-Path $scriptDir "deploy.py"

$argsList = @($controller, "--version", $Version)

if ($SimulateRuntime) {
    $argsList += "--simulate-runtime"
}
if ($SimulateFailure) {
    $argsList += "--simulate-failure"
}

python @argsList
exit $LASTEXITCODE
