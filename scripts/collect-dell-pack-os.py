"""Close the Dell system-ID rows from Dell's own driver pack catalog and pack manifests.

Each ``laptop-os-record`` row is one model/SystemID/OS combination. Two Dell documents decide the
missing system:

* the Dell Driver Pack Catalog (``downloads.dell.com/catalog/DriverPackCatalog.cab``, the inner
  ``driverpackcatalog.cab`` is actually a ``DriverPackManifest`` XML) lists every pack per
  SystemID and its ``SupportedOperatingSystems``; a SystemID with Windows 11 packs only has no
  Windows 10 pack,
* the pack manifest XML (``downloads.dell.com/<folder>/<pack>.xml``) declares
  ``<OS Name="Windows10" Arch="x64">`` per ``<System SystemID=...>`` and lists its driver
  components; a ``DeviceDescription`` matching Wi-Fi/WLAN but not WWAN/GNSS/Bluetooth proves the
  pack carries the wireless driver.

A Windows 10 cell closes as ``oem-os-not-listed`` when the catalog has no Windows 10 pack for the
SystemID, or as ``oem-wlan-listed`` when the Windows 10 pack lists the wireless driver for that
SystemID.

Usage: python scripts/collect-dell-pack-os.py docs/network-rescue-model-gaps.csv \
    artifacts/_dellxml/driverpackcatalog.cab docs/network-rescue-dell-os-record-proof.csv [--apply]
"""
import argparse
import collections
import csv
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent.parent
BRIDGE = ROOT / "scripts" / "oem-http.mjs"
NS = "{openmanage/cm/dm}"
WLAN = re.compile(r"wi-?fi|wireless lan|\bwlan\b", re.I)
EXCLUDE = re.compile(r"wwan|gnss|gps|bluetooth", re.I)
FIELDS = ["model", "systemId", "windows", "status", "evidence", "note"]


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
    parser.add_argument("catalog", type=Path, help="Extracted DriverPackManifest XML")
    parser.add_argument("output", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    manifest = ET.parse(args.catalog).getroot()
    packs = collections.defaultdict(set)
    for entry in manifest:
        systems = entry.find(NS + "SupportedOperatingSystems")
        codes = {item.attrib.get("osCode") for item in (systems if systems is not None else [])
                 if item.attrib.get("osCode")}
        supported = entry.find(NS + "SupportedSystems")
        for brand in (supported if supported is not None else []):
            for model in brand:
                system_id = (model.attrib.get("systemID") or "").upper()
                if system_id:
                    packs[system_id] |= codes

    with args.models.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    pending = [row for row in rows if row["type"] == "laptop-os-record"
               and row["windows10X64Evidence"] == "pending"]
    # The Windows 10 pack XML is linked from the rows that already carry a Win10 source.
    win10_urls = sorted({row["source"] for row in rows
                         if row["type"] == "laptop-os-record" and "Win10" in row["source"]})
    bodies = fetch(win10_urls)
    systems = {}
    for url, text in bodies.items():
        for block in re.split(r"(?=<System SystemID=)", text)[1:]:
            match = re.match(r'<System SystemID="([^"]+)"[^>]*Model="([^"]+)"', block)
            if not match:
                continue
            system_id = match.group(1).upper()
            os_match = re.search(r'<OS Name="([^"]+)" Arch="([^"]+)"', block)
            descriptions = re.findall(r'DeviceDescription="([^"]+)"', block)
            wlan = [value for value in descriptions if WLAN.search(value) and not EXCLUDE.search(value)]
            systems[system_id] = {"os": os_match.groups() if os_match else ("", ""),
                                  "wlan": wlan[:1], "url": url}

    proof, closable = [], []
    for row in pending:
        system_id = (row["platform"] or "").upper()
        if "Windows10" in packs.get(system_id, set()):
            record = systems.get(system_id)
            if record and record["os"] == ("Windows10", "x64") and record["wlan"]:
                closable.append((row, "oem-wlan-listed"))
                proof.append({"model": row["model"], "systemId": system_id, "windows": "10",
                              "status": "oem-wlan-listed", "evidence": record["url"],
                              "note": record["wlan"][0]})
            continue
        closable.append((row, "oem-os-not-listed"))
        proof.append({"model": row["model"], "systemId": system_id, "windows": "10",
                      "status": "oem-os-not-listed", "evidence": row["source"],
                      "note": "catalog has Windows 11 packs only"})
    with args.output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, FIELDS)
        writer.writeheader()
        writer.writerows(proof)
    print(f"pending={len(pending)} closable={len(closable)}")
    if args.apply and closable:
        raw = args.models.read_bytes()
        with args.models.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            rows, fields = list(reader), reader.fieldnames
        updates = 0
        wanted = {(row["model"], (row["platform"] or "").upper()) for row, _ in closable}
        status = {(row["model"], (row["platform"] or "").upper()): value for row, value in closable}
        for row in rows:
            key = (row["model"], (row["platform"] or "").upper())
            if key in wanted and row["type"] == "laptop-os-record" \
                    and row["windows10X64Evidence"] == "pending":
                row["windows10X64Evidence"] = status[key]
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
