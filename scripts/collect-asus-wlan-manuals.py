"""Find model-specific WLAN evidence in English ASUS motherboard manuals."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import re
from urllib.parse import quote
from urllib.request import Request, urlopen

import pymupdf

PDF_PATH = re.compile(r'(/pub/ASUS/mb/[^"<>?\\]+/[EQ]\d+_[^"<>?\\]+\.pdf)', re.I)
MODULE = re.compile(
    r"\b(?:MT79(?:02|20|21|22|25)[A-Z0-9]*|RTL(?:88|89)\d{2}[A-Z]{1,4}|"
    r"BE(?:200|201|202|211|213)(?:NGW)?|AX(?:101|200|201|210|211|411)(?:NGW)?|"
    r"(?:QCNCM|NCM)8(?:25|65)|WCN785[A-Z0-9]*|BE1750[AX]?)\b", re.I
)
WIRELESS = re.compile(r"Wi[\s-]*Fi|WLAN|wireless|802\.11", re.I)


def fetch(url):
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        return response.read()


def inspect(row):
    support = row["officialUrl"].rstrip("/") + "/helpdesk_manual/"
    result = {**row, "moduleEvidence": "manual-not-found", "modules": "", "manualUrl": "", "pages": ""}
    try:
        html = fetch(support).decode("utf-8", errors="replace")
        paths = list(dict.fromkeys(PDF_PATH.findall(html)))
        manuals = [path for path in paths if path.rsplit("/", 1)[-1].upper().startswith("E")]
        quick = [path for path in paths if path.rsplit("/", 1)[-1].upper().startswith("Q")]
        for path in (manuals[:1] + quick[:1]):
            url = "https://dlcdnets.asus.com" + quote(path, safe="/%")
            with pymupdf.open(stream=fetch(url), filetype="pdf") as pdf:
                found = {}
                for number, page in enumerate(pdf, 1):
                    page_text = page.get_text()
                    if not WIRELESS.search(page_text):
                        continue
                    for match in MODULE.finditer(page_text):
                        found.setdefault(match.group().upper(), set()).add(number)
                result.update(manualUrl=url, moduleEvidence="manual-no-explicit-module")
                if found:
                    result.update(
                        moduleEvidence="manual-module-candidate",
                        modules=";".join(sorted(found)),
                        pages=";".join(str(n) for n in sorted(set().union(*found.values()))),
                    )
                    break
    except (OSError, RuntimeError, ValueError):
        result["moduleEvidence"] = "manual-read-failed"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog")
    parser.add_argument("output")
    args = parser.parse_args()
    with open(args.catalog, newline="", encoding="utf-8-sig") as source:
        records = [
            row for row in csv.DictReader(source)
            if row["platform"] in {"AM5", "LGA1851"} and row["wifiClaim"] == "mentioned"
        ]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(inspect, records))
    with open(args.output, "w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)


if __name__ == "__main__":
    main()
