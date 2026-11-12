using Microsoft.VisualBasic.FileIO;

namespace AkikazuHardwareCheck.Core.SharedDesktop;

public enum RescueDeviceCategory { DiyDesktop, Laptop, Other }

public enum RescueDeviceTag
{
    BrandedDesktop, MiniPc, WindowsTablet, Handheld, AllInOne, Htpc, SingleBoardComputer, WindowsPhone, Mac, ModifiedChromebook,
}

public sealed record RescueCatalogModel(string Type, string Brand, string Model, string Platform, string Windows,
    string Module, string Windows10Evidence, string Windows11Evidence, Uri? Source, Uri? DriverPage, bool IsSeries,
    RescueDeviceCategory Category, RescueDeviceTag? DeviceTag);

public static class RescueModelCatalog
{
    private static readonly Lazy<RescueCatalogModel[]> Models = new(ReadModels);

    public static IReadOnlyList<RescueCatalogModel> Search(string query, RescueDeviceCategory? category = null,
        RescueDeviceTag? tag = null)
    {
        var exactQuery = query.Trim();
        var key = Normalize(exactQuery);
        if ((tag is not null && category != RescueDeviceCategory.Other) || (key.Length < 2 && category is null))
        {
            return [];
        }

        var terms = query.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries)
            .Select(Normalize).Where(term => term.Length > 0).ToArray();
        return Models.Value.Where(model => (category is null || model.Category == category) &&
                (tag is null || model.DeviceTag == tag))
            .Select(model => (Model: model, Name: Normalize(model.Model), Brand: Normalize(model.Brand)))
            .Where(row => (row.Brand + row.Name).Contains(key, StringComparison.Ordinal) ||
                terms.All(term => row.Name.Contains(term, StringComparison.Ordinal) ||
                row.Brand.Contains(term, StringComparison.Ordinal)))
            .OrderBy(row => row.Model.Model.Equals(exactQuery, StringComparison.OrdinalIgnoreCase) ||
                $"{row.Model.Brand} {row.Model.Model}".Equals(exactQuery, StringComparison.OrdinalIgnoreCase) ? 0 :
                row.Name == key || row.Brand + row.Name == key ? 1 :
                row.Name.StartsWith(key, StringComparison.Ordinal) ? 2 : 3)
            .ThenBy(row => row.Model.Model, StringComparer.OrdinalIgnoreCase)
            .Select(row => row.Model)
            .ToArray();
    }

    private static RescueCatalogModel[] ReadModels()
    {
        using var stream = typeof(RescueModelCatalog).Assembly.GetManifestResourceStream("rescue.model-gaps.csv")
            ?? throw new InvalidOperationException("The model catalog is missing.");
        using var csv = new TextFieldParser(stream);
        csv.SetDelimiters(",");
        var header = csv.ReadFields() ?? [];
        var categoryColumn = Array.IndexOf(header, "deviceCategory");
        var tagColumn = Array.IndexOf(header, "deviceTag");
        var entries = new List<RescueCatalogModel>();
        while (csv.ReadFields() is { Length: >= 11 } row)
        {
            var source = Https(row[8]);
            var category = ReadEnum<RescueDeviceCategory>(row, categoryColumn) ?? (row[0] switch
            {
                "motherboard" => RescueDeviceCategory.DiyDesktop,
                "laptop" or "laptop-os-record" => RescueDeviceCategory.Laptop,
                _ => RescueDeviceCategory.Other,
            });
            var support = RescueModelSupport.Describe(row[2], category == RescueDeviceCategory.Laptop);
            var driverPage = Https(support?.OfficialPage) ?? DriverTab(source);
            var tag = category == RescueDeviceCategory.Other
                ? ReadEnum<RescueDeviceTag>(row, tagColumn) ?? (row[0] == "all-in-one" ? RescueDeviceTag.AllInOne : null)
                : null;
            entries.Add(new RescueCatalogModel(row[0], row[1], row[2], row[3], row[4], row[6],
                row[9], row[10], source, driverPage, row[5] is "product-series" or "oem-series-catalog", category, tag));
        }

        return entries.ToArray();
    }

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
        new(value.Where(char.IsLetterOrDigit).Select(char.ToUpperInvariant).ToArray());
}
