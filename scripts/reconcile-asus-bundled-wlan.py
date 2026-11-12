"""Record exact ASUS OEM listings already backed by signed PCI INF in the rescue ZIP."""
import argparse
from collections import defaultdict
import csv
from pathlib import Path
from zipfile import ZipFile


SYSTEMS = ("10", "11")
WIRELESS_EVIDENCE = {
    "oem-spec-wlan-listed", "manual-module-candidate", "oem-spec-module", "oem-manual-module",
    "onboard-chip-unknown", "oem-signed-driver-local-exact-id",
}


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames, list(reader)


def write(path, fields, rows):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fields, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def scope_from_zip(path):
    with ZipFile(path) as bundle:
        entries = set(bundle.namelist())
        text = bundle.read("pe-driver-scope.txt").decode("ascii")
    scope = {}
    for line in text.splitlines():
        minimum, name = line.split()
        if name in scope:
            raise ValueError(f"Duplicate driver scope entry: {name}")
        scope[name] = int(minimum)
    return entries, scope


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("models", "index", "downloads", "snapshot-audit", "bundle", "signed-inf", "output"):
        parser.add_argument(f"--{field}", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    entries, scope = scope_from_zip(args.bundle)
    _, signed = read(args.signed_inf)
    builds = {item["windowsBuild"] for item in signed}
    if len(builds) != 1 or not all(build.isdecimal() and int(build) >= 22000 for build in builds):
        parser.error("signed INF evidence must come from a single Windows 11 build")
    target_builds = {"10": 19045, "11": int(next(iter(builds)))}
    signed_paths = defaultdict(set)
    for item in signed:
        path = item["inf"]
        parts = path.split("/")
        if (len(parts) >= 3 and parts[0] == "driver-packs" and path in entries
                and item["hardwareId"].upper().startswith("PCI\\")):
            signed_paths[parts[1]].add(path)

    _, index = read(args.index)
    packages = defaultdict(list)
    for package in index:
        folder = f"{package['packageId']}-{package['version']}"
        if folder in scope and signed_paths[folder] and package["sha256"]:
            packages[package["sha256"].upper()].append((package, folder))

    _, snapshot = read(args.snapshot_audit)
    hinted = {(row["platform"], row["model"]) for row in snapshot
              if row["brand"] == "ASUS" and row["status"] == "unique-snapshot-package"
              and row["sha256"].upper() in packages}
    _, downloads = read(args.downloads)
    exact = defaultdict(list)
    for row in downloads:
        os = row["windows"]
        if row["status"] != "oem-wlan-listed" or os not in SYSTEMS:
            continue
        for package, folder in packages.get(row["sha256"].upper(), ()):
            if package["windows"] not in (f"Windows {os} x64", "Windows 10/11 x64") or scope[folder] > target_builds[os]:
                continue
            exact[row["platform"], row["model"], os].append((package["packageId"], row["supportUrl"],
                                                              row["sha256"].upper(), signed_paths[folder]))

    model_fields, models = read(args.models)
    evidence = []
    for row in models:
        if row["type"] != "motherboard" or row["brand"] != "ASUS" or row["wlanEvidence"] not in WIRELESS_EVIDENCE:
            continue
        key = row["platform"], row["model"]
        for os in SYSTEMS:
            column = f"windows{os}X64Evidence"
            if row[column] != "pending":
                continue
            matches = exact[key[0], key[1], os]
            evidence.append(dict(platform=key[0], model=key[1], windows=os, snapshotHint="yes" if key in hinted else "no",
                                 status="bundled-oem-listing" if matches else "unmatched",
                                 packageIds=";".join(sorted({match[0] for match in matches})),
                                 supportUrl=";".join(sorted({match[1] for match in matches})),
                                 sha256=";".join(sorted({match[2] for match in matches})),
                                 signedInfCount=len({path for match in matches for path in match[3]})))
            if matches and args.apply:
                row[column] = "oem-wlan-listed"

    fields = ["platform", "model", "windows", "snapshotHint", "status", "packageIds", "supportUrl", "sha256", "signedInfCount"]
    write(args.output, fields, evidence)
    if args.apply and any(row["status"] == "bundled-oem-listing" for row in evidence):
        write(args.models, model_fields, models)
    print(f"{sum(row['status'] == 'bundled-oem-listing' for row in evidence)} exact OEM matches in {len(evidence)} model/OS rows.")


if __name__ == "__main__":
    main()
