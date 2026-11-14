"""Export searchable models from updater catalogs and supplemental sources."""

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import re
import unicodedata


ROOT = Path(__file__).resolve().parent.parent
BRANDS = {"asrock": "ASRock", "asus": "ASUS", "dell": "Dell", "gigabyte": "GIGABYTE", "hp": "HP",
          "lenovo": "Lenovo", "msi": "MSI"}
OTHER_TAGS = {"all-in-one": "AllInOne", "mini-pc": "MiniPc", "workstation": "Workstation",
              "branded-desktop": "BrandedDesktop", "windows-tablet": "WindowsTablet",
              "windows-handheld": "Handheld", "single-board-computer": "SingleBoardComputer",
              "htpc": "Htpc", "windows-phone": "WindowsPhone"}
ADAPTER_TYPES = {"usb-wifi": "USB Wi-Fi", "usb-ethernet": "USB Ethernet", "pcie-wifi": "PCIe Wi-Fi",
                 "pci-wifi": "PCI Wi-Fi", "pci-ethernet": "PCI/PCIe Ethernet"}
OEM_SOURCES = (
    ("nzxt", "NZXT", "DiyDesktop", ""), ("colorful", "Colorful", "DiyDesktop", ""),
    ("evga", "EVGA", "DiyDesktop", ""), ("panasonic", "Panasonic", "Laptop", ""),
    ("dynabook", "Dynabook", "Laptop", ""), ("xiaomi", "Xiaomi", "Laptop", ""),
    ("honor", "HONOR", "Laptop", ""), ("apple", "Apple", "Other", "Mac"),
    ("microsoft-surface", "Microsoft", "Other", ""), ("asus-rog-handhelds", "ASUS", "Other", "Handheld"),
    ("fujitsu", "Fujitsu", "Other", ""),
    ("special", "", "Other", ""),
    ("tplink", "TP-Link", "Other", "NetworkAdapter"), ("dlink", "D-Link", "Other", "NetworkAdapter"),
)


def read_json(path):
    return json.loads(path.read_bytes())


def identity(model):
    return tuple(model.get(field) for field in ("model", "support", "modelCode", "hardwareRevision"))


def catalog_row(brand, model, category, *, tag="", evidence=None, driver_page=""):
    name = model["model"]
    revision = model.get("hardwareRevision") or model.get("revision") or ""
    if revision and not re.search(rf"(?<!\w){re.escape(revision)}(?!\w)", name, re.I):
        name += f" {revision}"
    code = model.get("modelCode") or ""
    if code and code.casefold() not in name.casefold() and brand in {"Dynabook", "Apple"}:
        name += f" ({code})"
    aliases = [model.get("vendorModelId"), code, *model.get("modelAliases", []),
               *(variant["model"] for variant in model.get("modelVariants", []))]
    if model.get("hardwareRevision") and name != model["model"]:
        aliases.append(model["model"])
    aliases.extend(value for values in (model.get("smbios") or {}).values() if isinstance(values, list)
                   for value in values)
    tag = tag or next((OTHER_TAGS[value] for value in model.get("deviceTags", []) if value in OTHER_TAGS), "")
    evidence = evidence or {}
    kind = {"DiyDesktop": "motherboard", "Laptop": "laptop"}.get(category, "device")
    platform = model.get("socket") or model.get("family") or model.get("market") or ""
    if adapter := ADAPTER_TYPES.get(model.get("deviceCategory")):
        platform = " · ".join(filter(None, (adapter, platform)))
    windows = "Windows 11 upgrade catalog" if model.get("evidence") == "oem-os-upgrade-catalog" else ""
    return (kind, brand, name, platform, windows,
            "oem-model-catalog", "", "exact-network-id-and-install", model.get("support") or "",
            evidence.get("10", "pending"), evidence.get("11", "pending"), category, tag,
            "|".join(dict.fromkeys(str(alias) for alias in aliases if alias)), driver_page)


def oem_rows(state, source, brand, category, tag, indexed):
    report = read_json(state / source / "last-run.json")
    records = defaultdict(list)
    for url in report.get("activeUrls", report["packages"]):
        for listing in report["packages"].get(url, {}).get("listings", []):
            records[identity(listing)].append((url, listing))
    for key, row in report["boards"].items():
        model = row if isinstance(row, dict) else {"model": key, "support": row}
        evidence = dict.fromkeys(("10", "11"), "outside-x64-record") if model.get("evidence") == "outside-x64-record" else {}
        listings = records[identity(model)]
        for url, listing in listings:
            for version in re.findall(r"(?<!\d)(?:10|11)(?!\d)", str(listing.get("listedWindows", ""))):
                if version in indexed.get(url, set()):
                    evidence[version] = "oem-package-indexed"
                else:
                    ethernet = model.get("deviceCategory", "").endswith("-ethernet")
                    evidence.setdefault(version, "oem-network-listed" if ethernet else "oem-wlan-listed")
        driver_page = (model.get("bundlePage") or model.get("driverInstructions")
                       or (model["support"] if listings and source != "honor" else ""))
        model_category = "Laptop" if model.get("productType") == "laptop" else category
        yield catalog_row(model.get("brand") or brand, model, model_category, tag=tag, evidence=evidence, driver_page=driver_page)


