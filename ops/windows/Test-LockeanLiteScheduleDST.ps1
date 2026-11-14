param(
    [Parameter(Mandatory=$true)][string[]]$PermittedTask,
    [int]$Year = ((Get-Date).Year + 1)
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
try {
    Add-Type -Path @(
        (Join-Path $PSScriptRoot 'LockeanLiteSchedulerNative.cs'),
        (Join-Path $PSScriptRoot 'LockeanLiteAcceptance.cs'),
        (Join-Path $PSScriptRoot 'LockeanLiteScheduleReader.cs')
    ) -ReferencedAssemblies System,System.Core,System.Xml,Microsoft.CSharp
    $evidence = @(foreach ($name in $PermittedTask) {
        [LockeanAcceptance.ScheduleClient]::Query($name,$PermittedTask,$Year)
    })
    ConvertTo-Json -InputObject $evidence -Depth 4 -Compress
    if (@($evidence | Where-Object Status -eq 'FAIL').Count) { exit 1 }
    if (@($evidence | Where-Object Status -eq 'INCONCLUSIVE').Count) { exit 2 }
} catch {
    [pscustomobject]@{Status='BLOCKED'; HResult=$_.Exception.GetBaseException().HResult} | ConvertTo-Json -Compress
    exit 1
}
