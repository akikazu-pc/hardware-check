"""Join an attributed WinDriverIndex snapshot to exact motherboard WLAN candidates."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

BASE = "https://windriverindex.tucny.com/v1/latest"
VENDORS = {"ASRock": "asrock", "ASUS": "asus", "GIGABYTE": "gigabyte", "MSI": "msi"}
OEM_HOSTS = {
    "asrock": {"download.asrock.com"},
    "asus": {"dlcdnets.asus.com", "dlcdnet.asus.com"},
    "gigabyte": {"download.gigabyte.com"},
    "msi": {"download.msi.com", "download-2.msi.com"},
}
FIELDS = [
    "brand", "platform", "model", "boardId", "boardEvidenceUrl", "officialSupportUrl",
    "family", "listedVersion", "listedDate", "status", "downloadUrl", "sha256", "windowsEvidence",
    "snapshotGenerated",
]


def key(vendor, socket, name):
    return vendor, socket.upper(), re.sub(r"[^A-Z0-9]", "", name.upper())


def checked_snapshot(directory, name, manifest):
    payload = (directory / name).read_bytes()
    expected = manifest["data"]["files"][name]
    if len(payload) != expected["bytes"] or hashlib.sha256(payload).hexdigest() != expected["sha256"]:
        raise ValueError(f"{name} does not match snapshot manifest")
    data = json.loads(payload)
    if data["generated"] != manifest["generated"]:
        raise ValueError(f"{name} is from a different snapshot")
    return data["data"]


def fetch_board(board, generation, cache):
    url = f"{BASE}/by-board/{board['board_id']}.json"
    target = cache / f"{board['board_id']}.json"
    try:
        payload = target.read_bytes() if target.is_file() else subprocess.run(
            ["curl", "-fsSL", "--max-time", "12", url], capture_output=True, check=True, timeout=14,
        ).stdout
        report = json.loads(payload)
        embedded = report.get("board") or {}
        if (report.get("generated"), embedded.get("board_id"), embedded.get("vendor"), embedded.get("name")) != (
            generation, board["board_id"], board["vendor"], board["name"]
        ):
            return url, None
        if not target.is_file():
            target.write_bytes(payload)
        return url, report
    except (OSError, subprocess.SubprocessError, ValueError):
        return url, None


def inspect(row, boards, generation, cache, artefacts):
    board_matches = boards.get(key(VENDORS.get(row["brand"], ""), row["platform"], row["model"]), ())
    base = dict(brand=row["brand"], platform=row["platform"], model=row["model"], snapshotGenerated=generation)
    if len(board_matches) != 1:
        return [dict(base, status="board-unmatched" if not board_matches else "board-ambiguous")]
    board = board_matches[0]
    url, report = fetch_board(board, generation, cache)
    base.update(boardId=board["board_id"], boardEvidenceUrl=url, officialSupportUrl=board["support_url"])
    if not report:
        return [dict(base, status="board-report-unavailable")]

    results = []
    for family in report.get("families") or []:
        if family.get("component") != "wlan" or not family.get("listed_version"):
            continue
        name, version, date = family["family"], family["listed_version"], family.get("listed_date") or ""
        listing = dict(base, family=name, listedVersion=version, listedDate=date)
        matches = artefacts.get((board["vendor"], name, version, date), {})
        if len(matches) == 1:
            item = next(iter(matches.values()))
            listing.update(status="unique-snapshot-package", downloadUrl=item["url"],
                           sha256=(item.get("sha256") or "").upper(), windowsEvidence=item.get("os_raw") or "")
        else:
            listing["status"] = "package-ambiguous" if matches else "package-unresolved"
        results.append(listing)
    return results or [dict(base, status="no-wlan-listing-in-snapshot")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", type=Path)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    manifest = json.loads((args.snapshot / "manifest.json").read_bytes())
    generation = manifest["generated"]
    stamp = datetime.fromisoformat(generation).strftime("%Y%m%dT%H%M%S")
    cache = args.snapshot / "by-board" / stamp
    cache.mkdir(parents=True, exist_ok=True)
    boards = defaultdict(list)
    for board in checked_snapshot(args.snapshot, "boards.json", manifest):
        if board["product_type"] == "motherboard" and board.get("socket"):
            boards[key(board["vendor"], board["socket"], board["name"])].append(board)

    families = {item["family_id"]: item["name"] for item in checked_snapshot(args.snapshot, "families.json", manifest)
                if item["component"] == "wlan"}
    artefacts = defaultdict(dict)
    for item in checked_snapshot(args.snapshot, "artefacts.json", manifest):
        url = item.get("url") or ""
        parsed = urlsplit(url)
        if item["family_id"] not in families or item["kind"] != "driver" or item.get("is_beta"):
            continue
        if parsed.scheme != "https" or parsed.hostname not in OEM_HOSTS.get(item["vendor"], set()):
            continue
        identity = (item["vendor"], families[item["family_id"]], item["version_raw"], item.get("release_date") or "")
        artefacts[identity][item.get("sha256") or url] = item

    with args.models.open(encoding="utf-8-sig", newline="") as source:
        rows = [row for row in csv.DictReader(source) if row["type"] == "motherboard"
                and row["brand"] in VENDORS and "pending" in (row["windows10X64Evidence"], row["windows11X64Evidence"])]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = [result for group in pool.map(lambda row: inspect(row, boards, generation, cache, artefacts), rows)
                   for result in group]
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, FIELDS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(results)
    temporary.replace(args.output)
    print(f"Checked {len(rows)} motherboard records against {generation}.")


if __name__ == "__main__":
    main()
