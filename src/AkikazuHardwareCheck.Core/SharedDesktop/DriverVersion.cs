using System.Globalization;

namespace AkikazuHardwareCheck.Core.SharedDesktop;

/// <summary>
/// Compares the dotted numeric versions used by vendor network INFs.
/// Missing trailing segments count as zero, so 1.2 equals 1.2.0.
/// Invalid or missing inputs never report an update.
/// </summary>
public static class DriverVersion
{
    public static bool IsNewer(string? candidate, string? installed)
    {
        if (!TryParse(candidate, out var newer) || !TryParse(installed, out var current))
        {
            return false;
        }

        for (var index = 0; index < Math.Max(newer.Length, current.Length); index++)
        {
            var left = index < newer.Length ? newer[index] : 0;
            var right = index < current.Length ? current[index] : 0;
            if (left != right)
            {
                return left > right;
            }
        }

        return false;
    }

    private static bool TryParse(string? value, out int[] segments)
    {
        segments = [];
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        var parts = value.Trim().Split('.');
        var parsed = new int[parts.Length];
        for (var index = 0; index < parts.Length; index++)
        {
            if (!int.TryParse(parts[index], NumberStyles.None, CultureInfo.InvariantCulture, out parsed[index]))
            {
                return false;
            }
        }

        segments = parsed;
        return true;
    }
}
