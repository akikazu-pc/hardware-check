using System.ComponentModel;

namespace AkikazuHardwareCheck.Core.SharedDesktop;

public sealed record OfflinePackageCandidate(string InfPath, IReadOnlyList<OfflineInfMatch> Matches);
public sealed record OfflinePackageSearchResult(IReadOnlyList<OfflinePackageCandidate> Candidates, int UnreadableInfCount);

public static class OfflinePackageSearch
{
    public static OfflinePackageSearchResult Find(string root, IReadOnlyList<PciNetworkDevice> devices)
    {
        var options = new EnumerationOptions
        {
            RecurseSubdirectories = true,
            AttributesToSkip = FileAttributes.ReparsePoint,
            IgnoreInaccessible = false,
        };
        var candidates = new List<OfflinePackageCandidate>();
        var unreadable = 0;
        foreach (var path in Directory.EnumerateFiles(root, "*.inf", options))
        {
            try
            {
                var matches = OfflineInfMatcher.Match(path, devices);
                if (matches.Count > 0)
                {
                    candidates.Add(new OfflinePackageCandidate(path, matches));
                }
            }
            catch (Win32Exception)
            {
                unreadable++;
            }
        }

        // Prefer entries offering the first (most specific) hardware ID. This is a display order, not Windows driver ranking.
        return new OfflinePackageSearchResult(candidates
            .OrderBy(candidate => candidate.Matches.Min(match => Array.FindIndex(
                match.Device.HardwareIds, id => string.Equals(id, match.HardwareId, StringComparison.OrdinalIgnoreCase))))
            .ThenBy(candidate => candidate.InfPath, StringComparer.OrdinalIgnoreCase)
            .ToArray(), unreadable);
    }
}
