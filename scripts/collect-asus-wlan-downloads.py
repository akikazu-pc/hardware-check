"""Collect ASUS WLAN downloads by exact motherboard model and Windows version."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
from html import unescape
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


API = re.compile(r'https://(?:www|rog)\.asus\.com/support/webapi/ProductV2/GetPDDrivers\?[^"\s<>]+', re.I)
SYSTEMS = {"10": "45", "11": "52"}
WLAN = re.compile(r"wireless|wlan|wi[- ]?fi|無線區域網|無線網路|无线局域网|无线网卡", re.I)
FIELDS = ["model", "platform", "windows", "supportUrl", "status", "title", "version", "downloadUrl", "sha256"]
# ASUS answers HTTP 451 above roughly one request per second and per thread burst.
THROTTLE_SECONDS = 0.6
RETRY_SECONDS = 8.0
REGION = ""


def model_key(value):
    return re.sub(r"[^A-Z0-9+]", "", value.upper())


def fetch(url):
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(2):
        time.sleep(THROTTLE_SECONDS)
        try:
            with urlopen(request, timeout=20) as response:
                return response.read().decode("utf-8", errors="replace")
        except HTTPError as error:
            if error.code not in {429, 451} or attempt:
                raise
            time.sleep(RETRY_SECONDS)
    raise OSError("retry exhausted")


def official_download(package):
    download = (package.get("DownloadUrl") or {}).get("Global") or ""
    if download.startswith("/pub/ASUS/"):
        download = "https://dlcdnets.asus.com" + download
    parsed = urlsplit(download)
    return download if parsed.scheme == "https" and parsed.hostname in {"dlcdnets.asus.com", "dlcdnet.asus.com"} else ""


def oem_list_omits_wlan(categories):
    names = {category.get("Name", "").strip().lower() for category in categories
             if any(official_download(package) for package in category.get("Files") or [])}
    return ("lan" in names and bool(names & {"audio", "chipset"}) and not any(
        WLAN.search(category.get("Name", "")) or any(WLAN.search(package.get("Title") or "")
            for package in category.get("Files") or []) for category in categories))


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
    if endpoint is None and REGION:
        # Some models only expose GetPDOS/GetPDDrivers on a regional page
        # (e.g. asus.com/tw/supportonly/<model>/helpdesk_download/).
        regional = re.sub(r"^https://www\.asus\.com/", f"https://www.asus.com/{REGION}/", support)
        try:
            endpoint = API.search(fetch(regional))
            if endpoint is not None:
                base["supportUrl"] = regional
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
        categories = data.get("Obj") or []
        for category in categories:
            name = category.get("Name", "")
            named = name.strip().lower() in ("wireless", "wireless lan", "wlan") or bool(WLAN.search(name))
            titled = any(WLAN.search(package.get("Title") or "") for package in category.get("Files") or [])
            if not (named or titled):
                continue
            for package in category.get("Files") or []:
                download = official_download(package)
                if not download:
                    continue
                count += 1
                results.append(dict(base, windows=system, status="oem-wlan-listed",
                                    title=package.get("Title"), version=package.get("Version"),
                                    downloadUrl=download, sha256=(package.get("sha256") or "").upper()))
        if not count:
            status = "oem-wlan-not-listed" if oem_list_omits_wlan(categories) else "no-wlan-row-returned"
            results.append(dict(base, windows=system, status=status))
    return results


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def listed_windows(title):
    if not re.search(r"\b(?:x64|64[ -]*bit)\b", title, re.I):
        return set()
    windows = set(re.findall(r"\bwin(?:dows)?[ _-]*(10|11)\b", title, re.I))
    if re.search(r"\bwin(?:dows)?[ _-]*(?:10\s*[/&]\s*11|11\s*[/&]\s*10)\b", title, re.I):
        windows.update(SYSTEMS)
    return windows


def apply_oem_evidence(path, audit):
    confirmed = {}
    for item in audit:
        support, download = urlsplit(item["supportUrl"]), urlsplit(item["downloadUrl"])
        if (support.scheme != "https" or support.hostname not in {"www.asus.com", "rog.asus.com"}
                or not support.path.rstrip("/").endswith("/helpdesk_download")):
            continue
        key = item["platform"], item["model"], item["windows"]
        if (item["status"] == "oem-wlan-listed" and item["windows"] in listed_windows(item["title"] or "")
                and download.scheme == "https" and download.hostname in {"dlcdnets.asus.com", "dlcdnet.asus.com"}):
            confirmed[key] = item["status"]
        elif item["status"] == "oem-wlan-not-listed":
            confirmed.setdefault(key, item["status"])
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        rows, fields = list(reader), reader.fieldnames
    updates = defaultdict(int)
    for row in rows:
        if row["type"] != "motherboard" or row["brand"] != "ASUS":
            continue
        factory_wlan = row["wlanEvidence"] in {"manual-module-candidate", "oem-spec-wlan-listed", "oem-spec-module"}
        for system in SYSTEMS:
            field = f"windows{system}X64Evidence"
            status = confirmed.get((row["platform"], row["model"], system))
            two_omissions = status == "oem-wlan-not-listed" and row["wlanEvidence"] == "oem-spec-wlan-not-listed"
            if row[field] == "pending" and status and (factory_wlan or two_omissions):
                row[field] = status
                updates[f"{system}:{status}"] += 1
    if updates:
        raw = path.read_bytes()
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8", newline="") as output:
            writer = csv.DictWriter(output, fields, quoting=csv.QUOTE_ALL,
                                    lineterminator="\r\n" if b"\r\n" in raw else "\n")
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(path)
    return dict(updates)


def main():
    global THROTTLE_SECONDS, REGION
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", type=Path)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--model-list", type=Path, help="Optional CSV containing platform and model columns.")
    parser.add_argument("--all-pending", action="store_true", help="Query every pending ASUS model and system in the catalog")
    parser.add_argument("--apply-oem-evidence", action="store_true", help="Record checked OEM listing evidence with matching factory specifications")
    parser.add_argument("--refresh", action="store_true", help="Recheck successful pending model/OS queries.")
    parser.add_argument("--workers", type=int, default=2, help="Concurrent ASUS requests; high values trigger HTTP 451")
    parser.add_argument("--pause", type=float, default=THROTTLE_SECONDS, help="Seconds to wait before each request")
    parser.add_argument("--region", default="", help="Try this ASUS regional support page when the global page exposes no API, e.g. tw")
    args = parser.parse_args()
    THROTTLE_SECONDS = args.pause
    REGION = args.region.strip().strip("/")
    catalog = {model_key(row["model"]): row["officialUrl"] for row in read(args.catalog)}
    selected = {(row["platform"], row["model"]) for row in read(args.model_list)} if args.model_list else None
    rows = [row for row in read(args.models) if row["type"] == "motherboard" and row["brand"] == "ASUS"
            and ((row["platform"], row["model"]) in selected if selected is not None
                 else args.all_pending or row["gap"] == "factory-variant-to-exact-id-and-install")
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
            if not args.refresh and any(item["status"] in {"oem-wlan-listed", "oem-wlan-not-listed"} for item in previous[key]):
                query[f"windows{system}X64Evidence"] = "cached"
        if any(query[f"windows{system}X64Evidence"] == "pending" for system in SYSTEMS):
            requested.append(query)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for records in pool.map(lambda row: downloads(row, catalog), requested):
            grouped = defaultdict(list)
            for item in records:
                grouped[item["model"], item["platform"], item["windows"]].append(item)
            for key, batch in grouped.items():
                if any(item["status"] in {"oem-wlan-listed", "oem-wlan-not-listed"} for item in batch) or not previous[key]:
                    previous[key] = batch

    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, FIELDS)
        writer.writeheader()
        for records in previous.values():
            writer.writerows(records)
    temporary.replace(args.output)
    print(f"Requested {len(requested)} of {len(rows)} pending ASUS motherboard records.")
    if args.apply_oem_evidence:
        print("OEM WLAN listing updates:", apply_oem_evidence(args.models, read(args.output)))


if __name__ == "__main__":
    main()
