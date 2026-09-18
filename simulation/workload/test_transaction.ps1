<#
.SYNOPSIS
    Convenience wrapper for testing asynchronous transactions and queue workloads.
.PARAMETER Batch
    Number of jobs to submit (default: 1). Use > 1 to simulate a traffic burst.
.PARAMETER PatientId
    Identifier for the patient (default: 'pat-001').
.EXAMPLE
    .\simulation\workload\test_transaction.ps1
.EXAMPLE
    .\simulation\workload\test_transaction.ps1 -Batch 10
#>
param(
    [int]$Batch = 1,
    [string]$PatientId = "pat-001"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$runner = Join-Path $scriptDir "test_transaction.py"

python $runner --batch $Batch --patient-id $PatientId
exit $LASTEXITCODE
