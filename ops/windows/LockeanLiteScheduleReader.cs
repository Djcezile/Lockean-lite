using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;
using System.Xml;

namespace LockeanAcceptance
{
    [StructLayout(LayoutKind.Sequential)]
    public struct SchedulerSystemTime
    {
        public ushort Year, Month, DayOfWeek, Day, Hour, Minute, Second, Milliseconds;
        internal static SchedulerSystemTime From(DateTime d)
        {
            return new SchedulerSystemTime {Year=(ushort)d.Year,Month=(ushort)d.Month,Day=(ushort)d.Day,
                DayOfWeek=(ushort)d.DayOfWeek,Hour=(ushort)d.Hour,Minute=(ushort)d.Minute,Second=(ushort)d.Second};
        }
        internal DateTime Date() { return new DateTime(Year,Month,Day,Hour,Minute,Second,Milliseconds,DateTimeKind.Unspecified); }
    }

    // Read-only ABI projection of taskschd.h IRegisteredTask, in SDK vtable order.
    // Four IDispatch slots and every unused slot retain their positions. Reserved
    // slots have no callable signature and are never invoked. No mutator is exposed.
    // GUID/order: microsoft/win32metadata generation/WinSDK/RecompiledIdlHeaders/um/taskschd.h
    [ComImport, Guid("9c86f320-dee3-4dd1-b972-a303f26b061e"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    internal interface IRegisteredTaskReadOnly
    {
        void ReservedDispatch0(); void ReservedDispatch1(); void ReservedDispatch2(); void ReservedDispatch3();
        [return: MarshalAs(UnmanagedType.BStr)] string GetName();
        [return: MarshalAs(UnmanagedType.BStr)] string GetPath();
        int GetState();
        [return: MarshalAs(UnmanagedType.VariantBool)] bool GetEnabled();
        void ReservedEnabledSetter(); void ReservedRun(); void ReservedRunEx();
        [return: MarshalAs(UnmanagedType.IDispatch)] object GetInstances(int flags);
        void ReservedLastRun(); void ReservedLastResult(); void ReservedMissedRuns();
        [PreserveSig] int GetNextRunTime(out double oleDate);
        void ReservedDefinition();
        [return: MarshalAs(UnmanagedType.BStr)] string GetXml();
        void ReservedSecurityRead(); void ReservedSecurityWrite(); void ReservedStop();
        [PreserveSig] int GetRunTimes(ref SchedulerSystemTime start,ref SchedulerSystemTime end,ref uint count,out IntPtr times);
    }

    public sealed class ScheduleEvidence
    {
        public string Status, Task, NextRunLocal, Reason;
        public uint[] PredictionCounts = new uint[0];
        public bool Enabled;
        public int State, HResult;
        public string[] LocalTimes = new string[0], UtcTimes = new string[0];
    }

    public static class ScheduleClient
    {
        private static bool IsDaily(string n) { return n == "LockeanLite-DailyPaper" || n.EndsWith("-Daily",StringComparison.Ordinal); }
        private static void Identity(string name)
        {
            if(name!="LockeanLite-DailyPaper" && name!="LockeanLite-Watchdog" &&
                !Regex.IsMatch(name??"","\\ALockeanLite-Acceptance-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}-(Daily|Watchdog)\\z"))
                throw new InvalidOperationException("schedule_identity_denied");
        }
        private static void Allowed(string name,string[] allowlist)
        {
            Identity(name);
            if(allowlist==null || !allowlist.Contains(name,StringComparer.Ordinal)) throw new InvalidOperationException("schedule_identity_not_permitted");
        }
        public static void ValidateSchedule(string name,string xml)
        {
            Identity(name);
            var doc=Fixtures.Parse(xml);var ns=Fixtures.Names(doc);
            if(doc.SelectNodes("/t:Task/t:Triggers/*",ns).Count!=1 ||
                doc.SelectNodes("/t:Task/t:Triggers/t:CalendarTrigger",ns).Count!=1 ||
                doc.SelectNodes("/t:Task/t:Triggers/t:CalendarTrigger/*",ns).Count!=3 ||
                Fixtures.Text(doc,"/t:Task/t:Triggers/t:CalendarTrigger/t:Enabled")!="true" ||
                Fixtures.Text(doc,"/t:Task/t:Triggers/t:CalendarTrigger/t:ScheduleByWeek/t:WeeksInterval")!="1")
                throw new InvalidOperationException("schedule_cadence_invalid");
            var days=doc.SelectNodes("/t:Task/t:Triggers/t:CalendarTrigger/t:ScheduleByWeek/t:DaysOfWeek/*",ns);
            string[] expected={"Monday","Tuesday","Wednesday","Thursday","Friday"};
            if(days.Count!=5 || !days.Cast<XmlNode>().Select(n=>n.LocalName).OrderBy(n=>n).SequenceEqual(expected.OrderBy(n=>n)) ||
                days.Cast<XmlNode>().Any(n=>n.NamespaceURI!=Fixtures.NS || n.HasChildNodes))
                throw new InvalidOperationException("schedule_weekdays_invalid");
            string boundary=Fixtures.Text(doc,"/t:Task/t:Triggers/t:CalendarTrigger/t:StartBoundary");
            DateTime parsed;
            if(!Regex.IsMatch(boundary,"\\A[0-9]{4}-[0-9]{2}-[0-9]{2}T09:"+(IsDaily(name)?"15":"20")+":00\\z") ||
                !DateTime.TryParseExact(boundary,"yyyy-MM-dd'T'HH:mm:ss",CultureInfo.InvariantCulture,DateTimeStyles.None,out parsed))
                throw new InvalidOperationException("schedule_offset_or_wall_clock_invalid");
        }
        public static ScheduleEvidence Evaluate(string name,string xml,DateTime[] times,int hresult,bool enabled,int state)
        {
            ValidateSchedule(name,xml);
            var evidence=new ScheduleEvidence {Task=name,Enabled=enabled,State=state,HResult=hresult,Status="INCONCLUSIVE"};
            if(hresult!=0 || times==null) return evidence;
            var eastern=TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
            if(times.Any(d=>d.Kind!=DateTimeKind.Unspecified || d.Hour!=9 || d.Minute!=(IsDaily(name)?15:20) ||
                d.Second!=0 || d.DayOfWeek==DayOfWeek.Saturday || d.DayOfWeek==DayOfWeek.Sunday ||
                eastern.IsInvalidTime(d) || eastern.IsAmbiguousTime(d)))
            {evidence.Status="FAIL";return evidence;}
            if(times.Length<2) return evidence;
            evidence.LocalTimes=times.Select(d=>d.ToString("yyyy-MM-ddTHH:mm:ss",CultureInfo.InvariantCulture)).ToArray();
            evidence.UtcTimes=times.Select(d=>TimeZoneInfo.ConvertTimeToUtc(d,eastern).ToString("yyyy-MM-ddTHH:mm:ss'Z'",CultureInfo.InvariantCulture)).ToArray();
            evidence.Status="PASS";return evidence;
        }
        private static T WithTask<T>(string name,string[] permitted,Func<IRegisteredTaskReadOnly,T> read)
        {
            Allowed(name,permitted); // Before COM connection, and again before GetTask.
            object service=null,folder=null,registered=null;
            try
            {
                dynamic scheduler=service=Activator.CreateInstance(Type.GetTypeFromProgID("Schedule.Service"));
                scheduler.Connect(); dynamic root=folder=scheduler.GetFolder("\\");
                Allowed(name,permitted); registered=root.GetTask(name);
                var task=(IRegisteredTaskReadOnly)registered;
                if(task.GetName()!=name || task.GetPath()!="\\"+name) throw new InvalidOperationException("registered_identity_mismatch");
                return read(task);
            }
            finally
            {
                foreach(object item in new[]{registered,folder,service})
                    if(item!=null && Marshal.IsComObject(item)) Marshal.ReleaseComObject(item);
            }
        }
        public static ScheduleEvidence Inspect(string name,string[] permitted)
        {
            return WithTask(name,permitted,task=>{
                double date; int hr=task.GetNextRunTime(out date);
                return new ScheduleEvidence{Task=name,Status="INSPECTED",Enabled=task.GetEnabled(),State=task.GetState(),HResult=hr,
                    NextRunLocal=hr==0 && date>0 ? DateTime.FromOADate(date).ToString("yyyy-MM-ddTHH:mm:ss",CultureInfo.InvariantCulture):null};
            });
        }
        // Enabled/task-state readback is independent of predictions and XML serialization.
        public static void RequireDisabled(string name,string[] permitted)
        {
            WithTask(name,permitted,task=>{
                if(task.GetEnabled() || task.GetState()!=1) throw new InvalidOperationException("fixture_not_disabled_idle");
                object instances=task.GetInstances(0);
                try { if((int)((dynamic)instances).Count!=0) throw new InvalidOperationException("fixture_instances_present"); }
                finally { if(Marshal.IsComObject(instances)) Marshal.ReleaseComObject(instances); }
                return true;
            });
        }
        public static ScheduleEvidence Query(string name,string[] permitted,int year)
        {
            Allowed(name,permitted);
            if(year<DateTime.Now.Year+1 || year>2099) throw new InvalidOperationException("future_transition_year_required");
            if(TimeZoneInfo.Local.Id!="Eastern Standard Time") throw new InvalidOperationException("host_eastern_timezone_required");
            try
            {
                return WithTask(name,permitted,task=>{
                    string xml=task.GetXml();
                    try {ValidateSchedule(name,xml);}
                    catch(InvalidOperationException) {return new ScheduleEvidence{Task=name,Status="FAIL",Reason="invalid_registered_schedule"};}
                    // Current US rules: second Sunday in March, first Sunday in November.
                    // Query adjacent Fridays/Mondays and require actual installed rules to agree.
                    Func<int,int,DateTime> sunday=(month,ordinal)=>{
                        var first=new DateTime(year,month,1);
                        return first.AddDays(((7-(int)first.DayOfWeek)%7)+7*(ordinal-1));
                    };
                    DateTime spring=sunday(3,2),fall=sunday(11,1);
                    var dates=new[]{spring.AddDays(-2),spring.AddDays(1),fall.AddDays(-2),fall.AddDays(1)};
                    var eastern=TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
                    if(eastern.GetUtcOffset(dates[0].AddHours(12))!=TimeSpan.FromHours(-5) ||
                        eastern.GetUtcOffset(dates[1].AddHours(12))!=TimeSpan.FromHours(-4) ||
                        eastern.GetUtcOffset(dates[2].AddHours(12))!=TimeSpan.FromHours(-4) ||
                        eastern.GetUtcOffset(dates[3].AddHours(12))!=TimeSpan.FromHours(-5))
                        return new ScheduleEvidence{Task=name,Status="INCONCLUSIVE"};
                    var values=new List<DateTime>(); var counts=new List<uint>(); int outcome=0; bool incomplete=false;
                    foreach(DateTime date in dates)
                    {
                        var begin=SchedulerSystemTime.From(date);var end=SchedulerSystemTime.From(date.AddDays(1).AddTicks(-TimeSpan.TicksPerSecond));
                        uint count=32;IntPtr buffer=IntPtr.Zero;
                        try
                        {
                            // Native SYSTEMTIME values are local wall times; never apply ToLocalTime.
                            int hr=task.GetRunTimes(ref begin,ref end,ref count,out buffer);
                            counts.Add(count);
                            if(hr!=0 || count!=1 || buffer==IntPtr.Zero) {outcome=hr;incomplete=true;break;}
                            DateTime value=((SchedulerSystemTime)Marshal.PtrToStructure(buffer,typeof(SchedulerSystemTime))).Date();
                            if(value.Date!=date.Date) return new ScheduleEvidence{Task=name,Status="FAIL"};
                            values.Add(value);
                        }
                        finally {if(buffer!=IntPtr.Zero) Marshal.FreeCoTaskMem(buffer);}
                    }
                    var result=Evaluate(name,xml,values.ToArray(),outcome,task.GetEnabled(),task.GetState());
                    result.PredictionCounts=counts.ToArray();
                    if(incomplete || values.Count!=4) {result.Status="INCONCLUSIVE";result.Reason="prediction_unavailable_or_incomplete";}
                    // Guard against a definition changing between XML admission and query completion.
                    if(Fixtures.Canonical(xml)!=Fixtures.Canonical(task.GetXml())) result.Status="INCONCLUSIVE";
                    return result;
                });
            }
            catch(COMException e) {return new ScheduleEvidence{Task=name,Status="INCONCLUSIVE",HResult=e.HResult};}
        }
    }
}
