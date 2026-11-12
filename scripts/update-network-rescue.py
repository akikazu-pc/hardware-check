"""Check OEM motherboard and laptop WLAN metadata and stage changed driver archives locally."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime
from functools import partial
import hashlib
from html import unescape
import json
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
from urllib.parse import quote, urlencode, urlsplit, urlunsplit
from zipfile import BadZipFile, ZipFile

from network_rescue_adapters import load_tplink
from network_rescue_apple import load_apple
from network_rescue_china import HONOR_SUPPORT, load_honor, load_xiaomi
from network_rescue_japan import load_dynabook, load_panasonic


ROOT = Path(__file__).resolve().parent.parent
BASE = "https://windriverindex.tucny.com/v1/latest"
SNAPSHOT_FILES = ("boards.json", "families.json", "artefacts.json")
REPORT_FILES = {"all": "last-run.json", "laptops": "last-laptop-run.json", "devices": "last-device-run.json"}
PLATFORMS = {"AM4", "AM5", "LGA1700", "LGA1851"}
SNAPSHOT_SYSTEM_VENDORS = {"dell", "hp", "lenovo"}
OEM_PATHS = {
    "asus": ({"dlcdnets.asus.com", "dlcdnet.asus.com"}, "/pub/asus/mb/"),
    "asrock": ({"download.asrock.com"}, "/drivers/"),
    "gigabyte": ({"download.gigabyte.com"}, "/filelist/driver/mb_driver_"),
    "msi": ({"download.msi.com", "download-2.msi.com"}, "/dvr_exe/mb/"),
}
DIGEST = re.compile(r"[a-f0-9]{64}")
MAX_ARCHIVE = 512 * 1024 * 1024
MAX_EXTRACTED = 2 * 1024 * 1024 * 1024


def sha256(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def atomic_json(path, value):
    with TemporaryDirectory(dir=path.parent) as directory:
        temporary = Path(directory) / path.name
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)


def fetch(url, target, limit, *, referer=None, etag_options=(), seconds=90):
    command = ["curl", "-fsSL", *(["--referer", referer] if referer else []), *etag_options,
               "--proto", "=https", "--proto-redir", "=https", "--max-redirs", "5",
               "--max-time", str(seconds), "--speed-limit", "32768", "--speed-time", "30",
               "--max-filesize", str(limit), "-w", "%{http_code}", url, "-o", str(target)]
    try:
        result = subprocess.run(command, check=True, capture_output=True, timeout=seconds + 5)
    except subprocess.CalledProcessError as error:
        crashed = error.returncode & 0xFFFFFFFF == 0xC0000005
        interrupted_metadata = seconds == 90 and error.returncode in {18, 28, 56}
        if not (crashed or interrupted_metadata):
            raise
        # A single interrupted metadata request should not discard the rest of the brand scan.
        result = subprocess.run(command, check=True, capture_output=True, timeout=seconds + 5)
    return int(result.stdout)


def snapshot_data(state, manifest, stats, names=SNAPSHOT_FILES):
    payloads = {}
    directory = state / "snapshots"
    directory.mkdir(exist_ok=True)
    for name in names:
        info = manifest["data"]["files"][name]
        digest, size = info["sha256"].lower(), info["bytes"]
        if not DIGEST.fullmatch(digest) or not 0 < size <= 64 * 1024 * 1024:
            raise ValueError(f"Invalid snapshot manifest entry: {name}")
        target = directory / f"{digest}.json"
        if not target.is_file() or target.stat().st_size != size or sha256(target) != digest:
            with TemporaryDirectory(dir=directory) as scratch:
                temporary = Path(scratch) / name
                fetch(f"{BASE}/{name}", temporary, size)
                if temporary.stat().st_size != size or sha256(temporary) != digest:
                    raise ValueError(f"Snapshot integrity check failed: {name}")
                temporary.replace(target)
            stats["metadataFilesFetched"] += 1
        payloads[name] = json.loads(target.read_bytes())["data"]
    return payloads


def motherboard_key(board):
    name = re.sub(r"[^a-z0-9]", "", board["name"].casefold())
    return "|".join((board["vendor"], board["socket"], name, str(board.get("revision") or "").casefold()))


def system_catalog(data, product_type):
    models = {f"{row['vendor']}|{row['vendor_product_id']}": {
        "model": row["name"], "vendor": row["vendor"], "vendorModelId": row["vendor_product_id"],
        "sourceId": row["board_id"], "support": row["support_url"], "smbios": row.get("smbios"),
    } for row in data["boards.json"] if row.get("product_type") == product_type
        and row["vendor"] in SNAPSHOT_SYSTEM_VENDORS and row.get("vendor_product_id")}
    if product_type == "desktop":
        for model in models.values():
            name = model["model"].lower()
            tags = []
            if re.search(r"\ball[ -]in[ -]one\b|\baio\b", name):
                tags.append("all-in-one")
            if re.search(r"\b(?:mini|micro|tiny|nuc)\b", name):
                tags.append("mini-pc")
            if re.search(r"\b(?:workstation|thinkstation)\b|\bprecision\b.*\b(?:tower|rack|sff|compact)\b", name):
                tags.append("workstation")
            elif model["vendor"] == "dell" and re.search(r"\bprecision\b", name) and "desktops" not in name:
                tags.append("form-factor-unverified")
            elif model["vendor"] == "dell" and "precision" in name and "desktops" in name:
                tags.append("workstation")
            model.update(deviceTags=tags or ["branded-desktop"], evidence="snapshot-catalog")
    return models


def normalized_snapshot(data):
    boards = defaultdict(list)
    for row in data["boards.json"]:
        if row["product_type"] == "motherboard" and row.get("socket") in PLATFORMS and row["vendor"] in OEM_PATHS:
            boards[motherboard_key(row)].append({k: row.get(k) for k in
                                                ("board_id", "vendor", "name", "socket", "revision", "support_url")})

    families = {row["family_id"]: row["name"] for row in data["families.json"] if row["component"] == "wlan"}
    packages = {}
    for row in data["artefacts.json"]:
        vendor = row["vendor"]
        if vendor not in OEM_PATHS or row["kind"] != "driver" or row.get("is_beta") or row["family_id"] not in families:
            continue
        url = row.get("url") or ""
        parsed = urlsplit(url)
        hosts, prefix = OEM_PATHS[vendor]
        if parsed.scheme != "https" or parsed.hostname not in hosts or not parsed.path.lower().startswith(prefix):
            continue
        os = str(row.get("os_raw") or "")
        systems = [system for system in ("10", "11") if re.search(rf"\bWin(?:dows)?\s*{system}\s*(?:x64|64)", os, re.I)]
        if not systems:
            continue
        digest = (row.get("sha256") or "").lower()
        size = row.get("file_size") or 0
        if not DIGEST.fullmatch(digest) or not 0 < size <= MAX_ARCHIVE:
            continue
        family = families[row["family_id"]]
        # Stable URLs may publish different bytes. Versioned URLs are separate candidates.
        source_key = "|".join((vendor, family, parsed.path.casefold()))
        package = packages.setdefault(digest, dict(sha256=digest, vendor=vendor, family=family,
            version=row["version_raw"], releaseDate=row.get("release_date") or "", systems=systems,
            url=url, size=size, sources=[]))
        if source_key not in package["sources"]:
            package["sources"].append(source_key)
    return {key: items[0] for key, items in boards.items() if len(items) == 1}, packages


def board_packages(board, generation, package_lookup, scratch):
    path = scratch / f"board-{int(board['board_id'])}.json"
    try:
        fetch(f"{BASE}/by-board/{int(board['board_id'])}.json", path, 1024 * 1024)
        report = json.loads(path.read_bytes())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    embedded = report.get("board") or {}
    if (report.get("generated"), embedded.get("board_id"), embedded.get("vendor"), embedded.get("name")) != (
        generation, board["board_id"], board["vendor"], board["name"]
    ):
        return None

    matches = []
    for row in report.get("families", []):
        if row.get("component") != "wlan" or not row.get("listed_version"):
            continue
        key = (board["vendor"], row["family"], row["listed_version"], row.get("listed_date") or "")
        exact = package_lookup.get(key, ())
        if len(exact) == 1:
            matches.extend(exact)
    return sorted(set(matches))


def extract_direct_zip(archive, target):
    with ZipFile(archive) as source:
        files = [entry for entry in source.infolist() if not entry.is_dir()]
        if not any(entry.filename.lower().endswith(".inf") for entry in files):
            return False
        if sum(entry.file_size for entry in files) > MAX_EXTRACTED:
            raise ValueError("Uncompressed ZIP exceeds the extraction limit")
        seen = set()
        for entry in files:
            name = entry.filename
            parts = name.split("/")
            if (re.search(r'[\\:<>"|?*]', name) or any(part in ("", ".", "..") or part.endswith((" ", ".")) or Path(part).is_reserved() for part in parts)
                    or name.casefold() in seen or (entry.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError(f"Unsafe archive entry: {name}")
            seen.add(name.casefold())
        source.extractall(target, files)
        return True


def signed_inf(driver_dir, evidence):
    auditor = ROOT / "scripts/audit-network-rescue-library.ps1"
    subprocess.run(["pwsh", "-NoProfile", "-File", str(auditor), "-DriverDirectory", str(driver_dir),
                    "-EvidenceCsv", str(evidence)], check=True, capture_output=True, timeout=90)
    if not evidence.is_file() or not evidence.stat().st_size:
        return 0
    with evidence.open(encoding="utf-8-sig", newline="") as source:
        return len({row["inf"] for row in csv.DictReader(source)})


def stage_package(state, item, stats):
    digest = item["sha256"]
    cache = state / "originals"
    cache.mkdir(exist_ok=True)
    # Stable hash-based names keep the original distinct from updates to mutable OEM URLs.
    source = cache / f"{digest}.archive"
    if not source.is_file() or sha256(source) != digest:
        with TemporaryDirectory(dir=cache) as scratch:
            partial = Path(scratch) / "download"
            fetch(item["url"], partial, MAX_ARCHIVE)
            if partial.stat().st_size > MAX_ARCHIVE or sha256(partial) != digest:
                raise ValueError("OEM archive exceeds the size limit or its SHA-256 differs from the snapshot")
            partial.replace(source)
        stats["driverArchivesFetched"] += 1

    # Short extraction paths avoid Windows catalog verification failures.
    with TemporaryDirectory(prefix="nr-up-") as scratch:
        scratch = Path(scratch)
        drivers = scratch / "drivers"
        evidence = scratch / "signed-inf.csv"
        try:
            if not extract_direct_zip(source, drivers):
                return "needs-static-extraction", 0
        except BadZipFile:
            return "needs-static-extraction", 0
        count = signed_inf(drivers, evidence)
        if not count:
            return "no-signed-inf-on-this-windows", 0

        verified = state / "verified"
        verified.mkdir(exist_ok=True)
        destination = verified / digest
        if not destination.is_dir():
            with TemporaryDirectory(dir=verified) as publish:
                output = Path(publish) / "package"
                shutil.copytree(drivers, output / "drivers")
                shutil.copyfile(evidence, output / "signed-inf.csv")
                atomic_json(output / "package.json", dict(item, signedInfCount=count))
                output.rename(destination)
    return "verified-candidate", count


def refresh(state, known_hashes, *, scope="all"):
    state.mkdir(parents=True, exist_ok=True)
    state_file = state / "state.json"
    report = state / REPORT_FILES[scope]
    previous = json.loads(state_file.read_bytes()) if state_file.is_file() else None
    stats = dict(manifestRequests=1, metadataFilesFetched=0, boardReportsRequested=0, driverArchivesFetched=0)
    with TemporaryDirectory(prefix="nr-index-") as scratch:
        scratch = Path(scratch)
        manifest_path = scratch / "manifest.json"
        fetch(f"{BASE}/manifest.json", manifest_path, 1024 * 1024)
        manifest = json.loads(manifest_path.read_bytes())
        generation = manifest["generated"]
        fingerprints = {name: manifest["data"]["files"][name]["sha256"] for name in SNAPSHOT_FILES}
        if previous and datetime.fromisoformat(generation) < datetime.fromisoformat(previous["generation"]):
            raise ValueError("The source returned an older snapshot")
        changed = not previous or fingerprints != previous["fingerprints"]
        pending_catalogs = []
        counts = dict(newLaptops=0, newDevices=0)
        for product_type, filename, count_field in (("laptop", "laptops", "newLaptops"),
                                                    ("desktop", "devices", "newDevices")):
            if scope not in ("all", filename):
                continue
            path = state / f"{filename}.json"
            cached = json.loads(path.read_bytes()) if path.is_file() else {}
            if cached.get("fingerprint") != fingerprints["boards.json"]:
                pending_catalogs.append((product_type, path, cached, count_field))
        if changed and scope == "all":
            data = snapshot_data(state, manifest, stats)
        elif pending_catalogs:
            data = snapshot_data(state, manifest, stats, ("boards.json",))
        for product_type, path, cached, count_field in pending_catalogs:
            models = system_catalog(data, product_type)
            new_models = sorted(models.keys() - cached.get("models", {}).keys())
            counts[count_field] = len(new_models)
            atomic_json(path, dict(generation=generation, baseline=not cached, fingerprint=fingerprints["boards.json"],
                                   newModelIds=new_models, models=models))
        if scope != "all" or (not changed and not previous["queue"] and not previous["boardQueue"]):
            result = dict(status="catalog-updated" if pending_catalogs else "unchanged", generation=generation,
                          newBoards=0, newArchives=0, remaining=0, boardReportsPending=0, **counts, **stats)
            atomic_json(report, result)
            return result
        if changed:
            boards, packages = normalized_snapshot(data)
        else:
            boards, packages = previous["boards"], previous["packages"]
        queue = previous["queue"] if previous else {}
        board_queue = previous["boardQueue"] if previous else {}
        completed = previous["completed"] if previous else {}
        board_matches = previous.get("boardMatches", {}) if previous else {}
        old_boards = previous["boards"] if previous else {}
        old_packages = previous["packages"] if previous else {}
        new_boards = {key: row for key, row in boards.items() if key not in old_boards} if previous else {}
        new_packages = {key: row for key, row in packages.items() if key not in old_packages} if previous else {}
        old_sources = {source for item in old_packages.values() for source in item["sources"]}
        for digest, item in new_packages.items():
            if digest not in known_hashes and digest not in completed:
                kind = "changed-oem-source" if old_sources.intersection(item["sources"]) else "new-oem-archive"
                queue.setdefault(digest, dict(item, kind=kind, boardCandidates=[]))
        board_queue.update(new_boards)
        package_lookup = defaultdict(list)
        if board_queue:
            for digest, item in packages.items():
                key = (item["vendor"], item["family"], item["version"], item["releaseDate"])
                package_lookup[key].append(digest)
        for key in list(board_queue):
            board = boards.get(key)
            if board is None:
                del board_queue[key]
                continue
            stats["boardReportsRequested"] += 1
            matches = board_packages(board, generation, package_lookup, scratch)
            if matches is None:
                continue
            board_matches[key] = dict(board=board, packageHashes=matches)
            for digest in matches:
                if digest in known_hashes or digest in completed:
                    continue
                item = queue.setdefault(digest, dict(packages[digest], kind="new-motherboard-candidate", boardCandidates=[]))
                if board["name"] not in item["boardCandidates"]:
                    item["boardCandidates"].append(board["name"])
            del board_queue[key]

    current = dict(generation=generation, fingerprints=fingerprints, boards=boards, packages=packages,
                   queue=queue, boardQueue=board_queue, boardMatches=board_matches, completed=completed)
    # Persist discovered work before attempting driver downloads so interruption can be retried.
    atomic_json(state_file, current)
    if changed:
        atomic_json(state / "last-delta.json", dict(generation=generation, newBoards=list(new_boards.values()),
                                                  newArchives=list(new_packages.values())))
    outcomes = []
    for digest in list(queue):
        item = queue[digest]
        if digest in known_hashes:
            del queue[digest]
            continue
        try:
            status, count = stage_package(state, item, stats)
            outcome = dict(item, status=status, signedInfCount=count)
            completed[digest] = outcome
            del queue[digest]
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
            outcome = dict(item, status="retry-pending", detail=str(error))
        outcomes.append(outcome)
        atomic_json(state_file, current)
    result = dict(status="baseline-created" if not previous else "processed", generation=generation,
                  newBoards=len(new_boards), newArchives=len(new_packages), remaining=len(queue),
                  boardReportsPending=len(board_queue), outcomes=outcomes, **counts, **stats)
    atomic_json(report, result)
    return result


NZXT_CATALOG = "https://support.nzxt.com/api/v2/help_center/en-us/sections/39003384521627/articles.json"


def nzxt_listings(catalog):
    if catalog.get("next_page"):
        raise ValueError("NZXT motherboard catalog now requires pagination")
    boards = {}
    listings = defaultdict(list)
    for article in catalog["articles"]:
        match = re.fullmatch(r"(N[0-9]+ [A-Z][A-Z0-9]+) Downloads", article["title"])
        if not match:
            continue
        model = match[1]
        support = f"https://support.nzxt.com/hc/en-us/articles/{int(article['id'])}"
        boards[model] = support
        for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", article["body"], re.I | re.S):
            cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.I | re.S)
            if len(cells) < 2:
                continue
            label = unescape(re.sub(r"<[^>]+>", " ", cells[0]))
            if not re.search(r"\b(?:wi[- ]?fi|wlan|wireless(?: lan)?)\s+driver\b", label, re.I):
                continue
            for link in re.findall(r'href="([^"]+)"', cells[1], re.I):
                url = unescape(link)
                parsed = urlsplit(url)
                if (parsed.scheme == "https" and parsed.netloc == "cdn-g.nzxt.com"
                        and parsed.path.startswith("/dl/") and parsed.path.lower().endswith((".zip", ".exe"))):
                    listings[url].append(dict(model=model, support=support, label=" ".join(label.split())))
    if not boards or not listings:
        raise ValueError("No NZXT motherboard WLAN listings were parsed")
    return boards, listings


def refresh_oem(state, known_hashes, vendor, load_catalog, *, referer=None, catalog_kind=None, backfill=False):
    state.mkdir(exist_ok=True)
    report = state / "last-run.json"
    previous = json.loads(report.read_bytes()) if report.is_file() else {}
    completed = previous.get("packages", {})
    stats = dict(newUrls=0, driverArchivesFetched=0, reusedUrls=0, baselineUrls=0, archiveEvidenceReused=0, remaining=0)
    archive_results = {}
    with TemporaryDirectory(dir=state) as scratch:
        scratch = Path(scratch)
        boards, listings, request_count = load_catalog(scratch)
        stats["catalogRequests"] = request_count
        count_field = {None: "newBoards", "laptops": "newLaptops", "devices": "newDevices"}[catalog_kind]
        stats[count_field] = len(boards.keys() - previous.get("boards", {}).keys())
        stats["catalogModels"] = len(boards)
        stats["listedUrls"] = len(listings)
        stats["newUrls"] = len(listings.keys() - completed.keys())
        stats["remaining"] = len(listings)
        for url, candidates in listings.items():
            previous_item = completed.get(url, {})
            revisions = {(row["label"], row.get("listedRevision")) for row in candidates}
            previous_revisions = {(row["label"], row.get("listedRevision"))
                                  for row in previous_item.get("listings", [])}
            status = previous_item.get("status")
            if catalog_kind and not previous and not backfill:
                completed[url] = dict(status="baseline-listed", listings=candidates)
                stats["baselineUrls"] += 1
                stats["remaining"] -= 1
                continue
            baseline_needs_package = False
            if status == "baseline-listed":
                prior_models = {(row["model"], row["support"]) for row in previous_item["listings"]}
                baseline_needs_package = backfill or any((row["model"], row["support"]) not in prior_models
                                                         for row in candidates)
            if (status not in (None, "retry-pending") and revisions <= previous_revisions
                    and not baseline_needs_package):
                completed[url]["listings"] = candidates
                stats["reusedUrls"] += 1
                stats["remaining"] -= 1
                continue
            try:
                path = scratch / "original"
                fetch(url, path, MAX_ARCHIVE, referer=referer, seconds=600)
                stats["driverArchivesFetched"] += 1
                size = path.stat().st_size
                if not 0 < size <= MAX_ARCHIVE:
                    raise ValueError("OEM archive size outside allowed range")
                digest = sha256(path)
                item = dict(vendor=vendor, url=url, sha256=digest, size=size,
                            hashSource="computed-from-oem-download", listings=candidates)
                if digest in known_hashes:
                    status, count = "already-indexed", 0
                elif digest in archive_results:
                    status, count = archive_results[digest]
                    stats["archiveEvidenceReused"] += 1
                else:
                    originals = state / "originals"
                    originals.mkdir(exist_ok=True)
                    original = originals / f"{digest}.archive"
                    path.replace(original)
                    status, count = stage_package(state, item, stats)
                    archive_results[digest] = status, count
                completed[url] = dict(item, status=status, signedInfCount=count)
            except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
                completed[url] = dict(status="retry-pending", listings=candidates, detail=str(error))
            stats["remaining"] -= completed[url]["status"] != "retry-pending"
            atomic_json(report, dict(boards=boards, packages=completed, **stats))
    atomic_json(report, dict(boards=boards, packages=completed, **stats))
    return stats


def load_nzxt(scratch):
    path = scratch / "nzxt.json"
    fetch(NZXT_CATALOG, path, 4 * 1024 * 1024)
    return (*nzxt_listings(json.loads(path.read_bytes())), 1)


EVGA_CATALOG = "https://www.evga.com/support/drivers/data.json"
EVGA_SUPPORT = "https://www.evga.com/support/drivers/index.html"


def load_evga(scratch):
    path = scratch / "evga.json"
    cache = scratch.parent / "catalog.json"
    etag = scratch.parent / "catalog.etag"
    received_etag = scratch / "catalog.etag"
    options = ["--etag-save", str(received_etag)]
    if cache.is_file() and etag.is_file():
        options += ["--etag-compare", str(etag)]
    status = fetch(EVGA_CATALOG, path, 64 * 1024 * 1024, etag_options=options)
    if status == 304:
        path = cache
    boards = {}
    listings = defaultdict(list)
    for row in json.loads(path.read_bytes())["motherboard"]:
        if row["family"] not in {"Intel Z690", "Intel Z790", "AMD X570"}:
            continue
        model = row["partNumber"]
        boards[model] = dict(model=model, support=EVGA_SUPPORT, family=row["family"])
        if row["latest"] != "1" or row["os"] not in {"Windows 10 64bit", "Windows 11"}:
            continue
        if not re.search(r"\b(?:wi[- ]?fi|wlan|wireless)\b", row["type"], re.I):
            continue
        download = row["download"]
        if not re.fullmatch(r"/filesCdn/driver/[A-Za-z0-9_./%() -]+\.(?:zip|exe)", download, re.I):
            continue
        url = "https://www.evga.com" + quote(download, safe="/%")
        listings[url].append(dict(boards[model], label=row["type"], listedWindows=row["os"],
                                  listedRevision=f"{row['version']} / {row['releaseDate']}"))
    if not boards or not listings:
        raise ValueError("No EVGA motherboard WLAN listings were parsed")
    if status != 304:
        etag.unlink(missing_ok=True)
        path.replace(cache)
        if received_etag.is_file():
            received_etag.replace(etag)
    return boards, listings, 1


COLORFUL = "https://www.colorful.cn"
COLORFUL_ID = re.compile(r"(?:[0-9]+|[a-f0-9-]{36})")


def load_colorful(scratch):
    def request(endpoint, key, **params):
        path = scratch / f"{key}.json"
        query = "?" + urlencode(params) if params else ""
        fetch(f"{COLORFUL}/Home/{endpoint}{query}", path, 4 * 1024 * 1024)
        return json.loads(path.read_bytes())

    classes = request("GetProductClassList", "classes")
    series = sorted({row["id"] for row in classes if row["parent_id"] == "84"
                     and COLORFUL_ID.fullmatch(row["id"])})
    if not series:
        raise ValueError("No Colorful motherboard series found")
    with ThreadPoolExecutor(max_workers=4) as executor:
        catalog = executor.map(lambda key: request("GetProduct", key, modelid=84, attrId=key), series)
        boards = {row["id"]: dict(model=row["name"], support=f"{COLORFUL}/home/DownLoadInfo?id={row['id']}&mid=84")
                  for rows in catalog for row in rows if COLORFUL_ID.fullmatch(row["id"])}
        if not boards:
            raise ValueError("No Colorful motherboard models found")
        # A wireless card can be factory fitted even when the product name omits Wi-Fi.
        chipset = re.compile(r"(?<![A-Z0-9])(?:A320|A520|A620|B350|B450|B550|B650E?|B840|B850|"
                             r"X370|X470|X570|X670E?|X870E?|H610|H670|H770|H810|"
                             r"B660|B760|B860|Z690|Z790|Z890)", re.I)
        wifi_ids = [key for key, board in boards.items()
                    if chipset.search(board["model"]) or re.search(r"wifi|wlan|wireless", board["model"], re.I)]
        reports = executor.map(lambda key: request("GetProductDownload", f"board-{key}", mid=84, id=key), wifi_ids)
        listings = defaultdict(list)
        for key, rows in zip(wifi_ids, reports):
            for row in rows:
                if (row["files"], row["systemnum"]) != ("2898", "2897") or row["system"] not in ("2894", "3477"):
                    continue
                if not re.search(r"wi[- ]?fi|wlan|wireless|无线|無線", row["title"], re.I):
                    continue
                parsed = urlsplit(row["fileurl"])
                if (parsed.scheme != "https" or parsed.netloc != "download.colorful.cn"
                        or not parsed.path.lower().endswith((".zip", ".exe"))):
                    continue
                url = urlunsplit(parsed._replace(path=quote(parsed.path, safe="/%")))
                listings[url].append(dict(boards[key], label=row["title"], listedRevision=row["edit_time"],
                                          listedWindows={"2894": "10", "3477": "11"}[row["system"]]))
    return boards, listings, 1 + len(series) + len(wifi_ids)


SURFACE_CATALOG = "https://learn.microsoft.com/en-us/surface/Manage-surface-driver-and-firmware-updates"
SURFACE_FAMILIES = {"Surface Pro": "windows-tablet", "Surface Go": "windows-tablet", "Surface Studio": "all-in-one"}


def load_surface(scratch):
    path = scratch / "surface.html"
    fetch(SURFACE_CATALOG, path, 4 * 1024 * 1024)
    models = {}
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", path.read_text(encoding="utf-8"), re.I | re.S):
        heading = re.match(r"\s*<td><strong>([^<]+)</strong></td>", row)
        if not heading or heading[1] not in SURFACE_FAMILIES:
            continue
        for url, identifier, name in re.findall(
            r'<a href="(https://www\.microsoft\.com/download/details\.aspx\?id=(\d+))"[^>]*>([^<]+)</a>', row
        ):
            models[identifier] = dict(model=unescape(name), deviceTags=[SURFACE_FAMILIES[heading[1]]],
                                      support=SURFACE_CATALOG, bundlePage=url, evidence="driver-firmware-bundle")
    if not models:
        raise ValueError("No Surface Pro, Go or Studio bundle links were parsed")
    return models, {}, 1


ROG_HANDHELDS = "https://rog.asus.com/gaming-handhelds/rog-ally-series/"


def load_rog_handhelds(scratch):
    path = scratch / "rog-handhelds.html"
    fetch(ROG_HANDHELDS, path, 8 * 1024 * 1024)
    pattern = (r'href="(https://rog\.asus\.com/gaming-handhelds/rog-ally/[a-z0-9-]+/)"[^>]*>'
               r'<span class="ProductResultItem__mktName[^\"]*">([^<]+)</span></a></div>\s*'
               r'<div[^>]*aria-label="([A-Z0-9_.-]+)"')
    models = {code: dict(model=unescape(name), modelCode=code, deviceTags=["windows-handheld"],
                         support=url, evidence="product-catalog")
              for url, name, code in re.findall(pattern, path.read_text(encoding="utf-8"))}
    if not models:
        raise ValueError("No ROG handheld product records were parsed")
    return models, {}, 1


def main():
    import msvcrt

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=ROOT / "artifacts/network-rescue-update")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--laptops-only", dest="scope", action="store_const", const="laptops", help="Only check laptops")
    modes.add_argument("--devices-only", dest="scope", action="store_const", const="devices", help="Only check other device categories")
    parser.set_defaults(scope="all")
    parser.add_argument("--backfill-laptops", action="store_true", help="Also download unchanged laptop baseline packages")
    parser.add_argument("--backfill-devices", action="store_true", help="Also download unchanged device baseline packages")
    args = parser.parse_args()
    with (ROOT / "docs/network-rescue-driver-index.csv").open(encoding="utf-8-sig", newline="") as source:
        known_hashes = {row["sha256"].lower() for row in csv.DictReader(source)}
    args.state.mkdir(parents=True, exist_ok=True)
    with (args.state / "update.lock").open("a+b") as lock:
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise SystemExit(f"Cannot lock the update folder: {error}") from error
        try:
            result = refresh(args.state, known_hashes, scope=args.scope)
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
            result = dict(status="failed", detail=str(error), remaining=1, boardReportsPending=0)
        print(json.dumps({k: v for k, v in result.items() if k != "outcomes"}, ensure_ascii=True), flush=True)
        oem_results = {}
        motherboard_sources = (
            ("nzxt", load_nzxt, None),
            ("colorful", load_colorful, COLORFUL + "/"),
            ("evga", load_evga, None),
        )
        laptop_sources = (
            ("panasonic", partial(load_panasonic, fetch=fetch), None),
            ("dynabook", partial(load_dynabook, fetch=fetch), None),
            ("xiaomi", partial(load_xiaomi, fetch=fetch), "https://www.mi.com/"),
            ("honor", partial(load_honor, fetch=fetch), HONOR_SUPPORT),
        )
        device_sources = (
            ("apple", partial(load_apple, fetch=fetch), None),
            ("microsoft-surface", load_surface, None),
            ("asus-rog-handhelds", load_rog_handhelds, None),
            ("tplink", partial(load_tplink, fetch=fetch), None),
        )
        for kind, sources, backfill in (("devices", device_sources, args.backfill_devices),
                                       ("laptops", laptop_sources, args.backfill_laptops),
                                       (None, motherboard_sources, False)):
            if args.scope not in ("all", kind):
                continue
            for vendor, load_catalog, referer in sources:
                try:
                    oem_results[vendor] = refresh_oem(args.state / vendor, known_hashes, vendor, load_catalog,
                                                      referer=referer, catalog_kind=kind, backfill=backfill)
                except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
                    oem_results[vendor] = dict(status="failed", detail=str(error), remaining=1)
                print(json.dumps({vendor: oem_results[vendor]}, ensure_ascii=True), flush=True)
    print(f"Report: {args.state / REPORT_FILES[args.scope]}")
    if result["remaining"] or result["boardReportsPending"] or any(row["remaining"] for row in oem_results.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
