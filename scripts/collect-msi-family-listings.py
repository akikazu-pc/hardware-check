"""Resolve MSI laptop family rows to their regional SKUs and verify the whole family.

MSI lists a laptop series on one family page whose OS selector is often empty; the regional
SKUs live behind the family banner. The same-origin API exposes both steps:

* ``/api/v1/search?group=1&keyword=<name>`` -> family page URL and ``sub_product`` titles,
* ``/api/v1/product/support/banner?product=<family slug>`` -> ``sub_product_list`` slug mapping,
* ``/api/v1/product/support/os?product=<sku slug>&type=driver`` -> the SKU's OS selector,
* ``/api/v1/product/support/panel?product=<sku slug>&type=driver&os=<label>`` -> its driver table.

A family cell closes only when **every** regional SKU agrees: the system is absent from every OS
selector (``oem-os-not-listed``) or every table lists a Wireless LAN driver for it
(``oem-wlan-listed``). One unresolved or mixed SKU keeps the row pending.

www.msi.com answers 403 to curl and Python from this host, so all requests go through
``scripts/oem-http.mjs``.

Usage: python scripts/collect-msi-family-listings.py docs/network-rescue-model-gaps.csv \
    artifacts/msi-family-proof.csv [--apply-oem-evidence]
"""
import argparse
import csv
import json
from pathlib import Path
import re
import subprocess
import urllib.parse

ROOT = Path(__file__).resolve().parent.parent
BRIDGE = ROOT / "scripts" / "oem-http.mjs"
SEARCH = "https://www.msi.com/api/v1/search?page=1&group=1&keyword={}"
BANNER = "https://www.msi.com/api/v1/product/support/banner?product={}"
OS = "https://www.msi.com/api/v1/product/support/os?product={}&type=driver"
PANEL = "https://www.msi.com/api/v1/product/support/panel?product={}&type=driver&os={}"
SYSTEMS = {"10": "Win10 64", "11": "Win11 64"}
WLAN = re.compile(r"wireless|wlan|wi-?fi", re.I)
FIELDS = ["family", "sku", "osList", "wlan11", "status"]


def fetch(urls):
    completed = subprocess.run(["node", str(BRIDGE), *urls], cwd=ROOT, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=300)
    bodies = {}
    for item in json.loads(completed.stdout):
        if item["status"] == 200 and item["file"]:
            bodies[item["url"]] = Path(item["file"]).read_text(encoding="utf-8", errors="replace")
    return bodies


def family_slug(model, bodies, keyword=None):
    # "+" in a query string makes the endpoint answer HTTP 500, so callers retry without it.
    keyword = keyword if keyword is not None else model
    url = SEARCH.format(urllib.parse.quote(keyword))
    try:
        data = json.loads(bodies.get(url, "{}"))
    except json.JSONDecodeError:
        return ""
    for hit in (data.get("result") or {}).get("list") or data.get("list") or []:
        # The search title carries a "</br>Copilot+ PC" tail; a series hit adds its first SKU.
        title = re.sub(r"<[^>]+>.*$", "", hit.get("title") or "").strip()
        if title.lower() == model.strip().lower() or title.lower().startswith(model.strip().lower() + " "):
            return (hit.get("url") or "").rstrip("/").split("/")[-1]
    return ""


def sub_products(slug, bodies):
    url = BANNER.format(urllib.parse.quote(slug))
    try:
        data = json.loads(bodies.get(url, "{}"))
    except json.JSONDecodeError:
        return []
    return list((data.get("result") or {}).get("sub_product_list") or {})


def wlan_titles(body):
    try:
        downloads = ((json.loads(body).get("result") or {}).get("downloads") or {})
    except json.JSONDecodeError:
        return None
    titles = []
    for entries in downloads.values():
        for entry in entries if isinstance(entries, list) else []:
            title = entry.get("download_title", "") if isinstance(entry, dict) else ""
            if WLAN.search(title) and not re.search("bluetooth", title, re.I):
                titles.append(title)
    return titles


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--apply-oem-evidence", action="store_true")
    args = parser.parse_args()
    with args.models.open(encoding="utf-8-sig", newline="") as source:
        rows = [row for row in csv.DictReader(source) if row["brand"] == "MSI" and row["type"] == "laptop"
                and "pending" in (row["windows10X64Evidence"], row["windows11X64Evidence"])]

    bodies = fetch([SEARCH.format(urllib.parse.quote(row["model"])) for row in rows])
    families = {row["model"]: family_slug(row["model"], bodies) for row in rows}
    retry = [row["model"] for row in rows if not families.get(row["model"]) and "+" in row["model"]]
    if retry:
        bodies.update(fetch([SEARCH.format(urllib.parse.quote(model.replace("+", "").strip()))
                             for model in retry]))
        for model in retry:
            families[model] = family_slug(model, bodies, model.replace("+", "").strip())
    bodies.update(fetch([BANNER.format(urllib.parse.quote(slug)) for slug in families.values() if slug]))
    families = {model: slug for model, slug in families.items() if slug}
    subs = {model: [slug for slug in sub_products(families[model], bodies)] for model in families}
    subs = {model: slugs for model, slugs in subs.items() if slugs}
    bodies.update(fetch([OS.format(urllib.parse.quote(slug)) for slugs in subs.values() for slug in slugs]))
    bodies.update(fetch([PANEL.format(urllib.parse.quote(slug), urllib.parse.quote(SYSTEMS["11"]))
                         for slugs in subs.values() for slug in slugs]))

    proof, closable = [], {}
    for model, slugs in subs.items():
        statuses, win10 = {}, True
        for slug in slugs:
            try:
                os_list = json.loads(bodies.get(OS.format(urllib.parse.quote(slug)), "{}")).get("result") or []
            except json.JSONDecodeError:
                os_list = []
            win10 = win10 and SYSTEMS["10"] not in os_list
            titles = wlan_titles(bodies.get(PANEL.format(urllib.parse.quote(slug),
                                                        urllib.parse.quote(SYSTEMS["11"])), "")) or []
            statuses[slug] = "oem-wlan-listed" if titles else "no-wlan-title"
            proof.append({"family": model, "sku": slug, "osList": ";".join(os_list),
                          "wlan11": ";".join(titles[:2]), "status": statuses[slug]})
        outcome = {}
        if win10:
            outcome["10"] = "oem-os-not-listed"
        if all(value == "oem-wlan-listed" for value in statuses.values()):
            outcome["11"] = "oem-wlan-listed"
        if outcome:
            closable[model] = outcome
    with args.output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, FIELDS)
        writer.writeheader()
        writer.writerows(proof)
    print(f"families={len(subs)} skus={len(proof)} closable={len(closable)} "
          f"cells={sum(len(value) for value in closable.values())}")
    if args.apply_oem_evidence and closable:
        raw = args.models.read_bytes()
        with args.models.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            rows, fields = list(reader), reader.fieldnames
        updates = 0
        for row in rows:
            for system, status in closable.get(row["model"], {}).items():
                field = f"windows{system}X64Evidence"
                if row[field] == "pending":
                    row[field] = status
                    updates += 1
        temporary = args.models.with_suffix(args.models.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8",
                            newline="") as output:
            writer = csv.DictWriter(output, fields, quoting=csv.QUOTE_ALL,
                                    lineterminator="\r\n" if b"\r\n" in raw else "\n")
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(args.models)
        print("applied:", updates)


if __name__ == "__main__":
    main()
