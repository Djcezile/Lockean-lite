using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Xml;

namespace LockeanAcceptance
{
    // Exact identities are a capability boundary, not a wildcard/prefix check.
    public sealed class TaskPolicy
    {
        public string Daily { get; private set; }
        public string Watchdog { get; private set; }
        public TaskPolicy(Guid id)
        {
            if (id == Guid.Empty) throw new InvalidOperationException("empty_acceptance_id");
            string prefix = "LockeanLite-Acceptance-" + id.ToString("D") + "-";
            Daily = prefix + "Daily";
            Watchdog = prefix + "Watchdog";
        }
        public void Require(string name)
        {
            if (!String.Equals(name, Daily, StringComparison.Ordinal) &&
                !String.Equals(name, Watchdog, StringComparison.Ordinal))
                throw new InvalidOperationException("task_identity_denied");
        }
    }

    public static class Fixtures
    {
        internal const string NS = "http://schemas.microsoft.com/windows/2004/02/mit/task";
        internal static XmlDocument Parse(string xml)
        {
            var settings = new XmlReaderSettings { DtdProcessing = DtdProcessing.Prohibit, XmlResolver = null };
            var doc = new XmlDocument { XmlResolver = null };
            using (var text = new StringReader(xml))
            using (var reader = XmlReader.Create(text, settings)) doc.Load(reader);
            return doc;
        }
        internal static XmlNamespaceManager Names(XmlDocument doc)
        {
            var names = new XmlNamespaceManager(doc.NameTable); names.AddNamespace("t", NS); return names;
        }
        internal static string Text(XmlDocument doc, string path)
        {
            var nodes = doc.SelectNodes(path, Names(doc));
            if (nodes.Count != 1) throw new InvalidOperationException("required_task_field_missing_or_duplicate");
            return nodes[0].InnerText;
        }
        public static string Create(TaskPolicy policy, string name, string user)
        {
            policy.Require(name);
            // XML escaping is necessary even for operator-supplied nonsecret account IDs.
            string account = System.Security.SecurityElement.Escape(user);
            string command = System.Security.SecurityElement.Escape(Path.Combine(Environment.SystemDirectory, "cmd.exe"));
            string logon = name == policy.Daily ? "Password" : "InteractiveToken";
            string clock = name == policy.Daily ? "09:15:00" : "09:20:00";
            return "<Task version='1.2' xmlns='" + NS + "'><RegistrationInfo><URI>" + name +
                "</URI></RegistrationInfo><Triggers><CalendarTrigger><StartBoundary>2027-01-04T" + clock +
                "</StartBoundary><Enabled>true</Enabled><ScheduleByWeek><WeeksInterval>1</WeeksInterval>" +
                "<DaysOfWeek><Monday/><Tuesday/><Wednesday/><Thursday/><Friday/></DaysOfWeek></ScheduleByWeek>" +
                "</CalendarTrigger></Triggers><Principals><Principal id='p'><UserId>" + account +
                "</UserId><LogonType>" + logon + "</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal>" +
                "</Principals><Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>" +
                "<StartWhenAvailable>false</StartWhenAvailable><AllowStartOnDemand>false</AllowStartOnDemand>" +
                "<Enabled>false</Enabled><ExecutionTimeLimit>PT1M</ExecutionTimeLimit></Settings>" +
                "<Actions Context='p'><Exec><Command>" + command + "</Command><Arguments>/d /c exit 0</Arguments>" +
                "</Exec></Actions></Task>";
        }
        public static void Validate(TaskPolicy policy, string name, string xml)
        {
            policy.Require(name);
            var doc = Parse(xml); var ns = Names(doc);
            if (Text(doc,"/t:Task/t:RegistrationInfo/t:URI").TrimStart('\\') != name ||
                Text(doc,"/t:Task/t:Settings/t:Enabled") != "false" ||
                Text(doc,"/t:Task/t:Settings/t:StartWhenAvailable") != "false" ||
                Text(doc,"/t:Task/t:Settings/t:AllowStartOnDemand") != "false" ||
                Text(doc,"/t:Task/t:Settings/t:MultipleInstancesPolicy") != "IgnoreNew" ||
                Text(doc,"/t:Task/t:Principals/t:Principal/t:RunLevel") != "LeastPrivilege" ||
                Text(doc,"/t:Task/t:Principals/t:Principal/t:LogonType") != (name == policy.Daily ? "Password" : "InteractiveToken"))
                throw new InvalidOperationException("unsafe_fixture_policy");
            if (doc.SelectNodes("/t:Task/t:Principals/t:Principal", ns).Count != 1 ||
                doc.SelectNodes("/t:Task/t:Actions/*", ns).Count != 1 ||
                doc.SelectNodes("/t:Task/t:Actions/t:Exec/*", ns).Count != 2 ||
                !String.Equals(Text(doc,"/t:Task/t:Actions/t:Exec/t:Command"),
                    Path.Combine(Environment.SystemDirectory,"cmd.exe"), StringComparison.OrdinalIgnoreCase) ||
                Text(doc,"/t:Task/t:Actions/t:Exec/t:Arguments") != "/d /c exit 0")
                throw new InvalidOperationException("unsafe_fixture_action");
            if (String.IsNullOrWhiteSpace(Text(doc,"/t:Task/t:Principals/t:Principal/t:UserId")))
                throw new InvalidOperationException("fixture_account_missing");
            ScheduleClient.ValidateSchedule(name, xml);
        }
        internal static string Canonical(string xml) { return Parse(xml).OuterXml; }
        internal static bool SameSecurity(string a, string b)
        {
            var first = new RawSecurityDescriptor(a); var second = new RawSecurityDescriptor(b);
            var x = new byte[first.BinaryLength]; var y = new byte[second.BinaryLength];
            first.GetBinaryForm(x,0); second.GetBinaryForm(y,0); return x.SequenceEqual(y);
        }
    }

