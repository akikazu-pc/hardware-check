using Microsoft.VisualBasic.FileIO;
using System.Text;

namespace AkikazuHardwareCheck.Core.SharedDesktop;

public enum RescueDeviceCategory { DiyDesktop, Laptop, Other }

public enum RescueDeviceTag
{
    BrandedDesktop, MiniPc, WindowsTablet, Handheld, AllInOne, Htpc, SingleBoardComputer, WindowsPhone, Mac, ModifiedChromebook,
    Workstation, NetworkAdapter,
}

public sealed record RescueCatalogModel(string Type, string Brand, string Model, string Platform, string Windows,
    string Module, string Windows10Evidence, string Windows11Evidence, Uri? Source, Uri? DriverPage, bool IsSeries,
    RescueDeviceCategory Category, RescueDeviceTag? DeviceTag, bool RequiresRevisionSelection = false);

public static class RescueModelCatalog
{
    private sealed record CatalogRow(RescueCatalogModel Model, string[] Aliases);

    private sealed record SearchEntry(RescueCatalogModel Model, string DisplayName, string Brand, string LooseBrand,
        SearchKey[] Keys);

    private readonly record struct SearchKey(string Name, string FullName, string LooseName, string LooseFullName);

    private static readonly Lazy<SearchEntry[]> Models = new(() => BuildSearchIndex().ToArray());
    private static readonly Lazy<ILookup<(string Digits, int Plus), (SearchEntry Entry, string Key)>> FuzzyKeys = new(() =>
        Models.Value.SelectMany(entry => entry.Keys.SelectMany(key => new[] { key.Name, key.FullName })
            .Distinct(StringComparer.Ordinal).Select(key => (entry, key))).ToLookup(row => Fingerprint(row.key)));

    public static IReadOnlyList<RescueCatalogModel> Search(string query, RescueDeviceCategory? category = null,
        RescueDeviceTag? tag = null) => Search(query, category, tag, out _);

    public static IReadOnlyList<RescueCatalogModel> Search(string query, RescueDeviceCategory? category,
        RescueDeviceTag? tag, out bool approximate)
    {
        approximate = false;
        var (exactQuery, queryCategory, queryTag) = RescueCatalogQuery.Parse(query);
        if ((category is not null && queryCategory is not null && category != queryCategory) ||
            (tag is not null && queryTag is not null && tag != queryTag))
        {
            return [];
        }

        category ??= queryCategory;
        tag ??= queryTag;
        var key = Normalize(exactQuery);
        if ((tag is not null && category != RescueDeviceCategory.Other) || (key.Length < 2 && category is null))
        {
            return [];
        }

        var terms = exactQuery.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries)
            .Select(Normalize).Where(term => term.Length > 0).ToArray();
        var looseKey = WithoutPlus(key);
        var looseTerms = terms.Select(WithoutPlus).ToArray();
        bool InScope(SearchEntry entry) => (category is null || entry.Model.Category == category) &&
            (tag is null || entry.Model.DeviceTag == tag);
        var ranked = Models.Value.Where(InScope)
            .Select(entry => (entry.Model, Rank: MatchRank(entry, exactQuery, key, terms, looseKey, looseTerms)))
            .Where(row => row.Rank >= 0)
            .OrderBy(row => row.Rank)
            .ThenBy(row => row.Model.Model, StringComparer.OrdinalIgnoreCase)
            .ToArray();
        if (ranked.Length > 0)
        {
            approximate = ranked[0].Rank == 4;
            return ranked.Select(row => row.Model).ToArray();
        }

        if (key.Length < 6 || key.Length > 80)
        {
            return [];
        }

        var fingerprint = Fingerprint(key);
        if (fingerprint.Digits.Length == 0 && key.Length < 8)
        {
            return [];
        }

