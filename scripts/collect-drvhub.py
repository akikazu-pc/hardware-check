"""Collect per-model wireless driver records from the DrvHub driver database.

DrvHub publishes one page per device (``https://jp.drvhub.net/laptops/<brand>/<slug>``) whose
driver cards carry the device name, driver type, vendor, version, INF file and hardware ID. The
page offers a single "Windows 10 / 11 (64-bit)" target, so a wireless card listed on a model page
covers both Windows 10 and Windows 11 x64.

This is a third-party source: the table stores the result as ``third-party-wlan-listed`` and keeps
the page URL in ``source``. The catalog of available device pages is built by crawling the brand
index (``/laptops/<brand>`` plus ``?page=N``).

Usage: python scripts/collect-drvhub.py docs/network-rescue-model-gaps.csv \
    docs/network-rescue-drvhub-proof.csv [--brands Acer,ASUS] [--apply]
"""
import argparse
import csv
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.parse

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://jp.drvhub.net"
WIRELESS = re.compile(r"wireless network|wireless lan|wi-?fi|wlan card", re.I)
NOT_WLAN = re.compile(r"headset|mouse|keyboard|gamepad|printer|bluetooth", re.I)
INDEX_MODEL = re.compile(r'href="https://jp\.drvhub\.net/laptops/([a-z0-9\-]+)/([^"]+)"[^>]*>\s*([^<]{2,80})')


def fetch(url):
    completed = subprocess.run(
        ["node", str(ROOT / "scripts" / "oem-http.mjs"), url],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
    try:
        item = json.loads(completed.stdout)[0]
    except (ValueError, IndexError):
        return ""
    if item.get("status") != 200:
        return ""
    return Path(item["file"]).read_text(encoding="utf-8", errors="replace")


def catalog(brand):
    """Map normalised model code -> (label, url) for every device page of one brand."""
    models = {}
    first = fetch(f"{BASE}/laptops/{brand}")
    pages = [int(value) for value in re.findall(r"[?&]page=(\d+)", first)]
    last = max(pages) if pages else 1
    for page in range(1, last + 1):
        suffix = "" if page == 1 else f"?page={page}"
        html = first if page == 1 else fetch(f"{BASE}/laptops/{brand}{suffix}")
        found = INDEX_MODEL.findall(html)
        if not found and page > 1:
            time.sleep(2)
            html = fetch(f"{BASE}/laptops/{brand}{suffix}")
            found = INDEX_MODEL.findall(html)
        for found_brand, slug, label in found:
            label = re.sub(r"\s+", " ", label).strip()
            code = model_code(label)
            if code:
                models.setdefault(code, (label, f"{BASE}/laptops/{found_brand}/{slug}"))
        time.sleep(0.6)
    return models


def model_code(text):
    """Extract the alphanumeric model code from a product label or table model name."""
    text = re.sub(
        r"^(Acer|ASUS|ROG)\s+",
        "", re.sub(
            r"^(Acer|ASUS)\s+(Aspire|Nitro|ConceptD|Swift|Spin|TravelMate|Travel Mate|Predator|ROG|TUF)\s+",
            "", text, flags=re.I), flags=re.I)
    text = re.sub(r"^(Aspire|Nitro|ConceptD|Swift|Spin|TravelMate|Travel Mate|Predator|ROG|TUF)$", "", text, flags=re.I)
    candidates = re.findall(r"[A-Z]{1,4}\d{2,4}[A-Z0-9]*(?:-[A-Z0-9]+)*", text, re.I)
    if not candidates:
        return ""
    return max(candidates, key=lambda item: (len(item), item)).upper()


def drivers(html):
    """Parse the driver cards into dicts."""
    items = []
    for block in html.split('class="drivers-list__item driver-item')[1:]:
        title = re.search(r"driver-item__title[^>]*>\s*([^<]+)", block)
        if not title:
            continue
        entry = {"device": re.sub(r"\s+", " ", title.group(1)).strip()}
        for label, key in (("ドライバータイプ:", "type"), ("ベンダー:", "vendor"),
                           ("バージョン:", "version"), ("Hardware ID:", "hardware")):
            match = re.search(re.escape(label) + r"\s*</span>\s*<span[^>]*>\s*([^<]+)", block)
            if match:
                entry[key] = re.sub(r"\s+", " ", match.group(1)).strip()
        items.append(entry)
    return items


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("table", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--brands", default="Acer,ASUS")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    with args.table.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    pending = [row for row in rows if row["brand"] in args.brands.split(",") and (
        row["windows10X64Evidence"] == "pending" or row["windows11X64Evidence"] == "pending")]
    catalogs = {}
    proof = []
    matched = {}
    for row in pending:
        brand = row["brand"]
        if brand not in catalogs:
            catalogs[brand] = catalog(brand.lower())
            print(f"{brand}: {len(catalogs[brand])} device pages")
        code = model_code(row["model"])
        hit = catalogs[brand].get(code) if code else None
        if not hit:
            print(f"{row['model']}: no matching device page")
            continue
        label, url = hit
        html = fetch(url)
        wireless = [entry for entry in drivers(html)
                    if WIRELESS.search(entry["device"]) and not NOT_WLAN.search(entry["device"])]
        if not wireless:
            print(f"{row['model']}: page without wireless card")
            continue
        matched[row["model"]] = url
        for entry in wireless:
            proof.append({"model": row["model"], "drvhub_model": label, "device": entry["device"],
                          "vendor": entry.get("vendor", ""), "version": entry.get("version", ""),
                          "hardware": entry.get("hardware", ""), "os": "Windows 10 / 11 (64-bit)", "url": url})
        print(f"{row['model']}: {len(wireless)} wireless card(s) -> {label}")
        time.sleep(1)

    with args.output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, ["model", "drvhub_model", "device", "vendor", "version",
                                              "hardware", "os", "url"])
        writer.writeheader()
        writer.writerows(proof)
    print(f"pending={len(pending)} matched={len(matched)} proof_rows={len(proof)}")

    if args.apply and matched:
        for row in rows:
            url = matched.get(row["model"])
            if not url:
                continue
            for system in ("10", "11"):
                field = f"windows{system}X64Evidence"
                if row[field] == "pending":
                    row[field] = "third-party-wlan-listed"
            row["wlanEvidence"] = "third-party-drvhub"
            row["source"] = url
        with args.table.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, list(rows[0]), quoting=csv.QUOTE_ALL, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        print("applied:", len(matched))


if __name__ == "__main__":
    sys.exit(main())
