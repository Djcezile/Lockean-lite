param([string]$Installer,[string]$Scenario='valid',[string]$Mutation='')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$tokens=$null
$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($Installer,[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'installer_parse_failed'}
# Load definitions only. No installer top-level code or native task methods run.
foreach($function in $ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$false)){
    . ([scriptblock]::Create($function.Extent.Text))
}
class SyntheticSession {
    [hashtable]$Definitions=@{}
    [hashtable]$Originals=@{}
    [Collections.Generic.List[string]]$Events=[Collections.Generic.List[string]]::new()
    [datetime]$CurrentTime=[datetime]::Today.AddHours(6)
    [string]$CurrentUser='synthetic-user'
    [string]$Scenario
    [string]$Mutation
    [bool]$Disposed=$false
    [void]CheckPermissions(){
        $this.Events.Add('permissions')
        if($this.Scenario -eq 'permission'){throw 'task_management_elevation_required'}
    }

    [string]ReadXml([string]$name){
        if($this.Definitions.ContainsKey($name)){return $this.Definitions[$name]}
        return $null
    }
    [void]RequireIdle([string]$name){
        if($this.Scenario -eq 'running'){throw 'task_running'}
    }
    [string]ReadSecurity([string]$name){return 'synthetic-security'}
    [bool]SecurityMatches([string]$name,[string]$expected){
        return -not($this.Scenario -eq 'security-drift' -and $this.Definitions[$name] -cne $this.Originals[$name])
    }
    [string]NormalizeXml([string]$xml){return $xml}
    [void]Authenticate([string]$user){
        $this.Events.Add('authenticate')
        if($this.Scenario -in @('missing-credential','incorrect-credential')){throw 'task_authentication_failed'}
    }
    [void]Validate([string]$name,[string]$xml,[string]$security){
        $this.Events.Add('validate:'+ $name)
        if($this.Scenario -eq 'invalid-recovery' -and $xml -ceq $this.Originals[$name]){throw 'recovery_invalid'}
    }
    [void]Write([string]$name,[string]$xml,[string]$security,[bool]$existing){
        $restore=$this.Originals.ContainsKey($name) -and $xml -ceq $this.Originals[$name]
        if($restore){
            $this.Events.Add('restore:'+ $name)
            if($this.Scenario -eq 'both-rollbacks-fail' -or ($this.Scenario -eq 'rollback-fails' -and $name -eq 'watchdog')){throw 'SYNTHETIC_ROLLBACK_PASSWORD_MARKER'}
            $this.Definitions[$name]=$xml
            return
        }
        $this.Events.Add('write:'+ $name)
        $this.Definitions[$name]=$xml
        if($this.Scenario -eq 'tampered-readback' -and $name -eq 'watchdog'){
            $parts=$this.Mutation|ConvertFrom-Json
            $this.Definitions[$name]=$xml.Replace(" />","/>").Replace([string]$parts.old,[string]$parts.new)
        }
        if($this.Scenario -in @('partial','rollback-fails','both-rollbacks-fail','new-task-partial') -and $name -eq 'watchdog'){
            throw 'synthetic_activation_failure'
        }
    }
    [void]Remove([string]$name){
        $this.Events.Add('remove:'+ $name)
        $this.Definitions.Remove($name)
    }
    [void]Dispose(){$this.Disposed=$true}
}
function New-ScheduledTaskTrigger {
    param([switch]$Weekly,[int]$WeeksInterval,[string[]]$DaysOfWeek,[string]$At)
    [pscustomobject]@{StartBoundary='synthetic-default'}
}
$ApprovedCommit='synthetic-approved'
$session=[SyntheticSession]::new()
$session.Scenario=$Scenario
if($Scenario -eq 'late-window'){$session.CurrentTime=[datetime]::Today.AddHours(9)}
$session.Mutation=$Mutation
$week='<ScheduleByWeek><WeeksInterval>1</WeeksInterval><DaysOfWeek><Monday/><Tuesday/><Wednesday/><Thursday/><Friday/></DaysOfWeek></ScheduleByWeek>'
foreach($item in @(@{Name='daily';Logon='Password'},@{Name='watchdog';Logon='InteractiveToken'})){
    $session.Definitions[$item.Name]='<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"><Triggers><CalendarTrigger><StartBoundary>2026-01-02T08:15:00-05:00</StartBoundary><Enabled>true</Enabled>'+ $week +'</CalendarTrigger></Triggers><Principals><Principal id="Author"><UserId>synthetic-user</UserId><LogonType>'+ $item.Logon +'</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals><Settings><Enabled>true</Enabled><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><ExecutionTimeLimit>PT7H</ExecutionTimeLimit></Settings><Actions Context="Author"><Exec><Command>synthetic.exe</Command><Arguments>synthetic-action</Arguments></Exec></Actions></Task>'
}
if($Scenario -eq 'new-daily'){$session.Definitions.Remove('daily')}
if($Scenario -eq 'new-task-partial'){$session.Definitions.Remove('watchdog')}
if($Scenario -eq 'wrong-logon'){$session.Definitions['daily']=$session.Definitions['daily'].Replace('Password','InteractiveToken')}
$session.Originals=$session.Definitions.Clone()
$config=@{daily_task_name='daily';watchdog_task_name='watchdog';daily_start='09:15';watchdog_start='09:20'}
$binDir='synthetic-bin'
$ConfigPath='synthetic-config.json'
$backupDir=Join-Path $env:TEMP ('lockean-synthetic-'+[guid]::NewGuid().ToString('N'))
[void](New-Item -ItemType Directory -Path $backupDir)
$failure=''
$rollback=@()
try{
    Invoke-LockeanTaskInstallation -Session $session -WarningAction SilentlyContinue -WarningVariable warnings
}catch{
    $failure=$_.Exception.Message
    if($_.Exception.Data.Contains('RollbackFailures')){$rollback=@($_.Exception.Data['RollbackFailures'])}
}finally{
    # Only fixture files, created above, are removed.
    Get-ChildItem -LiteralPath $backupDir -File|Remove-Item
    Remove-Item -LiteralPath $backupDir
}
$preserved=$true
foreach($name in $session.Originals.Keys){
    if($session.Definitions.ContainsKey($name)){
        [xml]$before=$session.Originals[$name]
        [xml]$after=$session.Definitions[$name]
        foreach($section in @('Principals','Settings','Actions')){
            if($before.Task.$section.OuterXml -cne $after.Task.$section.OuterXml){$preserved=$false}
        }
    }else{$preserved=$false}
}
@{failure=$failure;rollback=$rollback;events=@($session.Events.ToArray());preserved=$preserved;disposed=$session.Disposed;definitions=$session.Definitions}|ConvertTo-Json -Compress -Depth 6
