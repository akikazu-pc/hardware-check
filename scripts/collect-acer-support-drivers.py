"""Query Acer's support search for exact model driver records through en-us.

The public product-support page (``/us-en/support/product-support/<page>``) loads its driver
table from ``POST /en-us/DynamicContent/GetDriversAndManuals`` with ``{ModelName, Local}``.
The backend answers with an Elasticsearch-style payload whose ``hits[0]._source
.global_download_details`` holds the driver files; each file's ``oss`` field lists the Windows
builds it serves (``10M1`` Windows 10 x64, ``11M1`` Windows 11 x64, ``11A1`` Windows 11 ARM64).

The endpoint is rate limited and occasionally answers with an empty hit list, so every model is
retried a few times with pauses.

Usage: python scripts/collect-acer-support-drivers.py docs/network-rescue-model-gaps.csv [--apply]
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
LOCALE = "en-us"
URL = f"https://www.acer.com/{LOCALE}/DynamicContent/GetDriversAndManuals"
WARM = f"https://www.acer.com/{LOCALE}/support/product-support/"
WLAN = re.compile(r"wireless|wlan|wi-?fi", re.I)
AUDIO = re.compile(r"audio|chipset|lan", re.I)
RETRIES = 4
UNAVAILABLE = {"outside-x64-record", "no-factory-wifi"}


def query(page_name, model_name, tries=RETRIES):
    for attempt in range(tries):
        warm = WARM + page_name
        body = json.dumps({"ModelName": model_name, "Local": LOCALE})
        completed = subprocess.run(
            ["node", str(ROOT / "scripts" / "acer-api-fetch.mjs"), warm, URL, body],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        if completed.returncode != 0:
            time.sleep(3)
            continue
        try:
            payload = json.loads(completed.stdout)
        except ValueError:
            time.sleep(3)
            continue
        hits = payload.get("hits") or []
        if hits:
            source = hits[0].get("_source") or {}
            details = json.loads(source.get("global_download_details") or "{}")
            files = (details.get("driver") or {}).get("files") or []
            if files:
                return files
        time.sleep(4)
    return None


def classify(files, windows):
    code = "10M1" if windows == "10" else "11M1"
    own = [item for item in files if code in (item.get("oss") or "").split(";")]
    other = [item for item in files if any(
        part in {"10M1", "11M1"} and part != code for part in (item.get("oss") or "").split(";"))]
    if not own:
        return None
    wlan = [item for item in own if WLAN.search((item.get("category") or "") + (item.get("fileName") or ""))]
    if wlan:
        return "oem-wlan-listed"
    if len(own) >= 5 and any(AUDIO.search(item.get("category") or "") for item in own):
        return "oem-wlan-not-listed"
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("table", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--pause", type=float, default=4.0)
    args = parser.parse_args()

    with args.table.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    pending = [row for row in rows if row["brand"] == "Acer" and (
        row["windows10X64Evidence"] == "pending" or row["windows11X64Evidence"] == "pending")]
    time.sleep(180)  # let any previous burst expire
    results = {}
    for row in pending:
        model = row["model"]
        page = re.sub(r"\s+", "_", model.strip()) if not model.startswith("Aspire ") else model.replace(" ", "_")
        stripped = re.sub(r"^(Aspire|Nitro|Spin|Swift|ConceptD|TravelMate)\s+", "", model)
        forms = [(model, page)]
        if stripped != model:
            forms.append((stripped, page))
        plain = re.sub(r"^(Aspire|Nitro|Spin|Swift|ConceptD|TravelMate)\s+", "", model).replace(" ", "_")
        forms.append((stripped, plain))
        if stripped != model:
            forms.append((model.replace(" ", "_"), page))
        candidates = list(dict.fromkeys(forms))
        files = None
        for model_name, page_name in candidates:
            files = query(page_name, model_name)
            if files:
                break
            time.sleep(args.pause)
        if not files:
            print(f"{model}: no data")
            continue
        for windows in ("10", "11"):
            field = f"windows{windows}X64Evidence"
            if row[field] != "pending":
                continue
            status = classify(files, windows)
            if not status:
                continue
            results[(model, windows)] = (status, files)
            print(f"{model} {windows} -> {status}")
        time.sleep(args.pause)

    if args.apply and results:
        for row in rows:
            for windows in ("10", "11"):
                hit = results.get((row["model"], windows))
                if hit and row[f"windows{windows}X64Evidence"] == "pending":
                    row[f"windows{windows}X64Evidence"] = hit[0]
        with args.table.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, list(rows[0]), quoting=csv.QUOTE_ALL, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        print("applied:", len(results))


if __name__ == "__main__":
    sys.exit(main())
