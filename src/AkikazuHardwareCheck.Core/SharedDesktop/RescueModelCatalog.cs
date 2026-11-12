using Microsoft.VisualBasic.FileIO;

namespace AkikazuHardwareCheck.Core.SharedDesktop;

public sealed record RescueCatalogModel(string Type, string Brand, string Model, string Platform, string Windows,
    string Module, string Windows10Evidence, string Windows11Evidence, Uri? Source, Uri? DriverPage, bool IsSeries);

public static class RescueModelCatalog
{
    private static readonly Lazy<RescueCatalogModel[]> Models = new(ReadModels);

    public static IReadOnlyList<RescueCatalogModel> Search(string query)
    {
        var key = Normalize(query);
        if (key.Length < 2)
        {
            return [];
        }

        var terms = query.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries)
            .Select(Normalize).Where(term => term.Length > 0).ToArray();
        return Models.Value.Select(model => (Model: model, Name: Normalize(model.Model), Brand: Normalize(model.Brand)))
            .Where(row => (row.Brand + row.Name).Contains(key, StringComparison.Ordinal) ||
                terms.All(term => row.Name.Contains(term, StringComparison.Ordinal) ||
                row.Brand.Contains(term, StringComparison.Ordinal)))
            .OrderBy(row => row.Name == key || row.Brand + row.Name == key ? 0 :
                row.Name.StartsWith(key, StringComparison.Ordinal) ? 1 : 2)
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
        csv.ReadFields();
        var entries = new List<RescueCatalogModel>();
        while (csv.ReadFields() is { Length: >= 11 } row)
        {
            var source = Https(row[8]);
            var support = RescueModelSupport.Describe(row[2], row[0] != "motherboard");
            var driverPage = Https(support?.OfficialPage) ?? DriverTab(source);
            entries.Add(new RescueCatalogModel(row[0], row[1], row[2], row[3], row[4], row[6],
                row[9], row[10], source, driverPage, row[5] is "product-series" or "oem-series-catalog"));
        }

        return entries.ToArray();
    }

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
