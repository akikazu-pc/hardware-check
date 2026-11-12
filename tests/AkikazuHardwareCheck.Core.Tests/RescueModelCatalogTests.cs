using AkikazuHardwareCheck.Core.SharedDesktop;

namespace AkikazuHardwareCheck.Core.Tests;

public sealed class RescueModelCatalogTests
{
    [Fact]
    public void FindsAllInOneWithSeparateWindowsEvidence()
    {
        var model = Assert.Single(RescueModelCatalog.Search("HP Presence 24"));
        Assert.Equal("all-in-one", model.Type);
        Assert.Equal("oem-driver-pack-listed", model.Windows10Evidence);
        Assert.Equal("pending", model.Windows11Evidence);
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
        Assert.Equal("pending", model.Windows10Evidence);
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
        Assert.Equal("pending", board.Windows10Evidence);
        Assert.Equal("pending", board.Windows11Evidence);

        var notebook = Assert.Single(RescueModelCatalog.Search("HP Dragonfly 13.5 inch G4 Notebook PC"));
        Assert.Equal("hpia.hpcloud.hp.com", notebook.Source?.Host);
        Assert.Null(notebook.DriverPage);
        Assert.Equal("oem-driver-pack-listed", notebook.Windows10Evidence);
        Assert.Equal("oem-driver-pack-listed", notebook.Windows11Evidence);
    }

    [Fact]
    public void ExposesAcerUpgradeEvidenceAndMsiModelsWithoutInferringWifiCompatibility()
    {
        var acer = Assert.Single(RescueModelCatalog.Search("Acer AP714-51GT"), model => model.Model == "AP714-51GT");
        Assert.Equal("pending", acer.Windows10Evidence);
        Assert.Equal("oem-os-upgrade-tested", acer.Windows11Evidence);

        var msi = Assert.Single(RescueModelCatalog.Search("MSI Creator M16 A12UC"));
        Assert.False(msi.IsSeries);
        Assert.Equal("pending", msi.Windows10Evidence);
        Assert.Equal("pending", msi.Windows11Evidence);
    }
}
