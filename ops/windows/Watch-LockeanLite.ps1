[CmdletBinding()]
param(
    [switch]$Once,
    [string]$ConfigPath = (Join-Path (Split-Path -Parent $PSScriptRoot) 'automation-config.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$automationRoot = Split-Path -Parent $ConfigPath
$logsDir = Join-Path $automationRoot 'logs'
New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
$audit = Join-Path $logsDir ('watchdog_boot_' + (Get-Date -Format yyyyMMdd) + '.log')

function Write-WatchdogAudit([string]$Message) {
    Add-Content -LiteralPath $audit -Value ((Get-Date -Format o) + ' ' + $Message) -Encoding UTF8
}

try {
    if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) { throw 'configuration_missing' }
    $config = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $repo = [string]$config.repo_root
    $python = [string]$config.python_path
    $approvedCommit = ([string]$config.approved_commit).ToLowerInvariant()
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'python_missing' }

    foreach ($name in @('ALPACA_API_KEY', 'ALPACA_SECRET_KEY')) {
        $value = [Environment]::GetEnvironmentVariable($name, 'User')
        if ([string]::IsNullOrWhiteSpace($value)) { throw 'user_credential_missing' }
        Set-Item -Path ('Env:' + $name) -Value $value
    }

    $head = (& git -C $repo rev-parse HEAD).Trim().ToLowerInvariant()
    $worktreeChanges = @(& git -C $repo status --porcelain)
    if ($LASTEXITCODE -ne 0 -or $head -ne $approvedCommit -or $worktreeChanges.Count -gt 0) {
        $schedulerAudit = Join-Path $logsDir ('scheduler_' + (Get-Date -Format yyyyMMdd) + '.log')
        Add-Content -LiteralPath $schedulerAudit -Value ((Get-Date -Format o) + ' WATCHDOG SOURCE MISMATCH') -Encoding UTF8
    }

    $notificationPath = Join-Path $env:LOCALAPPDATA 'LockeanLite\Secrets\notification-endpoint.xml'
    if (Test-Path -LiteralPath $notificationPath -PathType Leaf) {
        $secureEndpoint = Import-Clixml -LiteralPath $notificationPath
        if (-not ($secureEndpoint -is [System.Security.SecureString]) -or $secureEndpoint.Length -eq 0) {
            throw 'notification_destination_unavailable'
        }
        $endpointCredential = [System.Net.NetworkCredential]::new('Lockean', $secureEndpoint)
        $env:LOCKEAN_NOTIFICATION_WEBHOOK = $endpointCredential.Password
        Remove-Variable endpointCredential, secureEndpoint
    } else {
        Write-WatchdogAudit 'NOTIFICATION DESTINATION MISSING: alerts remain in local watchdog audit.'
    }

    Set-Location -LiteralPath $repo
    $arguments = @(
        '-m', 'lockean_lite.automation.session_watchdog',
        '--repo-root', $repo,
        '--automation-root', $automationRoot,
        '--poll-seconds', [string]$config.watchdog_poll_seconds,
        '--heartbeat-timeout-seconds', [string]$config.heartbeat_timeout_seconds,
        '--completion-grace-minutes', [string]$config.completion_grace_minutes
    )
    if ($Once) { $arguments += '--once' }
    & $python @arguments
    exit $LASTEXITCODE
}
catch {
    Write-WatchdogAudit 'WATCHDOG BOOT BLOCKED: inspect local configuration; details suppressed.'
    exit 1
}
finally {
    foreach ($name in @(
        'LOCKEAN_NOTIFICATION_WEBHOOK',
        'ALPACA_API_KEY',
        'ALPACA_SECRET_KEY'
    )) {
        Remove-Item -Path ('Env:' + $name) -ErrorAction SilentlyContinue
    }
}
