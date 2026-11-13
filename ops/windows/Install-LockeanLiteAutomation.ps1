[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,
    [string]$ApprovedCommit = '',
    [string]$ConfigPath = (Join-Path $env:LOCALAPPDATA 'LockeanLite\Automation\automation-config.json'),
    [switch]$Activate,
    [switch]$OperatorCredentialEntry
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ((Get-TimeZone).Id -ne 'Eastern Standard Time') {
    throw 'windows_timezone_must_be_eastern_standard_time'
}
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'python_missing' }

$head = (& git -C $RepoRoot rev-parse HEAD).Trim().ToLowerInvariant()
if ($LASTEXITCODE -ne 0 -or $head -notmatch '^[0-9a-f]{40}$') { throw 'git_head_unavailable' }
if ([string]::IsNullOrWhiteSpace($ApprovedCommit)) { $ApprovedCommit = $head }
$ApprovedCommit = $ApprovedCommit.ToLowerInvariant()
if ($ApprovedCommit -ne $head) { throw 'approved_commit_not_checked_out' }
$worktreeChanges = @(& git -C $RepoRoot status --porcelain)
if ($LASTEXITCODE -ne 0 -or $worktreeChanges.Count -gt 0) { throw 'worktree_not_clean' }

if ($Activate -and -not $OperatorCredentialEntry) {
    throw 'operator_credential_entry_required'
}

$automationRoot = Split-Path -Parent $ConfigPath
$binDir = Join-Path $automationRoot 'bin'
$stateDir = Join-Path $automationRoot 'state'
$backupDir = Join-Path $automationRoot 'backups'
foreach ($directory in @($automationRoot, $binDir, $stateDir, $backupDir, (Join-Path $automationRoot 'logs'))) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

if (Test-Path -LiteralPath $ConfigPath -PathType Leaf) {
    $configBackup = Join-Path $backupDir ('automation-config_' + (Get-Date -Format yyyyMMdd_HHmmss) + '.json')
    Copy-Item -LiteralPath $ConfigPath -Destination $configBackup
}

foreach ($name in @(
    'Run-LockeanLite.ps1',
    'Watch-LockeanLite.ps1',
    'Verify-LockeanLiteAutomation.ps1',
    'Set-LockeanLiteNotification.ps1',
    'Set-LockeanLitePush.ps1',
    'Install-LockeanLiteAutomation.ps1'
)) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $binDir $name) -Force
}

