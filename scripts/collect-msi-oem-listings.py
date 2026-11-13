"""Collect MSI per-model driver download listings for the network-rescue gap table.

MSI support pages are JavaScript shells. The page bundle at
``storage-asset.msi.com/frontend/js/components/product/support/api.js`` shows that the driver table
comes from the same-origin support API:

* ``/api/v1/product/support/os?product=<slug>&type=driver`` returns the OS selector for the exact
  product (``["Win11 64", "Win10 64", ...]``).
* ``/api/v1/product/support/panel?product=<slug>&type=driver&os=<OS label>`` returns the driver
  table for that OS. Entries carry ``download_title``, ``os``, ``download_version``,
  ``download_url`` and ``download_sha256`` and are grouped by category (LAN Drivers, On-Board
  Audio Drivers, System & Chipset Drivers, Network, Audio, Chipset, ...).
* ``/api/v1/product/support/banner?product=<family slug>`` maps the regional laptop sub-product
  slugs to their titles, e.g. ``{"Katana-GF66-12UC": "Katana GF66 12UC"}``.
* ``/api/v1/search?page=<n>&group=<8|1>&keyword=<model>`` resolves a model name to its product
  page. Motherboards use group 8, laptops group 1.

www.msi.com answers 403 to curl and Python from this host, so every request is sent through
``scripts/oem-http.mjs`` (Node's TLS stack). The bridge caches each body under
``artifacts/oem-cache/<sha1>.bin``; this script only parses that cache.

Evidence policy (strict):
* ``oem-wlan-listed``: the exact model page lists a WLAN/Wireless/Wi-Fi download whose own ``os``
  field is exactly the queried Windows x64 version. Bluetooth and wired LAN titles are ignored.
* ``oem-wlan-not-listed``: for that exact OS the populated table has LAN plus audio or chipset
  entries and no WLAN entry. A generic Killer universal package blocks the omission claim because
  it can carry Wi-Fi.
* ``oem-os-not-listed``: the exact model's OS selector omits the system while the other system's
  table is populated.
* An entry whose ``os`` field also covers another Windows version is a combined-system package and
  stays pending unless ``--allow-combined-os`` is given.
* A positive listing is only proposed/applied when the row's factory evidence (``wlanEvidence``)
  already names WLAN or a Wi-Fi module. MSI also publishes optional-module Wi-Fi packages on
  boards whose specification has no WLAN; those rows are held under ``specGated`` in the
  proposals JSON and can be released with ``--allow-spec-mismatch``.
* Empty tables, near model names, unresolved products and failed requests stay pending.

``--apply-oem-evidence`` writes the proposed statuses into the gaps CSV. Without it the script only
writes the proof table and the proposals JSON.
"""
import argparse
from collections import Counter
import csv
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import quote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "scripts" / "oem-http.mjs"
BASE = "https://www.msi.com"
SYSTEMS = (("10", "Win10 64"), ("11", "Win11 64"))
WLAN = re.compile(r"wi[- ]?fi|wlan|wireless", re.I)
BLUETOOTH = re.compile(r"bluetooth|\bbt\b", re.I)
LAN = re.compile(r"\blan\b|ethernet", re.I)
AUDIO = re.compile(r"audio|sound", re.I)
CHIPSET = re.compile(r"chipset", re.I)
KILLER_UNIVERSAL = re.compile(r"killer.*universal|universal.*killer", re.I)
DOWNLOAD_HOST = "msi.com"
MAX_SEARCH_PAGES = 3
REQUEST_CHUNK = 25
# A "populated" list for the other Windows version: a handful of real driver rows, not a partial
# table that only carries an audio add-on.
MIN_OTHER_OS_FILES = 5
PROOF_FIELDS = ["model", "platform", "windows", "supportUrl", "status", "title", "version",
                "downloadUrl", "sha256"]