        var results = FuzzyKeys.Value[fingerprint].Where(row => InScope(row.Entry) && IsOneEdit(key, row.Key))
            .Select(row => row.Entry.Model).Distinct().OrderBy(model => model.Model, StringComparer.OrdinalIgnoreCase).ToArray();
        approximate = results.Length > 0;
        return results;
    }

    private static (string Digits, int Plus) Fingerprint(string key) =>
        (new string(key.Where(char.IsDigit).ToArray()), key.Count(character => character == '+'));

    private static bool IsOneEdit(ReadOnlySpan<char> left, ReadOnlySpan<char> right)
    {
        if (Math.Abs(left.Length - right.Length) > 1)
        {
            return false;
        }

        if (left.Length > right.Length)
        {
            return IsOneEdit(right, left);
        }

        var first = 0;
        while (first < left.Length && left[first] == right[first])
        {
            first++;
        }

        if (left.Length < right.Length)
        {
            return left[first..].SequenceEqual(right[(first + 1)..]);
        }

        return first < left.Length && (left[(first + 1)..].SequenceEqual(right[(first + 1)..]) ||
            (first + 1 < left.Length && left[first] == right[first + 1] && left[first + 1] == right[first] &&
             left[(first + 2)..].SequenceEqual(right[(first + 2)..])));
    }

    private static int MatchRank(SearchEntry entry, string query, string key, string[] terms, string looseKey,
        string[] looseTerms)
    {
        if (entry.Model.Model.Equals(query, StringComparison.OrdinalIgnoreCase) ||
            entry.DisplayName.Equals(query, StringComparison.OrdinalIgnoreCase))
        {
            return 0;
        }

        var rank = -1;
        foreach (var candidate in entry.Keys)
        {
            if (candidate.Name == key || candidate.FullName == key)
            {
                return 1;
            }

            if (candidate.Name.StartsWith(key, StringComparison.Ordinal))
            {
                rank = 2;
            }
            else if (rank != 2 && Matches(candidate.Name, candidate.FullName, entry.Brand, key, terms))
            {
                rank = 3;
            }
            else if (rank < 0 && looseKey.Length > 0 &&
                     Matches(candidate.LooseName, candidate.LooseFullName, entry.LooseBrand, looseKey, looseTerms))
            {
                rank = 4;
            }
        }

        return rank;
    }

    private static bool Matches(string name, string fullName, string brand, string key, string[] terms)
    {
        if (fullName.Contains(key, StringComparison.Ordinal))
        {
            return true;
        }

        foreach (var term in terms)
        {
            if (!name.Contains(term, StringComparison.Ordinal) && !brand.Contains(term, StringComparison.Ordinal))
            {
                return false;
            }
        }

        return terms.Length > 0;
    }

    private static IEnumerable<SearchEntry> BuildSearchIndex()
    {
        var supplemental = ReadModels("rescue.search-models.csv", useLegacySupportLookup: false)
            .ToLookup(row => CatalogIdentity(row.Model));
        var matched = new HashSet<(RescueDeviceCategory Category, RescueDeviceTag? Tag, string Brand, string Model)>();
        foreach (var curated in ReadModels("rescue.model-gaps.csv", useLegacySupportLookup: true))
        {
            if (curated.Model.Type == "laptop-os-record")
            {
                yield return Index(curated.Model, curated.Aliases);
                continue;
            }

            var identity = CatalogIdentity(curated.Model);
            matched.Add(identity);
            yield return Index(curated.Model, curated.Aliases.Concat(supplemental[identity].SelectMany(row => row.Aliases)));
        }

        foreach (var group in supplemental)
        {
            if (!matched.Contains(group.Key))
            {
                yield return Index(group.First().Model, group.SelectMany(row => row.Aliases));
            }
        }
    }

    private static (RescueDeviceCategory Category, RescueDeviceTag? Tag, string Brand, string Model) CatalogIdentity(RescueCatalogModel model)
    {
        var brand = model.Brand.Trim();
        var name = model.Model.Trim();
        if (brand.Length > 0 && name.Length > brand.Length && char.IsWhiteSpace(name[brand.Length]) &&
            name.StartsWith(brand, StringComparison.OrdinalIgnoreCase))
        {
            name = name[brand.Length..].TrimStart();
        }

        return (model.Category, model.DeviceTag, brand.ToUpperInvariant(), name.ToUpperInvariant());
    }

    private static SearchEntry Index(RescueCatalogModel model, IEnumerable<string> aliases)
    {
        var brand = Normalize(model.Brand);
        var looseBrand = WithoutPlus(brand);
        var keys = aliases.Prepend(model.Model).Select(Normalize).Distinct(StringComparer.Ordinal)
            .Select(name =>
            {
                var looseName = WithoutPlus(name);
                return new SearchKey(name, brand + name, looseName, looseBrand + looseName);
            }).ToArray();
        return new SearchEntry(model, $"{model.Brand} {model.Model}", brand, looseBrand, keys);
    }

    private static IEnumerable<CatalogRow> ReadModels(string resourceName, bool useLegacySupportLookup)
    {
        using var stream = typeof(RescueModelCatalog).Assembly.GetManifestResourceStream(resourceName)
            ?? throw new InvalidOperationException($"The model catalog is missing: {resourceName}");
        using var csv = new TextFieldParser(stream);
        csv.SetDelimiters(",");
        var header = csv.ReadFields() ?? [];
        var categoryColumn = Array.IndexOf(header, "deviceCategory");
        var tagColumn = Array.IndexOf(header, "deviceTag");
        var aliasesColumn = Array.IndexOf(header, "aliases");
        var driverPageColumn = Array.IndexOf(header, "driverPage");
        while (csv.ReadFields() is { Length: >= 11 } row)
        {
            var source = Https(row[8]);
            var category = ReadEnum<RescueDeviceCategory>(row, categoryColumn) ?? (row[0] switch
            {
                "motherboard" => RescueDeviceCategory.DiyDesktop,
                "laptop" or "laptop-os-record" => RescueDeviceCategory.Laptop,
                _ => RescueDeviceCategory.Other,
            });
            var driverPage = Https(ReadColumn(row, driverPageColumn));
            if (driverPage is null && useLegacySupportLookup)
            {
                var support = RescueModelSupport.Describe(row[2], category == RescueDeviceCategory.Laptop);
                driverPage = Https(support?.OfficialPage) ?? DriverTab(source);
            }
            var tag = category == RescueDeviceCategory.Other
                ? ReadEnum<RescueDeviceTag>(row, tagColumn) ?? (row[0] == "all-in-one" ? RescueDeviceTag.AllInOne : null)
                : null;
            var model = new RescueCatalogModel(row[0], row[1], row[2], row[3], row[4], row[6],
                row[9], row[10], source, driverPage, row[5] is "product-series" or "oem-series-catalog", category, tag,
                row[7] == "manual-revision-selection");
            var aliases = ReadColumn(row, aliasesColumn)?.Split('|',
                StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries) ?? [];
            yield return new CatalogRow(model, aliases);
        }
    }

    private static string? ReadColumn(string[] row, int column) =>
        column >= 0 && column < row.Length ? row[column] : null;

    private static T? ReadEnum<T>(string[] row, int column) where T : struct, Enum =>
        column >= 0 && column < row.Length && Enum.TryParse<T>(row[column], out var value) && Enum.IsDefined(value)
            ? value : null;

    private static Uri? Https(string? url) =>
        Uri.TryCreate(url, UriKind.Absolute, out var uri) && uri.Scheme == Uri.UriSchemeHttps ? uri : null;

    private static Uri? DriverTab(Uri? source)
    {
        if (source is { Host: "www.asrock.com", Fragment: "#Download" })
        {
            return source;
        }

        return source is { Host: "www.acer.com" } &&
            source.AbsolutePath.Contains("/support/product-support/", StringComparison.OrdinalIgnoreCase) &&
            source.AbsolutePath.TrimEnd('/').EndsWith("/downloads", StringComparison.OrdinalIgnoreCase) ? source : null;
    }

    private static string Normalize(string value) =>
        new(value.Normalize(NormalizationForm.FormKC).Where(c => char.IsLetterOrDigit(c) || c == '+')
            .Select(char.ToUpperInvariant).ToArray());

    private static string WithoutPlus(string value) => value.Replace("+", "", StringComparison.Ordinal);
}
