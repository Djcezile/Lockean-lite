param([string]$NativeSource)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
Add-Type -Path $NativeSource -ReferencedAssemblies System,System.Core,System.Xml,Microsoft.CSharp
Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public class SyntheticTrigger { public bool Enabled = true; }
public class SyntheticTriggers {
    public int Count = 1;
    public SyntheticTrigger Trigger = new SyntheticTrigger();
    public SyntheticTrigger Item(int index) { return Trigger; }
}
public class SyntheticDefinition { public SyntheticTriggers Triggers = new SyntheticTriggers(); }
public class SyntheticTask {
    public SyntheticDefinition Definition = new SyntheticDefinition();
    public int State = 2;
    public bool Enabled = true;
    public DateTime NextRunTime = DateTime.Now.AddHours(2);
}
public class SyntheticTaskFolder {
    public SyntheticTask Task = new SyntheticTask();
    public SyntheticTask GetTask(string name) { return Task; }
    public bool Fail;
    public int Calls;
    public bool Authenticated = true;
    public int LastFlags;
    public object RegisterTask(string name, string xml, int flags, object user, object password, int logon, object security) {
        Calls++;
        LastFlags=flags;
        Authenticated &= logon == 1 && (string)password == "SYNTHETIC_PASSWORD_ONLY";
        if(Fail) throw new COMException("must never escape: " + password, unchecked((int)0x8007052e));
        return flags == 1 ? null : new object();
    }
}
"@
$native=[LockeanInstaller.SchedulerSession]::new()
$flags=[Reflection.BindingFlags]'Instance,NonPublic'
$folder=[SyntheticTaskFolder]::new()
$native.GetType().GetField('folder',$flags).SetValue($native,$folder)
$credentialType=$native.GetType().GetNestedType('Credential',[Reflection.BindingFlags]::NonPublic)
$credential=[Activator]::CreateInstance($credentialType,$true)
$secure=[Security.SecureString]::new()
foreach($character in 'SYNTHETIC_PASSWORD_ONLY'.ToCharArray()){$secure.AppendChar($character)}
$secure.MakeReadOnly()
$credentialType.GetField('Password',$flags).SetValue($credential,$secure)
$credentials=$native.GetType().GetField('credentials',$flags).GetValue($native)
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$credentials.Add($sid,$credential)
$queuedRejected=$false
try{$native.RequireIdle('synthetic')}catch{$queuedRejected=$true}
if(-not $queuedRejected){throw 'queued_task_not_rejected'}
$folder.Task.State=3
$native.RequireIdle('synthetic')
$folder.Task.NextRunTime=[datetime]::Now.AddMinutes(5)
$imminentRejected=$false
try{$native.RequireIdle('synthetic')}catch{$imminentRejected=$true}
if(-not $imminentRejected){throw 'imminent_enabled_task_not_rejected'}
$folder.Task.Enabled=$false
$native.RequireIdle('synthetic')
$folder.Task.State=4
$runningRejected=$false
try{$native.RequireIdle('synthetic')}catch{$runningRejected=$true}
if(-not $runningRejected){throw 'running_disabled_task_not_rejected'}
$folder.Task.State=3
$folder.Task.Enabled=$true
$folder.Task.Definition.Triggers.Trigger.Enabled=$false
$folder.Task.NextRunTime=[datetime]::new(1899,12,30)
$native.RequireIdle('synthetic')
$folder.Task.Definition.Triggers.Trigger.Enabled=$true
$folder.Task.NextRunTime=[datetime]::Now.AddMinutes(-5)
$catchUpRejected=$false
try{$native.RequireIdle('synthetic')}catch{$catchUpRejected=$true}
if(-not $catchUpRejected){throw 'overdue_enabled_task_not_rejected'}
$folder.Task.NextRunTime=[datetime]::Now.AddHours(2)
$fullAccess=[LockeanInstaller.SchedulerSession]::HasTaskManagementAccess('O:'+ $sid +'G:'+ $sid +'D:(A;;FA;;;'+$sid+')')
$readAccess=[LockeanInstaller.SchedulerSession]::HasTaskManagementAccess('O:'+ $sid +'G:'+ $sid +'D:(A;;FR;;;'+$sid+')')
if(-not $fullAccess -or $readAccess){throw 'native_access_check_failed'}
$xml='<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"><Principals><Principal><UserId>'+ $sid +'</UserId><LogonType>Password</LogonType></Principal></Principals></Task>'
$native.Validate('synthetic',$xml,'synthetic-security')
if($folder.LastFlags -ne 1){throw 'validation_not_read_only'}
$native.Write('synthetic',$xml,'synthetic-security',$true)
if($folder.LastFlags -ne 52){throw 'update_security_flags_changed'}
$native.Write('synthetic',$xml,'synthetic-security',$true)
$disabledXml=$xml.Replace('</Task>','<Settings><Enabled>false</Enabled></Settings></Task>')
$native.Write('synthetic',$disabledXml,'synthetic-security',$true)
if($folder.LastFlags -ne 60){throw 'disabled_update_flag_missing'}
$folder.Fail=$true
$failure=''
$hresult=0
try{$native.Write('synthetic',$xml,'synthetic-security',$true)}
catch{
    $failure=$_.Exception.GetBaseException().ToString()
    $hresult=$_.Exception.GetBaseException().HResult
}
if($failure.Contains('SYNTHETIC_PASSWORD_ONLY') -or -not $failure.Contains('8007052E')){throw 'credential_or_error_identity_not_protected'}
$native.Dispose()
if($credentials.Count -ne 0){throw 'credential_cache_not_cleared'}
@{authenticated=$folder.Authenticated;calls=$folder.Calls;hresult=$hresult;sanitized=$true;disposed=$true;accessChecks=$true;windowChecks=$true}|ConvertTo-Json -Compress
