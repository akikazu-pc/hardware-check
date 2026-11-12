"""Join motherboard module evidence to signed INF candidates and exact OEM listings."""
import argparse
from collections import defaultdict
import csv
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


MODULE = re.compile(
    r"\b(?:MT79(?:02|20|21|22|25|27|28)[A-Z0-9]*|(?:RTL)?(?:88|89)\d{2}[A-Z]{0,3}|"
    r"BE1750[ISWX]|BE(?:200|201|202|211|213)(?:NGW|D2W)?|AX(?:101|200|201|210|211|411)(?:NGW)?|"
    r"(?:QCNCM|NCM)865|3168|7265|8260|8265|9260|9462|9560)\b", re.I
)
SYSTEMS = ("10", "11")
FIELDS = [
    "brand", "platform", "model", "moduleEvidence", "module", "moduleSource", "auditWindowsBuild",
    "signedInfCount", "signedPciIdCount", "sampleInf", "samplePciId",
    "windows10OemPackageIds", "windows11OemPackageIds", "oemSupportUrl", "factorySubsystem", "offlineInstall",
]


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        return reader.fieldnames, list(reader)


def write(path, fields, rows):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def module_keys(text):
    keys = set()
    for match in MODULE.finditer(text):
        name = match.group().upper().removeprefix("RTL")
        if name == "QCNCM865":
            name = "NCM865"
        if name.startswith("MT79"):
            name = name[:6]
        elif name.startswith(("AX", "BE")) and not name.startswith("BE1750"):
            name = name[:5]
        keys.add(name)
    return keys


def url_key(url):
    parsed = urlsplit(url)
    return parsed.netloc.lower(), unquote(parsed.path)


def supports(package, system):
    return package["windows"] in (f"Windows {system} x64", "Windows 10/11 x64")


def candidate_package(inf, names):
    parts = inf.split("/")
    if len(parts) < 3:
        return ""
    if parts[0] == "driver-packs":
        return names.get(parts[1], "")
    if parts[0] == "pe-drivers":
        return parts[2]
    return ""