CLOSABLE = {"oem-wlan-listed", "oem-wlan-not-listed", "oem-os-not-listed"}
PLATFORM_PATHS = {
    "motherboard": ("/Motherboard/",),
    "laptop": ("/Laptop/", "/Content-Creation/", "/Business-Productivity/"),
}
SEARCH_GROUP = {"motherboard": "8", "laptop": "1"}
FACTORY_WLAN = {"manual-module-candidate", "oem-spec-wlan-listed", "oem-spec-module"}


def model_key(value):
    """Exact-model key: OEM titles vary only in punctuation, HTML line breaks and a
    ``; Copilot+ PC`` suffix around the model name."""
    text = re.split(r"<", value or "", maxsplit=1)[0]
    text = text.split(";")[0]
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def api_result(payload):
    if not isinstance(payload, dict):
        return None
    if "status" in payload:
        if (payload.get("status") or {}).get("code") != 200:
            return None
        return payload.get("result")
    return payload


def os_versions(value):
    """Windows x64 versions named by an entry's own ``os`` field."""
    versions = set()
    for system, _ in SYSTEMS:
        if re.search(rf"win\s*{system}\b", value or "", re.I):
            versions.add(system)
    return versions


def is_wlan(title):
    return bool(WLAN.search(title or "")) and not BLUETOOTH.search(title or "")


def download_host(url):
    try:
        return urlsplit(url or "").hostname or ""
    except ValueError:
        return ""


def download_is_oem(url):
    host = download_host(url)
    return host == DOWNLOAD_HOST or host.endswith("." + DOWNLOAD_HOST)


def entry_sha256(entry):
    value = re.sub(r"<[^>]*>", "", entry.get("download_sha256") or "")
    value = re.sub(r"^SHA-256:\s*", "", value, flags=re.I)
    return re.sub(r"[^0-9A-Fa-f]", "", value).lower()


@dataclass
class Bridge:
    """Batch transport over scripts/oem-http.mjs with in-run caching."""
    requests: int = 0
    failures: list = field(default_factory=list)
    bodies: dict = field(default_factory=dict)

    def fetch(self, urls):
        wanted = [url for url in dict.fromkeys(urls) if url not in self.bodies]
        for start in range(0, len(wanted), REQUEST_CHUNK):
            chunk = wanted[start:start + REQUEST_CHUNK]
            self.requests += len(chunk)
            try:
                completed = subprocess.run(
                    ["node", str(BRIDGE), *chunk], cwd=str(ROOT), capture_output=True,
                    text=True, encoding="utf-8", errors="replace", timeout=600, check=False)
            except (OSError, subprocess.TimeoutExpired) as error:
                for url in chunk:
                    self.bodies[url] = None
                    self.failures.append(f"{url}: {error}")
                continue
            if completed.returncode != 0:
                for url in chunk:
                    self.bodies[url] = None
                    self.failures.append(f"{url}: bridge exit {completed.returncode}")
                continue
            try:
                entries = json.loads(completed.stdout[completed.stdout.index("["):])
            except (ValueError, json.JSONDecodeError):
                for url in chunk:
                    self.bodies[url] = None
                    self.failures.append(f"{url}: unreadable bridge output")
                continue
            found = {}
            for entry in entries:
                found[entry.get("url")] = entry
            for url in chunk:
                entry = found.get(url) or {}
                status = entry.get("status", 0)
                path = Path(entry.get("file") or "")
                if status != 200 or not path.is_file():
                    self.bodies[url] = None
                    self.failures.append(f"{url}: status {status}")
                    continue
                try:
                    self.bodies[url] = json.loads(path.read_text(encoding="utf-8", errors="replace"))
                except (ValueError, OSError) as error:
                    self.bodies[url] = None
                    self.failures.append(f"{url}: {error}")

    def payload(self, url):
        return self.bodies.get(url)


