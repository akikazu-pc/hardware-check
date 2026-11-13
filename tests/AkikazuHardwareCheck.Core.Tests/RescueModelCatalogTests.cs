using AkikazuHardwareCheck.Core.SharedDesktop;

namespace AkikazuHardwareCheck.Core.Tests;

public sealed class RescueModelCatalogTests
{
    [Theory]
    [InlineData("NEC", "PC-VKT13HZG4", "nec/pc-vkt13hzg4")]
    [InlineData("Panasonic", "CF-191AYSXBM", "panasonic/cf-191aysxbm")]
    [InlineData("Fujitsu", "LIFEBOOK AH531", "fujitsu/lifebook-ah531")]
    public void FindsDriverHubModelCandidatesWithPendingEvidence(string brand, string model, string path)
    {
        var entry = Assert.Single(RescueModelCatalog.Search($"{brand} {model}", RescueDeviceCategory.Laptop),
            item => item.Model == model);
        Assert.Equal("pending", entry.Windows10Evidence);
        Assert.Equal("pending", entry.Windows11Evidence);
        Assert.Equal($"https://jp.drvhub.net/laptops/{path}", entry.Source?.AbsoluteUri);
        Assert.Null(entry.DriverPage);
    }

    [Fact]
    public void ExcludesDriverHubSeriesGenerationsFromModelSearch()
    {
        foreach (var generation in new[] { "CF-33-1", "CF-20-2", "CF-31-5", "CF-54-3", "CF-33-2" })
        {
            Assert.DoesNotContain(RescueModelCatalog.Search($"Panasonic {generation}", RescueDeviceCategory.Laptop),
                entry => entry.Model == generation);
        }
    }

    [Theory]
    [InlineData("AM1M-A", RescueDeviceCategory.DiyDesktop, null, "AM1M-A")]
    [InlineData("ESPRIMO D9500", RescueDeviceCategory.Other, RescueDeviceTag.BrandedDesktop, "ESPRIMO D9500")]
    public void FindsImportedDriverHubModelsInTheirDeviceClass(string query, RescueDeviceCategory category,
        RescueDeviceTag? tag, string model)
    {
        var entry = Assert.Single(RescueModelCatalog.Search(query, category, tag), item => item.Model == model);
        Assert.Equal("pending", entry.Windows10Evidence);
        Assert.Equal("pending", entry.Windows11Evidence);
        Assert.Equal("jp.drvhub.net", entry.Source?.Host);
        Assert.Null(entry.DriverPage);
    }

    [Theory]
    [InlineData("NH.U1BAA.001", "oem-wlan-listed", "AX1675i")]
    [InlineData("NX.KYXAA.002", "outside-x64-record", "802.11be")]
    public void FindsAcerRetailPartNumbersWithTheirSeparatePlatformEvidence(string part, string evidence, string module)
    {
        var row = Assert.Single(RescueModelCatalog.Search(part, RescueDeviceCategory.Laptop));
        Assert.Equal(evidence, row.Windows11Evidence);
        Assert.Contains(module, row.Module);
    }

    [Theory]
    [InlineData("ノートPC 富士通 ＦＭＶＡ４０ＦＷＪ２", "LIFEBOOK AH40/F1")]
    [InlineData("平板微软 Surface Ｇｏ ４", "Surface Go 4")]
    [InlineData("華擎Ａ６２０Ｍ－ＨＤＶ／Ｍ．２＋", "A620M-HDV/M.2+")]
    [InlineData("友讯 DUB-1312", "DUB-1312")]
    [InlineData("小米笔记本ＴＭ２４２３", "REDMI Book 16 2025(AMD)")]
    public void SearchesLocalizedNamesAndFullWidthModelCodes(string query, string expected)
    {
        var matches = RescueModelCatalog.Search(query, null, null, out var approximate);
        Assert.Equal(expected, matches[0].Model);
        Assert.False(approximate);
    }

    [Theory]
    [InlineData("華擎 A620M-HVD/M.2+", "A620M-HDV/M.2+")]
    [InlineData("Surfaec Go 4", "Surface Go 4")]
    [InlineData("Arhcer T3U Plus V1.60", "Archer T3U Plus V1.60")]
    public void SuggestsOneTypoWithoutCrossingHardwareRevision(string query, string expected)
    {
        var matches = RescueModelCatalog.Search(query, null, null, out var approximate);
        Assert.Contains(matches, match => match.Model == expected);
        Assert.True(approximate);
        Assert.DoesNotContain(matches, match => match.Model is "A620M-HDV/M.2" or "Archer T3U Plus V1");
    }

