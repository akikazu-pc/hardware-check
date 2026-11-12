"""Record MSI motherboard WLAN download listings by exact model and Windows version.

The MSI support API rejects non-browser clients, so the raw responses are captured from an
ordinary page session on www.msi.com and saved as JSON. This script never contacts MSI. It
reads that capture, writes one proof row per model and system, and with --apply-oem-evidence
records the same two outcomes as the ASUS route:

* oem-wlan-listed: the exact model page lists a WLAN driver for that Windows x64 version and
  the factory specification already lists WLAN or a module.
* oem-wlan-not-listed: the exact model page returns a LAN list for that Windows version, with
  audio or chipset files, but no WLAN row for that version, and the factory specification lists
  WLAN or a module, or also omits WLAN. It records the omission, not system incompatibility.

A title mismatch, revision suffix, empty response or blocked request leaves the row pending.
"""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


SYSTEMS = ("10", "11")
WLAN = re.compile(r"wi[- ]?fi|wlan|wireless", re.I)
BLUETOOTH = re.compile(r"bluetooth", re.I)
KILLER = re.compile(r"killer", re.I)
# Killer universal packages whose ZIP was downloaded, matched the OEM SHA-256 and statically shown to
# contain WLAN INFs for Windows 10/11 x64 (docs/network-rescue-oem-package-inf-proof.csv).
WLAN_PACKAGE_SHA256 = {"b77be57e07ddd1f3aaa1b552329128a7cb95bd3d3c4f78777477b5c3a1ef84d5"}
FACTORY_WLAN = {"manual-module-candidate", "oem-spec-wlan-listed", "oem-spec-module"}
DOWNLOAD_HOSTS = {"download.msi.com"}
FIELDS = ["model", "platform", "windows", "supportUrl", "status", "title", "version", "downloadUrl",
          "sha256", "candidateSha256Match"]


def model_key(value):
    return re.sub(r"[^A-Z0-9+]", "", value.upper())


def product_slug(model):
    """MSI product paths drop slashes and parentheses and join words with hyphens."""
    return re.sub(r"\s+", "-", re.sub(r"[/()]", "", model).strip())


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def pending_rows(models):
    return [row for row in models if row["type"] == "motherboard" and row["brand"] == "MSI"
            and any(row[f"windows{system}X64Evidence"] == "pending" for system in SYSTEMS)]


def load_capture(path):
    """Read a capture directory: pk.json holds unique network downloads and models-*.json map
    each product slug to [ok-or-status, title, category codes, space-separated download indexes].
    Category codes are A audio, C chipset, L LAN and O other, one per non-empty category."""
    packages = json.loads((path / "pk.json").read_text(encoding="utf-8"))
    capture = {}
    for part in sorted(path.glob("models-*.json")):
        for slug, (status, title, codes, indexes) in json.loads(part.read_text(encoding="utf-8")).items():
            names = {"A": "audio", "C": "chipset", "L": "lan", "O": "other"}
            capture[slug] = dict(
                http=200, code=200 if status == 1 else status, title=title,
                cats={f"{names[code]}-{position}": 1 for position, code in enumerate(codes)},
                net=[["LAN Drivers", *packages[int(index)]] for index in indexes.split()])
    return capture


def systems_of(os_field):
    return set(re.findall(r"win(10|11)\s*64", os_field or "", re.I))


def classify(row, capture, candidate_hashes):
    """Return proof rows for each pending system of one model."""
    slug = product_slug(row["model"])
    support = f"https://www.msi.com/Motherboard/{slug}/support"
    base = dict(model=row["model"], platform=row["platform"], supportUrl=support)
    # Every system is reported so the proof table stays complete after rows leave the pending state.
    pending = list(SYSTEMS)
    entry = capture.get(slug)
    if not entry or entry.get("http") != 200 or entry.get("code") != 200:
        return [dict(base, windows=system, status="support-api-unavailable") for system in pending]
    # A revision or regional suffix that the product title does not carry may be a different board.
    if model_key(entry.get("title") or "") != model_key(row["model"]):
        return [dict(base, windows=system, status="title-mismatch", title=entry.get("title") or "")
                for system in pending]
    network = [item for item in entry.get("net", []) if urlsplit(item[4]).hostname in DOWNLOAD_HOSTS]
    wlan = [item for item in network if (WLAN.search(item[1]) and not BLUETOOTH.search(item[1]))
            or item[5].lower() in WLAN_PACKAGE_SHA256]
    lan = [item for item in network if item not in wlan and not BLUETOOTH.search(item[1])]
    # Killer universal packages can carry Killer Wi-Fi as well as Ethernet, so they never prove an omission.
    killer = any(KILLER.search(item[1]) for item in lan)
    categories = {name.lower() for name in entry.get("cats", {})}
    has_other = any("audio" in name or "chipset" in name for name in categories)
    results = []
    for system in pending:
        listed = [item for item in wlan if system in systems_of(item[2])]
        if listed:
            for _, title, _, version, url, sha256, _ in listed:
                results.append(dict(base, windows=system, status="oem-wlan-listed", title=title,
                                    version=version or "", downloadUrl=url, sha256=sha256.lower(),
                                    candidateSha256Match=str(sha256.lower() in candidate_hashes[row["model"]]).lower()
                                    if candidate_hashes[row["model"]] else ""))
        elif killer:
            results.append(dict(base, windows=system, status="killer-universal-unresolved"))
        elif has_other and any(system in systems_of(item[2]) for item in lan):
            # A valid list for this Windows version without a WLAN row, even if another version has one.
            results.append(dict(base, windows=system, status="oem-wlan-not-listed"))
        else:
            results.append(dict(base, windows=system, status="no-valid-lan-list"))
    return results


