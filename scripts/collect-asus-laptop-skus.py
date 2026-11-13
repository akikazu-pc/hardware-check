"""Split ASUS laptop product series into exact SKUs and record WLAN listings per Windows x64.

SKU lists come from the series support page: www.asus.com pages render the model selector as
``selectListOption`` elements; rog.asus.com pages load it from ``GetPDCPUName``. For ROG, that
list, the series ``GetPDOS`` and the per-SKU ``GetPDDrivers`` results are captured from a page
session into ``--rog-capture`` JSON. A www page without a model selector whose URL ends in a
model code is that single SKU.

Each other SKU has its own ``https://www.asus.com/supportonly/<sku>/helpdesk_download/`` page that
embeds ``GetPDOS`` (Windows versions with downloads) and ``ProductV2/GetPDDrivers`` (per OS id:
45 = Windows 10, 52 = Windows 11, both x64). Every SKU becomes its own catalogue row. A series
row is closed for a system only when every SKU gives the same conclusive result: all list a WLAN
driver (``oem-wlan-listed``) or none offers downloads for that system (``oem-os-not-listed``).
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
from html import unescape
import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


OS_IDS = {"10": "45", "11": "52"}
REQUEST_PAUSE_SECONDS = 1.0
WLAN = re.compile(r"wireless\s*lan|\bwlan\b|wi-?fi", re.I)
OPTION = re.compile(r'selectListOption[^"]*"[^>]*>([^<]+)<')
SKU_CODE = re.compile(r"^[A-Z]{1,2}\d{3}[A-Z0-9]{0,6}$")
API = re.compile(r"https://www\.asus\.com/support/(?:webapi/[A-Za-z0-9]+|api/product\.asmx)/(GetPDOS|GetPDDrivers)\?[^\"\s<>]+")
DOWNLOAD_HOSTS = {"dlcdnets.asus.com", "dlcdnet.asus.com"}
FIELDS = ["series", "sku", "windows", "supportUrl", "status", "title", "version", "downloadUrl"]


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def fetch(url):
    # ASUS answers HTTP 451 to bursts; keep requests spaced.
    time.sleep(REQUEST_PAUSE_SECONDS)
    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=25) as response:
        return response.read().decode("utf-8", errors="replace")


def series_skus(row, rog_capture):
    if urlsplit(row["source"]).hostname == "rog.asus.com":
        return [sku for sku in rog_capture.get(row["model"], {}).get("skus", []) if SKU_CODE.match(sku)]
    try:
        html = fetch(row["source"].rstrip("/") + "/helpdesk_download/")
    except OSError:
        return []
    options = [unescape(option).strip() for option in OPTION.findall(html)]
    skus = [option for option in options if SKU_CODE.match(option)]
    if skus:
        return list(dict.fromkeys(skus))
    tail = urlsplit(row["source"]).path.rstrip("/").rsplit("-", 1)[-1].upper()
    # A single-model product page shows an OS selector instead of a model selector.
    return [tail] if SKU_CODE.match(tail) else []


ASUS_CDN = "https://dlcdnets.asus.com"
LAPTOP_DRIVER_ROOT = ASUS_CDN + "/pub/ASUS/GamingNB/Image/Driver/Networking/"


def download_url(file):
    url = (file.get("DownloadUrl") or {}).get("Global") or ""
    # ASUS mixes full URLs, "/pub/..." paths and "<file id>/<name>" paths under the laptop root.
    if url.startswith("/pub/ASUS/"):
        return ASUS_CDN + url
    if url and not url.startswith(("http://", "https://")):
        return LAPTOP_DRIVER_ROOT + url.lstrip("/")
    return url


def captured_results(record, sku):
    """Results for a ROG SKU from the page-session capture (series OS list, per-SKU driver lists)."""
    support = f"https://www.asus.com/supportonly/{sku.lower()}/helpdesk_download/"
    os_ids = {item.split(":", 1)[0] for item in record.get("os", [])}
    results = {}
    for system, os_id in OS_IDS.items():
        entry = record.get("d", {}).get(f"{sku}|{os_id}")
        if os_ids and os_id not in os_ids:
            results[system] = ("oem-os-not-listed", "", "", "")
        elif not entry:
            results[system] = ("no-driver-list", "", "", "")
        elif entry[3]:
            title, version, file, _ = entry[3][0]
            results[system] = ("oem-wlan-listed", title, version, file)
        else:
            results[system] = ("wlan-not-listed" if entry[1] else "no-network-category", "", "", "")
    return support, results


def sku_results(sku):
    """Return {system: (status, title, version, url)} for one exact SKU."""
    support = f"https://www.asus.com/supportonly/{sku.lower()}/helpdesk_download/"
    try:
        html = fetch(support)
    except OSError:
        return support, {system: ("support-page-unavailable", "", "", "") for system in OS_IDS}
    endpoints = {match.group(1): unescape(match.group(0)) for match in API.finditer(html)}
    if "GetPDOS" not in endpoints or "GetPDDrivers" not in endpoints:
        return support, {system: ("support-api-unavailable", "", "", "") for system in OS_IDS}
    try:
        listed = json.loads(fetch(endpoints["GetPDOS"]))
    except (OSError, ValueError):
        return support, {system: ("support-api-unavailable", "", "", "") for system in OS_IDS}
    os_ids = {str(item.get("Id")) for item in ((listed.get("Result") or {}).get("Obj") or [])}
    if not os_ids:
        return support, {system: ("os-list-empty", "", "", "") for system in OS_IDS}
    results = {}
    for system, os_id in OS_IDS.items():
        if os_id not in os_ids:
            results[system] = ("oem-os-not-listed", "", "", "")
            continue
        url = re.sub(r"osid=\d+", f"osid={os_id}", endpoints["GetPDDrivers"])
        try:
            categories = (json.loads(fetch(url)).get("Result") or {}).get("Obj") or []
        except (OSError, ValueError):
            results[system] = ("driver-api-unavailable", "", "", "")
            continue
        files = [file for category in categories for file in category.get("Files") or []
                 if WLAN.search(file.get("Title") or "") and not re.search("bluetooth", file.get("Title") or "", re.I)]
        files = [file for file in files if urlsplit(download_url(file)).hostname in DOWNLOAD_HOSTS]
        if files:
            first = files[0]
            results[system] = ("oem-wlan-listed", first.get("Title", ""), first.get("Version", ""),
                               download_url(first))
        else:
            names = {category.get("Name", "").lower() for category in categories}
            results[system] = ("wlan-not-listed" if "networking" in names else "no-network-category", "", "", "")
    return support, results


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", type=Path)
    parser.add_argument("--rog-capture", type=Path,
                        help="JSON: ROG series name -> {skus, os, d} captured from GetPDCPUName, GetPDOS, GetPDDrivers")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--apply-oem-evidence", action="store_true")
    args = parser.parse_args()
    rog_capture = json.loads(args.rog_capture.read_text(encoding="utf-8")) if args.rog_capture else {}
    models = read(args.models)
    fields = list(models[0])
    series = [row for row in models if row["type"] == "laptop" and row["brand"] == "ASUS"
              and row["wlanEvidence"] == "product-series"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        sku_lists = dict(zip((row["model"] for row in series), pool.map(lambda row: series_skus(row, rog_capture), series)))
        captured = {sku: captured_results(rog_capture[name], sku) for name, skus in sku_lists.items()
                    if name in rog_capture for sku in skus}
        online = sorted({sku for skus in sku_lists.values() for sku in skus} - set(captured))
        per_sku = {**captured, **dict(zip(online, pool.map(sku_results, online)))}
        all_skus = sorted(per_sku)
    existing = {row["model"] for row in models if row["type"] == "laptop" and row["brand"] == "ASUS"}
    proof, additions, updates = [], [], Counter()
    for row in series:
        skus = sku_lists[row["model"]]
        if not skus:
            proof.append(dict(series=row["model"], status="sku-list-unavailable", supportUrl=row["source"]))
            continue
        for system in OS_IDS:
            statuses = {per_sku[sku][1][system][0] for sku in skus}
            if len(statuses) == 1 and statuses <= {"oem-wlan-listed", "oem-os-not-listed"}:
                field = f"windows{system}X64Evidence"
                if row[field] == "pending":
                    row[field] = next(iter(statuses))
                    updates[f"series {system}:{row[field]}"] += 1
        for sku in skus:
            support, results = per_sku[sku]
            for system, (status, title, version, url) in results.items():
                proof.append(dict(series=row["model"], sku=sku, windows=system, supportUrl=support,
                                  status=status, title=title, version=version, downloadUrl=url))
            name = f"{row['model']} {sku}"
            if name in existing:
                continue
            item = {field: "" for field in fields}
            item.update(type="laptop", brand="ASUS", model=name, wlanEvidence="oem-driver-list",
                        gap="factory-variant-to-exact-id-and-install", source=support,
                        deviceCategory=row.get("deviceCategory") or "Laptop")
            for system, (status, *_rest) in results.items():
                item[f"windows{system}X64Evidence"] = status if status in {"oem-wlan-listed", "oem-os-not-listed"} else "pending"
                updates[f"sku {system}:{item[f'windows{system}X64Evidence']}"] += 1
            additions.append(item)
            existing.add(name)
    with args.output.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, FIELDS)
        writer.writeheader()
        writer.writerows(proof)
    print("SKUs:", len(all_skus), "proof:", dict(Counter((item.get("windows", ""), item["status"]) for item in proof)))
    print("Updates:", dict(updates), "new SKU rows:", len(additions))
    if args.apply_oem_evidence and (updates or additions):
        raw = args.models.read_bytes()
        temporary = args.models.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8",
                            newline="") as output:
            writer = csv.DictWriter(output, fields, quoting=csv.QUOTE_ALL,
                                    lineterminator="\r\n" if b"\r\n" in raw else "\n")
            writer.writeheader()
            writer.writerows(models + additions)
        temporary.replace(args.models)


if __name__ == "__main__":
    main()