    [Fact]
    public void KeepsDifferentDigitsAndConflictingCategoryOutsideResults()
    {
        Assert.Empty(RescueModelCatalog.Search("華擎 A620M-HVD/M.9+"));
        Assert.Empty(RescueModelCatalog.Search("Windows tablet Surface Go 4", RescueDeviceCategory.Laptop));
    }

    [Fact]
    public void WarnsWhenOnlyAPlusInsensitiveResultExists()
    {
        var matches = RescueModelCatalog.Search("Surface Go 4+", null, null, out var approximate);
        Assert.Contains(matches, match => match.Model == "Surface Go 4");
        Assert.True(approximate);
    }

    [Fact]
    public void OffersRelatedRevisionsWhenATypoQueryLeavesTheRevisionUnspecified()
    {
        var matches = RescueModelCatalog.Search("Arhcer T3U Plus", null, null, out var approximate);
        Assert.True(approximate);
        Assert.Contains(matches, match => match.Model == "Archer T3U Plus V1.60");
        Assert.Contains(matches, match => match.Model == "Archer T3U Plus V1");
    }

    [Fact]
    public void FindsAdditionalDeviceCategoriesWithSeparatePlatformEvidence()
    {
        var boards = RescueModelCatalog.Search("单板电脑");
        Assert.Equal(21, boards.Count);
        Assert.Contains(boards, model => model.Brand == "DFI" && model.Model == "AL051" &&
            model.DeviceTag == RescueDeviceTag.SingleBoardComputer);
        Assert.Contains(RescueModelCatalog.Search("HTPC Beebox N3150"), model => model.DeviceTag == RescueDeviceTag.Htpc);
        var phone = Assert.Single(RescueModelCatalog.Search("Windows 手机 Lumia 950"),
            model => model.Model == "Lumia 950");
        Assert.Equal("outside-x64-record", phone.Windows11Evidence);
    }

    [Theory]
    [InlineData("TM2423", RescueDeviceCategory.Laptop, null, "REDMI Book 16 2025(AMD)")]
    [InlineData("FMVA40FWJ2", RescueDeviceCategory.Laptop, null, "LIFEBOOK AH40/F1")]
    [InlineData("MacBookPro16,1", RescueDeviceCategory.Other, RescueDeviceTag.Mac, "MacBook Pro (16-inch, 2019) (MacBookPro16,1)")]
    [InlineData("Surface Go 4", RescueDeviceCategory.Other, RescueDeviceTag.WindowsTablet, "Surface Go 4")]
    [InlineData("Archer T3U Plus V1.60", RescueDeviceCategory.Other, RescueDeviceTag.NetworkAdapter, "Archer T3U Plus V1.60")]
    public void FindsSupplementalModelsByNameOrOfficialCode(string query, RescueDeviceCategory category,
        RescueDeviceTag? tag, string expected)
    {
        var results = RescueModelCatalog.Search(query, category, tag);
        Assert.Equal(expected, results[0].Model);
        Assert.NotNull(results[0].Source);
    }

    [Fact]
    public void FindsAllInOneWithSeparateWindowsEvidence()
    {
        var model = Assert.Single(RescueModelCatalog.Search("HP Presence 24"));
        Assert.Equal("all-in-one", model.Type);
        Assert.Equal("oem-driver-pack-listed", model.Windows10Evidence);
        Assert.Equal("oem-os-not-listed", model.Windows11Evidence);
        Assert.Equal(RescueDeviceCategory.Other, model.Category);
        Assert.Equal(RescueDeviceTag.AllInOne, model.DeviceTag);
        Assert.Contains(model, RescueModelCatalog.Search("", RescueDeviceCategory.Other, RescueDeviceTag.AllInOne));
        Assert.Empty(RescueModelCatalog.Search("A320M", RescueDeviceCategory.Other, RescueDeviceTag.AllInOne));
        Assert.Empty(RescueModelCatalog.Search("", RescueDeviceCategory.Laptop, RescueDeviceTag.AllInOne));
        Assert.Contains(RescueModelCatalog.Search("A320M", RescueDeviceCategory.DiyDesktop),
            entry => entry.Model == "A320M");
    }

