"""Sweep Acer regional driver databases for exact models that the US catalogue lacks.

``DynamicContent/GetDriversAndManuals`` returns different records per regional site: models sold in
EMEA often have no record on ``us-en`` but do have one on ``de-de``, ``fr-fr`` and similar sites.
Each hit carries ``global_download_details`` as a JSON string whose ``driver.files`` entries name the
category, the Acer OS code (``10M1`` = Windows 10 x64, ``11M1`` = Windows 11 x64) and the file.

Classification per system:

* ``oem-wlan-listed`` when a ``Wireless LAN``/Wi-Fi file covers that system,
* ``oem-os-not-listed`` when the only record for that system is Acer's Windows Update stub
  ("The Driver for this model can be updated via Windows Updates"),
* ``oem-wlan-not-listed`` when the system list is populated but carries no wireless file,
* unclassified otherwise.

Usage: python scripts/collect-acer-locale-listings.py docs/network-rescue-model-gaps.csv \
    docs/network-rescue-acer-locale-proof.csv [--locales de-de,fr-fr] [--apply]
"""
import argparse
import csv
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parent.parent
BRIDGE = ROOT / "scripts" / "oem-http.mjs"
DEFAULT_LOCALES = ("de-de", "fr-fr", "es-es", "it-it", "nl-nl", "ru-ru", "pl-pl", "tr-tr", "pt-pt")
WLAN = re.compile(r"wi-?fi|wireless|wlan", re.I)
STUB = re.compile(r"updated via windows updates", re.I)
SYSTEMS = {"10": "10M1", "11": "11M1"}
FIELDS = ["model", "windows", "status", "evidence", "locale"]


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def fetch_page_and_post(locale, model):
    warm = f"https://www.acer.com/{locale}/support/product-support/{model}"
    body = json.dumps({"ModelName": model, "Local": locale})
    completed = subprocess.run(
        ["node", str(BRIDGE), "--post-with-session", warm,
         f"https://www.acer.com/{locale}/DynamicContent/GetDriversAndManuals", body],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    try:
        item = json.loads(completed.stdout)[0]
    except (ValueError, IndexError):
        return []
    if item.get("status") != 200 or not item.get("file"):
        return []
    payload = json.loads(Path(item["file"]).read_text(encoding="utf-8", errors="replace"))
    hits = payload.get("hits") or []
    return [hit.get("_source") or {} for hit in hits]


def classify(files, system):
    code = SYSTEMS[system]
    covered = [item for item in files if code in (item.get("oss") or "")]
    wireless = [item for item in covered
                if WLAN.search((item.get("category") or "") + (item.get("fileName") or "")
                               + (item.get("description") or ""))]
    if wireless:
        item = wireless[0]
        return "oem-wlan-listed", f"{item.get('fileName')} ({item.get('category')})"
    if covered and all(STUB.search(item.get("description") or "") for item in covered):
        return "oem-os-not-listed", "Windows Update stub only"
    if len(covered) >= 5:
        return "oem-wlan-not-listed", f"{len(covered)} driver files, no wireless"
    return "", ""


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--locales", default=",".join(DEFAULT_LOCALES))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    rows = [row for row in read(args.models) if row["brand"] == "Acer" and row["type"] == "laptop"
            and row["wlanEvidence"] == "oem-model-catalog"
            and any(row[f"windows{system}X64Evidence"] == "pending" for system in SYSTEMS)]
    proof, found = [], {}
    for row in rows:
        code = row["model"].split()[-1]
        if code in found:
            continue
        for locale in [item.strip() for item in args.locales.split(",") if item.strip()]:
            for record in fetch_page_and_post(locale, code):
                try:
                    details = json.loads(record.get("global_download_details") or "{}")
                except ValueError:
                    continue
                files = (details.get("driver") or {}).get("files") or []
                if not files:
                    continue
                found[code] = locale
                for system in SYSTEMS:
                    status, evidence = classify(files, system)
                    if status:
                        proof.append({"model": row["model"], "windows": system, "status": status,
                                      "evidence": evidence, "locale": locale})
                break
            if code in found:
                break
        print(("hit " if code in found else "miss"), code, found.get(code, ""))
    with args.output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, FIELDS)
        writer.writeheader()
        writer.writerows(proof)
    print(f"models={len(rows)} with_data={len(found)} classified={len(proof)}")
    if args.apply and proof:
        raw = args.models.read_bytes()
        with args.models.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            data, fields = list(reader), reader.fieldnames
        wanted = {(item["model"], item["windows"]): item["status"] for item in proof}
        updates = 0
        for row in data:
            if row["brand"] != "Acer":
                continue
            for system in SYSTEMS:
                field = f"windows{system}X64Evidence"
                value = wanted.get((row["model"], system))
                if row[field] == "pending" and value in {"oem-wlan-listed", "oem-os-not-listed",
                                                         "oem-wlan-not-listed"}:
                    row[field] = value
                    updates += 1
        temporary = args.models.with_suffix(args.models.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8",
                            newline="") as output:
            writer = csv.DictWriter(output, fields, quoting=csv.QUOTE_ALL,
                                    lineterminator="\r\n" if b"\r\n" in raw else "\n")
            writer.writeheader()
            writer.writerows(data)
        temporary.replace(args.models)
        print("applied:", updates)


if __name__ == "__main__":
    main()
