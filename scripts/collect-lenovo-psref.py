"""Read Lenovo PSREF spec sheets for the factory wireless module and supported systems.

PSREF is Lenovo's product specification database. Every model has a spec PDF whose
``Operating System`` block lists the systems Lenovo offers and whose connectivity block names
the wireless module. A model that lists Windows 11 and no Windows 10 does not ship with a
Windows 10 driver set; combined with the WLAN package metadata from the model's download page
("Windows 11 (64-bit)" only) that closes the Windows 10 cell as not listed.

Usage: python scripts/collect-lenovo-psref.py docs/network-rescue-model-gaps.csv \
    artifacts/lenovo-psref-proof.csv [--apply-os-evidence]
"""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

import pymupdf


PSREF = "https://psref.lenovo.com/syspool/Sys/PDF/{series}/{model}/{model}_Spec.pdf"
MODULE = re.compile(
    r"\b(?:MT79(?:02|20|21|22|25|27)[A-Z0-9]*|RTL(?:88|89)\d{2}[A-Z]{1,4}|"
    r"BE(?:200|201|202|211|213)(?:NGW)?|AX(?:101|200|201|210|211|411)(?:NGW)?|"
    r"(?:QCNCM|NCM)8(?:25|65)|WCN785[A-Z0-9]*|BE1750[AX]?)\b", re.I
)
THROTTLE_SECONDS = 0.8
FIELDS = ["model", "psrefUrl", "sha256", "pages", "systems", "modules", "windows10", "windows11",
          "downloadOs", "status"]


def model_key(value):
    return re.sub(r"[^A-Z0-9+]", "", value.upper())


def fetch(url, timeout=40):
    time.sleep(THROTTLE_SECONDS)
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def psref_url(model):
    words = model.split()
    series = words[0]
    name = model.replace(" ", "_")
    return PSREF.format(series=quote(series), model=quote(name))


def download_os(support):
    """Operating systems of the WLAN package linked from the model row, if it is a Lenovo DS page."""
    if "downloads/" not in support.lower():
        return ""
    # support.lenovo.com answers 403 to scripts; the same package page is served by pcsupport.
    support = re.sub(r"^https://support\.lenovo\.com/[^/]+/[^/]+/(downloads/)(DS\d+)",
                    lambda m: "https://pcsupport.lenovo.com/us/en/downloads/" + m.group(2).lower(), support, flags=re.I)
    try:
        html = fetch(support).decode("utf-8", errors="replace")
    except (HTTPError, URLError, OSError):
        return ""
    systems = sorted(set(re.findall(r'"OperatingSystemKeys":\[([^\]]*)\]', html)))
    return ";".join(systems)


def inspect(row):
    result = {field: "" for field in FIELDS}
    result.update(model=row["model"], status="psref-not-found")
    url = psref_url(row["model"])
    try:
        payload = fetch(url)
    except (HTTPError, URLError, OSError):
        return result
    result.update(psrefUrl=url, sha256=hashlib.sha256(payload).hexdigest().upper())
    try:
        with pymupdf.open(stream=payload, filetype="pdf") as pdf:
            text = "".join(page.get_text() for page in pdf)
            result["pages"] = str(len(pdf))
    except (RuntimeError, ValueError):
        result["status"] = "psref-unreadable"
        return result
    block = re.search(r"Operating System\**\n(.*?)(?:\n[A-Z][A-Za-z ]+\n)", text, re.S)
    systems = sorted(set(re.findall(r"Windows[\u00ae\s]*1[01][A-Za-z0-9 ]*", block.group(1)))) if block else []
    result["systems"] = ";".join(s.strip() for s in systems)
    modules = {match.group().upper() for match in MODULE.finditer(text)}
    result["modules"] = ";".join(sorted(modules))
    result["windows10"] = "yes" if any("10" in s for s in systems) else "no"
    result["windows11"] = "yes" if any("11" in s for s in systems) else "no"
    result["downloadOs"] = download_os(row["source"])
    if not systems:
        result["status"] = "psref-os-unreadable"
    elif result["windows10"] == "no" and result["windows11"] == "yes":
        result["status"] = "psref-win11-only"
    else:
        result["status"] = "psref-win10-listed"
    return result


def apply_os_evidence(path, proof):
    """Close Windows 10 only when the spec sheet and the download package both list no Windows 10."""
    closable = {}
    for item in proof:
        if item["status"] != "psref-win11-only":
            continue
        package = [part for part in item["downloadOs"].split(";") if part]
        if package and all("Windows 11" in part and "Windows 10" not in part for part in package):
            closable[item["model"]] = item["modules"]
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        rows, fields = list(reader), reader.fieldnames
    updates = defaultdict(int)
    for row in rows:
        if row["type"] != "laptop" or row["brand"] != "Lenovo" or row["model"] not in closable:
            continue
        if row["windows10X64Evidence"] == "pending":
            row["windows10X64Evidence"] = "oem-os-not-listed"
            updates["win10:oem-os-not-listed"] += 1
        if not row["module"] and closable[row["model"]]:
            row["module"] = closable[row["model"]]
            updates["module"] += 1
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
    parser.add_argument("--apply-os-evidence", action="store_true")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    rows = [row for row in read(args.models) if row["type"] == "laptop" and row["brand"] == "Lenovo"
            and "pending" in (row["windows10X64Evidence"], row["windows11X64Evidence"])]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        proof = list(pool.map(inspect, rows))
    with args.output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, FIELDS)
        writer.writeheader()
        writer.writerows(proof)
    print(f"Checked {len(proof)} PSREF sheets:", sorted({item["status"] for item in proof}))
    if args.apply_os_evidence:
        print("OS evidence updates:", apply_os_evidence(args.models, proof))


if __name__ == "__main__":
    main()
