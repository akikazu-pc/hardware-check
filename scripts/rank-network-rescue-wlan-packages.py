"""Rank unbundled OEM WLAN archives by new pending Win11 board candidates."""
import argparse
from collections import defaultdict
import csv
from pathlib import Path
import re
from zipfile import ZipFile


WINDOWS11 = re.compile(r"\bWin(?:dows)?\s*(?:10\s*/\s*)?11\b", re.I)


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def model_key(row):
    return row["brand"], row["platform"], row["model"]


def archive_packages(index, bundle):
    with ZipFile(bundle) as zip_file:
        paths = [name.split("/") for name in zip_file.namelist() if name.lower().endswith(".inf")]
    roots = {parts[1] for parts in paths if len(parts) >= 3 and parts[0] == "driver-packs"}
    scoped = {parts[2] for parts in paths if len(parts) >= 4 and parts[:2] == ["pe-drivers", "windows11-x64"]}
    return {row["sha256"].upper() for row in index if WINDOWS11.search(row["windows"])
            and (f"{row['packageId']}-{row['version']}" in roots or row["packageId"] in scoped)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")

    pending = {model_key(row) for row in read(args.models)
               if row["type"] == "motherboard" and row["windows11X64Evidence"] == "pending"}
    candidates = defaultdict(set)
    metadata = {}
    for row in read(args.audit):
        digest = row["sha256"].upper()
        model = model_key(row)
        if (row["status"] == "unique-snapshot-package" and re.fullmatch(r"[0-9A-F]{64}", digest)
                and model in pending and WINDOWS11.search(row["windowsEvidence"])):
            candidates[digest].add(model)
            metadata.setdefault(digest, row)

    bundled = archive_packages(read(args.index), args.bundle)
    baseline = {model for digest in bundled for model in candidates.get(digest, ())}
    ordered = sorted((digest for digest in candidates if digest not in bundled),
                     key=lambda digest: -len(candidates[digest]))
    raw_ranks = {digest: rank for rank, digest in enumerate(ordered, 1)}
    raw = {model for digest in ordered[:args.limit] for model in candidates[digest]} - baseline

    remaining = ordered.copy()
    covered = baseline.copy()
    result = []
    for rank in range(1, args.limit + 1):
        if not remaining:
            break
        digest = max(remaining, key=lambda item: len(candidates[item] - covered))
        additional = candidates[digest] - covered
        if not additional:
            break
        remaining.remove(digest)
        covered.update(additional)
        item = metadata[digest]
        result.append(dict(rank=rank, rawRank=raw_ranks[digest], brand=item["brand"], family=item["family"],
                           version=item["listedVersion"], candidateModels=len(candidates[digest]),
                           additionalModels=len(additional), sha256=digest, downloadUrl=item["downloadUrl"],
                           snapshotGenerated=item["snapshotGenerated"]))

    fields = ["rank", "rawRank", "brand", "family", "version", "candidateModels", "additionalModels",
              "sha256", "downloadUrl", "snapshotGenerated"]
    with args.output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fields, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(result)
    print(f"Baseline {len(baseline)} boards; raw counts select {len(raw)} new; "
          f"overlap-aware selection adds {len(covered - baseline)} with {len(result)} packages.")


if __name__ == "__main__":
    main()