def model_key(brand, model):
    return tuple(
        "".join(character for character in unicodedata.normalize("NFKC", value)
                if character.isalnum() or character == "+").casefold()
        for value in (brand, model)
    )


def driverhub_rows(existing):
    occupied = {model_key(row[1], label) for row in existing
                for label in (row[2], *row[13].split("|")) if label}
    with (ROOT / "docs/network-rescue-model-gaps.csv").open(encoding="utf-8-sig", newline="") as stream:
        occupied.update(model_key(row["brand"], row["model"]) for row in csv.DictReader(stream))
    groups = defaultdict(list)
    model_groups = defaultdict(set)
    with (ROOT / "docs/network-rescue-driverhub-model-candidates.csv").open(
        encoding="utf-8-sig", newline=""
    ) as stream:
        for entry in csv.DictReader(stream):
            if entry["granularity"] in {"model", "manual-revision"}:
                key = model_key(entry["catalogBrand"], entry["comparisonModel"])
                groups[key].append(entry)
                model_groups[model_key(entry["catalogBrand"], entry["model"])].add(key)
    for key, entries in groups.items():
        brand = entries[0]["catalogBrand"]
        aliases = dict.fromkeys(entry[field] for entry in entries for field in ("model", "comparisonModel")
                                if field == "comparisonModel" or len(model_groups[model_key(brand, entry[field])]) == 1)
        keys = {model_key(brand, label) for label in aliases}
        if key in occupied or not keys.isdisjoint(occupied):
            continue
        occupied.update(keys)
        entry = next((row for row in entries if row["brand"].casefold() == brand.casefold()), entries[0])
        model = entry["model"] if entry["model"] in aliases else entry["comparisonModel"]
        if entry["granularity"] == "manual-revision":
            model = entry["comparisonModel"]
        category = entry["category"]
        kind = {"Laptop": "laptop", "DiyDesktop": "motherboard", "Other": "device"}[category]
        gap = ("manual-revision-selection" if entry["granularity"] == "manual-revision"
               else "exact-network-id-and-install")
        yield (kind, brand, model, "", "", "third-party-model-candidate", "",
               gap, entry["source"], entry["status"], entry["status"],
               category, entry["tag"], "|".join(label for label in aliases if label != model and "|" not in label), "")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=ROOT / "artifacts/network-rescue-update")
    parser.add_argument("--device-state", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/network-rescue-search-models.csv")
    args = parser.parse_args()
    devices = args.device_state or args.state
    with (ROOT / "docs/network-rescue-driver-index.csv").open(encoding="utf-8-sig", newline="") as stream:
        indexed = {row["downloadUrl"]: set(re.findall(r"\b(?:10|11)\b", row["windows"])) for row in csv.DictReader(stream)}

    rows = []
    motherboard = read_json(args.state / "state.json")
    for row in motherboard["boards"].values():
        rows.append(catalog_row(BRANDS[row["vendor"]], dict(row, model=row["name"], support=row["support_url"]), "DiyDesktop"))
    for root, filename, category in ((args.state, "laptops", "Laptop"), (devices, "devices", "Other")):
        catalog = read_json(root / f"{filename}.json")
        if catalog["fingerprint"] != motherboard["fingerprints"]["boards.json"]:
            raise ValueError(f"{filename}.json and motherboard state use different snapshots")
        models = catalog["models"].values()
        support_pages = defaultdict(set)
        for row in models:
            support_pages[row["vendor"], row["model"].casefold()].add(row["support"])
        for row in models:
            if len(support_pages[row["vendor"], row["model"].casefold()]) > 1:
                code = row["vendorModelId"].split("/", 1)[0].upper()
                row = dict(row, model=f"{row['model']} ({code})")
            rows.append(catalog_row(BRANDS[row["vendor"]], row, category))
    for source, brand, category, tag in OEM_SOURCES:
        root = devices if category == "Other" else args.state
        rows.extend(oem_rows(root, source, brand, category, tag, indexed))
    rows.extend(driverhub_rows(rows))

    with (ROOT / "docs/network-rescue-model-gaps.csv").open(encoding="utf-8-sig", newline="") as stream:
        header = next(csv.reader(stream))
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow([*header, "aliases", "driverPage"])
        writer.writerows(sorted(rows, key=lambda row: (row[11], row[1].casefold(), row[2].casefold(), row[8], row[13])))
    print(dict(Counter(row[11] for row in rows)))


if __name__ == "__main__":
    main()
