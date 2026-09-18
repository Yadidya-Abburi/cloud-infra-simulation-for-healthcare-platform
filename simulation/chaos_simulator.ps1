<#
.SYNOPSIS
    PowerShell CLI wrapper for Chaos Simulator and Incident Drills.
.PARAMETER Scenario
    Scenario to run: 'a' (EHR Outage), 'b' (Worker Crash), or 'all' (Both).
.EXAMPLE
    .\simulation\chaos_simulator.ps1 -Scenario all
.EXAMPLE
    .\simulation\chaos_simulator.ps1 -Scenario a
#>
param(
    [ValidateSet("a", "b", "all")]
    [string]$Scenario = "all"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$simulator = Join-Path $scriptDir "chaos_simulator.py"

python $simulator --scenario $Scenario --simulate-runtime
exit $LASTEXITCODE
