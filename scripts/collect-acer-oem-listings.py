"""Collect Acer per-model driver listings for the pending laptop cells of the gaps table.

The Acer support site is a SPA that loads its driver list from a same-origin JSON endpoint
(``POST /us-en/DynamicContent/GetDriversAndManuals`` with ``{"ModelName": <code>, "Local": "en-us"}``).
The endpoint sits behind Akamai: a bare POST is denied, but the cookies from a GET of the model's
support page plus a short settle time are accepted. ``scripts/oem-http.mjs --post-with-session``
performs that warm-up and POST; this collector only parses the cached JSON body. Each driver file
carries an ``oss`` code (10M1 = Windows 10 x64, 11M1 = Windows 11 x64), so one listing can cover
both systems. Every download link names the product in ``Step3``; it must match the queried model,
because the endpoint can also return a -G2/G sibling.

Outcomes per exact model and system:

* oem-wlan-listed: the exact model lists a Wireless LAN driver for that system.
* oem-wlan-not-listed: the exact model lists LAN and audio or chipset files for that system but no
  Wireless LAN file. It records the omission, not system incompatibility.
* oem-os-not-listed: the exact model lists at least MIN_OTHER_OS_FILES files for the other system
  and none for this one.

Near matches, empty or short lists, files tagged with several systems, and series-level rows stay
pending. Series rows have no exact model code, so the API only returns one arbitrary family SKU;
they are reported with a reason instead of a proposal.

``sha256`` stays empty: this collector records the listing (title, version, download URL), not a
downloaded package.

Usage:
    python scripts/collect-acer-oem-listings.py docs/network-rescue-model-gaps.csv \\
        artifacts/network-rescue-handoff/acer-oem-proof.csv
    python scripts/collect-acer-oem-listings.py ... --apply-oem-evidence

``--apply-oem-evidence`` rewrites the evidence columns of the gaps table in place; the default run
only writes the proof CSV (one row per queried model and pending system) and the proposals JSON
(with a reason for every cell that stays pending).
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import parse_qs, quote

ROOT = Path(__file__).resolve().parent.parent
BRIDGE = ROOT / "scripts" / "oem-http.mjs"
API_URL = "https://www.acer.com/us-en/DynamicContent/GetDriversAndManuals"
SUPPORT_URL = "https://www.acer.com/us-en/support/product-support/{}"
LOCAL = "en-us"
SYSTEMS = ("10", "11")
OSS = {"10": "10M1", "11": "11M1"}
SYSTEM_NAME = {"10": "Windows 10 x64", "11": "Windows 11 x64"}
# A list this long for the other system shows the page is populated, not truncated or empty.
MIN_OTHER_OS_FILES = 10
FIELDS = ["model", "windows", "supportUrl", "status", "title", "version", "downloadUrl", "sha256", "step3"]
CLOSING = {"oem-wlan-listed", "oem-wlan-not-listed", "oem-os-not-listed"}
# Acer model codes: A114-61, 311R-31, P40-41-G2, SFA16-I31T, SP513-55NA. Series-only names such as
# "TravelMate P2" or "Aspire 14 AI" have no hyphenated code and are not queried.
CODE_RE = re.compile(r"(?<![A-Za-z0-9])((?:[A-Z]{1,5}\d{2,4}[A-Z]{0,3}|\d{3}[A-Z]{1,3})(?:-[A-Z0-9]{1,6}){1,3})(?![A-Za-z0-9])")
LED = re.compile(r"\bLED\b", re.I)


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        writer.writerows(rows)


def model_codes(model):
    """Exact Acer model codes named by a row; two codes mean the row is ambiguous."""
    return [code.upper() for code in CODE_RE.findall(model)]


def normalize(text):
    return re.sub(r"\s+", " ", (text or "").replace("_", " ")).strip().upper()


def mentions(text, code):
    """True when the code appears as a whole token, so B311-32 never matches B311-32G."""
    if not code:
        return False
    return re.search(rf"(?<![A-Z0-9-]){re.escape(code.upper())}(?![A-Z0-9-])",
                     normalize(text)) is not None


def split_oss(value):
    return [part.strip() for part in re.split(r"[;|]", value or "") if part.strip()]


def is_wlan(item):
    category = (item.get("category") or "").strip().lower()
    name = item.get("fileName") or ""
    if "bluetooth" in category or "led" in category or LED.search(name):
        return False
    return category == "wireless lan" or name.lower().startswith(("wireless lan", "wlan_"))


def is_lan(item):
    category = (item.get("category") or "").strip().lower()
    return category in {"lan", "ethernet", "gbe"} or (item.get("fileName") or "").lower().startswith("lan_")


def is_audio_or_chipset(item):
    category = (item.get("category") or "").strip().lower()
    return category.startswith("audio") or category == "chipset"


def step3_of(item):
    link = item.get("link") or ""
    if "?" not in link:
        return ""
    values = parse_qs(link.split("?", 1)[1]).get("Step3") or []
    return values[0].strip() if values else ""


def download_url(item):
    link = item.get("link") or ""
    if not link:
        return ""
    return "https://global-download.acer.com/" + quote(link, safe="/:?&=+%,._-")


def newest(files):
    def key(item):
        try:
            return datetime.strptime(item.get("date") or "", "%Y/%m/%d")
        except ValueError:
            return datetime.min
    return max(files, key=key)


def parse_hits(payload):
    """Flatten an exact hit into driver files, and remember the hit-level OS markers."""
    hits = []
    for hit in payload.get("hits") or []:
        source = hit.get("_source") or {}
        try:
            details = json.loads(source.get("global_download_details") or "{}")
        except json.JSONDecodeError:
            details = {}
        driver = details.get("driver") or {}
        files = [item for item in driver.get("files") or [] if isinstance(item, dict)]
        hits.append({
            "title": source.get("title") or "",
            "description": source.get("description") or "",
            "productType": source.get("product_type") or "",
            "itemType": source.get("itemtype") or "",
            "files": files,
            "step3": next((step3_of(item) for item in files if step3_of(item)), ""),
        })
    return hits


def classify_hit(hit, files_by_system, combined_by_system):
    result = {}
    for system in SYSTEMS:
        own = files_by_system[system]
        other = files_by_system["11" if system == "10" else "10"]
        item = {"fileCount": len(own), "otherFileCount": len(other), "step3": hit["step3"]}
        wlan = [file for file in own if is_wlan(file)]
        if wlan:
            top = newest(wlan)
            item.update(status="oem-wlan-listed", title=top.get("fileName") or "",
                        version=top.get("version") or "", date=top.get("date") or "",
                        downloadUrl=download_url(top), step3=step3_of(top) or hit["step3"])
        elif combined_by_system[system]:
            # A file tagged for several systems can hide the WLAN row; such a list only proves a
            # positive listing, never an omission.
            item["status"] = "combined-system-files"
        elif own:
            if any(is_lan(file) for file in own) and any(is_audio_or_chipset(file) for file in own):
                item.update(status="oem-wlan-not-listed",
                            step3=next((step3_of(file) for file in own if step3_of(file)), hit["step3"]))
            else:
                item["status"] = "short-list"
        elif len(other) >= MIN_OTHER_OS_FILES:
            item.update(status="oem-os-not-listed",
                        step3=next((step3_of(file) for file in other if step3_of(file)), hit["step3"]))
        else:
            item["status"] = "support-list-empty"
        result[system] = item
    return result


def step3_matches(hit, code):
    """Step3 must name the same product, not a -G2/G sibling.

    Acer abbreviates some product names in Step3 (EX215-24 is "EXTENSA 215-24"), so the hit's own
    title/description is accepted as the reference as well; the title itself must still match code.
    """
    value = hit["step3"]
    if not value:
        return True
    return any(mentions(value, candidate) for candidate in (code, hit["title"], hit["description"]))


def classify(payload, code):
    """Return per-system evidence for the exact model; only exact hits contribute."""
    hits = parse_hits(payload)
    exact = [hit for hit in hits if mentions(hit["title"], code) or mentions(hit["description"], code)]
    exact = [hit for hit in exact if step3_matches(hit, code)]
    if not exact:
        status = "near-model-match" if hits else "support-list-empty"
        titles = [hit["title"] for hit in hits if hit["title"]][:3]
        return {system: {"status": status, "fileCount": 0, "otherFileCount": 0, "step3": "",
                         "observedTitles": titles, "hasHits": bool(hits)}
                for system in SYSTEMS}
    files_by_system = {system: [] for system in SYSTEMS}
    combined_by_system = {system: False for system in SYSTEMS}
    step3 = next((hit["step3"] for hit in exact if hit["step3"]), "")
    for hit in exact:
        for item in hit["files"]:
            codes = split_oss(item.get("oss"))
            if len(codes) == 1 and codes[0] in OSS.values():
                system = next(key for key, value in OSS.items() if value == codes[0])
                files_by_system[system].append(item)
            elif len(codes) > 1:
                for system, oss in OSS.items():
                    if oss in codes:
                        combined_by_system[system] = True
    result = classify_hit({"files": [item for hit in exact for item in hit["files"]],
                           "productType": " ".join(hit["productType"] for hit in exact),
                           "step3": step3}, files_by_system, combined_by_system)
    if not any(hit["files"] for hit in exact) and not step3:
        for system in SYSTEMS:
            result[system]["status"] = "support-list-empty"
    for system in SYSTEMS:
        result[system]["modelTitle"] = exact[0]["title"]
        result[system]["hasHits"] = True
    return result


def bridge_query(code):
    warm = SUPPORT_URL.format(code)
    body = json.dumps({"ModelName": code, "Local": LOCAL})
    try:
        proc = subprocess.run(
            ["node", str(BRIDGE), "--post-with-session", warm, API_URL, body],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=180)
    except (OSError, subprocess.TimeoutExpired) as error:
        return warm, {"status": 0, "error": f"bridge error: {error}"}
    try:
        result = json.loads(proc.stdout)[0]
    except (json.JSONDecodeError, IndexError):
        return warm, {"status": 0, "error": (proc.stderr or proc.stdout or "bridge failed")[:300]}
    if result.get("status") != 200:
        return warm, {"status": result.get("status", 0), "error": f"HTTP {result.get('status')}"}
    try:
        payload = json.loads(Path(result["file"]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return warm, {"status": result["status"], "error": f"unreadable body: {error}"}
    return warm, {"status": 200, "payload": payload}


def build_entries(rows, query_cache):
    """Classify every pending row and system; keep the per-row evidence plus a pending reason."""
    entries = []
    for row in rows:
        codes = model_codes(row["model"])
        series = row.get("wlanEvidence") == "oem-series-catalog"
        for system in SYSTEMS:
            field = f"windows{system}X64Evidence"
            if row[field] != "pending":
                continue
            base = {"type": row["type"], "brand": row["brand"], "model": row["model"],
                    "windows": system, "current": row[field], "source": row["source"]}
            if not codes:
                entries.append(dict(base, status="no-exact-model-code",
                                    reason="series-level catalogue row names no exact model code; a "
                                           "series query only returns one arbitrary family SKU"))
                continue
            if len(codes) > 1:
                entries.append(dict(base, status="ambiguous-model-code",
                                    reason="row names " + " / ".join(codes) + "; a single listing "
                                           "cannot be attributed to the row"))
                continue
            code = codes[0]
            record = query_cache.get(code) or {}
            if record.get("status") != 200:
                entries.append(dict(base, status="api-error", code=code,
                                    reason=f"listing request failed: {record.get('error', 'unknown')}"))
                continue
            evidence = classify(record["payload"], code)[system]
            entry = dict(base, status=evidence["status"], code=code,
                         supportUrl=SUPPORT_URL.format(code), evidence=evidence,
                         seriesRow=series)
            if evidence["status"] not in CLOSING:
                entry["reason"] = pending_reason(evidence, code, series)
            entries.append(entry)
    return entries


def pending_reason(evidence, code, series):
    status = evidence["status"]
    if status == "near-model-match":
        titles = ", ".join(evidence.get("observedTitles") or []) or "unknown titles"
        return f"API returned near matches only for {code} ({titles})"
    if status == "combined-system-files":
        return "files are tagged with several systems, so an omission cannot be proven"
    if status == "support-list-empty":
        if evidence.get("hasHits"):
            return "exact model's listing has no driver files"
        return "exact model code returns no driver listing"
    if status == "short-list":
        return "exact model's list is too short to prove a populated listing"
    return status


def to_proposals(entries):
    proposals = []
    pending = []
    for entry in entries:
        evidence = entry.get("evidence") or {}
        if entry["status"] in CLOSING:
            proposals.append({
                "type": entry["type"],
                "brand": entry["brand"],
                "model": entry["model"],
                "windows": entry["windows"],
                "current": entry["current"],
                "proposed": entry["status"],
                "evidence": {
                    "supportUrl": entry["supportUrl"],
                    "queriedModel": entry["code"],
                    "modelTitle": evidence.get("modelTitle") or "",
                    "title": evidence.get("title") or "",
                    "version": evidence.get("version") or "",
                    "downloadUrl": evidence.get("downloadUrl") or "",
                    "sha256": "",
                    "step3": evidence.get("step3") or "",
                    "systemFileCount": evidence.get("fileCount", 0),
                    "otherSystemFileCount": evidence.get("otherFileCount", 0),
                    "seriesRow": entry["seriesRow"],
                },
            })
        else:
            pending.append({
                "type": entry["type"],
                "brand": entry["brand"],
                "model": entry["model"],
                "windows": entry["windows"],
                "current": entry["current"],
                "reason": entry.get("reason") or entry["status"],
                "evidence": {
                    "queriedModel": entry.get("code") or "",
                    "supportUrl": entry.get("supportUrl") or "",
                    "catalogUrl": entry.get("source") or "",
                    "status": entry["status"],
                    "observedTitles": evidence.get("observedTitles") or [],
                },
            })
    return proposals, pending


def apply_oem_evidence(path, models, proposals):
    updates = Counter()
    by_cell = {(item["model"], item["windows"]): item["proposed"] for item in proposals}
    for row in models:
        if row["brand"] != "Acer":
            continue
        for system in SYSTEMS:
            field = f"windows{system}X64Evidence"
            status = by_cell.get((row["model"], system))
            if row[field] == "pending" and status:
                row[field] = status
                updates[f"{system}:{status}"] += 1
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
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", type=Path, help="gaps CSV")
    parser.add_argument("output", type=Path, help="proof CSV")
    parser.add_argument("--proposals", type=Path,
                        default=ROOT / "artifacts" / "network-rescue-handoff" / "acer-proposals.json")
    parser.add_argument("--apply-oem-evidence", action="store_true")
    args = parser.parse_args()
    models = read_csv(args.models)
    pending = [row for row in models if row["brand"] == "Acer" and row.get("type") == "laptop"
               and "pending" in (row["windows10X64Evidence"], row["windows11X64Evidence"])]
    query_codes = []
    for row in pending:
        codes = model_codes(row["model"])
        if len(codes) == 1 and codes[0] not in query_codes:
            query_codes.append(codes[0])
    started = time.time()
    cache = {}
    for index, code in enumerate(query_codes, 1):
        warm, record = bridge_query(code)
        cache[code] = record
        state = record.get("status") if record.get("status") != 200 else "ok"
        print(f"[{index}/{len(query_codes)}] {code} {state}", flush=True)
    elapsed = time.time() - started
    entries = build_entries(pending, cache)
    proof = []
    for entry in entries:
        if not entry.get("code"):
            # Series and ambiguous rows have no exact model to query; the proposals JSON carries
            # their reason, the proof table only holds actual listing lookups.
            continue
        evidence = entry.get("evidence") or {}
        proof.append({
            "model": entry["model"],
            "windows": entry["windows"],
            "supportUrl": entry.get("supportUrl") or entry["source"],
            "status": entry["status"],
            "title": evidence.get("title") or "",
            "version": evidence.get("version") or "",
            "downloadUrl": evidence.get("downloadUrl") or "",
            "sha256": "",
            "step3": evidence.get("step3") or "",
        })
    write_csv(args.output, FIELDS, proof)
    proposals, left_pending = to_proposals(entries)
    report = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "brand": "Acer",
        "sourceCsv": str(args.models),
        "collector": "scripts/collect-acer-oem-listings.py",
        "systems": [SYSTEM_NAME[system] for system in SYSTEMS],
        "modelsQueried": query_codes,
        "requests": {"bridgeCalls": len(query_codes),
                     "httpGets": len(query_codes), "httpPosts": len(query_codes),
                     "httpRequests": 2 * len(query_codes)},
        "elapsedSeconds": round(elapsed, 1),
        "proposals": proposals,
        "pending": left_pending,
    }
    args.proposals.parent.mkdir(parents=True, exist_ok=True)
    args.proposals.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Models queried:", len(query_codes))
    print("Proof statuses:", dict(Counter((entry["windows"], entry["status"]) for entry in entries)))
    print("Proposed closures:", dict(Counter((entry["windows"], entry["status"]) for entry in entries
                                             if entry["status"] in CLOSING)))
    print("Left pending:", dict(Counter((entry["windows"], entry["status"]) for entry in entries
                                        if entry["status"] not in CLOSING)))
    print(f"Elapsed: {elapsed:.1f}s; bridge calls: {len(query_codes)}")
    if args.apply_oem_evidence:
        print("OEM listing updates:", apply_oem_evidence(args.models, models, proposals))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
