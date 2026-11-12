using System.ComponentModel;

namespace AkikazuHardwareCheck.Core.SharedDesktop;

public sealed record OfflinePackageCandidate(string InfPath, IReadOnlyList<OfflineInfMatch> Matches, bool IsPossible = false);
public sealed record OfflinePackageSearchResult(IReadOnlyList<OfflinePackageCandidate> Candidates, int UnreadableInfCount);

public static class OfflinePackageSearch
{
    public static OfflinePackageSearchResult Find(string root, IReadOnlyList<NetworkDeviceCandidate> devices) =>
        Find(root, devices, includePossible: false);

    public static OfflinePackageSearchResult Find(string root, IReadOnlyList<NetworkDeviceCandidate> devices, bool includePossible) =>
        Find([root], devices, includePossible);

    public static OfflinePackageSearchResult Find(IEnumerable<string> roots, IReadOnlyList<NetworkDeviceCandidate> devices, bool includePossible)
    {
        var options = new EnumerationOptions
        {
            RecurseSubdirectories = true,
            AttributesToSkip = FileAttributes.ReparsePoint,
            IgnoreInaccessible = false,
        };
        var candidates = new List<OfflinePackageCandidate>();
        var possible = new List<OfflinePackageCandidate>();
        var unreadable = 0;
        foreach (var path in roots.SelectMany(root => Directory.EnumerateFiles(root, "*.inf", options)))
        {
            try
            {
                var alternatives = includePossible ? new List<OfflineInfMatch>() : null;
                var matches = OfflineInfMatcher.Match(path, devices, alternatives);
                if (matches.Count > 0)
                {
                    candidates.Add(new OfflinePackageCandidate(path, matches));
                }
                if (alternatives is { Count: > 0 })
                {
                    possible.Add(new OfflinePackageCandidate(path, alternatives, IsPossible: true));
                }
            }
            catch (Win32Exception)
            {
                unreadable++;
            }
        }

        // Prefer entries offering the first (most specific) hardware ID. This is a display order, not Windows driver ranking.
        var confirmedDevices = candidates.SelectMany(candidate => candidate.Matches).Select(match => match.Device).ToHashSet();
        var remaining = possible.Select(candidate => candidate with
        {
            Matches = candidate.Matches.Where(match => !confirmedDevices.Contains(match.Device)).ToArray(),
        }).Where(candidate => candidate.Matches.Count > 0);
        return new OfflinePackageSearchResult(candidates
            .OrderBy(candidate => candidate.Matches.Min(match => Array.FindIndex(
                match.Device.HardwareIds, id => string.Equals(id, match.HardwareId, StringComparison.OrdinalIgnoreCase))))
            .ThenBy(candidate => candidate.InfPath, StringComparer.OrdinalIgnoreCase)
            .Concat(remaining.OrderBy(candidate => candidate.InfPath, StringComparer.OrdinalIgnoreCase))
            .ToArray(), unreadable);
    }
}