@dataclass
class Target:
    row: dict
    kind: str
    page: str = ""
    family_path: str = ""
    sub_title: str = ""
    product_slug: str = ""
    family_slug: str = ""
    support_url: str = ""
    error: str = ""
    os_result: list | None = None
    panels: dict = field(default_factory=dict)


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def pending_targets(models, limit=None):
    targets = []
    for row in models:
        if row["type"] not in SEARCH_GROUP or row["brand"] != "MSI":
            continue
        if not any(row[f"windows{system}X64Evidence"] == "pending" for system, _ in SYSTEMS):
            continue
        targets.append(Target(row=row, kind=row["type"]))
    return targets[:limit] if limit else targets


def search_url(keyword, group, page):
    return f"{BASE}/api/v1/search?page={page}&group={group}&keyword={quote(keyword)}"


def path_segment(path):
    return (path or "").rstrip("/").rsplit("/", 1)[-1]


def type_matches(kind, path):
    return any((path or "").startswith(prefix) for prefix in PLATFORM_PATHS[kind])


def product_path(item):
    """The search API also returns a support_url; keep the canonical product path."""
    path = item.get("url") or item.get("support_url") or ""
    path = path.split("?")[0].rstrip("/")
    if path.endswith("/support"):
        path = path[:-len("/support")]
    return path


def pick_candidate(results, target):
    typed = [item for item in results or []
             if isinstance(item, dict) and type_matches(target.kind, item.get("url"))]
    wanted = model_key(target.row["model"])
    sub_matches = []
    for item in typed:
        for sub in item.get("sub_product") or []:
            if model_key(sub) == wanted:
                sub_matches.append((item, sub))
    if sub_matches:
        item, sub = sub_matches[0]
        return product_path(item), sub, item.get("title") or ""
    for item in typed:
        if model_key(item.get("title")) == wanted:
            return product_path(item), "", item.get("title") or ""
    return None


def discover(bridge, targets):
    """Resolve each model to an MSI product page, paginating the search only as needed."""
    state = {id(target): {"last": 1, "done": False} for target in targets}
    for page in range(1, MAX_SEARCH_PAGES + 1):
        batch = []
        for target in targets:
            info = state[id(target)]
            if info["done"] or page > info["last"]:
                continue
            batch.append((target, search_url(target.row["model"],
                                             SEARCH_GROUP[target.kind], page)))
        if not batch:
            break
        bridge.fetch([url for _, url in batch])
        for target, url in batch:
            info = state[id(target)]
            payload = api_result(bridge.payload(url))
            if not isinstance(payload, dict):
                info["done"] = True
                target.error = "search-request-failed"
                continue
            info["last"] = max(1, int((payload.get("pageInfo") or {}).get("last_page") or 1))
            found = pick_candidate(payload.get("list") or [], target)
            if found:
                path, sub_title, _ = found
                target.page = path
                target.family_path = path.split("?")[0].rstrip("/")
                target.sub_title = sub_title
                info["done"] = True
            elif page >= min(info["last"], MAX_SEARCH_PAGES):
                info["done"] = True
                target.error = "no-exact-product-page"
    # A literal "+" in a model name makes the search endpoint answer 500 for some names. Retry
    # with the sign spelled out as a space; matching still uses the original model name.
    retry = [target for target in targets if target.error == "search-request-failed"]
    if retry:
        urls = {id(target): search_url(re.sub(r"\s+", " ", target.row["model"].replace("+", " ")),
                                       SEARCH_GROUP[target.kind], 1) for target in retry}
        bridge.fetch(list(urls.values()))
        for target in retry:
            payload = api_result(bridge.payload(urls[id(target)]))
            if not isinstance(payload, dict):
                continue
            found = pick_candidate(payload.get("list") or [], target)
            if found:
                path, sub_title, _ = found
                target.page = path
                target.family_path = path.split("?")[0].rstrip("/")
                target.sub_title = sub_title
                target.error = ""
            else:
                target.error = "no-exact-product-page"
    for target in targets:
        if not target.page and not target.error:
            target.error = "no-exact-product-page"


