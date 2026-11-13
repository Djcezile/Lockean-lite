using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Security;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Xml;

namespace LockeanInstaller
{
    // Passwords never cross this adapter's PowerShell-visible API.
    public sealed class SchedulerSession : IDisposable
    {
        private dynamic service;
        private dynamic folder;
        private readonly Dictionary<string, Credential> credentials = new Dictionary<string, Credential>();

        private sealed class Credential : IDisposable
        {
            internal string User;
            internal string Domain;
            internal SecureString Password;
            public void Dispose() { if (Password != null) Password.Dispose(); }
        }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct CredentialInfo
        {
            internal int Size;
            internal IntPtr Parent;
            internal string Message;
            internal string Caption;
            internal IntPtr Banner;
        }

        [DllImport("credui.dll", CharSet = CharSet.Unicode)]
        private static extern uint CredUIPromptForWindowsCredentialsW(
            ref CredentialInfo info, uint error, ref uint package, IntPtr input, uint inputSize,
            out IntPtr output, out uint outputSize, ref bool save, uint flags);
        [DllImport("credui.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool CredUnPackAuthenticationBufferW(
            uint flags, IntPtr buffer, uint size, IntPtr user, ref uint userSize,
            IntPtr domain, ref uint domainSize, IntPtr password, ref uint passwordSize);
        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool LogonUserW(string user, string domain, IntPtr password,
            int logonType, int provider, out IntPtr token);
        [DllImport("kernel32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool CloseHandle(IntPtr token);

        [StructLayout(LayoutKind.Sequential)]
        private struct GenericMapping
        {
            internal uint Read, Write, Execute, All;
        }
        [DllImport("advapi32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool DuplicateToken(IntPtr token, int level, out IntPtr duplicate);
        [DllImport("advapi32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool AccessCheck(IntPtr descriptor, IntPtr token, uint desired,
            ref GenericMapping mapping, IntPtr privileges, ref uint size, out uint granted,
            [MarshalAs(UnmanagedType.Bool)] out bool status);

        public static bool HasTaskManagementAccess(string security)
        {
            var descriptor = new RawSecurityDescriptor(security);
            var bytes = new byte[descriptor.BinaryLength];
            descriptor.GetBinaryForm(bytes, 0);
            var pinned = GCHandle.Alloc(bytes, GCHandleType.Pinned);
            IntPtr token = IntPtr.Zero;
            IntPtr privileges = Marshal.AllocHGlobal(4096);
            try
            {
                using (var identity = WindowsIdentity.GetCurrent())
                    if (!DuplicateToken(identity.Token, 2, out token))
                        throw new InvalidOperationException("task_access_token_unavailable");
                var mapping = new GenericMapping { Read = 0x120089, Write = 0x120116,
                    Execute = 0x1200a0, All = 0x1f01ff };
                uint size = 4096, granted;
                uint required = mapping.All;
                if (descriptor.SystemAcl != null) required |= 0x01000000; // ACCESS_SYSTEM_SECURITY
                bool status;
                if (!AccessCheck(pinned.AddrOfPinnedObject(), token, required, ref mapping,
                    privileges, ref size, out granted, out status))
                    throw new InvalidOperationException("task_access_check_failed");
                return status && (granted & required) == required;
            }
            finally
            {
                if (token != IntPtr.Zero) CloseHandle(token);
                Marshal.FreeHGlobal(privileges);
                pinned.Free();
            }
        }

        public DateTime CurrentTime { get { return DateTime.Now; } }

        public string CurrentUser { get { return WindowsIdentity.GetCurrent().User.Value; } }

        private sealed class TaskOperationException : Exception
        {
            internal TaskOperationException(string operation, int code)
                : base(operation + "_0x" + code.ToString("X8")) { HResult = code; }
        }

        public static Exception SafeFailure(string operation, Exception error)
        {
            // Never forward provider messages, inner exceptions or credential-bearing arguments.
            var safe = new TaskOperationException(operation, error.HResult);
            safe.Data["ProviderHResult"] = error.HResult;
            var win32 = error as System.ComponentModel.Win32Exception;
            if (win32 != null) safe.Data["Win32Error"] = win32.NativeErrorCode;
            return safe;
        }

        public void CheckPermissions()
        {
            if (!new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator))
                throw new InvalidOperationException("task_management_elevation_required");
            try
            {
                service = Activator.CreateInstance(Type.GetTypeFromProgID("Schedule.Service"));
                service.Connect();
                folder = service.GetFolder("\\");
                if (!HasTaskManagementAccess((string)folder.GetSecurityDescriptor(7)))
                    throw new InvalidOperationException("task_folder_access_denied");
            }
            catch (Exception error) { throw SafeFailure("task_service_unavailable", error); }
        }

        private static string Sid(string user)
        {
            if (user.StartsWith("S-1-", StringComparison.Ordinal))
                return new SecurityIdentifier(user).Value;
            return ((SecurityIdentifier)new NTAccount(user).Translate(typeof(SecurityIdentifier))).Value;
        }

        public string ReadXml(string name)
        {
            try { return (string)folder.GetTask(name).Xml; }
            catch (COMException error)
            {
                if (error.HResult == unchecked((int)0x80070002)) return null;
                throw SafeFailure("task_read_failed", error);
            }
            catch (Exception error) { throw SafeFailure("task_read_failed", error); }
        }

        public string ReadSecurity(string name)
        {
            try
            {
                // Include auditing metadata. Refuse an unreadable SACL rather than losing it.
                string descriptor = (string)folder.GetTask(name).GetSecurityDescriptor(15);
                if (!HasTaskManagementAccess(descriptor))
                    throw new InvalidOperationException("task_write_or_recovery_access_denied");
                return descriptor;
            }
            catch (Exception error) { throw SafeFailure("task_security_read_failed", error); }
        }

        public void RequireIdle(string name)
        {
            try
            {
                dynamic task = folder.GetTask(name);
                if (((int)task.State != 1 && (int)task.State != 3) || ((bool)task.Enabled &&
                    (DateTime)task.NextRunTime > DateTime.MinValue &&
                    (DateTime)task.NextRunTime <= DateTime.Now.AddMinutes(30)))
                    throw new InvalidOperationException("task_running");
            }
            catch (Exception error) { throw SafeFailure("task_not_idle", error); }
        }

        private static void Clear(IntPtr buffer, int bytes)
        {
            if (buffer != IntPtr.Zero)
                for (int i = 0; i < bytes; i++) Marshal.WriteByte(buffer, i, 0);
        }

        public void Authenticate(string user)
        {
            if (!Environment.UserInteractive)
                throw new InvalidOperationException("operator_interactive_desktop_required");
            string expected;
            try { expected = Sid(user); }
            catch (Exception error) { throw SafeFailure("task_identity_invalid", error); }
            if (credentials.ContainsKey(expected)) return;
            IntPtr packed = IntPtr.Zero, userBuffer = IntPtr.Zero;
            IntPtr domainBuffer = IntPtr.Zero, passwordBuffer = IntPtr.Zero;
            uint packedSize = 0, userSize = 0, domainSize = 0, passwordSize = 0;
            int passwordBytes = 0;
            Credential credential = null;
            try
            {
                var info = new CredentialInfo();
                info.Size = Marshal.SizeOf(typeof(CredentialInfo));
                info.Caption = "Lockean Lite scheduler deployment";
                info.Message = "Enter the Windows password for " + user + ". Used for task registration and recovery only.";
                uint package = 0;
                bool save = false;
                // Secure desktop Windows UI, without a save checkbox or credential persistence.
                uint result = CredUIPromptForWindowsCredentialsW(
                    ref info, 0, ref package, IntPtr.Zero, 0, out packed, out packedSize, ref save, 0x1000);
                if (result != 0) throw new System.ComponentModel.Win32Exception((int)result);
                CredUnPackAuthenticationBufferW(1, packed, packedSize, IntPtr.Zero, ref userSize,
                    IntPtr.Zero, ref domainSize, IntPtr.Zero, ref passwordSize);
                if (Marshal.GetLastWin32Error() != 122 || userSize == 0 || passwordSize <= 1)
                    throw new InvalidOperationException("credential_buffer_invalid");
                userBuffer = Marshal.AllocHGlobal(checked((int)userSize * 2));
                domainBuffer = domainSize == 0 ? IntPtr.Zero : Marshal.AllocHGlobal(checked((int)domainSize * 2));
                passwordBytes = checked((int)passwordSize * 2);
                passwordBuffer = Marshal.AllocHGlobal(passwordBytes);
                if (!CredUnPackAuthenticationBufferW(1, packed, packedSize, userBuffer, ref userSize,
                    domainBuffer, ref domainSize, passwordBuffer, ref passwordSize))
                    throw new InvalidOperationException("credential_unpack_failed");
                string enteredUser = Marshal.PtrToStringUni(userBuffer);
                string enteredDomain = domainBuffer == IntPtr.Zero ? null : Marshal.PtrToStringUni(domainBuffer);
                string account = String.IsNullOrEmpty(enteredDomain) ? enteredUser : enteredDomain + "\\" + enteredUser;
                if (!String.Equals(Sid(account), expected, StringComparison.Ordinal))
                    throw new InvalidOperationException("credential_identity_mismatch");
                credential = new Credential();
                credential.User = enteredUser;
                credential.Domain = String.IsNullOrEmpty(enteredDomain) ? Environment.MachineName : enteredDomain;
                int separator = enteredUser.IndexOf('\\');
                if (separator >= 0)
                {
                    credential.Domain = enteredUser.Substring(0, separator);
                    credential.User = enteredUser.Substring(separator + 1);
                }
                else if (enteredUser.Contains("@")) credential.Domain = null;
                credential.Password = new SecureString();
                for (int i = 0; i < passwordBytes / 2; i++)
                {
                    char character = (char)Marshal.ReadInt16(passwordBuffer, i * 2);
                    if (character == '\0') break;
                    credential.Password.AppendChar(character);
                }
                if (credential.Password.Length == 0) throw new InvalidOperationException("credential_empty");
                credential.Password.MakeReadOnly();
                IntPtr token;
                // Batch logon tests the actual task-account password and batch-logon right.
                if (!LogonUserW(credential.User, credential.Domain, passwordBuffer, 4, 0, out token))
                    throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
                try
                {
                    using (var authenticated = new WindowsIdentity(token))
                        if (authenticated.User.Value != expected)
                            throw new InvalidOperationException("authenticated_identity_mismatch");
                }
                finally { CloseHandle(token); }
                credentials.Add(expected, credential);
                credential = null;
            }
            catch (Exception error) { throw SafeFailure("task_authentication_failed", error); }
            finally
            {
                if (credential != null) credential.Dispose();
                Clear(passwordBuffer, passwordBytes);
                Clear(packed, checked((int)packedSize));
                if (passwordBuffer != IntPtr.Zero) Marshal.FreeHGlobal(passwordBuffer);
                if (domainBuffer != IntPtr.Zero) Marshal.FreeHGlobal(domainBuffer);
                if (userBuffer != IntPtr.Zero) Marshal.FreeHGlobal(userBuffer);
                if (packed != IntPtr.Zero) Marshal.FreeCoTaskMem(packed);
            }
        }

        private void Register(string name, string xml, string security, int flags)
        {
            IntPtr passwordBuffer = IntPtr.Zero;
            string temporaryPassword = null;
            GCHandle pinnedPassword = new GCHandle();
            try
            {
                var document = new XmlDocument();
                document.LoadXml(xml);
                var ns = new XmlNamespaceManager(document.NameTable);
                ns.AddNamespace("t", "http://schemas.microsoft.com/windows/2004/02/mit/task");
                var principal = document.SelectSingleNode("/t:Task/t:Principals/t:Principal", ns);
                string user = principal.SelectSingleNode("t:UserId", ns).InnerText;
                string type = principal.SelectSingleNode("t:LogonType", ns).InnerText;
                int logon;
                if (type == "Password")
                {
                    logon = 1;
                    Credential credential = credentials[Sid(user)];
                    passwordBuffer = Marshal.SecureStringToBSTR(credential.Password);
                    // Automation VARIANT requires a temporary managed string for COM marshaling.
                    // It is never passed to PowerShell or used in exception text.
                    temporaryPassword = Marshal.PtrToStringBSTR(passwordBuffer);
                    pinnedPassword = GCHandle.Alloc(temporaryPassword, GCHandleType.Pinned);
                }
                else if (type == "InteractiveToken" && Sid(user) == Sid(CurrentUser)) logon = 3;
                else throw new InvalidOperationException("unsupported_task_logon");
                object registered = folder.RegisterTask(name, xml, flags, user, temporaryPassword, logon, String.IsNullOrEmpty(security) ? null : security);
                if (registered != null && Marshal.IsComObject(registered)) Marshal.ReleaseComObject(registered);
            }
            catch (Exception error) { throw SafeFailure("task_registration_failed", error); }
            finally
            {
                if (pinnedPassword.IsAllocated)
                {
                    Clear(pinnedPassword.AddrOfPinnedObject(), temporaryPassword.Length * 2);
                    pinnedPassword.Free();
                }
                temporaryPassword = null;
                if (passwordBuffer != IntPtr.Zero) Marshal.ZeroFreeBSTR(passwordBuffer);
            }
        }

        public string NormalizeXml(string xml)
        {
            try
            {
                dynamic definition = service.NewTask(0);
                try { definition.XmlText = xml; return (string)definition.XmlText; }
                finally { if (Marshal.IsComObject(definition)) Marshal.ReleaseComObject(definition); }
            }
            catch (Exception error) { throw SafeFailure("task_xml_invalid", error); }
        }

        public void Validate(string name, string xml, string security) { Register(name, xml, security, 1); }
        public void Write(string name, string xml, string security, bool existing)
        {
            // Update existing definitions only; never recreate a task lost concurrently.
            // Preserve the ACL and suppress any registration-trigger execution.
            Register(name, xml, security, (existing ? 4 | 16 : 2) | 32);
        }

        public void Remove(string name)
        {
            try { folder.DeleteTask(name, 0); }
            catch (Exception error) { throw SafeFailure("task_removal_failed", error); }
        }

        public bool SecurityMatches(string name, string expected)
        {
            var actual = new RawSecurityDescriptor(ReadSecurity(name));
            var prior = new RawSecurityDescriptor(expected);
            var a = new byte[actual.BinaryLength];
            var b = new byte[prior.BinaryLength];
            actual.GetBinaryForm(a, 0);
            prior.GetBinaryForm(b, 0);
            return Convert.ToBase64String(a) == Convert.ToBase64String(b);
        }

        public void Dispose()
        {
            foreach (Credential credential in credentials.Values) credential.Dispose();
            credentials.Clear();
            if (folder != null && Marshal.IsComObject(folder)) Marshal.ReleaseComObject(folder);
            if (service != null && Marshal.IsComObject(service)) Marshal.ReleaseComObject(service);
            folder = null;
            service = null;
        }
    }
}
