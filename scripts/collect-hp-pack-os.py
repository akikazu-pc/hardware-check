"""Close HP cells for a system that HP publishes no driver pack for.

Two HP documents are combined for the exact model:

* the HP Client Driver Pack Catalog (``HPClientDriverPackCatalog.cab``) names the model and its
  driver packs per Windows version; a model that only appears under Windows 11 entries has no
  Windows 10 pack, and the other way round for older models,
* each pack's ``.cva`` file (``ftp.hp.com``) lists the exact models in ``[System Information]`` and
  the supported systems in ``[Operating Systems]`` (``W10_*`` or ``W11_*`` keys).

A cell closes as ``oem-os-not-listed`` only when the catalog has entries for the exact model, none
of them is for the target system, and every linked pack declares the other system only in its own
CVA. Models without any catalog entry stay pending.

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
FIELDS = ["model", "windows", "packs", "catalogOs", "cvaOs"]
SYSTEMS = {"10": ("Windows 10", ("W11_",)), "11": ("Windows 11", ("W10_", "WT64_"))}


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
        if row["brand"] != "HP" or row["type"] != "laptop":
            continue
        entries = by_system.get(norm(row["model"])) or by_system.get(norm("HP " + row["model"])) or []
        if not entries:
            continue
        catalog_os = sorted({entry.findtext("OSName") or "" for entry in entries})
        ids = sorted({entry.findtext("SoftPaqId") for entry in entries})
        for system, (catalog_prefix, other_keys) in SYSTEMS.items():
            if row[f"windows{system}X64Evidence"] != "pending":
                continue
            if any(name.startswith(catalog_prefix) for name in catalog_os):
                continue
            candidates.append((row["model"], system, ids, catalog_os, other_keys))
    cva_urls = {softpaq: packs[softpaq].findtext("CvaFileUrl") for _, _, ids, _, _ in candidates
                for softpaq in ids if softpaq in packs}
    bodies = fetch(sorted({url for url in cva_urls.values() if url}))
    cva_os = {}
    for softpaq, url in cva_urls.items():
        cva_os[softpaq] = re.findall(r"^((?:W\d\d|WT64)_[A-Z0-9]+)=", bodies.get(url, ""), re.M)
    # Some packs carry no [Operating Systems] section; their release notes state the systems and
    # the supported models explicitly, which serves as the same declaration.
    notes = {}
    for softpaq in sorted({softpaq for _, _, ids, _, _ in candidates for softpaq in ids}):
        if cva_os.get(softpaq) or softpaq not in packs:
            continue
        exe = packs[softpaq].findtext("Url") or ""
        if not exe.endswith(".exe"):
            continue
        notes[softpaq] = exe[:-4] + ".html"
    bodies.update(fetch(sorted(notes.values())))
    release = {}
    for softpaq, url in notes.items():
        text = re.sub(r"<[^>]+>", " ", bodies.get(url, ""))
        text = re.sub(r"\s+", " ", text)
        systems = re.search(r"OPERATING SYSTEM\(S\):\s*(.*?)\s*LANGUAGE", text)
        models = re.search(r"HARDWARE PRODUCT MODEL\(S\):\s*(.*?)(?:OPERATING SYSTEM|LANGUAGE)", text)
        release[softpaq] = {"systems": systems.group(1).strip() if systems else "",
                            "models": norm(models.group(1)) if models else ""}

    proof, closable = [], []
    for model, system, ids, catalog_os, other_keys in candidates:
        target = "Windows 11" if system == "10" else "Windows 10"
        other = "Windows 10" if target == "Windows 11" else "Windows 11"
        proven = True
        for softpaq in ids:
            keys = cva_os.get(softpaq, [])
            if keys:
                # CVA declaration: every key must name the other system (WT64_ = Windows 10 x64).
                proven = proven and all(key.startswith(other_keys) for key in keys)
            else:
                note = release.get(softpaq, {})
                proven = proven and bool(note) and target in note["systems"] \
                    and other not in note["systems"] and norm(model) in note["models"]
            if not proven:
                break
        if not proven:
            continue
        closable.append((model, system))
        declared = sorted({key for softpaq in ids for key in cva_os.get(softpaq, [])}
                          | {release[softpaq]["systems"] for softpaq in ids if softpaq in release})
        proof.append({"model": model, "windows": system, "packs": ";".join(ids),
                      "catalogOs": ";".join(catalog_os), "cvaOs": "|".join(declared)})
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
        wanted = set(closable)
        for row in rows:
            for system in SYSTEMS:
                field = f"windows{system}X64Evidence"
                if (row["model"], system) in wanted and row[field] == "pending":
                    row[field] = "oem-os-not-listed"
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
