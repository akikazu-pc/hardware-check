"""Collect comparable WLAN evidence from the ASUS catalog's exact model specs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from html import unescape
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


ROW = re.compile(r'<div class="rowTableTitle">(.*?)</div>', re.S)
TAG = re.compile(r"<[^>]*>")
WLAN = re.compile(r"\b(?:wi[ -]?fi|wlan|wireless|802\.11|antenna)\b", re.I)
MODULE = re.compile(
    r"\b(?:MT79(?:02|20|21|22|25|27|28)[A-Z0-9]*|RTL(?:88|89)\d{2}[A-Z]{1,4}|"
    r"BE(?:200|201|202|211|213)(?:NGW)?|AX(?:101|200|201|210|211|411)(?:NGW)?|"
    r"(?:QCNCM|NCM)8(?:25|65)|WCN785[A-Z0-9]*|BE1750[AX]?)\b", re.I
)
OPTIONAL = re.compile(r"(?:wi[ -]?fi|wireless)\s+module\s+is sold separately|\bslot only\b", re.I)
SECTION_ALIASES = {"back i/o ports": "back panel i/o ports", "internal i/o ports": "internal i/o connectors"}
REQUIRED_SECTIONS = {"model", "cpu", "chipset", "back panel i/o ports", "internal i/o connectors"}


def clean(value):
    return " ".join(unescape(TAG.sub(" ", value)).split())


def model_key(value):
    return re.sub(r"[^A-Z0-9+]", "", value.upper())


def inspect(row):
    url = row["officialUrl"].rstrip("/") + "/techspec/"
    result = {**row, "specUrl": url, "specEvidence": "unverified", "modules": "", "officialOs": "", "detail": ""}
    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=12) as response:
            if urlsplit(response.url).path.rstrip("/").casefold() != urlsplit(url).path.rstrip("/").casefold():
                result["detail"] = "unexpected-redirect"
                return result
            html = response.read().decode("utf-8", errors="replace").split("<script type=\"application/json\"", 1)[0]
    except OSError as error:
        result["detail"] = f"http-{error.code}" if hasattr(error, "code") else type(error).__name__
        return result

    headings = list(ROW.finditer(html))
    sections = {}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(html)
        label = clean(heading[1]).casefold()
        key = SECTION_ALIASES.get(label, label)
        if key in sections:
            result["detail"] = "duplicate-section"
            return result
        sections[key] = clean(html[heading.end():end])
    if model_key(sections.get("model", "")) != model_key(row["model"]):
        result["detail"] = "model-mismatch"
        return result
    if not REQUIRED_SECTIONS.issubset(sections):
        result["detail"] = "incomplete-spec"
        return result

    wireless = " ".join(value for label, value in sections.items() if WLAN.search(label))
    ports = sections["back panel i/o ports"]
    internal = sections["internal i/o connectors"]
    modules = sorted({match.upper() for match in MODULE.findall(wireless)})
    result["modules"] = ";".join(modules)
    os_text = sections.get("operating system", "")
    result["officialOs"] = ";".join(os for os in ("Windows 10", "Windows 11") if re.search(rf"\b{os}\b", os_text, re.I))
    if OPTIONAL.search(wireless) and not modules and not WLAN.search(ports):
        result["specEvidence"] = "oem-spec-slot-only"
    elif WLAN.search(wireless) and (modules or WLAN.search(ports) or re.search(r"\b802\.11\w*\b", wireless)):
        result["specEvidence"] = "oem-spec-module" if modules else "oem-spec-wlan-listed"
    elif not (wireless or WLAN.search(ports) or WLAN.search(internal) or row["wifiClaim"] == "mentioned"):
        result["specEvidence"] = "oem-spec-wlan-not-listed"
    else:
        result["detail"] = "wireless-details-ambiguous"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--refresh", action="store_true", help="Recheck existing successful results.")
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    with args.catalog.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    if not rows:
        parser.error("catalog is empty")
    def key(row):
        return tuple(row[column] for column in ("platform", "manufacturer", "model", "wifiClaim", "officialUrl"))

    cached = {}
    if args.output.is_file() and not args.refresh:
        with args.output.open(encoding="utf-8-sig", newline="") as source:
            cached = {key(row): row for row in csv.DictReader(source) if row["specEvidence"] != "unverified"}

    pending = [row for row in rows if key(row) not in cached]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        cached.update((key(row), row) for row in pool.map(inspect, pending))
    results = [cached[key(row)] for row in rows]
    print(f"Fetched {len(pending)} of {len(rows)} specifications.")
    with args.output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    for status in sorted({row["specEvidence"] for row in results}):
        print(status, sum(row["specEvidence"] == status for row in results))


if __name__ == "__main__":
    main()
