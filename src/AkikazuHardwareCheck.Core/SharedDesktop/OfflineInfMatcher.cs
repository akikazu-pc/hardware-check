using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;

namespace AkikazuHardwareCheck.Core.SharedDesktop;

public sealed record OfflineInfMatch(PciNetworkDevice Device, string HardwareId, string ModelsSection);

public static class OfflineInfMatcher
{
    private const int INF_STYLE_WIN4 = 2;
    private static readonly Guid NetworkClass = new("4d36e972-e325-11ce-bfc1-08002be10318");

    public static IReadOnlyList<OfflineInfMatch> Match(string path, IReadOnlyList<PciNetworkDevice> devices)
    {
        var inf = SetupOpenInfFile(path, null, INF_STYLE_WIN4, out _);
        if (inf == new IntPtr(-1))
        {
            throw new Win32Exception(Marshal.GetLastWin32Error());
        }

        try
        {
            if (!SetupFindFirstLine(inf, "Version", "ClassGuid", out var version) ||
                !Guid.TryParse(ReadField(ref version, 1), out var classGuid) || classGuid != NetworkClass ||
                !SetupFindFirstLine(inf, "Manufacturer", null, out var manufacturer))
            {
                return [];
            }

            var modelIds = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            do
            {
                var section = new StringBuilder(4096);
                if (SetupDiGetActualModelsSection(ref manufacturer, IntPtr.Zero, section, section.Capacity,
                    out _, IntPtr.Zero))
                {
                    ReadModels(inf, section.ToString(), modelIds);
                }
            }
            while (MoveNext(ref manufacturer));

            var matches = new List<OfflineInfMatch>();
            foreach (var device in devices)
            {
                foreach (var hardwareId in device.HardwareIds)
                {
                    if (modelIds.TryGetValue(hardwareId, out var section))
                    {
                        matches.Add(new OfflineInfMatch(device, hardwareId, section));
                        break;
                    }
                }
            }

            return matches;
        }
        finally
        {
            SetupCloseInfFile(inf);
        }
    }

    public static string? ReadDriverVersion(string path)
    {
        var inf = SetupOpenInfFile(path, null, INF_STYLE_WIN4, out _);
        if (inf == new IntPtr(-1))
        {
            return null;
        }

        try
        {
            return SetupFindFirstLine(inf, "Version", "DriverVer", out var line) ? ReadField(ref line, 2) : null;
        }
        finally
        {
            SetupCloseInfFile(inf);
        }
    }

    private static void ReadModels(IntPtr inf, string section, Dictionary<string, string> modelIds)
    {
        if (!SetupFindFirstLine(inf, section, null, out var model))
        {
            return;
        }

        do
        {
            // Field 1 is the install section. Field 2 is the model's hardware ID.
            // Later fields are compatible IDs and are intentionally excluded from this preview.
            if (ReadField(ref model, 2) is { } id)
            {
                modelIds.TryAdd(id, section);
            }
        }
        while (MoveNext(ref model));
    }

    private static string? ReadField(ref InfContext context, int index)
    {
        var value = new StringBuilder(4096);
        return SetupGetStringField(ref context, index, value, value.Capacity, out _) ? value.ToString() : null;
    }

    private static bool MoveNext(ref InfContext context)
    {
        var hasNext = SetupFindNextLine(ref context, out var next);
        context = next;
        return hasNext;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct InfContext
    {
        public IntPtr Inf;
        public IntPtr CurrentInf;
        public uint Section;
        public uint Line;
    }

    [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr SetupOpenInfFile(string fileName, string? infClass, int style, out uint errorLine);

    [DllImport("setupapi.dll", ExactSpelling = true)]
    private static extern void SetupCloseInfFile(IntPtr inf);

    [DllImport("setupapi.dll", CharSet = CharSet.Unicode)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetupFindFirstLine(IntPtr inf, string section, string? key, out InfContext context);

    [DllImport("setupapi.dll", ExactSpelling = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetupFindNextLine(ref InfContext context, out InfContext next);

    [DllImport("setupapi.dll", CharSet = CharSet.Unicode)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetupGetStringField(ref InfContext context, int index, StringBuilder buffer,
        int size, out uint requiredSize);

    [DllImport("setupapi.dll", CharSet = CharSet.Unicode)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetupDiGetActualModelsSection(ref InfContext context, IntPtr alternatePlatform,
        StringBuilder section, int size, out uint requiredSize, IntPtr reserved);
}
