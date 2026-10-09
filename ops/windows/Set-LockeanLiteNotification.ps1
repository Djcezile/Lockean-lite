[CmdletBinding()]
param(
    [System.Security.SecureString]$Endpoint
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($null -eq $Endpoint) {
    $Endpoint = Read-Host 'Paste the HTTPS notification endpoint' -AsSecureString
}
if ($Endpoint.Length -eq 0) { throw 'notification_destination_empty' }

$credential = [System.Net.NetworkCredential]::new('Lockean', $Endpoint)
try {
    $uri = [Uri]$credential.Password
    if ($uri.Scheme -ne 'https' -or [string]::IsNullOrWhiteSpace($uri.Host)) {
        throw 'notification_destination_must_be_https'
    }
} finally {
    Remove-Variable credential -ErrorAction SilentlyContinue
}

$destinationDirectory = Join-Path $env:LOCALAPPDATA 'LockeanLite\Secrets'
$destinationPath = Join-Path $destinationDirectory 'notification-endpoint.xml'
New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
$Endpoint | Export-Clixml -LiteralPath $destinationPath -Force
Write-Host 'Notification destination stored with Windows user-scope DPAPI protection.'
