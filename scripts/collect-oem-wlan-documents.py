"""Extract WLAN evidence from model-specific MSI and ASRock documents."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from pathlib import Path
import re
import subprocess
from urllib.parse import quote
from urllib.request import Request, urlopen

import pymupdf


MODULE = re.compile(
    r"\b(?:MT79(?:02|20|21|22|25|27|28)[A-Z0-9]*|RTL(?:88|89)\d{2}[A-Z]{1,4}|"
    r"BE(?:200|201|202|211|213)(?:NGW)?|AX(?:101|200|201|210|211|411)(?:NGW)?|"
    r"(?:QCNCM|NCM)8(?:25|65)|WCN785[A-Z0-9]*|BE1750[AX]?)\b", re.I
)
WIRELESS = re.compile(r"Wi[\s-]*Fi|WLAN|802\.11|Wireless-AC", re.I)
MSI_SECTION = re.compile(
    r"^(?:Wireless(?:\s+LAN)?|Wi[ -]?Fi)\s*(?:/|&)\s*(?:Bluetooth|BT)[ \t]*\n"
    r"(.+?)(?=^Audio\b|^FEATURES\b|^CONNECTIONS\b|\Z)", re.I | re.M | re.S
)
OPTIONAL = re.compile(r"module.{0,28}(?:sold separately|not included)|slot only", re.I)
ASROCK_SECTION = re.compile(
    r"^Wireless\s+LAN[ \t]*(?:\n\s*|\s*)(?:\(([^)]+)\)\s*)?"
    r"(\u2022.*?)(?=^(?:USB|Rear Panel|Storage|Connector|BIOS|OS)\b|\Z)", re.I | re.M | re.S
)
ASROCK_INTRO = re.compile(r"Thank you for purchasing\s+ASRock\s+(.+?)\s+motherboard", re.I | re.S)


def model_key(value):
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def fetch(row):
    model = row["model"]
    if row["manufacturer"] == "ASRock":
        slug = quote(model.replace("/", ""), safe="")
        urls = [f"https://download.asrock.com/Manual/{slug}.pdf"]
    else:
        slug = quote(model.upper().replace(" ", "-"), safe="-")
        urls = [f"https://storage-asset.msi.com/datasheet/mb/{region}/{slug}.pdf" for region in ("global", "jp")]
    for url in urls:
        try:
            if row["manufacturer"] == "ASRock":
                payload = subprocess.run(
                    ["curl", "-fsSL", "--max-time", "20", "--max-filesize", str(24 * 1024 * 1024), url],
                    check=True, capture_output=True, timeout=22,
                ).stdout
            else:
                request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urlopen(request, timeout=12) as response:
                    payload = response.read(24 * 1024 * 1024 + 1)
            if payload.startswith(b"%PDF-") and len(payload) <= 24 * 1024 * 1024:
                return row, url, payload
        except (OSError, subprocess.SubprocessError):
            continue
    return row, urls[0], b""


def classify(row, url, payload):
    result = {**row, "specUrl": url, "specEvidence": "unverified", "modules": "", "pages": "", "detail": "pdf-unavailable"}
    if not payload:
        return result
    try:
        with pymupdf.open(stream=payload, filetype="pdf") as document:
            pages = [page.get_text().replace("\u00ad\n", "").replace("\u00ad", "") for page in document[:15]]
    except (ValueError, RuntimeError):
        result["detail"] = "pdf-unreadable"
        return result

    key = model_key(row["model"])
    if row["manufacturer"] == "MSI":
        for number, page in enumerate(pages[:2], 1):
            match = re.search(r"^Model Name\s*\n([^\n]+)", page, re.I | re.M)
            if match and model_key(match[1]) == key:
                wireless = MSI_SECTION.search(page)
                if wireless and WIRELESS.search(wireless[1]):
                    return positive(result, wireless[1], number)
                if row["catalogHint"] == "mentioned" or WIRELESS.search(page):
                    result["detail"] = "wireless-details-ambiguous"
                else:
                    result.update(specEvidence="oem-spec-wlan-not-listed", pages=str(number), detail="")
                return result
        result["detail"] = "exact-model-field-missing"
        return result

    introduction = next((m for page in pages[:8] if (m := ASROCK_INTRO.search(page))), None)
    if introduction is None:
        result["detail"] = "manual-introduction-missing"
        return result
    models = {model_key(model) for model in re.split(r"\s+/\s+", introduction[1])}
    if key not in models:
        result["detail"] = "manual-model-mismatch"
        return result
    for number, page in enumerate(pages, 1):
        for wireless in ASROCK_SECTION.finditer(page):
            qualifier, description = wireless.groups()
            if qualifier and model_key(qualifier) != key:
                continue
            if not qualifier and len(models) != 1:
                continue
            if WIRELESS.search(description) and not OPTIONAL.search(description):
                return positive(result, description, number)
    result["detail"] = "no-model-specific-wlan-section"
    return result


def positive(result, description, number):
    modules = {match.upper() for match in MODULE.findall(description)}
    modules.update(re.findall(r"Wireless-AC\s+(3168|7265|8260|8265|9260|9462|9560)\b", description, re.I))
    result.update(
        specEvidence="oem-spec-module" if modules else "oem-spec-wlan-listed",
        modules=";".join(sorted(modules)), pages=str(number), detail="",
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--brand", choices=("ASRock", "MSI"), required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--refresh", action="store_true", help="Recheck previously classified documents.")
    args = parser.parse_args()
    if args.workers < 1 or (args.limit is not None and args.limit < 1):
        parser.error("workers and limit must be positive")
    with args.catalog.open(encoding="utf-8-sig", newline="") as source:
        rows = [
            dict(platform=row["platform"], manufacturer=args.brand, model=row["model"],
                 catalogHint=row.get("wirelessEvidence", row.get("wifiClaim", "")))
            for row in csv.DictReader(source)
        ]
    if not rows:
        parser.error("catalog is empty")
    rows.sort(key=lambda row: (row["catalogHint"] not in ("mentioned", "model-name-hint"), row["platform"], row["model"]))
    if args.limit:
        rows = rows[:args.limit]
    def key(row):
        return tuple(row[field] for field in ("manufacturer", "platform", "model", "catalogHint"))

    cached = {}
    if args.output.is_file():
        with args.output.open(encoding="utf-8-sig", newline="") as source:
            cached = {key(row): row for row in csv.DictReader(source) if row["specEvidence"] != "unverified"}
    pending = [row for row in rows if args.refresh or key(row) not in cached]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for response in pool.map(fetch, pending):
            result = classify(*response)
            result_key = key(result)
            if result["detail"] == "pdf-unavailable" and result_key in cached:
                continue
            cached[result_key] = result
    selected = {key(row) for row in rows}
    results = [cached[key(row)] for row in rows]
    results.extend(row for item, row in cached.items() if item not in selected)
    print(f"Fetched {len(pending)} of {len(rows)} documents.")
    with args.output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    for status in sorted({row["specEvidence"] for row in results}):
        print(status, sum(row["specEvidence"] == status for row in results))


if __name__ == "__main__":
    main()
