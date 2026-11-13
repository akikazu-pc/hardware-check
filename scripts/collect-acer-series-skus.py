"""Build the exact-SKU inventory for the Acer series-only rows from Acer's public sitemap.

Every Acer support page is listed in ``https://www.acer.com/sitemap_usen.xml`` as
``/us-en/support/product-support/<code>``. The catalogue rows that only carry a marketing series
name (``oem-series-catalog``) cannot be queried directly, so this script resolves each series to a
representative code through the same driver-listing endpoint, derives the code family prefix, and
lists the sitemap codes that share it. The family list is evidence for the next step (querying each
SKU); it does not close a series cell by itself, because the sitemap cannot prove that a marketing
series maps one-to-one onto a code family.

Usage: python scripts/collect-acer-series-skus.py docs/network-rescue-model-gaps.csv \
    docs/network-rescue-acer-series-skus.csv
"""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent
BRIDGE = ROOT / "scripts" / "oem-http.mjs"
SITEMAP = "https://www.acer.com/sitemap_usen.xml"
API = "https://www.acer.com/us-en/DynamicContent/GetDriversAndManuals"
WARM = "https://www.acer.com/us-en/support/product-support/A515-58GM"
CODE = re.compile(r"^[A-Z][A-Z0-9]*-[A-Z0-9]+$")
EMBEDDED = re.compile(r"\b([A-Z]{1,6}[0-9]{1,4}[A-Z0-9]*-[A-Z0-9]{1,8})\b")
FIELD = ["series", "seedCode", "seedDescription", "prefix", "candidates", "sitemapCodes"]


def bridge(url):
    completed = subprocess.run(["node", str(BRIDGE), url], cwd=ROOT, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=180)
    result = json.loads(completed.stdout)[0]
    if result.get("status") != 200:
        return ""
    return Path(result["file"]).read_text(encoding="utf-8", errors="replace")


def bridge_post(code):
    body = json.dumps({"ModelName": code, "Local": "en-us"})
    completed = subprocess.run(["node", str(BRIDGE), "--post-with-session", WARM, API, body], cwd=ROOT,
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    result = json.loads(completed.stdout)[0]
    if result.get("status") != 200:
        return {}
    return json.loads(Path(result["file"]).read_text(encoding="utf-8"))


def seed(series):
    """Ask the driver endpoint for the series name; it answers with its nearest real code.

    Long marketing names ("Nitro 16 Intel") often miss, so trailing qualifier words are dropped
    one at a time until the endpoint answers.
    """
    words = series.split()
    for length in range(len(words), 0, -1):
        payload = bridge_post(" ".join(words[:length]))
        hits = payload.get("hits") or []
        if not hits:
            continue
        source = hits[0].get("_source") or {}
        title, description = source.get("title") or "", source.get("description") or ""
        match = EMBEDDED.search(title) or EMBEDDED.search(description)
        if match:
            return match.group(1), description
        return "", ""
    return "", ""


def prefix_of(code):
    head = code.split("-", 1)[0]
    return head if len(head) >= 2 else ""


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    sitemap = bridge(SITEMAP)
    codes = sorted({path.rsplit("/", 1)[-1] for path in re.findall(r"<loc>([^<]+)</loc>", sitemap)
                    if "product-support/" in path} - {"result-page"})
    codes = [code for code in codes if CODE.match(code)]
    families = Counter(prefix_of(code) for code in codes)
    with args.models.open(encoding="utf-8-sig", newline="") as source:
        rows = [row for row in csv.DictReader(source) if row["brand"] == "Acer" and row["type"] == "laptop"
                and row["wlanEvidence"] == "oem-series-catalog"
                and "pending" in (row["windows10X64Evidence"], row["windows11X64Evidence"])]
    proof = []
    for row in rows:
        seed_code, seed_description = seed(row["model"])
        prefix = prefix_of(seed_code)
        candidates = [code for code in codes if prefix and prefix_of(code) == prefix]
        proof.append({"series": row["model"], "seedCode": seed_code, "seedDescription": seed_description,
                      "prefix": prefix, "candidates": len(candidates), "sitemapCodes": ";".join(candidates)})
    with args.output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, FIELD)
        writer.writeheader()
        writer.writerows(proof)
    print(f"series={len(proof)} sitemapCodes={len(codes)} families={len(families)}")
    print("mapped:", sum(1 for item in proof if item["seedCode"]),
          "families with >1 code:", sum(1 for item in proof if item["candidates"] > 1))


if __name__ == "__main__":
    main()
