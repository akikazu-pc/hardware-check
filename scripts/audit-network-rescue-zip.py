"""Reuse signed INF audit results for unchanged package bytes during local triage."""
import argparse
from collections import defaultdict
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile


FIELDS = ("windowsBuild", "inf", "hardwareId", "adapterName")
ROOT = Path(__file__).resolve().parent.parent
AUDITOR = ROOT / "scripts/audit-network-rescue-library.ps1"
CORE = ROOT / "src/AkikazuHardwareCheck.Core/bin/Release/net10.0-windows/win-x64/AkikazuHardwareCheck.Core.dll"


def sha256(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def package_key(name):
    parts = name.split("/")
    if parts[0] == "driver-packs" and len(parts) >= 3:
        return "/".join(parts[:2])
    if parts[0] == "pe-drivers" and len(parts) >= 3:
        return "/".join(parts[:3] if len(parts) >= 4 else parts[:2])
    return None


def groups_from_zip(bundle):
    groups = defaultdict(list)
    seen = set()
    for entry in bundle.infolist():
        if entry.is_dir() or not (key := package_key(entry.filename)):
            continue
        parts = entry.filename.split("/")
        if ("\\" in entry.filename or ":" in entry.filename or any(part in ("", ".", "..") for part in parts)
                or entry.filename.casefold() in seen):
            raise ValueError(f"Unexpected archive entry: {entry.filename}")
        seen.add(entry.filename.casefold())
        groups[key].append(entry)
    return groups


def fingerprint(bundle, entries, destination=None):
    digest = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: item.filename):
        digest.update(entry.filename.encode("utf-8") + b"\0")
        with bundle.open(entry) as source:
            content = hashlib.sha256()
            if destination is None:
                content = hashlib.file_digest(source, "sha256")
            else:
                path = destination.joinpath(*entry.filename.split("/"))
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("wb") as target:
                    while chunk := source.read(1024 * 1024):
                        content.update(chunk)
                        target.write(chunk)
        digest.update(content.digest())
    return digest.hexdigest()


def read_json(path, default):
    if not path.is_file():
        return default
    return json.loads(path.read_bytes())


def write_json(path, value):
    with TemporaryDirectory(dir=path.parent) as directory:
        temporary = Path(directory) / path.name
        temporary.write_text(json.dumps(value, separators=(",", ":")), encoding="utf-8")
        temporary.replace(path)


def run_auditor(staging, output):
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(AUDITOR), "-DriverDirectory", str(staging), "-EvidenceCsv", str(output)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    evidence = defaultdict(list)
    if output.is_file() and output.stat().st_size:
        with output.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                evidence[package_key(row["inf"])].append(row)
    return evidence


def audit(bundle, cache, output, fresh):
    cache.mkdir(parents=True, exist_ok=True)
    manifest_path = cache / "last-bundle.json"
    results = {}
    fingerprints = {}
    missing = {}
    # SetupAPI and catalog verification can fail on deep Windows paths.
    with bundle.open("rb") as source, TemporaryDirectory(prefix="nr-audit-") as temporary:
        bundle_hash = hashlib.file_digest(source, "sha256").hexdigest()
        sidecar = bundle.with_suffix(bundle.suffix + ".sha256")
        if sidecar.is_file() and sidecar.read_text(encoding="ascii").split()[0].lower() != bundle_hash:
            raise ValueError("ZIP SHA-256 differs from its sidecar")

        previous = read_json(manifest_path, {})
        previous_groups = previous.get("packages", {})
        same_archive = previous.get("bundleSha256") == bundle_hash
        staging = Path(temporary) / "drivers"
        staging.mkdir()
        with ZipFile(source) as archive:
            groups = groups_from_zip(archive)
            if not groups:
                raise ValueError("ZIP contains no driver packages")
            for key, entries in groups.items():
                prior = previous_groups.get(key)
                staged = False
                if not fresh and same_archive and prior and (cache / f"{prior}.json").is_file():
                    digest = prior
                else:
                    staged = fresh or not prior
                    digest = fingerprint(archive, entries, staging if staged else None)
                fingerprints[key] = digest
                record = cache / f"{digest}.json"
                if not fresh and record.is_file():
                    results[key] = read_json(record, [])
                else:
                    if not staged:
                        fingerprint(archive, entries, staging)
                    missing[key] = record

        if missing:
            audited = run_auditor(staging, Path(temporary) / "signed.csv")
            for key, record in missing.items():
                results[key] = audited.get(key, [])
                write_json(record, results[key])

    rows = sorted((row for group in results.values() for row in group), key=lambda row: tuple(row[f] or "" for f in FIELDS))
    with TemporaryDirectory(dir=output.parent) as directory:
        temporary_csv = Path(directory) / output.name
        with temporary_csv.open("w", encoding="utf-8", newline="") as destination:
            writer = csv.DictWriter(destination, FIELDS, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)
        temporary_csv.replace(output)
    write_json(manifest_path, dict(bundleSha256=bundle_hash, packages=fingerprints))
    return dict(bundleSha256=bundle_hash, packages=len(groups), audited=len(missing),
                reused=len(groups)-len(missing), signedRows=len(rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("cache", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--fresh", action="store_true", help="Run the signature checks again regardless of cache.")
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("INF matching requires Windows")
    environment = "|".join((str(sys.getwindowsversion().build), platform.machine(), os.environ.get("COMPUTERNAME", ""),
                            sha256(CORE), sha256(AUDITOR), sha256(Path(__file__))))
    namespace = hashlib.sha256(environment.encode("utf-8")).hexdigest()
    print(json.dumps(audit(args.bundle, args.cache / namespace, args.output, args.fresh)))


if __name__ == "__main__":
    main()
