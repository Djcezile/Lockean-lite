[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$entropy = New-Object byte[] 16
$generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $generator.GetBytes($entropy)
} finally {
    $generator.Dispose()
}

$token = -join ($entropy | ForEach-Object { $_.ToString('x2') })
$topic = 'lockean-' + $token
$endpointText = 'https://ntfy.sh/' + $topic
$secureEndpoint = ConvertTo-SecureString -String $endpointText -AsPlainText -Force

$destinationDirectory = Join-Path $env:LOCALAPPDATA 'LockeanLite\Secrets'
$destinationPath = Join-Path $destinationDirectory 'notification-endpoint.xml'
New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
$secureEndpoint | Export-Clixml -LiteralPath $destinationPath -Force

$clipboardAvailable = $null -ne (Get-Command Set-Clipboard -ErrorAction SilentlyContinue)
if ($clipboardAvailable) {
    Set-Clipboard -Value $topic
}

Write-Host ''
Write-Host 'Lockean Lite mobile push is configured with a private ntfy topic.'
Write-Host 'Install the ntfy mobile app, tap +, and subscribe to this exact topic:'
Write-Host ''
Write-Host $topic
Write-Host ''
if ($clipboardAvailable) {
    Write-Host 'The topic was also copied to the Windows clipboard.'
}
Write-Host 'Keep the topic private: anyone who knows it can subscribe or publish.'
Write-Host 'After the phone is subscribed, run Verify-LockeanLiteAutomation.ps1.'

Remove-Variable endpointText, secureEndpoint, entropy, token -ErrorAction SilentlyContinue
