"""Expand the model table with laptop families found only in the DrvHub database.

For every requested brand the script crawls the DrvHub brand index, canonicalises each model page
to a base model code (dropping configuration suffixes such as ``A315-23-R144`` -> ``A315-23``),
skips codes already present in the table, and fetches the remaining model pages. Pages that list a
wireless network card become new rows with both systems marked ``third-party-wlan-listed`` (the
DrvHub page targets Windows 10 / 11 x64 together).

Usage: python scripts/expand-drvhub-library.py docs/network-rescue-model-gaps.csv \
    docs/network-rescue-drvhub-expansion-proof.csv --brands acer,asus [--apply] [--limit N]
"""
import argparse
import csv
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://jp.drvhub.net"
WIRELESS = re.compile(r"wireless network|wireless lan|wi-?fi|wlan card", re.I)
NOT_WLAN = re.compile(r"headset|mouse|keyboard|gamepad|printer|bluetooth", re.I)
INDEX_MODEL = re.compile(r'href="https://jp\.drvhub\.net/laptops/([a-z0-9\-]+)/([^"]+)"[^>]*>\s*([^<]{2,80})')
CODE = re.compile(r"[A-Z]{1,4}\d{2,4}[A-Z0-9]*(?:-[A-Z0-9]+)*", re.I)
COLUMNS = ["type", "brand", "model", "platform", "os", "wlanEvidence", "module", "gap", "source",
           "windows10X64Evidence", "windows11X64Evidence", "deviceCategory", "deviceTag"]
BRAND_NAMES = {"acer": "Acer", "asus": "ASUS", "lenovo": "Lenovo", "dell": "Dell", "hp": "HP", "msi": "MSI"}


def fetch(url):
    completed = subprocess.run(
        ["node", str(ROOT / "scripts" / "oem-http.mjs"), url],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
    try:
        item = json.loads(completed.stdout)[0]
    except (ValueError, IndexError):
        return ""
    return Path(item["file"]).read_text(encoding="utf-8", errors="replace") if item.get("status") == 200 else ""


def model_code(text):
    text = re.sub(r"^(Acer|ASUS|ROG)\s+", "", text, flags=re.I)
    text = re.sub(r"^(Acer|ASUS)\s+(Aspire|Nitro|ConceptD|Swift|Spin|TravelMate|Travel Mate|Predator|ROG|TUF)\s+", "", text, flags=re.I)
    candidates = CODE.findall(text)
    return max(candidates, key=lambda item: (len(item), item)).upper() if candidates else ""


def base_code(code):
    parts = code.split("-")
    return "-".join(parts[:2]) if len(parts) >= 3 else code


def drivers(html):
    items = []
    for block in html.split('class="drivers-list__item driver-item')[1:]:
        title = re.search(r"driver-item__title[^>]*>\s*([^<]+)", block)
        if not title:
            continue
        entry = {"device": re.sub(r"\s+", " ", title.group(1)).strip()}
        for label, key in (("ベンダー:", "vendor"), ("バージョン:", "version")):
            match = re.search(re.escape(label) + r"\s*</span>\s*<span[^>]*>\s*([^<]+)", block)
            if match:
                entry[key] = re.sub(r"\s+", " ", match.group(1)).strip()
        items.append(entry)
    return items


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("table", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--brands", default="acer,asus")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--count-only", action="store_true")
    args = parser.parse_args()

    with args.table.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    known = {(row["brand"], re.sub(r"[^A-Z0-9]", "", base_code(model_code(row["model"])))) for row in rows}
    proof, added = [], []
    for brand in args.brands.split(","):
        brand_name = BRAND_NAMES.get(brand, brand.title())
        first = fetch(f"{BASE}/laptops/{brand}")
        pages = [int(value) for value in re.findall(r"[?&]page=(\d+)", first)]
        last = max(pages) if pages else 1
        families = {}
        for page in range(1, last + 1):
            html = first if page == 1 else fetch(f"{BASE}/laptops/{brand}?page={page}")
            for found_brand, slug, label in INDEX_MODEL.findall(html):
                code = model_code(label)
                if not code:
                    continue
                base = base_code(code)
                families.setdefault(base, {"label": re.sub(r"\s+", " ", label).strip(),
                                            "url": f"{BASE}/laptops/{found_brand}/{slug}"})
            time.sleep(0.4)
        new_families = [code for code in families
                        if (brand_name, re.sub(r"[^A-Z0-9]", "", code)) not in known]
        print(f"{brand}: {len(families)} families, {len(new_families)} missing from table")
        if args.count_only:
            continue
        for code, info in sorted(families.items()):
            if (brand_name, re.sub(r"[^A-Z0-9]", "", code)) in known:
                continue
            if args.limit and len(added) >= args.limit:
                break
            html = fetch(info["url"])
            wireless = [entry for entry in drivers(html)
                        if WIRELESS.search(entry["device"]) and not NOT_WLAN.search(entry["device"])]
            if not wireless:
                continue
            added.append({"type": "laptop", "brand": brand_name, "model": code, "platform": "",
                          "os": "", "wlanEvidence": "third-party-drvhub", "module": "",
                          "gap": "third-party-source", "source": info["url"],
                          "windows10X64Evidence": "third-party-wlan-listed",
                          "windows11X64Evidence": "third-party-wlan-listed",
                          "deviceCategory": "", "deviceTag": ""})
            for entry in wireless:
                proof.append({"brand": brand_name, "model": code, "device": entry["device"],
                              "vendor": entry.get("vendor", ""), "version": entry.get("version", ""),
                              "url": info["url"]})
            print(f"  + {code}: {len(wireless)} card(s)")
            time.sleep(0.4)
    with args.output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, ["brand", "model", "device", "vendor", "version", "url"])
        writer.writeheader()
        writer.writerows(proof)
    print(f"families_added={len(added)} proof_rows={len(proof)}")
    if args.apply and added:
        rows.extend(added)
        with args.table.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, COLUMNS, quoting=csv.QUOTE_ALL, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        print("applied:", len(added))


if __name__ == "__main__":
    sys.exit(main())