def source_fallback(bridge, target):
    """Archived products are sometimes missing from search but named in the row's source URL."""
    path = urlsplit(target.row.get("source") or "").path
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2 or parts[0] not in ("Motherboard", "Laptop", "Content-Creation",
                                         "Business-Productivity"):
        return
    family_path = f"/{parts[0]}/{parts[1]}"
    slug = parts[1]
    url = f"{BASE}/api/v1/product/support/banner?product={quote(slug)}"
    bridge.fetch([url])
    banner = api_result(bridge.payload(url))
    if not isinstance(banner, dict):
        return
    wanted = model_key(target.row["model"])
    for sub_slug, title in (banner.get("sub_product_list") or {}).items():
        if model_key(title) == wanted:
            target.page = f"{family_path}?sub_product={sub_slug}"
            target.family_path = family_path
            target.sub_title = title
            target.error = ""
            return
    if model_key(banner.get("title")) == wanted:
        target.page = family_path
        target.family_path = family_path
        target.sub_title = ""
        target.error = ""


def resolve_slugs(bridge, targets):
    for target in targets:
        if target.error and target.error != "no-exact-product-page":
            continue
        if not target.page:
            source_fallback(bridge, target)
        if not target.page:
            continue
        target.family_slug = path_segment(target.family_path)
        target.product_slug = target.family_slug
    # Regional laptop SKUs live under a family page; the banner lists their exact slugs.
    families = {}
    for target in targets:
        if target.page and target.sub_title:
            families.setdefault(target.family_slug, target.family_path)
    urls = {slug: f"{BASE}/api/v1/product/support/banner?product={quote(slug)}"
            for slug in families}
    bridge.fetch(list(urls.values()))
    for target in targets:
        if not target.page or target.error:
            continue
        if not target.sub_title:
            continue
        banner = api_result(bridge.payload(urls[target.family_slug]))
        mapping = (banner or {}).get("sub_product_list") or {}
        match = [slug for slug, title in mapping.items()
                 if model_key(title) == model_key(target.sub_title)]
        if not match:
            target.error = "sub-product-unresolved"
            continue
        target.product_slug = match[0]
    for target in targets:
        if target.error:
            continue
        target.support_url = f"{BASE}{target.family_path}/support"
        if target.sub_title:
            target.support_url += f"?sub_product={quote(target.product_slug)}"


def fetch_listings(bridge, targets):
    """OS selector for each resolved product, then the panel for every listed system."""
    resolved = [target for target in targets if target.product_slug and not target.error]
    slugs = list(dict.fromkeys(target.product_slug for target in resolved))
    os_urls = {slug: f"{BASE}/api/v1/product/support/os?product={quote(slug)}&type=driver"
               for slug in slugs}
    bridge.fetch(list(os_urls.values()))
    for target in resolved:
        result = api_result(bridge.payload(os_urls[target.product_slug]))
        if not isinstance(result, list):
            target.error = "os-selector-request-failed"
            continue
        target.os_result = [label for label in result if isinstance(label, str)]

    panels = {}
    for target in resolved:
        if target.error or target.os_result is None:
            continue
        for _, label in SYSTEMS:
            if label in target.os_result:
                panels[(target.product_slug, label)] = (
                    f"{BASE}/api/v1/product/support/panel?product={quote(target.product_slug)}"
                    f"&type=driver&os={quote(label)}")
    bridge.fetch(list(panels.values()))
    for target in resolved:
        if target.error or target.os_result is None:
            continue
        for _, label in SYSTEMS:
            if label in target.os_result:
                target.panels[label] = bridge.payload(panels[(target.product_slug, label)])


def table_items(panel):
    """Flatten a panel result into (category, entry) pairs."""
    result = api_result(panel)
    if not isinstance(result, dict):
        return None, []
    downloads = result.get("downloads")
    if not isinstance(downloads, dict):
        return result, []
    items = []
    for category, entries in downloads.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and entry.get("download_title"):
                items.append((category, entry))
    return result, items


