"""Read Lenovo's per-model driver-page OS list (the ``OSs`` array) for pending laptops.

The Lenovo product downloads page embeds the model's supported system list as
``"OSs":[{"ID":...,"Value":"Windows 11 (64-bit)"}]``. That list is Lenovo's own selector for the
driver downloads, so a model whose list has no Windows 10 offers no Windows 10 driver set.
The page is fetched through ``scripts/oem-http.mjs`` because support.lenovo.com answers 403 to
the Python and curl clients from this host.

Usage: python scripts/collect-lenovo-os-list.py docs/network-rescue-model-gaps.csv \
    artifacts/lenovo-os-list-proof.csv [--apply]
"""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parent.parent
BRIDGE = ROOT / "scripts" / "oem-http.mjs"
PRODUCT = "https://support.lenovo.com/us/en/products/laptops-and-netbooks/{series}/{slug}/downloads"
FIELDS = ["model", "productUrl", "description", "systems", "windows10", "windows11", "status"]


def fetch(urls):
    """Return {url: body} using the Node transport bridge in a single process."""
    completed = subprocess.run(["node", str(BRIDGE), *urls], capture_output=True, text=True, check=True)
    bodies = {}
    for item in json.loads(completed.stdout):
        if item["status"] != 200 or not item["file"]:
            continue
        bodies[item["url"]] = Path(item["file"]).read_text(encoding="utf-8", errors="replace")
    return bodies


def product_url(model):
    slug = re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")
    return PRODUCT.format(series="legion-series", slug=slug)


def inspect(model, body):
    """Only the block whose ``UrlCS`` names this exact model counts; sibling blocks are common."""
    result = {field: "" for field in FIELDS}
    result.update(model=model, productUrl=product_url(model), status="os-list-unreadable")
    slug = re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-").upper()
    for match in re.finditer(r'"UrlCS":"([^"]+)"', body):
        if not match.group(1).endswith("/" + slug):
            continue
        block = body[match.start():match.start() + 4000]
        result["description"] = match.group(1).rsplit("/", 1)[-1]
        systems = sorted({value for value in re.findall(r'"Value":"(Windows [^"]+)"', block)
                          if "Windows 1" in value})
        result["systems"] = ";".join(systems)
        result["windows10"] = "yes" if any("Windows 10" in system for system in systems) else "no"
        result["windows11"] = "yes" if any("Windows 11" in system for system in systems) else "no"
        result["status"] = "os-list" if systems else "os-list-empty"
        return result
    result["status"] = "model-block-not-found"
    return result


def apply_os(path, proof):
    closable = {item["model"] for item in proof
                if item["status"] == "os-list" and item["windows10"] == "no" and item["windows11"] == "yes"}
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
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    pending = [row for row in read(args.models) if row["type"] == "laptop" and row["brand"] == "Lenovo"
               and "pending" in (row["windows10X64Evidence"], row["windows11X64Evidence"])]
    urls = sorted({product_url(row["model"]) for row in pending})
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        chunks = list(pool.map(lambda chunk: fetch(chunk), [urls[i::args.workers] for i in range(args.workers)]))
    bodies = {}
    for chunk in chunks:
        bodies.update(chunk)
    proof = [inspect(row["model"], bodies[product_url(row["model"])])
             if product_url(row["model"]) in bodies
             else dict({field: "" for field in FIELDS}, model=row["model"], productUrl=product_url(row["model"]),
                       status="product-page-unavailable")
             for row in pending]
    with args.output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, FIELDS)
        writer.writeheader()
        writer.writerows(proof)
    print(f"Checked {len(proof)} product pages:", {item["status"] for item in proof})
    if args.apply:
        print("OS updates:", apply_os(args.models, proof))


if __name__ == "__main__":
    main()
