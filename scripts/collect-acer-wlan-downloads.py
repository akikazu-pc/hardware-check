"""Record Acer laptop WLAN download listings by exact model and Windows x64 version.

Acer support pages load their driver lists from a same-origin POST endpoint
(``/<locale>/DynamicContent/GetDriversAndManuals``). The responses are captured from an ordinary
page session on www.acer.com and reduced to one entry per catalogue model; this script never
contacts Acer. Each driver file carries its own ``oss`` code (10M1 = Windows 10 x64, 11M1 =
Windows 11 x64), so one response can hold both systems. Every download link names the product in
its ``Step3`` parameter, which must equal the queried model, because the endpoint also returns
near matches such as a ``-G2`` or ``G`` sibling.

Outcomes per pending model and system:

* oem-wlan-listed: the exact model lists a Wireless LAN driver for that system.
* oem-wlan-not-listed: the exact model lists LAN and audio or chipset files for that system but
  no Wireless LAN file. It records the omission, not system incompatibility.
* oem-os-not-listed: the exact model lists at least MIN_OTHER_OS_FILES files, none for that system.

Near matches, empty responses and short lists stay pending.
"""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import re


SYSTEMS = ("10", "11")
LED = re.compile(r"\bLED\b", re.I)
# A list this long for another system shows the page is populated, not truncated or empty.
MIN_OTHER_OS_FILES = 10
SUPPORT_URL = "https://www.acer.com/us-en/support/product-support/{}"
FIELDS = ["model", "windows", "supportUrl", "queriedModel", "step3", "status", "fileName", "version",
          "date", "systemFileCount"]


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_capture(path):
    """Chunks map each catalogue model to [found, queried model, exact, Step3 values, oss codes,
    {system: [file count, has LAN, has audio or chipset, WLAN count, [version, file, date]]}]."""
    capture = {}
    for part in sorted(path.glob("models-*.json")):
        capture.update(json.loads(part.read_text(encoding="utf-8")))
    return capture


def classify(row, entry):
    base = dict(model=row["model"])
    if not entry or not entry[0]:
        return [dict(base, windows=system, status="support-list-empty") for system in SYSTEMS]
    _, queried, exact, steps, oss, systems = entry
    base.update(supportUrl=SUPPORT_URL.format(queried), queriedModel=queried, step3=steps)
    if not exact:
        return [dict(base, windows=system, status="near-model-match") for system in SYSTEMS]
    results = []
    for system in SYSTEMS:
        listing = systems.get(system)
        # Files tagged with several systems (for example "10M1;11M1") are not counted per system,
        # so they can hide a WLAN row; such lists only support positive listings.
        combined = any(";" in code and f"{system}M1" in code.split(";") for code in oss.split("|"))
        if listing is None:
            other = sum(value[0] for value in systems.values())
            status = ("combined-system-files" if combined
                      else "oem-os-not-listed" if other >= MIN_OTHER_OS_FILES else "short-list")
            results.append(dict(base, windows=system, status=status, systemFileCount=0))
            continue
        count, has_lan, has_other, wlan, top = listing
        item = dict(base, windows=system, systemFileCount=count)
        if wlan and top and LED.search(top[1]):
            # A Wi-Fi indicator LED utility is not a WLAN adapter driver.
            item.update(status="wlan-row-ambiguous", version=top[0], fileName=top[1], date=top[2])
        elif wlan and top:
            item.update(status="oem-wlan-listed", version=top[0], fileName=top[1], date=top[2])
        elif combined:
            item.update(status="combined-system-files")
        elif has_lan and has_other:
            item.update(status="oem-wlan-not-listed")
        else:
            item.update(status="short-list")
        results.append(item)
    return results


def apply_oem_evidence(path, models, proof):
    confirmed = {(item["model"], item["windows"]): item["status"] for item in proof}
    updates = Counter()
    for row in models:
        if row["type"] != "laptop" or row["brand"] != "Acer":
            continue
        for system in SYSTEMS:
            field = f"windows{system}X64Evidence"
            status = confirmed.get((row["model"], system))
            if row[field] == "pending" and status in {"oem-wlan-listed", "oem-wlan-not-listed", "oem-os-not-listed"}:
                row[field] = status
                updates[f"{system}:{status}"] += 1
            elif row[field] == "oem-os-upgrade-tested" and status == "oem-wlan-listed":
                # The upgrade list names the model; the exact support list now also names the WLAN driver.
                row[field] = status
                updates[f"{system}:upgrade-tested->oem-wlan-listed"] += 1
    if updates:
        raw = path.read_bytes()
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8",
                            newline="") as output:
            writer = csv.DictWriter(output, list(models[0]), quoting=csv.QUOTE_ALL,
                                    lineterminator="\r\n" if b"\r\n" in raw else "\n")
            writer.writeheader()
            writer.writerows(models)
        temporary.replace(path)
    return dict(updates)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--capture", type=Path, required=True, help="Directory of models-*.json capture chunks")
    parser.add_argument("--apply-oem-evidence", action="store_true")
    args = parser.parse_args()
    models = read(args.models)
    capture = load_capture(args.capture)
    proof = [item for row in models if row["type"] == "laptop" and row["brand"] == "Acer"
             and row["model"] in capture for item in classify(row, capture[row["model"]])]
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, FIELDS)
        writer.writeheader()
        writer.writerows(proof)
    temporary.replace(args.output)
    print("Proof statuses:", dict(Counter((item["windows"], item["status"]) for item in proof)))
    if args.apply_oem_evidence:
        print("OEM WLAN listing updates:", apply_oem_evidence(args.models, models, proof))


if __name__ == "__main__":
    main()
