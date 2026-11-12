"""Report bounded model and driver-evidence coverage from local updater state."""

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE = ROOT / "artifacts/network-rescue-update"


def read_json(path):
    return json.loads(path.read_bytes())


def ratio(numerator, denominator):
    return dict(count=numerator, total=denominator,
                percent=round(100 * numerator / denominator, 2) if denominator else None)


def snapshot_coverage(state):
    updater = runpy.run_path(str(ROOT / "scripts/update-network-rescue.py"))
    saved = read_json(state / "state.json")
    fingerprint = saved["fingerprints"]["boards.json"]
    rows = read_json(state / "snapshots" / f"{fingerprint}.json")["data"]
    scopes = [
        ("motherboards", [row for row in rows if row["product_type"] == "motherboard"
          and row.get("socket") in updater["PLATFORMS"] and row["vendor"] in updater["OEM_PATHS"]], saved["boards"]),
    ]
    for category, filename in (("laptop", "laptops"), ("desktop", "devices")):
        catalog = read_json(state / f"{filename}.json")
        if catalog["fingerprint"] != fingerprint:
            raise ValueError(f"{filename}.json and motherboard state use different snapshots; refresh both")
        expected = updater["system_catalog"]({"boards.json": rows}, category)
        scopes.append((filename, expected.values(), catalog["models"]))
    total = sum(len(expected) for _, expected, _ in scopes)
    result = dict(generation=saved["generation"])
    for name, expected, models in scopes:
        if name == "motherboards":
            key = lambda row: (row["vendor"], row["board_id"])
        else:
            key = lambda row: (row["vendor"], row["sourceId"])
        included = {key(row) for row in models.values()}
        result[name] = dict(shareOfSnapshot=ratio(len(expected), total),
                            included=ratio(sum(key(row) in included for row in expected), len(expected)))
    result["overall"] = ratio(sum(result[name]["included"]["count"] for name, _, _ in scopes), total)
    return result


def model_evidence(report, models, samples=()):
    def identity(row):
        return (row["model"], row["support"], row.get("modelCode"), row.get("hardwareRevision"))

    expected = {identity(row) for row in models}
    listed, signed = set(), set()
    for url in report.get("activeUrls", report["packages"]):
        package = report["packages"].get(url)
        if not package:
            continue
        linked = {identity(row) for row in package["listings"]} & expected
        listed.update(linked)
        if package["status"] == "verified-candidate" and package.get("signedInfCount", 0) > 0:
            signed.update(linked)
        current = {(identity(row), row["label"], row.get("listedRevision")) for row in package["listings"]}
        for sample in samples:
            verified = sample["packages"].get(url, {})
            if verified.get("status") != "verified-candidate" or verified.get("signedInfCount", 0) <= 0:
                continue
            if package.get("sha256") and package["sha256"] != verified.get("sha256"):
                continue
            signed.update(identity(row) for row in verified["listings"]
                          if (identity(row), row["label"], row.get("listedRevision")) in current
                          and identity(row) in expected)
    return dict(oemDownload=ratio(len(listed), len(expected)), signedPackage=ratio(len(signed), len(expected)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--device-state", type=Path, help="Override standalone-device reports with a separate run")
    parser.add_argument("--evidence", nargs=2, action="append", default=[], metavar=("VENDOR", "REPORT"),
                        help="Include exact URL and revision matches from a sample verification report")
    args = parser.parse_args()
    evidence_reports = defaultdict(list)
    for vendor, report in args.evidence:
        evidence_reports[vendor].append(read_json(Path(report)))
    with (ROOT / "docs/network-rescue-model-gaps.csv").open(encoding="utf-8-sig", newline="") as source:
        boards = [row for row in csv.DictReader(source) if row["type"] == "motherboard"]
    os_evidence = {}
    for version in (10, 11):
        counts = Counter(row[f"windows{version}X64Evidence"] for row in boards)
        oem = counts["oem-package-indexed"] + counts["oem-wlan-listed"]
        os_evidence[f"win{version}"] = dict(oemDownload=ratio(oem, len(boards)), outcomes=counts)

    sources = {}
    for vendor in ("panasonic", "dynabook", "xiaomi", "honor", "tplink", "dlink", "apple", "microsoft-surface",
                   "asus-rog-handhelds", "fujitsu"):
        state = args.state if vendor in {"panasonic", "dynabook", "xiaomi", "honor"} else args.device_state or args.state
        path = state / vendor / "last-run.json"
        if not path.is_file():
            continue
        report = read_json(path)
        models = list(report["boards"].values())
        samples = evidence_reports[vendor]
        evidence = model_evidence(report, models, samples)
        if vendor == "tplink":
            evidence["byCategory"] = {category: model_evidence(report, [row for row in models if row["deviceCategory"] == category], samples)
                                      for category in sorted({row["deviceCategory"] for row in models})}
        sources[vendor] = evidence
    print(json.dumps(dict(snapshot=snapshot_coverage(args.state), motherboardX64=os_evidence, oemSources=sources),
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