    // Injection is for offline synthetic implementations. The live implementation is private.
    public interface ITaskBackend : IDisposable
    {
        void CheckPermissions();
        string ReadXml(string name);
        string ReadSecurity(string name);
        void RequireIdle(string name);
        void Authenticate(string name, string user);
        void Validate(string name, string xml, string security);
        string NormalizeXml(string name, string xml);
        void Write(string name, string xml, string security, bool existing);
        void Remove(string name);
    }

    public sealed class GuardedSession : IDisposable
    {
        private readonly TaskPolicy policy;
        private readonly ITaskBackend backend;
        private readonly bool mutations, credentials;
        private readonly HashSet<string> authenticated = new HashSet<string>(StringComparer.Ordinal);
        public TaskPolicy Policy { get { return policy; } }
        internal bool IsNative {get {return backend is NativeBackend;}}
        public GuardedSession(TaskPolicy policy, ITaskBackend synthetic, bool approveMutation, bool approveCredential)
        {
            this.policy = policy; backend = synthetic; mutations = approveMutation; credentials = approveCredential;
        }
        private sealed class NativeBackend : ITaskBackend
        {
            private readonly TaskPolicy policy;
            private readonly LockeanInstaller.SchedulerSession native = new LockeanInstaller.SchedulerSession();
            public NativeBackend(TaskPolicy policy) { this.policy=policy; }
            // Recheck at the native boundary even after the facade has checked.
            public void CheckPermissions() { native.CheckPermissions(); }
            public string ReadXml(string n) { policy.Require(n); return native.ReadXml(n); }
            public string ReadSecurity(string n) { policy.Require(n); return native.ReadSecurity(n); }
            public void RequireIdle(string n) { policy.Require(n); native.RequireIdle(n); ScheduleClient.RequireDisabled(n,new[]{n}); }
            public void Authenticate(string n,string u) { policy.Require(n); if(n!=policy.Daily) throw new InvalidOperationException("password_fixture_required"); native.Authenticate(u); }
            public void Validate(string n,string x,string s) { policy.Require(n); Fixtures.Validate(policy,n,x); native.Validate(n,x,s); }
            public string NormalizeXml(string n,string x) { policy.Require(n); Fixtures.Validate(policy,n,x); return native.NormalizeXml(x); }
            public void Write(string n,string x,string s,bool e) { policy.Require(n); Fixtures.Validate(policy,n,x); native.Write(n,x,s,e); }
            public void Remove(string n) { policy.Require(n); native.Remove(n); }
            public void Dispose() { native.Dispose(); }
        }
        public static GuardedSession CreateNative(TaskPolicy policy, bool approved, bool credentialApproved)
        {
            if (!approved) throw new InvalidOperationException("separate_disposable_mutation_approval_required");
            return new GuardedSession(policy, new NativeBackend(policy), approved, credentialApproved);
        }
        internal static Exception Safe(string label, Exception error)
        {
            // Existing reviewed adapter removes messages, arguments and inner exceptions.
            return LockeanInstaller.SchedulerSession.SafeFailure(label, error);
        }
        private void Gate(string name, bool mutation)
        {
            policy.Require(name);
            if (mutation && !mutations) throw new InvalidOperationException("disposable_mutation_not_approved");
        }
        public void CheckPermissions()
        {
            if (!mutations) throw new InvalidOperationException("disposable_mutation_not_approved");
            try { backend.CheckPermissions(); } catch(Exception e) { throw Safe("permissions",e); }
        }
        public string ReadXml(string name)
        {
            Gate(name,false);
            try { string x = backend.ReadXml(name); if (x != null) Fixtures.Validate(policy,name,x); return x; }
            catch(Exception e) { throw Safe("read",e); }
        }
        public string ReadSecurity(string name)
        {
            Gate(name,false); RequireFixture(name);
            try { return backend.ReadSecurity(name); } catch(Exception e) { throw Safe("security",e); }
        }
        private void RequireFixture(string name)
        {
            if (ReadXml(name) == null) throw new InvalidOperationException("fixture_missing");
        }
        public void RequireIdle(string name)
        {
            Gate(name,false); RequireFixture(name);
            try { backend.RequireIdle(name); } catch(Exception e) { throw Safe("idle",e); }
        }
        public void Authenticate(string name,string xml)
        {
            Gate(name,true); Fixtures.Validate(policy,name,xml);
            if (!credentials) throw new InvalidOperationException("separate_credential_entry_approval_required");
            if (name != policy.Daily) throw new InvalidOperationException("password_fixture_required");
            string user = Fixtures.Text(Fixtures.Parse(xml),"/t:Task/t:Principals/t:Principal/t:UserId");
            try { backend.Authenticate(name,user); authenticated.Add(user); }
            catch(Exception e) { throw Safe("authentication",e); }
        }
        private void RequireAuthentication(string name,string xml)
        {
            if (name == policy.Daily && !authenticated.Contains(Fixtures.Text(Fixtures.Parse(xml),"/t:Task/t:Principals/t:Principal/t:UserId")))
                throw new InvalidOperationException("password_authentication_required");
        }
        public void Validate(string name,string xml,string security)
        {
            Gate(name,true); Fixtures.Validate(policy,name,xml); RequireAuthentication(name,xml);
            new RawSecurityDescriptor(security);
            try { backend.Validate(name,xml,security); } catch(Exception e) { throw Safe("validate",e); }
        }
        public void Write(string name,string xml,string security,bool existing)
        {
            Gate(name,true); Fixtures.Validate(policy,name,xml); RequireAuthentication(name,xml);
            new RawSecurityDescriptor(security);
            string prior = ReadXml(name);
            if ((prior != null) != existing) throw new InvalidOperationException("fixture_existence_changed");
            if (existing) RequireIdle(name);
            try { backend.Write(name,xml,security,existing); } catch(Exception e) { throw Safe("write",e); }
        }
        public void Remove(string name)
        {
            Gate(name,true); RequireIdle(name);
            try { backend.Remove(name); } catch(Exception e) { throw Safe("remove",e); }
        }
        public bool SecurityMatches(string name,string security)
        {
            Gate(name,false); return Fixtures.SameSecurity(ReadSecurity(name),security);
        }
        public void Verify(string name,string xml,string security)
        {
            Gate(name,false);
            string normalized;
            try { normalized=backend.NormalizeXml(name,xml); } catch(Exception e) { throw Safe("normalize",e); }
            if (Fixtures.Canonical(ReadXml(name)) != Fixtures.Canonical(normalized) || !SecurityMatches(name,security))
                throw new InvalidOperationException("fixture_readback_mismatch");
            RequireIdle(name);
        }
        public void Dispose() { authenticated.Clear(); backend.Dispose(); }
    }