def apply_oem_evidence(path, models, proof):
    confirmed = defaultdict(set)
    for item in proof:
        confirmed[item["platform"], item["model"], item["windows"]].add(item["status"])
    updates = Counter()
    for row in models:
        if row["type"] != "motherboard" or row["brand"] != "MSI":
            continue
        for system in SYSTEMS:
            field = f"windows{system}X64Evidence"
            statuses = confirmed.get((row["platform"], row["model"], system), set())
            if row[field] != "pending" or len(statuses) != 1:
                continue
            status = next(iter(statuses))
            factory_wlan = row["wlanEvidence"] in FACTORY_WLAN
            if ((status == "oem-wlan-listed" and factory_wlan)
                    or (status == "oem-wlan-not-listed"
                        and (factory_wlan or row["wlanEvidence"] == "oem-spec-wlan-not-listed"))):
                row[field] = status
                updates[f"{system}:{status}"] += 1
    if updates:
        write_models(path, models)
    return dict(updates)


def apply_laptop_listings(path, models, proof):
    """Laptop proof rows come from a family support page whose specification lists the exact model.
    Only positive listings are applied: the short laptop lists do not prove an omission."""
    listed = {(item["model"], item["windows"]) for item in proof
              if item["status"] == "oem-wlan-listed" and item["specListsModel"] == "true"
              and urlsplit(item["downloadUrl"]).hostname in DOWNLOAD_HOSTS}
    updates = Counter()
    for row in models:
        if row["type"] != "laptop" or row["brand"] != "MSI":
            continue
        for system in SYSTEMS:
            field = f"windows{system}X64Evidence"
            if row[field] == "pending" and (row["model"], system) in listed:
                row[field] = "oem-wlan-listed"
                updates[f"{system}:oem-wlan-listed"] += 1
    if updates:
        write_models(path, models)
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
    parser.add_argument("--capture", type=Path, help="JSON object of product slug to captured API summary")
    parser.add_argument("--candidates", type=Path, help="Board package candidate CSV for SHA-256 cross-checks")
    parser.add_argument("--emit-slugs", type=Path, help="Write the pending product slugs as a JSON array")
    parser.add_argument("--apply-oem-evidence", action="store_true")
    parser.add_argument("--laptop-proof", type=Path,
                        help="Apply positive rows of an MSI laptop family listing proof CSV")
    args = parser.parse_args()
    models = read(args.models)
    if args.laptop_proof:
        print("MSI laptop listing updates:", apply_laptop_listings(args.models, models, read(args.laptop_proof)))
    rows = pending_rows(models)
    if args.emit_slugs:
        args.emit_slugs.write_text(json.dumps(sorted({product_slug(row["model"]) for row in rows})), encoding="utf-8")
        print(f"Wrote {len({product_slug(row['model']) for row in rows})} slugs.")
    if not args.capture:
        return
    capture = (load_capture(args.capture) if args.capture.is_dir()
               else json.loads(args.capture.read_text(encoding="utf-8")))
    candidate_hashes = defaultdict(set)
    if args.candidates:
        for item in read(args.candidates):
            if item["vendor"] == "msi":
                candidate_hashes[item["model"]].add(item["sha256"].lower())
    boards = [row for row in models if row["type"] == "motherboard" and row["brand"] == "MSI"
              and product_slug(row["model"]) in capture]
    proof = [item for row in boards for item in classify(row, capture, candidate_hashes)]
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, FIELDS)
        writer.writeheader()
        writer.writerows(proof)
    temporary.replace(args.output)
    print("Proof statuses:", dict(Counter(item["status"] for item in proof)))
    if args.apply_oem_evidence:
        print("OEM WLAN listing updates:", apply_oem_evidence(args.models, models, proof))


if __name__ == "__main__":
    main()
