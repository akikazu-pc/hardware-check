"""Collect ASUS WLAN downloads by exact motherboard model and Windows version."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
from html import unescape
import json
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


API = re.compile(r'https://(?:www|rog)\.asus\.com/support/webapi/ProductV2/GetPDDrivers\?[^"\s<>]+', re.I)
SYSTEMS = {"10": "45", "11": "52"}
FIELDS = ["model", "platform", "windows", "supportUrl", "status", "title", "version", "downloadUrl", "sha256"]


def model_key(value):
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def fetch(url):
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=12) as response:
        return response.read().decode("utf-8", errors="replace")


def downloads(row, catalog):
    key = model_key(row["model"])
    support = catalog.get(key, "")
    if support:
        support = support.rstrip("/") + "/helpdesk_download/"
    pending = [system for system in SYSTEMS if row[f"windows{system}X64Evidence"] == "pending"]
    base = dict(model=row["model"], platform=row["platform"], supportUrl=support)
    endpoint = None
    try:
        if support:
            endpoint = API.search(fetch(support))
    except OSError:
        pass
    if endpoint is None:
        return [dict(base, windows=system, status="support-api-unavailable") for system in pending]

    parts = urlsplit(unescape(endpoint[0]))
    parameters = dict(parse_qsl(parts.query, keep_blank_values=True))
    results = []
    for system in pending:
        parameters["osid"] = SYSTEMS[system]
        url = urlunsplit(parts._replace(query=urlencode(parameters)))
        try:
            data = json.loads(fetch(url)).get("Result") or {}
        except (OSError, ValueError):
            results.append(dict(base, windows=system, status="api-request-failed"))
            continue
        if model_key(data.get("Model") or "") != key:
            results.append(dict(base, windows=system, status="api-model-unverified"))
            continue

        count = 0
        for category in data.get("Obj") or []:
            if category.get("Name", "").strip().lower() not in ("wireless", "wireless lan", "wlan"):
                continue
            for package in category.get("Files") or []:
                download = (package.get("DownloadUrl") or {}).get("Global") or ""
                if download.startswith("/pub/ASUS/"):
                    download = "https://dlcdnets.asus.com" + download
                host = urlsplit(download).hostname
                if not download.startswith("https://") or host not in ("dlcdnets.asus.com", "dlcdnet.asus.com"):
                    continue
                count += 1
                results.append(dict(base, windows=system, status="oem-wlan-listed",
                                    title=package.get("Title"), version=package.get("Version"),
                                    downloadUrl=download, sha256=(package.get("sha256") or "").upper()))
        if not count:
            results.append(dict(base, windows=system, status="no-wlan-row-returned"))
    return results


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", type=Path)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--refresh", action="store_true", help="Recheck successful pending model/OS queries.")
    args = parser.parse_args()
    catalog = {model_key(row["model"]): row["officialUrl"] for row in read(args.catalog)}
    rows = [row for row in read(args.models) if row["type"] == "motherboard" and row["brand"] == "ASUS"
            and row["gap"] == "factory-variant-to-exact-id-and-install"
            and any(row[f"windows{system}X64Evidence"] == "pending" for system in SYSTEMS)]
    previous = defaultdict(list)
    if args.output.is_file():
        for item in read(args.output):
            previous[item["model"], item["platform"], item["windows"]].append(item)
    requested = []
    for row in rows:
        query = dict(row)
        for system in SYSTEMS:
            key = row["model"], row["platform"], system
            if not args.refresh and any(item["status"] == "oem-wlan-listed" for item in previous[key]):
                query[f"windows{system}X64Evidence"] = "cached"
        if any(query[f"windows{system}X64Evidence"] == "pending" for system in SYSTEMS):
            requested.append(query)

    with ThreadPoolExecutor(max_workers=8) as pool:
        for records in pool.map(lambda row: downloads(row, catalog), requested):
            grouped = defaultdict(list)
            for item in records:
                grouped[item["model"], item["platform"], item["windows"]].append(item)
            for key, batch in grouped.items():
                if any(item["status"] == "oem-wlan-listed" for item in batch) or not previous[key]:
                    previous[key] = batch

    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, FIELDS)
        writer.writeheader()
        for records in previous.values():
            writer.writerows(records)
    temporary.replace(args.output)
    print(f"Requested {len(requested)} of {len(rows)} pending ASUS motherboard records.")


if __name__ == "__main__":
    main()