    public enum DrillFault { None, PartialWrite, RollbackFailure }
    public sealed class DrillResult
    {
        public string Status;
        public string ActivationError;
        public string[] RollbackFailures;
    }
    public static class Drill
    {
        public static DrillResult Run(GuardedSession session,string user,string security,DrillFault fault,Action saveRecovery=null)
        {
            if(session.IsNative && saveRecovery==null) throw new InvalidOperationException("persistent_recovery_capture_required");
            var policy = session.Policy; string[] names = { policy.Daily, policy.Watchdog };
            session.CheckPermissions();
            foreach (string n in names) if (session.ReadXml(n) != null)
                throw new InvalidOperationException("disposable_name_already_exists");
            var originals = names.ToDictionary(n=>n,n=>Fixtures.Create(policy,n,user));
            session.Authenticate(policy.Daily,originals[policy.Daily]);
            // Validate both recovery definitions before the first fixture write.
            foreach (string n in names) session.Validate(n,originals[n],security);
            var created = new List<string>();
            try
            {
                foreach(string n in names)
                {
                    // Track before provider call: even a thrown call may have persisted a task.
                    created.Add(n); session.Write(n,originals[n],security,false);
                    session.Verify(n,originals[n],security);
                }
            }
            catch(Exception initial)
            {
                var failures = new List<string>();
                foreach(string n in created.AsEnumerable().Reverse())
                    try { if(session.ReadXml(n)!=null) session.Remove(n); }
                    catch(Exception e) { failures.Add(n+":"+GuardedSession.Safe("cleanup",e).Message); }
                return new DrillResult {Status="BLOCKED",ActivationError=GuardedSession.Safe("activation",initial).Message,RollbackFailures=failures.ToArray()};
            }
            if(saveRecovery!=null) saveRecovery();
            // Retain the service's actual normalized originals as recovery targets.
            foreach(string n in names) originals[n]=session.ReadXml(n);
            var attempted = new List<string>();
            Exception activation = null;
            try
            {
                foreach(string n in names)
                {
                    string candidate = originals[n].Replace("2027-01-04T","2027-01-05T");
                    session.Validate(n,candidate,security); attempted.Add(n);
                    session.Write(n,candidate,security,true); session.Verify(n,candidate,security);
                    if(n==policy.Watchdog && fault!=DrillFault.None)
                        throw new InvalidOperationException("synthetic_partial_write");
                }
            }
            catch(Exception e) { activation = GuardedSession.Safe("activation",e); }
            var rollback = new List<string>();
            // Even success restores the initial disabled pair; fixtures remain for readonly inspection.
            foreach(string n in attempted.AsEnumerable().Reverse())
                try
                {
                    if(n==policy.Watchdog && fault==DrillFault.RollbackFailure)
                        throw new InvalidOperationException("synthetic_restore_failure");
                    session.Write(n,originals[n],security,true); session.Verify(n,originals[n],security);
                }
                catch(Exception e) { rollback.Add(n+":"+GuardedSession.Safe("rollback",e).Message); }
            return new DrillResult {Status=activation==null && rollback.Count==0 ? "PASS":"BLOCKED",
                ActivationError=activation==null ? "":activation.Message,RollbackFailures=rollback.ToArray()};
        }
    }

