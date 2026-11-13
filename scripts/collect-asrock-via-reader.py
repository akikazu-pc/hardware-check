"""Collect ASRock WLAN availability from the reader-rendered Download.html page.

The capture-based ``collect-asrock-wlan-downloads.py`` needs browser snapshots. When no capture is
at hand, ``www.asrock.com`` answers our own transports with an Akamai block, but the public reader
proxy renders ``/mb/<platform>/<model>/Download.html`` as text. Every driver block looks like::

    Intel Wireless Lan driver ver:22.70.0.6
    <description>
    SHA256: <hash> Windows® 10 64bit

    Windows® 11 64bit 47.5 MB 2024/7/23[Global](https://download.asrock.com/...)

so the systems a driver covers are the ``Windows® 10 64bit`` / ``Windows® 11 64bit`` markers that
follow its block.

For each model and system the script reports ``oem-wlan-listed`` when a WLAN/Wi-Fi driver covers
that system and ``oem-wlan-not-listed`` when the block set for that system is populated but has no
WLAN driver. Models whose download page is missing stay untouched.

Usage: python scripts/collect-asrock-via-reader.py docs/network-rescue-model-gaps.csv \
    artifacts/asrock-reader-proof.csv [--apply]
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
WLAN = re.compile(r"wlan|wi-?fi|wireless", re.I)
VERSION = re.compile(r"ver:", re.I)
SYSTEMS = {"10": "10 64bit", "11": "11 64bit"}
FIELDS = ["model", "windows", "status", "title", "version", "url"]


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def fetch(urls):
    completed = subprocess.run(["node", str(BRIDGE), *urls], cwd=ROOT, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=900)
    bodies = {}
    for item in json.loads(completed.stdout):
        if item["status"] == 200 and item["file"]:
            bodies[item["url"]] = Path(item["file"]).read_text(encoding="utf-8", errors="replace")
    return bodies


def blocks(text):
    """Split the page into driver blocks keyed by their version title line."""
    current = None
    for line in text.splitlines():
        if VERSION.search(line) and len(line) < 200:
            if current:
                yield current
            current = {"title": line.strip(), "body": []}
        elif current is not None:
            current["body"].append(line)
    if current:
        yield current


def classify(text, system):
    marker = SYSTEMS[system]
    covered = [block for block in blocks(text) if marker in "\n".join(block["body"])]
    wlan = [block for block in covered if WLAN.search(block["title"])]
    if wlan:
        return "oem-wlan-listed", wlan[0]["title"]
    if len(covered) >= 5:
        return "oem-wlan-not-listed", None
    return "no-valid-list", None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    pending = [row for row in read_rows(args.models) if row["brand"] == "ASRock"
               and row["type"] == "motherboard"
               and any(row[f"windows{system}X64Evidence"] == "pending" for system in SYSTEMS)]
    pages = {}
    for row in pending:
        match = re.search(r"asrock\.com/mb/(AMD|Intel)/([^/]+)/", row["source"])
        if match:
            pages[row["model"]] = f"https://www.asrock.com/mb/{match.group(1)}/{match.group(2)}/Download.html"
    bodies = fetch([READER + url for url in sorted(set(pages.values()))])

    proof = []
    for model, url in sorted(pages.items()):
        text = bodies.get(READER + url, "")
        if len(text) < 1000:
            continue
        for system in SYSTEMS:
            status, title = classify(text, system)
            proof.append({"model": model, "windows": system, "status": status,
                          "title": title or "", "version": "", "url": url})
    with args.output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, FIELDS)
        writer.writeheader()
        writer.writerows(proof)
    print(f"models={len(pages)} rows={len(proof)}")
    for item in proof:
        print(item["model"], item["windows"], item["status"])
    if args.apply:
        raw = args.models.read_bytes()
        with args.models.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            rows, fields = list(reader), reader.fieldnames
        status = {(item["model"], item["windows"]): item["status"] for item in proof}
        updates = 0
        for row in rows:
            if row["brand"] != "ASRock" or row["type"] != "motherboard":
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
