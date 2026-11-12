"""Record ASRock motherboard WLAN download listings by exact model and Windows x64 version.

ASRock product pages load their download table from a static ``Download.html`` next to the
product page (``/mb/<AMD|Intel>/<model>/Download.html``); every row names its Windows versions
and most rows carry a SHA-256. The specification is part of the product ``index.asp``. Both are
captured from an ordinary page session and reduced to JSON; this script never contacts ASRock.

Capture directory:
* pk.json: unique network rows as [name, systems, sha256, download URL].
* models-*.json: model -> [HTTP status, row count, category codes (A audio, C chipset), indexes].
* specs-*.json: model -> 1 when the exact product page (title naming the model) has a
  "Wireless LAN" specification row without "not included"/"sold separately" wording, 0 when it
  has no such row, the model name carries no Wi-Fi marker and the page lists wired LAN.
  Ambiguous pages and title mismatches are left out.

Outcomes per model and system match the MSI and ASUS routes: oem-wlan-listed needs factory
WLAN evidence; oem-wlan-not-listed needs a LAN row for that system, audio or chipset rows, no
WLAN row for that system, and factory WLAN evidence or a specification without WLAN.
"""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import re
from urllib.parse import quote, urlsplit


SYSTEMS = ("10", "11")
WLAN = re.compile(r"wireless\s*lan|\bwlan\b|wi-?fi", re.I)
LAN = re.compile(r"\blan\b|ethernet", re.I)
EXCLUDED = re.compile(r"bluetooth|utility", re.I)
FACTORY_WLAN = {"manual-module-candidate", "oem-spec-wlan-listed", "oem-spec-module"}
DOWNLOAD_HOSTS = {"download.asrock.com"}
FIELDS = ["model", "platform", "windows", "supportUrl", "status", "title", "downloadUrl", "sha256"]


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_capture(path):
    packages = json.loads((path / "pk.json").read_text(encoding="utf-8"))
    pages, specs = {}, {}
    for part in sorted(path.glob("models-*.json")):
        pages.update(json.loads(part.read_text(encoding="utf-8")))
    for part in sorted(path.glob("specs-*.json")):
        for model, listed in json.loads(part.read_text(encoding="utf-8")).items():
            specs[model] = "wlan-listed" if listed == 1 else "wlan-not-listed" if listed == 0 else str(listed)
    return packages, pages, specs


def systems_of(text):
    return set(re.findall(r"W(?:indows)?\D{0,3}(10|11)\s*64", text, re.I))


def support_url(row):
    vendor = "AMD" if row["platform"].startswith("AM") else "Intel"
    return f"https://www.asrock.com/mb/{vendor}/{quote(row['model'].replace('/', ''))}/index.asp#Download"


def classify(row, packages, page):
    base = dict(model=row["model"], platform=row["platform"], supportUrl=support_url(row))
    if not page or page[0] != 200:
        return [dict(base, windows=system, status="support-list-unavailable") for system in SYSTEMS]
    _, count, codes, indexes = page
    rows = [packages[int(index)] for index in indexes.split()]
    rows = [item for item in rows if not EXCLUDED.search(item[0])
            and (not item[3] or urlsplit(item[3]).hostname in DOWNLOAD_HOSTS)]
    wlan = [item for item in rows if WLAN.search(item[0])]
    lan = [item for item in rows if item not in wlan and LAN.search(item[0])]
    results = []
    for system in SYSTEMS:
        listed = [item for item in wlan if system in systems_of(item[1])]
        if listed:
            results.extend(dict(base, windows=system, status="oem-wlan-listed", title=name,
                                downloadUrl=url, sha256=sha256) for name, _, sha256, url in listed)
        elif count and set(codes) & {"A", "C"} and any(system in systems_of(item[1]) for item in lan):
            results.append(dict(base, windows=system, status="oem-wlan-not-listed"))
        else:
            results.append(dict(base, windows=system, status="no-valid-lan-list"))
    return results


def apply_specs(models, specs):
    """Record specification evidence for catalogue-only rows; returns the number updated."""
    updated = 0
    for row in models:
        if row["type"] != "motherboard" or row["brand"] != "ASRock" or row["wlanEvidence"] != "oem-model-catalog":
            continue
        spec = specs.get(row["model"])
        if spec == "wlan-listed":
            row.update(wlanEvidence="oem-spec-wlan-listed", gap="chip-exact-id-driver-install")
        elif spec == "wlan-not-listed":
            row.update(wlanEvidence="oem-spec-wlan-not-listed", gap="factory-wifi-not-listed-confirmation")
        else:
            continue
        # The specification and the download table share index.asp; the app opens #Download.
        row["source"] = support_url(row)
        updated += 1
    return updated


def apply_oem_evidence(models, proof):
    confirmed = defaultdict(set)
    for item in proof:
        confirmed[item["platform"], item["model"], item["windows"]].add(item["status"])
    updates = Counter()
    for row in models:
        if row["type"] != "motherboard" or row["brand"] != "ASRock":
            continue
        factory_wlan = row["wlanEvidence"] in FACTORY_WLAN
        for system in SYSTEMS:
            field = f"windows{system}X64Evidence"
            statuses = confirmed.get((row["platform"], row["model"], system), set())
            if row[field] != "pending" or len(statuses) != 1:
                continue
            status = next(iter(statuses))
            if ((status == "oem-wlan-listed" and factory_wlan)
                    or (status == "oem-wlan-not-listed"
                        and (factory_wlan or row["wlanEvidence"] == "oem-spec-wlan-not-listed"))):
                row[field] = status
                updates[f"{system}:{status}"] += 1
    return dict(updates)


def write_models(path, models):
    raw = path.read_bytes()
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8",
                        newline="") as output:
        writer = csv.DictWriter(output, list(models[0]), quoting=csv.QUOTE_ALL,
                                lineterminator="\r\n" if b"\r\n" in raw else "\n")
        writer.writeheader()
        writer.writerows(models)
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--apply-oem-evidence", action="store_true")
    args = parser.parse_args()
    models = read(args.models)
    packages, pages, specs = load_capture(args.capture)
    spec_updates = apply_specs(models, specs) if args.apply_oem_evidence else 0
    boards = [row for row in models if row["type"] == "motherboard" and row["brand"] == "ASRock"
              and row["model"] in pages]
    proof = [item for row in boards for item in classify(row, packages, pages[row["model"]])]
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, FIELDS)
        writer.writeheader()
        writer.writerows(proof)
    temporary.replace(args.output)
    print("Proof statuses:", dict(Counter((item["windows"], item["status"]) for item in proof)))
    if args.apply_oem_evidence:
        updates = apply_oem_evidence(models, proof)
        print("Specification updates:", spec_updates, "OEM WLAN listing updates:", updates)
        if spec_updates or updates:
            write_models(args.models, models)


if __name__ == "__main__":
    main()
