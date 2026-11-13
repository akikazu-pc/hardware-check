"""Close the HP Windows 10 cells that HP publishes no Windows 10 driver pack for.

Two HP documents are combined for the exact model:

* the HP Client Driver Pack Catalog (``HPClientDriverPackCatalog.cab``) names the model and its
  driver packs per Windows version; the pending models only appear under Windows 11 entries,
* each pack's ``.cva`` file (``ftp.hp.com``) lists the exact models in ``[System Information]`` and
  the supported systems in ``[Operating Systems]``; for these packs that section holds only
  ``W11_*`` keys.

A Windows 10 cell closes as ``oem-os-not-listed`` only when the catalog has entries for the exact
model, none of them is a Windows 10 entry, and every linked pack declares Windows 11 only in its
own CVA. Older models without any catalog entry stay pending.

Usage: python scripts/collect-hp-pack-os.py docs/network-rescue-model-gaps.csv \
    artifacts/network-rescue-hp-cva/x/hpclientdriverpackcatalog.cab \
    docs/network-rescue-hp-pack-os-proof.csv [--apply]
"""
import argparse
import csv
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent.parent
BRIDGE = ROOT / "scripts" / "oem-http.mjs"
FIELDS = ["model", "packs", "catalogOs", "cvaOs"]
SYSTEM = "Windows 10"


def norm(value):
    return re.sub(r"[^A-Z0-9]+", "", (value or "").upper())


def fetch(urls):
    completed = subprocess.run(["node", str(BRIDGE), *urls], cwd=ROOT, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=300)
    bodies = {}
    for item in json.loads(completed.stdout):
        if item["status"] == 200 and item["file"]:
            bodies[item["url"]] = Path(item["file"]).read_text(encoding="utf-8", errors="replace")
    return bodies


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", type=Path)
    parser.add_argument("catalog", type=Path, help="Extracted HPClientDriverPackCatalog XML")
    parser.add_argument("output", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    root = ET.parse(args.catalog).getroot()
    packs = {entry.findtext("Id"): entry for entry in root.iter("SoftPaq")}
    by_system = {}
    for entry in root.iter("ProductOSDriverPack"):
        by_system.setdefault(norm(entry.findtext("SystemName")), []).append(entry)
    with args.models.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))

    candidates = []
    for row in rows:
        if row["brand"] != "HP" or row["type"] != "laptop" or row["windows10X64Evidence"] != "pending":
            continue
        entries = by_system.get(norm(row["model"])) or by_system.get(norm("HP " + row["model"])) or []
        ids = sorted({entry.findtext("SoftPaqId") for entry in entries})
        if not ids:
            continue
        catalog_os = sorted({entry.findtext("OSName") or "" for entry in entries})
        if any(name.startswith(SYSTEM) for name in catalog_os):
            continue
        candidates.append((row["model"], ids, catalog_os))

    cva_urls = {softpaq: packs[softpaq].findtext("CvaFileUrl") for _, ids, _ in candidates
                for softpaq in ids if softpaq in packs}
    bodies = fetch(sorted({url for url in cva_urls.values() if url}))
    cva_os = {}
    for softpaq, url in cva_urls.items():
        text = bodies.get(url, "")
        cva_os[softpaq] = re.findall(r"^(W\d\d_[A-Z0-9]+)=", text, re.M)

    proof, closable = [], []
    for model, ids, catalog_os in candidates:
        systems = {softpaq: cva_os.get(softpaq, []) for softpaq in ids}
        if any(not keys or any(not key.startswith("W11_") for key in keys) for keys in systems.values()):
            continue
        closable.append(model)
        proof.append({"model": model, "packs": ";".join(ids), "catalogOs": ";".join(catalog_os),
                      "cvaOs": ";".join(sorted({key for keys in systems.values() for key in keys}))})
    with args.output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, FIELDS)
        writer.writeheader()
        writer.writerows(proof)
    print(f"candidates={len(candidates)} closable={len(closable)}")
    if args.apply and closable:
        raw = args.models.read_bytes()
        with args.models.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            rows, fields = list(reader), reader.fieldnames
        updates = 0
        names = set(closable)
        for row in rows:
            if row["brand"] == "HP" and row["type"] == "laptop" and row["model"] in names \
                    and row["windows10X64Evidence"] == "pending":
                row["windows10X64Evidence"] = "oem-os-not-listed"
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