$config = [ordered]@{
    repo_root = $RepoRoot
    python_path = $python
    approved_commit = $ApprovedCommit
    daily_task_name = 'LockeanLite-DailyPaper'
    watchdog_task_name = 'LockeanLite-Watchdog'
    daily_start = '09:15'
    watchdog_start = '09:20'
    heartbeat_timeout_seconds = 180
    completion_grace_minutes = 15
    watchdog_poll_seconds = 120
}
$configJson = $config | ConvertTo-Json
[System.IO.File]::WriteAllText(
    $ConfigPath,
    $configJson,
    [System.Text.UTF8Encoding]::new($false)
)
$configHash = (Get-FileHash -LiteralPath $ConfigPath -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "Staged Lockean Lite automation for commit $ApprovedCommit."

if (-not $Activate) {
    Write-Host 'Scheduled tasks were not changed. Run verification, then rerun with -Activate.'
    exit 0
}

$verificationPath = Join-Path $stateDir ('verification_' + $ApprovedCommit + '.json')
if (-not (Test-Path -LiteralPath $verificationPath -PathType Leaf)) {
    throw 'matching_verification_receipt_missing'
}
$verification = Get-Content -LiteralPath $verificationPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($verification.approved_commit -ne $ApprovedCommit -or
    $verification.repo_root -ne $RepoRoot -or
    $verification.config_sha256 -ne $configHash -or
    $verification.tests_passed -ne $true -or
    $verification.dry_run_passed -ne $true -or
    $verification.notification_simulation_passed -ne $true -or
    $verification.live_notification_verified -ne $true) {
    throw 'matching_verification_receipt_invalid'
}

$notificationPath = Join-Path $env:LOCALAPPDATA 'LockeanLite\Secrets\notification-endpoint.xml'
if (-not (Test-Path -LiteralPath $notificationPath -PathType Leaf)) {
    throw 'notification_destination_unavailable'
}

function New-LockeanSchedulerSession {
    param([string]$SourceRoot)
    # Compile only from the clean, pinned repository, never from a credential-bearing parameter.
    Add-Type -Path (Join-Path $SourceRoot 'ops/windows/LockeanLiteSchedulerNative.cs') `
        -ReferencedAssemblies 'System', 'System.Core', 'System.Xml', 'Microsoft.CSharp'
    return [LockeanInstaller.SchedulerSession]::new()
}

function New-LockeanTaskXml {
    param([string]$User, [string]$Logon, [string]$Script, [string]$Boundary)
    $command = [Security.SecurityElement]::Escape((Get-Process -Id $PID).Path)
    $arguments = [Security.SecurityElement]::Escape(
        '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $Script + '" -ConfigPath "' + $ConfigPath + '"')
    $userXml = [Security.SecurityElement]::Escape($User)
    return @"
<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task" version="1.4">
  <RegistrationInfo><Description>Lockean Lite; approved commit $ApprovedCommit</Description></RegistrationInfo>
  <Triggers><CalendarTrigger><StartBoundary>$Boundary</StartBoundary><Enabled>true</Enabled>
    <ScheduleByWeek><WeeksInterval>1</WeeksInterval><DaysOfWeek><Monday/><Tuesday/><Wednesday/><Thursday/><Friday/></DaysOfWeek></ScheduleByWeek>
  </CalendarTrigger></Triggers>
  <Principals><Principal id="Author"><UserId>$userXml</UserId><LogonType>$Logon</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><StartWhenAvailable>true</StartWhenAvailable><Enabled>true</Enabled>
    <WakeToRun>true</WakeToRun><ExecutionTimeLimit>PT9H</ExecutionTimeLimit></Settings>
  <Actions Context="Author"><Exec><Command>$command</Command><Arguments>$arguments</Arguments></Exec></Actions>
</Task>
"@
}

function Invoke-LockeanTaskInstallation {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)]$Session)
    $snapshots = @()
    $attempted = [Collections.Generic.List[object]]::new()
    $activationFailed = $false
    try {
        $Session.CheckPermissions()
        $dailyName = [string]$config.daily_task_name
        $watchdogName = [string]$config.watchdog_task_name
        $weekdays = @('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday')
        $dailyTrigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek $weekdays -At $config.daily_start
        $watchdogTrigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek $weekdays -At $config.watchdog_start
        # Offset-free boundaries follow the host's Eastern wall clock across DST.
        $triggerDate = [datetime]::Today.ToString('yyyy-MM-dd', [cultureinfo]::InvariantCulture)
        $dailyBoundary = "${triggerDate}T$($config.daily_start):00"
        $watchdogBoundary = "${triggerDate}T$($config.watchdog_start):00"
        $dailyTrigger.StartBoundary = $dailyBoundary
        $watchdogTrigger.StartBoundary = $watchdogBoundary
        $snapshots = foreach ($plan in @(
            @{ Name = $dailyName; Boundary = $dailyTrigger.StartBoundary; Logon = 'Password'; Script = 'Run-LockeanLite.ps1' }
            @{ Name = $watchdogName; Boundary = $watchdogTrigger.StartBoundary; Logon = 'InteractiveToken'; Script = 'Watch-LockeanLite.ps1' }
        )) {
            $startTime = [datetime]::ParseExact($plan.Boundary, "yyyy-MM-dd'T'HH:mm:ss", [cultureinfo]::InvariantCulture)
            if ($startTime -le $Session.CurrentTime.AddMinutes(30)) {
                throw 'activation_window_too_close_or_start_already_passed'
            }
            $original = $Session.ReadXml($plan.Name)
            $security = $null
            if ($original) {
                $Session.RequireIdle($plan.Name)
                $security = $Session.ReadSecurity($plan.Name)
                [xml]$definition = $original
                if (@($definition.Task.Principals.Principal).Count -ne 1 -or
                    $definition.Task.Principals.Principal.LogonType -cne $plan.Logon) {
                    throw 'existing_task_logon_policy_mismatch'
                }
                if (@($definition.Task.Triggers.ChildNodes).Count -ne 1 -or
                    $definition.Task.Triggers.FirstChild.LocalName -cne 'CalendarTrigger') {
                    throw 'existing_task_trigger_shape_unsupported'
                }
                $definition.Task.Triggers.CalendarTrigger.StartBoundary = $plan.Boundary
            } else {
                [xml]$definition = New-LockeanTaskXml -User $Session.CurrentUser -Logon $plan.Logon `
                    -Script (Join-Path $binDir $plan.Script) -Boundary $plan.Boundary
                [xml]$definition = $Session.NormalizeXml($definition.OuterXml)
            }
            $user = [string]$definition.Task.Principals.Principal.UserId
            if ([string]::IsNullOrWhiteSpace($user)) { throw 'task_principal_missing' }
            [pscustomobject]@{
                Name = $plan.Name; Boundary = $plan.Boundary; Xml = $original
                Security = $security; Desired = $definition.OuterXml; User = $user; Logon = $plan.Logon
            }
        }
        # Both recovery snapshots are persisted before credential entry or task mutation.
        $backupSuffix = (Get-Date -Format yyyyMMdd_HHmmss) + '_' + [guid]::NewGuid().ToString('N')
        foreach ($snapshot in $snapshots) {
            if ($snapshot.Xml) {
                $snapshot.Xml | Set-Content -LiteralPath (Join-Path $backupDir ($snapshot.Name + '_' + $backupSuffix + '.xml')) -Encoding UTF8
                $snapshot.Security | Set-Content -LiteralPath (Join-Path $backupDir ($snapshot.Name + '_' + $backupSuffix + '.sddl')) -Encoding UTF8
            }
        }
        foreach ($snapshot in $snapshots) {
            if ($snapshot.Logon -eq 'Password') { $Session.Authenticate($snapshot.User) }
        }
        foreach ($snapshot in $snapshots) {
            if ($snapshot.Xml) { $Session.Validate($snapshot.Name, $snapshot.Xml, $snapshot.Security) }
            $Session.Validate($snapshot.Name, $snapshot.Desired, $snapshot.Security)
        }
        foreach ($snapshot in $snapshots) {
            # Refuse concurrent changes rather than overwriting another operator's work.
            if ($Session.ReadXml($snapshot.Name) -cne $snapshot.Xml) { throw 'task_changed_after_preflight' }
            if ($snapshot.Xml) {
                $Session.RequireIdle($snapshot.Name)
                if (-not $Session.SecurityMatches($snapshot.Name, $snapshot.Security)) { throw 'task_security_changed_after_preflight' }
            }
            # Include the failing write in recovery, since a provider failure may be partial.
            $attempted.Add($snapshot)
            $Session.Write($snapshot.Name, $snapshot.Desired, $snapshot.Security, [bool]$snapshot.Xml)
        }
        foreach ($snapshot in $snapshots) {
            [xml]$registered = $Session.ReadXml($snapshot.Name)
            [xml]$desired = $snapshot.Desired
            foreach ($section in @('Principals', 'Settings', 'Actions')) {
                $actualSection = $registered.Task.$section.CloneNode($true)
                $desiredSection = $desired.Task.$section.CloneNode($true)
                if ($section -eq 'Settings') {
                    # Enabled=true is also the schema default when omitted.
                    foreach ($node in @($actualSection, $desiredSection)) {
                        foreach ($enabled in @($node.SelectNodes("*[local-name()='Enabled']"))) {
                            $null = $node.RemoveChild($enabled)
                        }
                    }
                }
                if ($actualSection.OuterXml -cne $desiredSection.OuterXml) {
                    throw 'registered_task_metadata_mismatch'
                }
            }
            if ($snapshot.Xml -and -not $Session.SecurityMatches($snapshot.Name, $snapshot.Security)) {
                throw 'registered_task_security_mismatch'
            }
        }
        foreach ($expected in @(
            @{ Name = $dailyName; Boundary = $dailyBoundary }
            @{ Name = $watchdogName; Boundary = $watchdogBoundary }
        )) {
            [xml]$registered = $Session.ReadXml($expected.Name)
            $ns = [System.Xml.XmlNamespaceManager]::new($registered.NameTable)
            $ns.AddNamespace('t', 'http://schemas.microsoft.com/windows/2004/02/mit/task')
            $triggers = $registered.SelectNodes('/t:Task/t:Triggers/*', $ns)
            $calendar = $registered.SelectSingleNode('/t:Task/t:Triggers/t:CalendarTrigger', $ns)
            if ($triggers.Count -ne 1 -or $null -eq $calendar) {
                throw 'registered_task_wall_clock_boundary_mismatch'
            }
            $boundaries = $calendar.SelectNodes('t:StartBoundary', $ns)
            if ($boundaries.Count -ne 1 -or $boundaries[0].SelectNodes('*|@*').Count -ne 0 -or
                $boundaries[0].InnerText -cne $expected.Boundary) {
                throw 'registered_task_wall_clock_boundary_mismatch'
            }

            $schedules = $calendar.SelectNodes("*[starts-with(local-name(), 'ScheduleBy')]", $ns)
            $weekly = $calendar.SelectSingleNode('t:ScheduleByWeek[not(@*) and not(text()[normalize-space()])]', $ns)
            if ($schedules.Count -ne 1 -or $null -eq $weekly -or $weekly.SelectNodes('*').Count -ne 2) {
                throw 'registered_task_weekday_schedule_mismatch'
            }
            $interval = $weekly.SelectSingleNode('t:WeeksInterval[not(*) and not(@*)]', $ns)
            $days = $weekly.SelectSingleNode('t:DaysOfWeek[not(@*) and not(text()[normalize-space()])]', $ns)
            if ($null -eq $interval -or $interval.InnerText.Trim() -cne '1' -or $null -eq $days) {
                throw 'registered_task_weekday_schedule_mismatch'
            }
            $dayNames = @($days.SelectNodes('t:*[not(*) and not(@*) and not(normalize-space())]', $ns) |
                ForEach-Object { $_.LocalName })
            if ($days.SelectNodes('*').Count -ne $weekdays.Count -or $dayNames.Count -ne $weekdays.Count -or
                (Compare-Object -ReferenceObject $weekdays -DifferenceObject $dayNames -CaseSensitive)) {
                throw 'registered_task_weekday_schedule_mismatch'
            }

            # Task Scheduler defaults both the trigger and the task to enabled.
            foreach ($enabledPath in @(
                '/t:Task/t:Triggers/t:CalendarTrigger/t:Enabled'
                '/t:Task/t:Settings/t:Enabled'
            )) {
                $enabled = $registered.SelectNodes($enabledPath, $ns)
                if ($enabled.Count -gt 1 -or ($enabled.Count -eq 1 -and
                    ($enabled[0].SelectNodes('*|@*').Count -ne 0 -or $enabled[0].InnerText.Trim() -cnotin @('true', '1')))) {
                    throw 'registered_task_disabled_or_invalid_enabled'
                }
            }
        }
    } catch {
        $activationFailed = $true
        $activationError = $_
        $rollbackFailures = [Collections.Generic.List[string]]::new()
        for ($index = $attempted.Count - 1; $index -ge 0; $index--) {
            $snapshot = $attempted[$index]
            try {
                if ($snapshot.Xml) {
                    $Session.Write($snapshot.Name, $snapshot.Xml, $snapshot.Security, $true)
                    [xml]$restored = $Session.ReadXml($snapshot.Name)
                    [xml]$prior = $snapshot.Xml
                    if ($restored.OuterXml -cne $prior.OuterXml -or
                        -not $Session.SecurityMatches($snapshot.Name, $snapshot.Security)) {
                        throw 'rollback_readback_mismatch'
                    }
                } else {
                    $Session.Remove($snapshot.Name)
                    if ($Session.ReadXml($snapshot.Name)) { throw 'rollback_removal_mismatch' }
                }
            } catch {
                # Native errors have already been sanitized. Never forward arbitrary provider text.
                $rollbackFailures.Add($snapshot.Name + ':0x' + $_.Exception.GetBaseException().HResult.ToString('X8'))
            }
        }
        $activationError.Exception.Data['RollbackFailures'] = $rollbackFailures.ToArray()
        if ($rollbackFailures.Count) {
            Write-Warning ('INSTALLATION BLOCKED; recovery requires operator attention: ' + ($rollbackFailures -join ','))
        }
        $PSCmdlet.ThrowTerminatingError($activationError)
    } finally {
        try { $Session.Dispose() }
        catch {
            if (-not $activationFailed) { throw 'credential_cleanup_failed_installation_blocked' }
            Write-Warning ('credential_cleanup_failed_0x' + $_.Exception.GetBaseException().HResult.ToString('X8'))
        }
    }
}

$session = New-LockeanSchedulerSession -SourceRoot $RepoRoot
Invoke-LockeanTaskInstallation -Session $session
Write-Host 'Activated and verified LockeanLite-DailyPaper plus LockeanLite-Watchdog.'