    [Theory]
    [InlineData("A620M-HDV/M.2")]
    [InlineData("A620M-HDV/M.2+")]
    public void ExactModelOutranksTheOtherPunctuationVariant(string model)
    {
        var results = RescueModelCatalog.Search($"ASRock {model}");
        Assert.Equal(model, results[0].Model);
        Assert.Contains(results, entry => entry.Model != model && entry.Model.StartsWith("A620M-HDV/M.2"));
    }

    [Fact]
    public void FindsAnExactModelWithItsDriverPageAndSeparateWindowsEvidence()
    {
        var results = RescueModelCatalog.Search("rog strix b860 g gaming wifi");
        var model = results[0];
        Assert.Equal("ROG STRIX B860-G GAMING WIFI", model.Model);
        Assert.Equal("www.asus.com", model.DriverPage?.Host);
        Assert.Equal("oem-wlan-not-listed", model.Windows10Evidence);
        Assert.Equal("oem-package-indexed", model.Windows11Evidence);
    }

    [Fact]
    public void KeepsDistinctWindowsRecordsAndReturnsNoResultsForAnUnknownModel()
    {
        var results = RescueModelCatalog.Search("Dell Pro Max 18 Plus MB18250");
        Assert.Contains(results, model => model.Windows11Evidence == "oem-wlan-listed");
        Assert.Empty(RescueModelCatalog.Search("nonexistent-model-QXZ790527"));
        Assert.Empty(RescueModelCatalog.Search("  "));
    }

    [Fact]
    public void KeepsAsrockRevisionsAndHpDeploymentPacksDistinctFromWifiEvidence()
    {
        var boards = RescueModelCatalog.Search("ASRock A320M Pro4");
        Assert.Contains(boards, model => model.Model == "A320M Pro4 R2.0");
        var board = Assert.Single(boards, model => model.Model == "A320M Pro4");
        Assert.Equal("#Download", board.DriverPage?.Fragment);
        // The specification and both Windows download lists omit WLAN; that is not a Wi-Fi driver.
        Assert.Equal("oem-wlan-not-listed", board.Windows10Evidence);
        Assert.Equal("oem-wlan-not-listed", board.Windows11Evidence);

        var notebook = Assert.Single(RescueModelCatalog.Search("HP Dragonfly 13.5 inch G4 Notebook PC"));
        Assert.Equal("hpia.hpcloud.hp.com", notebook.Source?.Host);
        Assert.Null(notebook.DriverPage);
        Assert.Equal("oem-driver-pack-listed", notebook.Windows10Evidence);
        Assert.Equal("oem-driver-pack-listed", notebook.Windows11Evidence);
    }

    [Fact]
    public void ExposesAcerUpgradeAndMsiExactModelListingEvidence()
    {
        // The Windows 11 upgrade list alone does not establish a WLAN driver for another system.
        var acer = Assert.Single(RescueModelCatalog.Search("Acer A314-22S"), model => model.Model == "Aspire A314-22S");
        Assert.Equal("pending", acer.Windows10Evidence);
        Assert.Equal("oem-os-upgrade-tested", acer.Windows11Evidence);

        var listed = Assert.Single(RescueModelCatalog.Search("Acer AP714-51GT"), model => model.Model == "AP714-51GT");
        Assert.Equal("oem-wlan-listed", listed.Windows10Evidence);
        Assert.Equal("oem-os-upgrade-tested", listed.Windows11Evidence);

        // The exact sub-product support page lists an Intel WLAN driver for both systems.
        var msi = Assert.Single(RescueModelCatalog.Search("MSI Katana GF66 12UC"), model => model.Model == "Katana GF66 12UC");
        Assert.False(msi.IsSeries);
        Assert.Equal("oem-wlan-listed", msi.Windows10Evidence);
        Assert.Equal("oem-wlan-listed", msi.Windows11Evidence);

        var creator = Assert.Single(RescueModelCatalog.Search("MSI Creator M16 A12UC"));
        Assert.Equal("oem-wlan-listed", creator.Windows10Evidence);
        Assert.Equal("oem-wlan-listed", creator.Windows11Evidence);
    }
}