def table_populated(panel, system):
    """A real per-system table has LAN plus an audio or chipset entry for that system."""
    _, items = table_items(panel)
    has_lan = has_audio = False
    for category, entry in items:
        versions = os_versions(entry.get("os"))
        if system not in versions:
            continue
        title = entry.get("download_title") or ""
        if is_wlan(title):
            continue
        if BLUETOOTH.search(title):
            continue
        if LAN.search(title) or LAN.search(category):
            has_lan = True
        if AUDIO.search(category) or CHIPSET.search(category) or AUDIO.search(title):
            has_audio = True
    return has_lan and has_audio


def table_substantive(panel, system):
    """Fewer requirements than table_populated: used to prove the other OS is present at all."""
    _, items = table_items(panel)
    count = 0
    has_kind = False
    for category, entry in items:
        if system not in os_versions(entry.get("os")):
            continue
        count += 1
        title = entry.get("download_title") or ""
        if (LAN.search(title) or LAN.search(category) or AUDIO.search(category)
                or CHIPSET.search(category) or is_wlan(title)):
            has_kind = True
    return count >= MIN_OTHER_OS_FILES and has_kind


def judge_listing(system, panel, allow_combined, model_title):
    """Return (status, title, version, url, sha256) for one system of one model."""
    if panel is None:
        return "request-failed", "", "", "", ""
    result, items = table_items(panel)
    if result is None:
        return "empty-driver-table", "", "", "", ""
    if model_key(result.get("title")) != model_key(model_title):
        return "title-mismatch", "", "", "", ""
    if not items:
        return "empty-driver-table", "", "", "", ""

    wlan = []
    killer = False
    has_lan = has_audio = False
    for category, entry in items:
        versions = os_versions(entry.get("os"))
        if system not in versions:
            continue
        title = entry.get("download_title") or ""
        if is_wlan(title):
            wlan.append(entry)
            continue
        if KILLER_UNIVERSAL.search(title):
            killer = True
        if LAN.search(title) or LAN.search(category):
            has_lan = True
        if AUDIO.search(category) or CHIPSET.search(category) or AUDIO.search(title):
            has_audio = True

    exact = [entry for entry in wlan if os_versions(entry.get("os")) == {system}]
    combined = [entry for entry in wlan if len(os_versions(entry.get("os"))) > 1]
    chosen = None
    if exact:
        chosen = exact[0]
    elif combined and allow_combined:
        chosen = combined[0]
    if chosen:
        url = chosen.get("download_url") or ""
        sha = entry_sha256(chosen)
        if not download_is_oem(url):
            return "non-oem-download-host", chosen.get("download_title") or "", \
                chosen.get("download_version") or "", url, sha
        return ("oem-wlan-listed", chosen.get("download_title") or "",
                chosen.get("download_version") or "", url, sha)
    if combined:
        entry = combined[0]
        return ("combined-system-package", entry.get("download_title") or "",
                entry.get("download_version") or "", entry.get("download_url") or "",
                entry_sha256(entry))
    if killer:
        return "generic-killer-package", "", "", "", ""
    if has_lan and has_audio:
        return "oem-wlan-not-listed", "", "", "", ""
    return "no-valid-lan-list", "", "", "", ""


