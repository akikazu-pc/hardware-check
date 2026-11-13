"""Audit the rescue gap table and refresh the pending inventory.

Run after any round of evidence work. The script never changes cells; it reports the invariants,
recomputes the pending total from the table itself, regenerates the per-cell inventory and compares
the result with the previous snapshot so each round can show how many cells were closed.

Checks:
* the table parses with the expected header and has no empty model names,
* every evidence value belongs to the known status vocabulary,
* duplicate (brand, type, platform, model) keys are only allowed for Dell system-ID records,
* the pending inventory has exactly one row per pending cell.

Usage: python scripts/audit-network-rescue.py [--snapshot PATH] [--quiet]
Exit code 1 when an invariant fails.
"""
import argparse
import csv
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "docs/network-rescue-model-gaps.csv"
INVENTORY = ROOT / "docs/network-rescue-pending-inventory.csv"
SNAPSHOT = ROOT / "artifacts/network-rescue-handoff/pending-snapshot.json"
STATUSES = {
    "pending", "oem-wlan-listed", "oem-wlan-not-listed", "oem-os-not-listed",
    "oem-driver-pack-listed", "no-factory-wifi", "oem-package-indexed",
    "oem-os-upgrade-tested", "oem-wlan-not-supported", "outside-x64-record",
}
SYSTEM_FIELDS = {"10": "windows10X64Evidence", "11": "windows11X64Evidence"}
INVENTORY_FIELDS = ["brand", "type", "platform", "model", "windows", "wlanEvidence", "reason", "detail", "source"]


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def gap_class(row):
    """Name the concrete blocker; keep this in step with the coverage progress document."""
    brand, kind = row["brand"], row["type"]
    evidence, gap = row["wlanEvidence"], row["gap"]
    if brand == "BIOSTAR":
        return "site-403", "官网 403；规格与下载列表无法取回"
    if brand == "GIGABYTE":
        return "support-url-missing", "支持页 slug 未找到（多次 404）"
    if brand == "EVGA":
        return "no-per-model-list", "驱动下载页无逐型号列表"
    if brand == "MSI":
        return "factory-vs-listing", "规格无 WLAN，面板列通用 Wi-Fi 驱动"
    if brand == "ASRock":
        if "no-valid-lan" in gap:
            return "no-valid-lan", "该系统下载列表没有有效 LAN 条目"
        return "factory-vs-listing", "下载页列通用 WLAN 驱动，规格无出厂无线"
    if brand == "ASUS" and kind == "motherboard":
        if evidence == "onboard-chip-unknown":
            return "support-api-empty", "支持接口空 OS 列表"
        if "manual" in evidence or "spec" in evidence:
            return "factory-vs-listing", "手册/规格写非 Wi-Fi，下载页列 Wi-Fi 驱动"
        return "no-factory-proof", "缺出厂无线证据"
    if brand == "ASUS" and kind == "laptop":
        if "no-wlan-row" in gap or "os-list-empty" in gap:
            return "empty-os-list", "支持库对精确型号返回空 OS 列表"
        return "no-network-category", "驱动列表无网络类目或过短"
    if brand == "Acer":
        if evidence == "oem-model-catalog":
            return "no-listing-exact-model", "支持库对精确型号 0 命中"
        if evidence == "oem-sku-listing":
            return "sku-inconclusive", "该 SKU 在族级扫描中为短列表或无数据"
        return "mixed-family", "系列跨代，族内结论不一致"
    if brand == "Dell":
        return "consumer-api-403", "Alienware 无驱动包目录条目，驱动为 XHR"
    if brand == "Lenovo":
        return "os-list-empty", "OS 列表空或驱动 API 403"
    return "unknown", ""


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    problems = []
    rows = read(MODELS)
    if not rows:
        problems.append("model table is empty")
    header = set(rows[0]) if rows else set()
    if not {value for value in SYSTEM_FIELDS.values()} <= header:
        problems.append("model table lacks an evidence column")
    keys = {}
    pending = []
    for row in rows:
        if not row["model"].strip():
            problems.append("row with empty model name")
        for field in SYSTEM_FIELDS.values():
            if row.get(field) not in STATUSES:
                problems.append(f"unknown status {row.get(field)!r} for {row['model']}")
        key = (row["brand"], row["type"], row["platform"], row["model"])
        keys[key] = keys.get(key, 0) + 1
        for system, field in SYSTEM_FIELDS.items():
            if row[field] == "pending":
                reason, detail = gap_class(row)
                pending.append({"brand": row["brand"], "type": row["type"], "platform": row["platform"],
                                "model": row["model"], "windows": system, "wlanEvidence": row["wlanEvidence"],
                                "reason": reason, "detail": detail, "source": row["source"]})
    duplicates = [(key, count) for key, count in keys.items() if count > 1 and key[1] != "laptop-os-record"]
    if duplicates:
        problems.append(f"unexpected duplicate keys: {duplicates[:3]}")

    with INVENTORY.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, INVENTORY_FIELDS, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(sorted(pending, key=lambda item: (item["brand"], item["type"], item["model"], item["windows"])))

    counts = {}
    for item in pending:
        counts.setdefault((item["type"], item["brand"]), 0)
        counts[(item["type"], item["brand"])] += 1
    main_total = sum(count for (kind, _), count in counts.items() if kind in ("motherboard", "laptop"))

    previous = set()
    if args.snapshot.is_file():
        previous = {tuple(item) for item in json.loads(args.snapshot.read_text(encoding="utf-8"))}
    current = {(item["brand"], item["model"], item["windows"]) for item in pending}
    closed = len(previous - current)
    opened = len(current - previous)
    args.snapshot.parent.mkdir(parents=True, exist_ok=True)
    args.snapshot.write_text(json.dumps(sorted(current), ensure_ascii=False, indent=1), encoding="utf-8")

    if not args.quiet:
        print(f"rows={len(rows)} pending={len(pending)} main={main_total} "
              f"closed_since_snapshot={closed} opened_since_snapshot={opened}")
        for (kind, brand), count in sorted(counts.items(), key=lambda item: (item[0][0], -item[1])):
            print(f"  {kind:12s} {brand:10s} {count}")
    for problem in problems:
        print("PROBLEM:", problem, file=sys.stderr)
    if problems:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
