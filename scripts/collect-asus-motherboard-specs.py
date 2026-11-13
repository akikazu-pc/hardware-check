"""Check the factory wireless specification of ASUS motherboards in their own manuals.

The ASUS support page of each model links the model-specific English manual. A board that
ships with a wireless module always documents it in the manual's specification table, so a
manual without any wireless entry is evidence that no factory module is fitted. This separates
"the OEM download list omits WLAN" from "the board has no factory WLAN", which the download
collector needs before it can close a model and system.

Usage: python scripts/collect-asus-motherboard-specs.py docs/network-rescue-model-gaps.csv \
    docs/asus-motherboard-discovery.csv artifacts/spec-proof.csv [--apply-spec]
"""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
from pathlib import Path
import re
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

import pymupdf


PDF_PATH = re.compile(r'(/pub/ASUS/mb/[^"<>?\\]+/[EQ]\d+_[^"<>?\\]+\.pdf)', re.I)
WIRELESS = re.compile(r"Wi[\s-]*Fi|WLAN|wireless|802\.11", re.I)
SPEC_ROW = re.compile(r"Expansion Slot", re.I)
SPEC_EXTRA = re.compile(r"Storage", re.I)
MODULE = re.compile(
    r"\b(?:MT79(?:02|20|21|22|25|27)[A-Z0-9]*|RTL(?:88|89)\d{2}[A-Z]{1,4}|"
    r"BE(?:200|201|202|211|213)(?:NGW)?|AX(?:101|200|201|210|211|411)(?:NGW)?|"
    r"(?:QCNCM|NCM)8(?:25|65)|WCN785[A-Z0-9]*|BE1750[AX]?)\b", re.I
)
THROTTLE_SECONDS = 0.8
FIELDS = ["model", "platform", "manualUrl", "sha256", "pages", "wirelessPages", "modules", "status"]


def model_key(value):
    return re.sub(r"[^A-Z0-9+]", "", value.upper())


def fetch(url):
    time.sleep(THROTTLE_SECONDS)
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def manual_urls(support, model):
    html = fetch(support.rstrip("/") + "/helpdesk_manual/").decode("utf-8", errors="replace")
    paths = list(dict.fromkeys(PDF_PATH.findall(html)))
    key = model_key(model)
    # Related models share this page. Only the file named after this model counts, and only when
    # it is the user manual (or its E-document variant): a series manual documents the WIFI
    # siblings too, and a quick start guide has no specification table at all.
    matched = [path for path in paths if key in model_key(path.rsplit("/", 1)[-1])]
    if "WIFI" not in key:
        matched = [path for path in matched if "WIFI" not in path.upper()]
    manuals = [path for path in matched if "_UM_" in path.upper() or "_EM_" in path.upper()]
    return ["https://dlcdnets.asus.com" + quote(path, safe="/%") for path in manuals[:1]]


def inspect(row, catalog):
    support = catalog.get(model_key(row["model"]), "")
    result = {field: "" for field in FIELDS}
    result.update(model=row["model"], platform=row["platform"], status="manual-not-found")
    if not support:
        return result
    try:
        urls = manual_urls(support, row["model"])
    except OSError:
        result["status"] = "manual-page-unavailable"
        return result
    if not urls:
        return result
    url = urls[0]
    result["manualUrl"] = url
    try:
        payload = fetch(url)
    except OSError:
        result["status"] = "manual-download-failed"
        return result
    result["sha256"] = hashlib.sha256(payload).hexdigest().upper()
    try:
        with pymupdf.open(stream=payload, filetype="pdf") as pdf:
            pages, wireless, modules, spec_pages = [], set(), set(), set()
            for number, page in enumerate(pdf, 1):
                text = page.get_text()
                pages.append(number)
                if WIRELESS.search(text):
                    wireless.add(number)
                    modules.update(match.group().upper() for match in MODULE.finditer(text))
                if SPEC_ROW.search(text) and SPEC_EXTRA.search(text):
                    spec_pages.add(number)
    except (RuntimeError, ValueError):
        result["status"] = "manual-unreadable"
        return result
    result.update(pages=str(len(pages)), wirelessPages=";".join(str(n) for n in sorted(wireless)),
                  modules=";".join(sorted(modules)))
    if not wireless:
        result["status"] = "manual-wlan-absent"
    elif wireless & spec_pages:
        # Wireless appears in the specification table itself, not only in BIOS or safety text.
        result["status"] = "manual-spec-wlan-listed"
    else:
        result["status"] = "manual-wlan-mentioned"
    return result


def apply_spec(path, proof):
    """Record the factory WLAN state; a manual without WLAN is the missing second omission."""
    factory = {}
    for item in proof:
        if item["status"] == "manual-wlan-absent":
            factory[item["model"]] = ("oem-spec-wlan-not-listed", "")
        elif item["status"] == "manual-spec-wlan-listed" and item["modules"]:
            # A manual module name is a candidate; the exact SUBSYS and the driver still need proof.
            factory[item["model"]] = ("manual-module-candidate", item["modules"])
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        rows, fields = list(reader), reader.fieldnames
    updates = defaultdict(int)
    for row in rows:
        if row["type"] != "motherboard" or row["brand"] != "ASUS" or row["model"] not in factory:
            continue
        evidence, modules = factory[row["model"]]
        if row["wlanEvidence"] != evidence:
            row["wlanEvidence"] = evidence
            updates[evidence] += 1
        if modules and not row["module"]:
            row["module"] = modules
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
    global THROTTLE_SECONDS
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", type=Path)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--apply-spec", action="store_true")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--pause", type=float, default=THROTTLE_SECONDS)
    args = parser.parse_args()
    THROTTLE_SECONDS = args.pause
    catalog = {model_key(row["model"]): row["officialUrl"] for row in read(args.catalog)}
    rows = [row for row in read(args.models) if row["type"] == "motherboard" and row["brand"] == "ASUS"
            and row["wlanEvidence"] in {"catalog-model", "oem-spec-wlan-not-listed"}
            and any(row[f"windows{system}X64Evidence"] == "pending" for system in ("10", "11"))]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        proof = list(pool.map(lambda row: inspect(row, catalog), rows))
    with args.output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, FIELDS)
        writer.writeheader()
        writer.writerows(proof)
    print(f"Checked {len(proof)} manuals:", {item["status"] for item in proof})
    if args.apply_spec:
        print("Factory WLAN updates:", apply_spec(args.models, proof))


if __name__ == "__main__":
    main()
