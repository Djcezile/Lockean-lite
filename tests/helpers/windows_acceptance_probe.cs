using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using LockeanAcceptance;

namespace LockeanAcceptanceTests {
public sealed class Fake : ITaskBackend {
    public Dictionary<string,string> Xml = new Dictionary<string,string>();
    public Dictionary<string,string> Security = new Dictionary<string,string>();
    public int Calls, Writes;
    public bool Running, FailAuth, DriftXml, DriftSecurity, FailPermission;
    public void CheckPermissions() { Calls++; if(FailPermission)throw new Exception("SYNTHETIC_SECRET_MARKER"); }
    public string ReadXml(string n) { Calls++; return Xml.ContainsKey(n) ? Xml[n] : null; }
    public string ReadSecurity(string n) { Calls++; return Security[n]; }
    public void RequireIdle(string n) { Calls++; if(Running) throw new Exception("SYNTHETIC_SECRET_MARKER"); }
    public void Authenticate(string n,string u) { Calls++; if(FailAuth) throw new Exception("SYNTHETIC_SECRET_MARKER"); }
    public void Validate(string n,string x,string s) { Calls++; }
    public string NormalizeXml(string n,string x) { Calls++; return x; }
    public void Write(string n,string x,string s,bool e) {
        Calls++; Writes++; Xml[n]=DriftXml ? x.Replace("IgnoreNew","Parallel") : x;
        Security[n]=DriftSecurity ? "O:SYG:SYD:(A;;FR;;;SY)" : s;
    }
    public void Remove(string n) { Calls++; Xml.Remove(n); Security.Remove(n); }
    public void Dispose() {}
}
public static class Probe {
    static readonly string Sddl="O:SYG:SYD:(A;;FA;;;SY)";
    static void Need(bool value) { if(!value) throw new Exception("synthetic_assertion"); }
    static bool Reject(Action a) { try { a(); return false; } catch { return true; } }
    static GuardedSession Session(TaskPolicy p, Fake f, bool mutation=true,bool credential=true) {
        return new GuardedSession(p,f,mutation,credential);
    }
    public static Dictionary<string,bool> Run() {
        var r=new Dictionary<string,bool>();
        Action<string,Action> check=(n,a)=>{ try { a(); r[n]=true; } catch { r[n]=false; } };
        var p=new TaskPolicy(Guid.NewGuid());
        string daily=p.Daily, watch=p.Watchdog;
        string xml=Fixtures.Create(p,daily,"S-1-5-18");
        foreach(string op in new[]{"ReadXml","ReadSecurity","RequireIdle","Authenticate","Validate","Write","Remove","SecurityMatches"}) {
            check("isolation_"+op,()=>{
                foreach(string bad in new[]{"LockeanLite-DailyPaper","LockeanLite-Watchdog", "lockeanlite-dailypaper", "\\"+daily, daily+"\\x",daily.ToUpperInvariant(),"LockeanLite-Acceptance-"+Guid.NewGuid()+"-Daily",daily+" "}) {
                    var f=new Fake(); using(var s=Session(p,f)) {
                        Need(Reject(()=>{
                            switch(op) {
                                case "ReadXml":s.ReadXml(bad);break;
                                case "ReadSecurity":s.ReadSecurity(bad);break;
                                case "RequireIdle":s.RequireIdle(bad);break;
                                case "Authenticate":s.Authenticate(bad,xml);break;
                                case "Validate":s.Validate(bad,xml,Sddl);break;
                                case "Write":s.Write(bad,xml,Sddl,false);break;
                                case "Remove":s.Remove(bad);break;
                                case "SecurityMatches":s.SecurityMatches(bad,Sddl);break;
                            }
                        })); Need(f.Calls==0);
                    }
                }
            });
            check("native_isolation_"+op,()=>{
                var type=typeof(GuardedSession).GetNestedType("NativeBackend",System.Reflection.BindingFlags.NonPublic);
                var native=Activator.CreateInstance(type,System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Public,null,new object[]{p},null);
                string method=op=="SecurityMatches"?"ReadSecurity":op;
                object[] args=method=="Authenticate"?new object[]{"LockeanLite-DailyPaper","never_authenticate"}:
                    method=="Validate"?new object[]{"LockeanLite-DailyPaper",xml,Sddl}:
                    method=="Write"?new object[]{"LockeanLite-DailyPaper",xml,Sddl,false}:new object[]{"LockeanLite-DailyPaper"};
                try {type.GetMethod(method).Invoke(native,args);throw new Exception("native_guard_missing");}
                catch(System.Reflection.TargetInvocationException e){Need(e.InnerException.Message=="task_identity_denied");}
                finally {((IDisposable)native).Dispose();}
            });
        }
        check("approval_before_native_connection",()=>Need(Reject(()=>GuardedSession.CreateNative(p,false,false))));
        check("permission_failure",()=>{var f=new Fake{FailPermission=true};using(var s=Session(p,f)){Need(Reject(()=>Drill.Run(s,"S-1-5-18",Sddl,DrillFault.None)));Need(f.Writes==0);}});
        check("existing_fixture",()=>{var f=new Fake();f.Xml[daily]=xml;using(var s=Session(p,f)){Need(Reject(()=>Drill.Run(s,"S-1-5-18",Sddl,DrillFault.None)));Need(f.Writes==0);}});
        check("native_normalization_guard",()=>{
            var type=typeof(GuardedSession).GetNestedType("NativeBackend",System.Reflection.BindingFlags.NonPublic);
            var n=Activator.CreateInstance(type,System.Reflection.BindingFlags.Instance|System.Reflection.BindingFlags.Public,null,new object[]{p},null);
            try{type.GetMethod("NormalizeXml").Invoke(n,new object[]{"LockeanLite-DailyPaper",xml});throw new Exception("missing_guard");}
            catch(System.Reflection.TargetInvocationException e){Need(e.InnerException.Message=="task_identity_denied");}
            finally{((IDisposable)n).Dispose();}
        });
        check("no_mutation_approval",()=>{var f=new Fake();using(var s=Session(p,f,false,false)){Need(Reject(()=>s.Write(watch,Fixtures.Create(p,watch,"S-1-5-18"),Sddl,false)));Need(f.Calls==0);}});
        check("native_adapter_private",()=>Need(typeof(GuardedSession).GetNestedType("NativeBackend",System.Reflection.BindingFlags.NonPublic).IsNestedPrivate));
        check("xml_external_entity",()=>Need(Reject(()=>Fixtures.Validate(p,daily,"<!DOCTYPE Task [<!ENTITY x SYSTEM 'file:///does-not-exist'>]>"+xml))));
        check("native_serialization",()=>{
            object service=null,definition=null;
            try {
                dynamic scheduler=service=Activator.CreateInstance(Type.GetTypeFromProgID("Schedule.Service"));scheduler.Connect();
                foreach(string n in new[]{daily,watch}) {
                    dynamic task=definition=scheduler.NewTask(0);task.XmlText=Fixtures.Create(p,n,System.Security.Principal.WindowsIdentity.GetCurrent().User.Value);
                    Fixtures.Validate(p,n,(string)task.XmlText);
                    Marshal.ReleaseComObject(definition);definition=null;
                }
            } finally {if(definition!=null)Marshal.ReleaseComObject(definition);if(service!=null)Marshal.ReleaseComObject(service);}
        });
        check("credential_approval",()=>{var f=new Fake();using(var s=Session(p,f,true,false)){Need(Reject(()=>s.Authenticate(daily,xml)));Need(f.Calls==0);}});
        var mutations=new Dictionary<string,string>{
            {"unsafe_action",xml.Replace("/d /c exit 0","/c powershell Run-LockeanLite.ps1")},
            {"extra_action",xml.Replace("</Actions>","<Exec><Command>evil.exe</Command></Exec></Actions>")},
            {"enabled_fixture",xml.Replace("<Enabled>false</Enabled>","<Enabled>true</Enabled>")},
            {"catchup",xml.Replace("<StartWhenAvailable>false","<StartWhenAvailable>true")},
            {"registration_trigger",xml.Replace("</Triggers>","<RegistrationTrigger/></Triggers>")},
            {"wrong_logon",xml.Replace("Password","InteractiveToken")}
        };
        foreach(var item in mutations) {var pair=item;check(pair.Key,()=>{var f=new Fake();using(var s=Session(p,f)){Need(Reject(()=>s.Write(daily,pair.Value,Sddl,false)));Need(f.Calls==0);}});}
        check("missing_auth",()=>{var f=new Fake();using(var s=Session(p,f)){Need(Reject(()=>s.Write(daily,xml,Sddl,false)));Need(f.Calls==0);}});
        check("secret_redaction",()=>{var f=new Fake{FailAuth=true};using(var s=Session(p,f)){try{s.Authenticate(daily,xml);throw new Exception("expected_rejection");}catch(Exception e){Need(!e.ToString().Contains("SYNTHETIC_SECRET_MARKER"));Need(e.InnerException==null);}}});
        check("running",()=>{var f=new Fake{Running=true};f.Xml[daily]=xml;using(var s=Session(p,f)){s.Authenticate(daily,xml);Need(Reject(()=>s.Write(daily,xml,Sddl,true)));Need(f.Writes==0);}});
        foreach(string field in new[]{"principal_drift","settings_drift","security_drift"}) {
            check(field,()=>{var f=new Fake();using(var s=Session(p,f)){s.Authenticate(daily,xml);s.Write(daily,xml,Sddl,false);
                if(field=="principal_drift") f.Xml[daily]=xml.Replace("S-1-5-18","S-1-5-19");
                if(field=="settings_drift") f.Xml[daily]=xml.Replace("IgnoreNew","Parallel");
                if(field=="security_drift") f.Security[daily]="O:SYG:SYD:(A;;FR;;;SY)";
                Need(Reject(()=>s.Verify(daily,xml,Sddl)));
            }});
        }
        foreach(var fault in new[]{DrillFault.None,DrillFault.PartialWrite,DrillFault.RollbackFailure}) {
            string key=fault==DrillFault.None ? "success_preservation":fault==DrillFault.PartialWrite?"partial_rollback":"rollback_failure_primary";
            check(key,()=>{var f=new Fake();using(var s=Session(p,f)){
                var result=Drill.Run(s,"S-1-5-18",Sddl,fault);
                Need(f.Xml.Count==2 && f.Xml.Values.All(x=>x.Contains("<Enabled>false</Enabled>")));
                if(fault==DrillFault.None) Need(result.Status=="PASS" && result.RollbackFailures.Length==0);
                else {Need(result.Status=="BLOCKED" && result.ActivationError.StartsWith("activation_"));Need(result.RollbackFailures.Length==(fault==DrillFault.PartialWrite?0:1));}
                if(fault!=DrillFault.RollbackFailure) foreach(string n in new[]{daily,watch}) Need(f.Xml[n]==Fixtures.Create(p,n,"S-1-5-18"));
            }});
        }
        check("cleanup_guard",()=>{var f=new Fake();f.Xml[daily]=xml.Replace("/d /c exit 0","evil");using(var s=Session(p,f)){Need(Reject(()=>s.Remove(daily)));Need(f.Xml.Count==1);}});
        string temp=Path.Combine(Path.GetTempPath(),"lockean-synthetic-"+Guid.NewGuid());Directory.CreateDirectory(temp);
        try {
            string file=Path.Combine(temp,"original.xml");File.WriteAllText(file,xml);
            string hash=BackupFiles.Hash(file);
            check("backup_valid",()=>Need(BackupFiles.Read(temp,"original.xml",hash)==xml));
            check("backup_hash",()=>Need(Reject(()=>BackupFiles.Read(temp,"original.xml",new string('0',64)))));
            check("backup_path",()=>Need(Reject(()=>BackupFiles.Read(temp,"../original.xml",hash))));
            check("backup_unc",()=>Need(Reject(()=>BackupFiles.RequireLocalRoot("\\\\invalid-host\\share\\backup"))));
            check("backup_missing",()=>Need(Reject(()=>BackupFiles.Read(temp,"missing.xml",hash))));
            check("backup_disabled",()=>Need(Reject(()=>Fixtures.Validate(p,daily,xml.Replace("<Enabled>false</Enabled>","<Enabled>true</Enabled>")))));
            var pins=new Dictionary<string,string>();
            foreach(string n in new[]{daily,watch}) {
                File.WriteAllText(Path.Combine(temp,n+".xml"),Fixtures.Create(p,n,"S-1-5-18"));
                File.WriteAllText(Path.Combine(temp,n+".sddl"),Sddl);
                pins[n+".xml"]=BackupFiles.Hash(Path.Combine(temp,n+".xml"));
                pins[n+".sddl"]=BackupFiles.Hash(Path.Combine(temp,n+".sddl"));
            }
            check("recovery_pins",()=>{var bad=new Dictionary<string,string>(pins);bad[daily+".xml"]=new string('0',64);Need(Reject(()=>RecoverySet.Load(p,temp,bad)));});
            var recovery=RecoverySet.Load(p,temp,pins);
            check("recovery_valid",()=>{var f=new Fake();f.Xml[daily]=xml;f.Xml[watch]=Fixtures.Create(p,watch,"S-1-5-18");foreach(string n in new[]{daily,watch})f.Security[n]=Sddl;using(var s=Session(p,f)){Need(recovery.Restore(s).Length==0);Need(f.Writes==2);}});
            check("recovery_auth",()=>{var f=new Fake{FailAuth=true};using(var s=Session(p,f)){Need(Reject(()=>recovery.Restore(s)));Need(f.Writes==0);}});
            check("recovery_drift",()=>{var f=new Fake{DriftSecurity=true};f.Xml[daily]=xml;f.Xml[watch]=Fixtures.Create(p,watch,"S-1-5-18");foreach(string n in new[]{daily,watch})f.Security[n]=Sddl;using(var s=Session(p,f)){Need(recovery.Restore(s).Length==2);}});
            check("recovery_all_attempted",()=>{var f=new Fake{DriftXml=true};f.Xml[daily]=xml;f.Xml[watch]=Fixtures.Create(p,watch,"S-1-5-18");foreach(string n in new[]{daily,watch})f.Security[n]=Sddl;using(var s=Session(p,f)){Need(recovery.Restore(s).Length==2);Need(f.Writes==2);}});
        } finally {Directory.Delete(temp,true);}
        Action<string,DateTime[],string,bool,int> schedule=(key,dates,expect,disabled,hr)=>check(key,()=>{
            var values=dates.Select(d=>DateTime.SpecifyKind(d.AddHours(9).AddMinutes(15),DateTimeKind.Unspecified)).ToArray();
            var evidence=ScheduleClient.Evaluate(daily,xml,values,hr,!disabled,0);
            Need(evidence.Status==expect);
            if(expect=="PASS" && dates.Length==2) {
                Need(evidence.UtcTimes[0].Substring(11,5)==(dates[0].Month==3?"14:15":"13:15"));
                Need(evidence.UtcTimes[1].Substring(11,5)==(dates[1].Month==3?"13:15":"14:15"));
            }
        });
        DateTime[] spring={new DateTime(2027,3,12),new DateTime(2027,3,15)};
        DateTime[] fall={new DateTime(2027,11,5),new DateTime(2027,11,8)};
        schedule("dst_spring_daily",spring,"PASS",true,0);schedule("dst_fall_daily",fall,"PASS",true,0);
        foreach(var pair in new[]{new{K="dst_spring_watchdog",Dates=spring},new{K="dst_fall_watchdog",Dates=fall}})check(pair.K,()=>{
            var result=ScheduleClient.Evaluate(watch,Fixtures.Create(p,watch,"S-1-5-18"),pair.Dates.Select(d=>d.AddHours(9).AddMinutes(20)).ToArray(),0,false,0);
            Need(result.Status=="PASS");
            Need(result.UtcTimes[0].Substring(11,5)==(pair.Dates[0].Month==3?"14:20":"13:20"));
            Need(result.UtcTimes[1].Substring(11,5)==(pair.Dates[1].Month==3?"13:20":"14:20"));
        });
        schedule("dst_missing",new DateTime[0],"INCONCLUSIVE",true,0);
        schedule("dst_hresult",spring,"INCONCLUSIVE",true,unchecked((int)0x80070005));
        schedule("dst_truncated",spring,"INCONCLUSIVE",true,1);
        schedule("dst_weekend",new[]{new DateTime(2027,3,13)},"FAIL",true,0);
        check("dst_mismatch",()=>Need(ScheduleClient.Evaluate(daily,xml,new[]{new DateTime(2027,3,12,8,15,0)},0,false,0).Status=="FAIL"));
        check("dst_offset",()=>Need(Reject(()=>ScheduleClient.ValidateSchedule(daily,xml.Replace("T09:15:00","T09:15:00-05:00")))));
        check("dst_daily_recurrence",()=>Need(Reject(()=>ScheduleClient.ValidateSchedule(daily,xml.Replace("ScheduleByWeek","ScheduleByDay")))));
        check("dst_disabled",()=>Need(ScheduleClient.Evaluate(daily,xml,spring.Select(d=>d.AddHours(9).AddMinutes(15)).ToArray(),0,false,0).Enabled==false));
        check("dst_exact_allowlist",()=>Need(Reject(()=>ScheduleClient.Query("LockeanLite-DailyPaper",new[]{watch},2027))));
        check("dst_readonly_surface",()=>Need(!typeof(ScheduleClient).GetMethods().Any(m=>new[]{"Write","Remove","Run","Enable","Authenticate","Register"}.Contains(m.Name))));
        check("dst_abi",()=>Need(Marshal.SizeOf(typeof(SchedulerSystemTime))==16));
        return r;
    }
}}
