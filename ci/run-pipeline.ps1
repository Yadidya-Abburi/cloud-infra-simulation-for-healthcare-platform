<#
.SYNOPSIS
    Convenience wrapper to run the DevSecOps CI/CD Pipeline on Windows PowerShell.
.PARAMETER SimulateFailure
    Optional failure type to simulate ('secret', 'container', or 'dependency').
.EXAMPLE
    .\ci\run-pipeline.ps1
.EXAMPLE
    .\ci\run-pipeline.ps1 -SimulateFailure secret
#>
param(
    [ValidateSet("secret", "container", "dependency")]
    [string]$SimulateFailure = ""
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$projectRoot = Split-Path -Parent $scriptDir
$runner = Join-Path $scriptDir "run-pipeline.py"

if ($SimulateFailure) {
    python $runner --simulate-failure $SimulateFailure
} else {
    python $runner
}

exit $LASTEXITCODE
