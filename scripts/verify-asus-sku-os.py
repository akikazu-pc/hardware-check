"""Recheck the operating-system list of each pending ASUS laptop SKU on its own support page.

The series-level capture in ``collect-asus-laptop-skus.py`` records one OS list for a whole ROG
series. A SKU whose own support page offers no such OS is therefore only "no driver list" there,
not proof that the manufacturer omits the system. This script queries ``GetPDOS`` for each pending
SKU, closes the cell when the OEM OS list has no entry for that system, and then closes a series
cell only when every SKU recorded under it agrees.

Usage: python scripts/verify-asus-sku-os.py docs/network-rescue-model-gaps.csv \
    docs/network-rescue-asus-sku-os-proof.csv [--apply]
"""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
from html import unescape
import json
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen


OS_IDS = {"10": "45", "11": "52"}
SKU_CODE = re.compile(r"[A-Z]{1,2}\d{3}[A-Z0-9]{0,6}$")
API = re.compile(r'https://www\.asus\.com/support/(?:webapi/[A-Za-z0-9]+|api/product\.asmx)/'
                 r'GetPDOS\?[^"\s<>]+')
THROTTLE_SECONDS = 1.0
FIELDS = ["model", "sku", "supportUrl", "osIds", "windows10", "windows11", "status"]


def fetch(url):
    time.sleep(THROTTLE_SECONDS)
    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=25) as response:
        return response.read().decode("utf-8", errors="replace")


def sku_of(model):
    tail = model.rsplit(" ", 1)[-1]
    return tail if SKU_CODE.match(tail) else ""


def inspect(row):
    sku = sku_of(row["model"])
    support = f"https://www.asus.com/supportonly/{sku.lower()}/helpdesk_download/"
    result = dict(model=row["model"], sku=sku, supportUrl=support, osIds="", windows10="", windows11="",
                  status="support-page-unavailable")
    try:
        html = fetch(support)
    except OSError:
        return result
    endpoint = API.search(html)
    if not endpoint:
        return result
    try:
        listed = json.loads(fetch(unescape(endpoint.group(0))))
    except (OSError, ValueError):
        return result
    os_ids = [str(item.get("Id")) for item in ((listed.get("Result") or {}).get("Obj") or [])]
    result["osIds"] = ";".join(os_ids)
    result["windows10"] = "yes" if OS_IDS["10"] in os_ids else "no"
    result["windows11"] = "yes" if OS_IDS["11"] in os_ids else "no"
    result["status"] = "os-list-empty" if not os_ids else "os-listed"
    return result


def apply_os(path, proof):
    """Close cells from the SKU OS list, then a series cell when every recorded SKU agrees."""
    absent = {(item["model"], system) for item in proof if item["status"] == "os-listed"
              for system, os_id in OS_IDS.items() if os_id not in item["osIds"].split(";")}
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        rows, fields = list(reader), reader.fieldnames
    by_model = {row["model"]: row for row in rows}
    updates = defaultdict(int)
    for model, system in absent:
        row = by_model.get(model)
        if row and row[f"windows{system}X64Evidence"] == "pending":
            row[f"windows{system}X64Evidence"] = "oem-os-not-listed"
            updates[f"sku win{system}"] += 1
    for row in rows:
        if row["type"] != "laptop" or row["brand"] != "ASUS":
            continue
        children = [by_model[name] for name in by_model
                    if name.startswith(row["model"] + " ") and sku_of(name)]
        if not children:
            continue
        for system in OS_IDS:
            field = f"windows{system}X64Evidence"
            values = {child[field] for child in children}
            if row[field] == "pending" and len(values) == 1 and values <= {"oem-os-not-listed"}:
                row[field] = values.pop()
                updates[f"series win{system}"] += 1
    if updates:
        raw = path.read_bytes()
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8",
                            newline="") as output:
            writer = csv.DictWriter(output, fields, quoting=csv.QUOTE_ALL,
                                    lineterminator="\r\n" if b"\r\n" in raw else "\n")
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(path)
    return dict(updates)


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    rows = [row for row in read(args.models) if row["type"] == "laptop" and row["brand"] == "ASUS"
            and "pending" in (row["windows10X64Evidence"], row["windows11X64Evidence"]) and sku_of(row["model"])]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        proof = list(pool.map(inspect, rows))
    with args.output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, FIELDS)
        writer.writeheader()
        writer.writerows(proof)
    print(f"Checked {len(proof)} pending SKU pages:", {item['status'] for item in proof})
    if args.apply:
        print("OS updates:", apply_os(args.models, proof))


if __name__ == "__main__":
    main()