def rank_packages(downloads, package_by_id, missing, limit):
    indexed_hashes = {item["sha256"].upper() for item in package_by_id.values()}
    coverage = defaultdict(lambda: defaultdict(set))
    metadata = {}
    for item in downloads:
        digest = item["sha256"].upper()
        key = item["model"], item["platform"], item["windows"]
        if (item["status"] != "oem-wlan-listed" or digest in indexed_hashes or
                not re.fullmatch(r"[A-F0-9]{64}", digest) or key not in missing):
            continue
        # A name in an OEM title is a planning hint. The final map still requires signed INF evidence.
        modules = module_keys(item["title"]) & missing[key]
        if modules:
            coverage[digest][key].update(modules)
            metadata.setdefault(digest, item)

    remaining = list(coverage)
    result = []
    for rank in range(1, limit + 1):
        if not remaining:
            break
        def score(digest):
            candidates = coverage[digest]
            complete = sum(bool(missing[key]) and missing[key] <= modules for key, modules in candidates.items())
            covered = sum(len(missing[key] & modules) for key, modules in candidates.items())
            return complete, covered
        digest = max(remaining, key=score)
        complete, covered = score(digest)
        if not covered:
            break
        remaining.remove(digest)
        item = metadata[digest]
        result.append(dict(rank=rank, version=item["version"], officialListings=len(coverage[digest]),
                           expectedCompleteModelOs=complete, missingModulesCovered=covered,
                           sha256=digest, downloadUrl=item["downloadUrl"]))
        for key, modules in coverage[digest].items():
            missing[key].difference_update(modules)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--packages", type=Path, required=True)
    parser.add_argument("--asus-downloads", type=Path, required=True)
    parser.add_argument("--signed-inf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Advance fully mapped model/OS records to OEM package indexed.")
    parser.add_argument("--include-listed", action="store_true", help="Recheck model/OS rows with OEM listing evidence.")
    parser.add_argument("--rank-output", type=Path, help="Rank new archives by missing variants named in official titles.")
    parser.add_argument("--rank-limit", type=int, default=2)
    args = parser.parse_args()
    if args.rank_limit < 1:
        parser.error("--rank-limit must be positive")

    model_fields, models = read(args.models)
    _, packages = read(args.packages)
    _, downloads = read(args.asus_downloads)
    _, evidence = read(args.signed_inf)
    builds = {row["windowsBuild"] for row in evidence}
    if len(builds) != 1:
        parser.error("signed INF evidence must come from a single Windows build")
    build = next(iter(builds))
    names = {f"{row['packageId']}-{row['version']}": row["packageId"] for row in packages}
    package_by_id = {row["packageId"]: row for row in packages}
    package_by_url = {url_key(row["downloadUrl"]): row for row in packages}
    by_module = defaultdict(list)
    for match in evidence:
        if not match["hardwareId"].upper().startswith("PCI\\"):
            continue
        package = candidate_package(match["inf"], names)
        keys = module_keys(match["adapterName"])
        if package == "qualcomm-wifi7" and match["hardwareId"].upper().startswith("PCI\\VEN_17CB&DEV_1107"):
            keys.add("NCM865")
        if "8922AE" in keys:
            keys.add("8922")
        for key in keys:
            by_module[key].append((package, match["inf"], match["hardwareId"]))

    oem = defaultdict(dict)
    for item in downloads:
        if item["status"] != "oem-wlan-listed":
            continue
        package = package_by_url.get(url_key(item["downloadUrl"]))
        if not package or not supports(package, item["windows"]):
            continue
        if item["sha256"] and item["sha256"] != package["sha256"]:
            continue
        oem[item["model"], item["platform"], item["windows"]][package["packageId"]] = item["supportUrl"]

    output = []
    updated = defaultdict(int)
    missing = defaultdict(set)
    eligible = {"pending", "oem-wlan-listed"} if args.include_listed else {"pending"}
    for row in models:
        if row["type"] != "motherboard" or row["gap"] != "factory-variant-to-exact-id-and-install":
            continue
        pending = [os for os in SYSTEMS if row[f"windows{os}X64Evidence"] in eligible]
        if not pending:
            continue
        modules = module_keys(row["module"])
        if "Qualcomm Wi-Fi 7" in row["module"] and row["model"] == "X870E AORUS MASTER":
            modules.add("NCM865")
        all_mapped = {os: bool(modules) for os in pending}
        for module in sorted(modules) or ["unparsed"]:
            matches = sorted(set(by_module[module]), key=lambda item: (not item[0], item))
            package_ids = {pkg for pkg, _, _ in matches if pkg in package_by_id}
            exact = {}
            sources = set()
            for os in pending:
                allowed = oem[row["model"], row["platform"], os] if row["brand"] == "ASUS" else {}
                exact[os] = sorted(package_ids.intersection(allowed))
                sources.update(allowed[pkg] for pkg in exact[os])
                all_mapped[os] &= bool(exact[os])
                if row["brand"] == "ASUS" and not exact[os]:
                    missing[row["model"], row["platform"], os].add(module)
            preferred = set(exact.get("10", []) + exact.get("11", []))
            selected = next((item for item in matches if item[0] in preferred), matches[0] if matches else ("", "", ""))
            output.append(dict(
                brand=row["brand"], platform=row["platform"], model=row["model"], moduleEvidence=row["module"],
                module=module, moduleSource=row["source"], auditWindowsBuild=build,
                signedInfCount=len({inf for _, inf, _ in matches}),
                signedPciIdCount=len({pci for _, _, pci in matches}), sampleInf=selected[1], samplePciId=selected[2],
                windows10OemPackageIds=";".join(exact.get("10", [])), windows11OemPackageIds=";".join(exact.get("11", [])),
                oemSupportUrl=";".join(sorted(sources)), factorySubsystem="pending", offlineInstall="pending",
            ))
        for os, mapped in all_mapped.items():
            if mapped:
                updated[os] += 1
                if args.apply:
                    row[f"windows{os}X64Evidence"] = "oem-package-indexed"

    write(args.output, FIELDS, output)
    if args.rank_output:
        fields = ["rank", "version", "officialListings", "expectedCompleteModelOs", "missingModulesCovered",
                  "sha256", "downloadUrl"]
        write(args.rank_output, fields, rank_packages(downloads, package_by_id, missing, args.rank_limit))
    if args.apply and updated:
        write(args.models, model_fields, models)
    print(f"{len(output)} module rows. Fully mapped eligible model/OS records: {dict(updated)}")


if __name__ == "__main__":
    main()