def classify(target, allow_combined):
    """One proof row per pending system of one model."""
    base = dict(model=target.row["model"], platform=target.row["platform"],
                supportUrl=target.support_url)
    model_title = target.sub_title or target.row["model"]
    proof = []
    for system, label in SYSTEMS:
        entry = dict(base, windows=label, status="", title="", version="", downloadUrl="",
                     sha256="")
        if target.error:
            entry["status"] = target.error
        elif target.os_result is None:
            entry["status"] = "os-selector-request-failed"
        elif not target.os_result:
            entry["status"] = "os-selector-empty"
        elif not any(other in target.os_result for _, other in SYSTEMS):
            entry["status"] = "no-windows10-11-entry"
        elif label not in target.os_result:
            other_label = next(other for other_system, other in SYSTEMS
                               if other_system != system)
            other_system = next(other_system for other_system, other in SYSTEMS
                                if other_system != system)
            other_panel = target.panels.get(other_label)
            if other_label in target.os_result and table_substantive(other_panel, other_system):
                entry["status"] = "oem-os-not-listed"
            else:
                entry["status"] = "os-selector-missing-system"
        else:
            status, title, version, url, sha = judge_listing(
                system, target.panels.get(label), allow_combined, model_title)
            entry.update(status=status, title=title, version=version, downloadUrl=url,
                         sha256=sha)
        proof.append(entry)
    return proof


def spec_allows_positive(target):
    """Mirror the factory-spec gate of the existing MSI collector.

    MSI's driver tab can list an Intel/Killer Wi-Fi package for a board whose factory
    specification has no WLAN or Wi-Fi module (optional M.2 module support or shared board data).
    A positive listing is only applied when the specification already names WLAN or a module;
    otherwise it is recorded in the proof and held for review.
    """
    return target.kind != "motherboard" or target.row.get("wlanEvidence") in FACTORY_WLAN


def update_evidence(target, proof, allow_spec_mismatch):
    """Apply the closable proof rows to the still-pending cells of one target."""
    row = target.row
    updates = Counter()
    by_system = {entry["windows"]: entry for entry in proof}
    for system, label in SYSTEMS:
        field = f"windows{system}X64Evidence"
        entry = by_system.get(label) or {}
        if row[field] != "pending" or entry.get("status") not in CLOSABLE:
            continue
        if (entry["status"] == "oem-wlan-listed" and not allow_spec_mismatch
                and not spec_allows_positive(target)):
            continue
        row[field] = entry["status"]
        updates[f"{system}:{entry['status']}"] += 1
    return updates


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