    // Pin each absolute backup root and each digest independently of untrusted file contents.
    public static class BackupFiles
    {
        public static void RequireLocalRoot(string root)
        {
            // Reject UNC/device/drive-relative paths before any filesystem/network access.
            if(!System.Text.RegularExpressions.Regex.IsMatch(root??"","\\A[A-Za-z]:\\\\") || Path.GetFullPath(root)!=root)
                throw new InvalidOperationException("canonical_local_backup_root_required");
            var cursor=new DirectoryInfo(root);
            while(cursor!=null)
            {
                if(cursor.Exists && (cursor.Attributes&FileAttributes.ReparsePoint)!=0)
                    throw new InvalidOperationException("backup_reparse_denied");
                cursor=cursor.Parent;
            }
        }
        public static string Hash(string path)
        {
            using(var input=File.OpenRead(path)) using(var hash=SHA256.Create())
                return BitConverter.ToString(hash.ComputeHash(input)).Replace("-","").ToLowerInvariant();
        }
        public static string Read(string root,string leaf,string expectedSHA256)
        {
            RequireLocalRoot(root);
            if(
                String.IsNullOrWhiteSpace(leaf) || Path.GetFileName(leaf)!=leaf || leaf.Contains(":") ||
                !System.Text.RegularExpressions.Regex.IsMatch(expectedSHA256??"","\\A[0-9a-fA-F]{64}\\z"))
                throw new InvalidOperationException("backup_path_or_digest_invalid");
            var cursor=new DirectoryInfo(root);
            while(cursor!=null) { if((cursor.Attributes & FileAttributes.ReparsePoint)!=0) throw new InvalidOperationException("backup_reparse_denied"); cursor=cursor.Parent; }
            string file=Path.Combine(root,leaf);
            if(!File.Exists(file) || (File.GetAttributes(file)&FileAttributes.ReparsePoint)!=0)
                throw new InvalidOperationException("backup_missing_or_reparse");
            // A single shared-read handle prevents replacement/writes during hash and consumption.
            using(var input=new FileStream(file,FileMode.Open,FileAccess.Read,FileShare.Read))
            using(var hash=SHA256.Create())
            {
                string actual=BitConverter.ToString(hash.ComputeHash(input)).Replace("-","");
                if(!actual.Equals(expectedSHA256,StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("backup_digest_mismatch");
                input.Position=0; using(var reader=new StreamReader(input)) return reader.ReadToEnd();
            }
        }
    }

    // Recovery can address only the original GUID pair. No production recovery API.
    public sealed class RecoverySet
    {
        private TaskPolicy policy;
        private Dictionary<string,string> xml,security;
        public static Dictionary<string,string> Save(GuardedSession session,string absoluteRoot)
        {
            BackupFiles.RequireLocalRoot(absoluteRoot);
            if(!Path.IsPathRooted(absoluteRoot) || Path.GetFullPath(absoluteRoot)!=absoluteRoot || Directory.Exists(absoluteRoot))
                throw new InvalidOperationException("new_absolute_recovery_root_required");
            // Create a protected new directory; never change ACLs of existing evidence.
            string sid=System.Security.Principal.WindowsIdentity.GetCurrent().User.Value;
            var acl=new DirectorySecurity();acl.SetSecurityDescriptorSddlForm("O:BAG:BAD:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;"+sid+")");
            Directory.CreateDirectory(absoluteRoot,acl);
            var pins=new Dictionary<string,string>(StringComparer.Ordinal);
            foreach(string n in new[]{session.Policy.Daily,session.Policy.Watchdog})
            {
                session.Policy.Require(n);session.RequireIdle(n);
                foreach(var item in new[]{new{Leaf=n+".xml",Content=session.ReadXml(n)},new{Leaf=n+".sddl",Content=session.ReadSecurity(n)}})
                {
                    string path=Path.Combine(absoluteRoot,item.Leaf);
                    using(var file=new FileStream(path,FileMode.CreateNew,FileAccess.Write,FileShare.None))
                    using(var writer=new StreamWriter(file,new System.Text.UTF8Encoding(false))) writer.Write(item.Content);
                    pins[item.Leaf]=BackupFiles.Hash(path);
                }
            }
            return pins;
        }
        public static RecoverySet Load(TaskPolicy policy,string absoluteRoot,IDictionary<string,string> trustedPins)
        {
            var result=new RecoverySet{policy=policy,xml=new Dictionary<string,string>(),security=new Dictionary<string,string>()};
            string[] names={policy.Daily,policy.Watchdog};
            if(trustedPins==null || trustedPins.Count!=4) throw new InvalidOperationException("exact_recovery_pin_set_required");
            foreach(string n in names)
            {
                policy.Require(n);
                result.xml[n]=BackupFiles.Read(absoluteRoot,n+".xml",trustedPins[n+".xml"]);
                result.security[n]=BackupFiles.Read(absoluteRoot,n+".sddl",trustedPins[n+".sddl"]);
                Fixtures.Validate(policy,n,result.xml[n]);new RawSecurityDescriptor(result.security[n]);
            }
            return result;
        }
        public string[] Restore(GuardedSession session)
        {
            // All pins/content were validated before this method can authenticate or write.
            if(session.Policy.Daily!=policy.Daily || session.Policy.Watchdog!=policy.Watchdog)
                throw new InvalidOperationException("recovery_session_mismatch");
            session.CheckPermissions(); session.Authenticate(policy.Daily,xml[policy.Daily]);
            foreach(string n in new[]{policy.Daily,policy.Watchdog}) session.Validate(n,xml[n],security[n]);
            var failures=new List<string>();
            foreach(string n in new[]{policy.Watchdog,policy.Daily})
                try {session.Write(n,xml[n],security[n],true);session.Verify(n,xml[n],security[n]);}
                catch(Exception e) {failures.Add(n+":"+GuardedSession.Safe("recovery",e).Message);}
            return failures.ToArray();
        }
    }
}
