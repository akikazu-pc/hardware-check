"""Map Acer marketing series to their sitemap code families and verify the family.

Every Acer support page is listed in ``https://www.acer.com/sitemap_usen.xml`` as
``/us-en/support/product-support/<code>``. The catalogue rows that only carry a marketing series
name (``oem-series-catalog``) cannot be queried directly, so this script:

1. resolves each series to a representative code through the driver-listing endpoint,
2. derives the family prefix (the part before ``-``) and lists the sitemap codes in that family,
3. with ``--query``, queries every code of the family and classifies its driver list per system,
4. closes a series cell only when **every** code in the family returns the same conclusive status.

The sitemap covers the US support catalogue; a series is only closed for that scope, which is the
same scope as the ``/us-en/`` support pages used for the exact-model rows.

Usage:
  python scripts/collect-acer-series-skus.py docs/network-rescue-model-gaps.csv docs/network-rescue-acer-series-skus.csv
  python scripts/collect-acer-series-skus.py docs/network-rescue-model-gaps.csv docs/network-rescue-acer-series-skus.csv \
      --query --proof artifacts/acer-series-proof.csv --apply-oem-evidence
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
import importlib.util
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
SYSTEMS = ("10", "11")
CONFIRMED = {"oem-wlan-listed", "oem-wlan-not-listed", "oem-os-not-listed"}
INVENTORY = ["series", "seedCode", "seedDescription", "prefix", "candidates", "sitemapCodes"]
PROOF = ["series", "sku", "windows", "status", "title", "version", "downloadUrl"]


def collector():
    """Reuse the exact-model Acer collector's query and classification helpers."""
    spec = importlib.util.spec_from_file_location("acer", ROOT / "scripts" / "collect-acer-oem-listings.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    """Ask the driver endpoint for the series name; drop trailing qualifier words until it answers."""
    words = series.split()
    for length in range(len(words), 0, -1):
        payload = bridge_post(" ".join(words[:length]))
        hits = payload.get("hits") or []
        if not hits:
            continue
        source = hits[0].get("_source") or {}
        title, description = source.get("title") or "", source.get("description") or ""
        match = EMBEDDED.search(title) or EMBEDDED.search(description)
        return (match.group(1) if match else ""), description
    return "", ""


def prefix_of(code):
    head = code.split("-", 1)[0]
    return head if len(head) >= 2 else ""


def build_inventory(models):
    sitemap = bridge(SITEMAP)
    codes = sorted({path.rsplit("/", 1)[-1] for path in re.findall(r"<loc>([^<]+)</loc>", sitemap)
                    if "product-support/" in path} - {"result-page"})
    codes = [code for code in codes if CODE.match(code)]
    rows = [row for row in models if row["brand"] == "Acer" and row["type"] == "laptop"
            and row["wlanEvidence"] == "oem-series-catalog"
            and "pending" in (row["windows10X64Evidence"], row["windows11X64Evidence"])]
    inventory = []
    for row in rows:
        seed_code, seed_description = seed(row["model"])
        prefix = prefix_of(seed_code)
        candidates = [code for code in codes if prefix and prefix_of(code) == prefix]
        inventory.append({"series": row["model"], "seedCode": seed_code, "seedDescription": seed_description,
                          "prefix": prefix, "candidates": len(candidates),
                          "sitemapCodes": ";".join(candidates)})
    return inventory


def query_family(acer, series, codes):
    """Query each code of the family and return the per-system statuses plus the proof rows."""
    results, proof = {}, []
    for code in codes:
        warm, response = acer.bridge_query(code)
        if response.get("status") != 200 or "payload" not in response:
            results[code] = {"10": "api-error", "11": "api-error"}
            continue
        evidence = acer.classify(response["payload"], code)
        results[code] = {}
        for system in SYSTEMS:
            item = evidence.get(system) or {}
            results[code][system] = item.get("status", "unknown")
            proof.append({"series": series, "sku": code, "windows": system,
                          "status": item.get("status", "unknown"), "title": item.get("title", ""),
                          "version": item.get("version", ""), "downloadUrl": item.get("downloadUrl", "")})
    return results, proof


def aggregate(results):
    """A series cell closes only when every code of its family reports the same conclusive status."""
    outcome = {}
    for system in SYSTEMS:
        statuses = {values.get(system, "unknown") for values in results.values()}
        outcome[system] = statuses.pop() if len(statuses) == 1 and statuses <= CONFIRMED else ""
    return outcome


def apply_cells(models, closable):
    raw = Path(models).read_bytes()
    with Path(models).open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        rows, fields = list(reader), reader.fieldnames
    updates = Counter()
    by_series = {item["series"]: item["outcome"] for item in closable}
    for row in rows:
        if row["brand"] != "Acer" or row["type"] != "laptop" or row["model"] not in by_series:
            continue
        for system, status in by_series[row["model"]].items():
            field = f"windows{system}X64Evidence"
            if status and row[field] == "pending":
                row[field] = status
                updates[f"{system}:{status}"] += 1
    if updates:
        temporary = Path(models).with_suffix(Path(models).suffix + ".tmp")
        with temporary.open("w", encoding="utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8",
                            newline="") as output:
            writer = csv.DictWriter(output, fields, quoting=csv.QUOTE_ALL,
                                    lineterminator="\r\n" if b"\r\n" in raw else "\n")
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(models)
    return dict(updates)


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--refresh", action="store_true", help="Rebuild the series inventory")
    parser.add_argument("--query", action="store_true", help="Query every code of each series family")
    parser.add_argument("--proof", type=Path, help="Per-SKU proof table written by --query")
    parser.add_argument("--apply-oem-evidence", action="store_true")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()

    if args.refresh or not args.output.is_file():
        inventory = build_inventory(read_csv(args.models))
        with args.output.open("w", encoding="utf-8", newline="") as destination:
            writer = csv.DictWriter(destination, INVENTORY)
            writer.writeheader()
            writer.writerows(inventory)
        print(f"inventory: series={len(inventory)} candidates={sum(item['candidates'] for item in inventory)}")
        if not args.query:
            return

    inventory = read_csv(args.output)
    families = [(item["series"], [code for code in item["sitemapCodes"].split(";") if code])
                for item in inventory if item["candidates"] and int(item["candidates"]) > 1]
    acer = collector()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda pair: query_family(acer, pair[0], pair[1]), families))
    proof, closable = [], []
    for (series, codes), (per_code, rows) in zip(families, results):
        proof.extend(rows)
        outcome = aggregate(per_code)
        if any(outcome.values()):
            closable.append({"series": series, "codes": codes, "outcome": outcome})
    if args.proof:
        with args.proof.open("w", encoding="utf-8", newline="") as destination:
            writer = csv.DictWriter(destination, PROOF)
            writer.writeheader()
            writer.writerows(proof)
    print(f"families={len(families)} skus={len(proof) // 2} seriesCells={len(closable)} "
          f"cells={sum(1 for item in closable for status in item['outcome'].values() if status)}")
    if args.apply_oem_evidence:
        print("applied:", apply_cells(args.models, closable))


if __name__ == "__main__":
    main()