def write_outputs(output, proposals_path, proof, targets, bridge, elapsed, allow_combined,
                  allow_spec_mismatch):
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, PROOF_FIELDS)
        writer.writeheader()
        writer.writerows(proof)
    temporary.replace(output)

    proposed, pending_rows, spec_gated = [], [], []
    for target in targets:
        for entry in target.proof:
            system = "10" if entry["windows"] == "Win10 64" else "11"
            current = target.row[f"windows{system}X64Evidence"]
            if current != "pending":
                continue
            if entry["status"] in CLOSABLE:
                item = {
                    "type": target.kind, "brand": "MSI", "model": target.row["model"],
                    "windows": system,
                    "os": entry["windows"], "current": current,
                    "proposed": entry["status"],
                    "evidence": {
                        "url": target.support_url or target.row.get("source", ""),
                        "title": entry["title"], "version": entry["version"],
                        "download": entry["downloadUrl"],
                    },
                }
                if (entry["status"] == "oem-wlan-listed" and not allow_spec_mismatch
                        and not spec_allows_positive(target)):
                    item["heldReason"] = (f"wlanEvidence={target.row.get('wlanEvidence') or 'empty'}"
                                          " does not list WLAN or a Wi-Fi module")
                    spec_gated.append(item)
                    pending_rows.append({
                        "type": target.kind, "brand": "MSI", "model": target.row["model"],
                        "windows": system, "os": entry["windows"],
                        "reason": "oem-wlan-listed-spec-gap", "title": entry["title"],
                    })
                else:
                    proposed.append(item)
            else:
                pending_rows.append({
                    "type": target.kind, "brand": "MSI", "model": target.row["model"],
                    "windows": system,
                    "os": entry["windows"], "reason": entry["status"],
                    "title": entry["title"],
                })
    payload = {
        "brand": "MSI",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "allowCombinedOs": allow_combined,
        "allowSpecMismatch": allow_spec_mismatch,
        "summary": {
            "modelsQueried": len(targets),
            "cellsExamined": len(proof),
            "proposedClosures": len(proposed),
            "byProposedStatus": dict(Counter(item["proposed"] for item in proposed)),
            "specGatedListings": len(spec_gated),
            "byPendingReason": dict(Counter(item["reason"] for item in pending_rows)),
            "requests": bridge.requests,
            "requestFailures": len(bridge.failures),
            "elapsedSeconds": round(elapsed, 1),
        },
        "proposals": proposed,
        "specGated": spec_gated,
        "leftPending": pending_rows,
    }
    proposals_path.parent.mkdir(parents=True, exist_ok=True)
    proposals_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("gaps", type=Path, help="docs/network-rescue-model-gaps.csv")
    parser.add_argument("output", type=Path, help="proof CSV to write")
    parser.add_argument("--proposals", type=Path,
                        help="proposals JSON (default: msi-proposals.json next to the output)")
    parser.add_argument("--apply-oem-evidence", action="store_true",
                        help="write the proposed statuses into the gaps CSV")
    parser.add_argument("--allow-combined-os", action="store_true",
                        help="accept WLAN entries whose os field also names another Windows version")
    parser.add_argument("--allow-spec-mismatch", action="store_true",
                        help="propose/apply a positive listing even when the row's wlanEvidence does "
                             "not name WLAN or a module (default: hold for review)")
    parser.add_argument("--limit", type=int, help="only examine the first N pending models")
    args = parser.parse_args()

    started = time.monotonic()
    raw_before = args.gaps.read_bytes()
    models = read_csv(args.gaps)
    targets = pending_targets(models, args.limit)
    if not targets:
        print("No pending MSI rows to examine.")
        return 0
    bridge = Bridge()
    print(f"Examining {len(targets)} pending MSI models ...")
    discover(bridge, targets)
    resolve_slugs(bridge, targets)
    fetch_listings(bridge, targets)

    proof = []
    for target in targets:
        target.proof = classify(target, args.allow_combined_os)
        proof.extend(target.proof)
    elapsed = time.monotonic() - started

    proposals_path = args.proposals or args.output.with_name("msi-proposals.json")
    payload = write_outputs(args.output, proposals_path, proof, targets, bridge,
                            elapsed, args.allow_combined_os, args.allow_spec_mismatch)
    summary = payload["summary"]
    print(f"Proof rows: {len(proof)}")
    print("Proof statuses:", dict(Counter(entry["status"] for entry in proof)))
    print(f"Proposed closures: {summary['proposedClosures']} "
          f"{summary['byProposedStatus']}")
    if summary["specGatedListings"]:
        print(f"Positive listings held by the factory-spec gate: "
              f"{summary['specGatedListings']} (see specGated in the proposals JSON)")
    print(f"Requests: {bridge.requests}, failures: {len(bridge.failures)}, "
          f"elapsed: {elapsed:.1f}s")
    unresolved = [target.row["model"] for target in targets if target.error]
    if unresolved:
        print(f"Unresolved models ({len(unresolved)}): {', '.join(unresolved[:10])}"
              + (" ..." if len(unresolved) > 10 else ""))
    changed = args.gaps.read_bytes() != raw_before
    if changed and not args.apply_oem_evidence:
        print("WARNING: the gaps CSV changed during this run; the outputs describe the snapshot "
              "read at start, not the current file.")
    if args.apply_oem_evidence:
        updates = Counter()
        for target in targets:
            if target.error:
                continue
            updates.update(update_evidence(target, target.proof, args.allow_spec_mismatch))
        if updates:
            write_models(args.gaps, models)
        print("Applied to gaps CSV:", dict(updates))
    else:
        print("Proof table and proposals written; gaps CSV untouched "
              "(pass --apply-oem-evidence to write it).")
    if bridge.failures:
        print("First request failures:")
        for failure in bridge.failures[:5]:
            print(" ", failure)
    if changed and not args.apply_oem_evidence:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
