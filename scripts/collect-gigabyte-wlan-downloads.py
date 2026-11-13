"""Collect Gigabyte WLAN availability from the rendered support tables.

Gigabyte's support page loads its driver table through an API that Akamai blocks for our transport
(403 on every regional host). The public reader proxy renders the page instead and returns the
table as markdown rows ``| Description | Version | OS |`` grouped under ``## <category>`` headings,
where the OS column names the systems each driver supports.

For each model and system this script reports:

* ``oem-wlan-listed`` when a WLAN/Wi-Fi row names that system in its OS column,
* ``oem-wlan-not-listed`` when the table has LAN/audio/chipset rows for that system but no WLAN row,
* ``no-wlan-row-returned`` otherwise.

Usage: python scripts/collect-gigabyte-wlan-downloads.py docs/network-rescue-model-gaps.csv \
    docs/network-rescue-gigabyte-spec-proof.csv [--apply]
"""
import argparse
import csv
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parent.parent
BRIDGE = ROOT / "scripts" / "oem-http.mjs"
READER = "https://r.jina.ai/"
WLAN = re.compile(r"wi-?fi|wireless|wlan", re.I)
SUPPORT_ROW = re.compile(r"^\| ([^|]+)\| ([^|]+)\| ([^|]+)\|", re.M)
SYSTEMS = {"10": "Windows 10 64bit", "11": "Windows 11 64bit"}
FIELDS = ["model", "windows", "status", "title", "version", "url"]


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def fetch(urls):
    completed = subprocess.run(["node", str(BRIDGE), *urls], cwd=ROOT, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=600)
    bodies = {}
    for item in json.loads(completed.stdout):
        if item["status"] == 200 and item["file"]:
            bodies[item["url"]] = Path(item["file"]).read_text(encoding="utf-8", errors="replace")
    return bodies


def tables(text):
    """Yield (category, description, version, systems) for every driver row on the page."""
    for section in re.split(r"\n## ", text):
        category = section.split("\n", 1)[0].strip()
        for description, version, systems in SUPPORT_ROW.findall(section):
            description, version, systems = description.strip(), version.strip(), systems.strip()
            if description in {"Description", "---"} or not systems:
                continue
            yield category, description, version, systems


REVISION = re.compile(r"(?:rev\.?|revision)\s*([0-9.]+)", re.I)
ONLY_REVISION = re.compile(r"only for (?:pcb )?rev\.?\s*([0-9.]+)", re.I)


def board_revision(model):
    match = REVISION.search(model)
    return match.group(1) if match else ""


def classify(rows, system, model=""):
    wanted = SYSTEMS[system]
    wlan = [row for row in rows if WLAN.search(row[1]) and wanted in row[3]]
    revision = board_revision(model)
    # Some drivers are published for one PCB revision only; they do not cover the other revisions.
    scoped = [row for row in wlan
              if not (revision and ONLY_REVISION.search(row[1])
                      and ONLY_REVISION.search(row[1]).group(1) != revision)]
    if scoped:
        return "oem-wlan-listed", scoped[0]
    if wlan:
        return "oem-wlan-not-listed", None
    supported = [row for row in rows if wanted in row[3]]
    if not supported:
        return "no-wlan-row-returned", None
    categories = {row[0].lower() for row in supported}
    populated = any("lan" in name or "audio" in name or "chipset" in name for name in categories)
    return ("oem-wlan-not-listed" if populated else "no-wlan-row-returned"), None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--support-map", type=Path, help="CSV with model and supportUrl columns")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    pending = [row for row in read_rows(args.models) if row["brand"] == "GIGABYTE"
               and row["type"] == "motherboard"
               and any(row[f"windows{system}X64Evidence"] == "pending" for system in SYSTEMS)]
    support = {}
    if args.support_map:
        support.update({row["model"]: row["supportUrl"] for row in read_rows(args.support_map)})
    for row in pending:
        if row["model"] in support:
            continue
        # The catalog stores a manual PDF or a spec page; derive the support page address.
        match = re.search(r"gigabyte\.com(?:/[a-z]{2})?/Motherboard/([A-Za-z0-9\-\.]+)/", row["source"])
        slug = match.group(1) if match else ""
        if not slug:
            continue
        support[row["model"]] = f"https://www.gigabyte.com/Motherboard/{slug}/support"
    bodies = fetch([READER + url for url in sorted(set(support.values()))])

    proof = []
    for model, url in sorted(support.items()):
        text = bodies.get(READER + url, "")
        if not text:
            continue
        rows = list(tables(text))
        record = {"model": model, "url": url}
        for system in SYSTEMS:
            status, row = classify(rows, system, model)
            proof.append({"model": model, "windows": system, "status": status,
                          "title": row[1] if row else "", "version": row[2] if row else "", "url": url})
            record[system] = status
        print(model, record)
    with args.output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, FIELDS)
        writer.writeheader()
        writer.writerows(proof)
    print(f"models={len(support)} rows={len(proof)}")
    if args.apply:
        raw = args.models.read_bytes()
        with args.models.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            rows, fields = list(reader), reader.fieldnames
        status = {(item["model"], item["windows"]): item["status"] for item in proof}
        updates = 0
        for row in rows:
            if row["brand"] != "GIGABYTE" or row["type"] != "motherboard":
                continue
            for system in SYSTEMS:
                field = f"windows{system}X64Evidence"
                value = status.get((row["model"], system))
                if row[field] == "pending" and value in {"oem-wlan-listed", "oem-wlan-not-listed"}:
                    row[field] = value
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
