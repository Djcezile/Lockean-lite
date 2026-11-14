param([Parameter(Mandatory=$true)][string]$Ops)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
try {
    $sources = @(
        (Join-Path $Ops 'LockeanLiteSchedulerNative.cs'),
        (Join-Path $Ops 'LockeanLiteAcceptance.cs'),
        (Join-Path $Ops 'LockeanLiteScheduleReader.cs'),
        (Join-Path $PSScriptRoot 'windows_acceptance_probe.cs')
    )
    Add-Type -Path $sources -ReferencedAssemblies System,System.Core,System.Xml,Microsoft.CSharp
    [LockeanAcceptanceTests.Probe]::Run() | ConvertTo-Json -Compress
} catch {
    # Provider text, exception objects and compiler source snippets stay out of evidence.
    Write-Output ('offline_probe_failed_0x{0:X8}' -f $_.Exception.HResult)
    exit 1
}
