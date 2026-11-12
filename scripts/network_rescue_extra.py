"""Additional original-equipment support catalogs for network rescue."""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from html import unescape
import json
import re
from urllib.parse import quote, urlencode, urlsplit, urlunsplit


DLINK_SUPPORT = "https://support.dlink.com"
DLINK_CATALOG = f"{DLINK_SUPPORT}/allpro.aspx"
ROWS = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.I | re.S)
PRODUCT_LINK = re.compile(r'<a\b[^>]*class="aRedirect"[^>]*>([^<]+)</a>', re.I)
DLINK_DRIVER_SAMPLE = {"AE65U", "DUB-1312", "DUB-E100", "DUB-E250", "DWA-181-US", "DWA-X1850-B1", "DWA-X3000"}
REVISION_SELECT = re.compile(r'<select\b[^>]*id="ddlHardWare"[^>]*>(.*?)</select>', re.I | re.S)
REVISION_OPTION = re.compile(r'<option\b[^>]*value="([0-9]+)"[^>]*>\s*([A-Z0-9]+)\s*</option>', re.I)
WINDOWS_TITLE = re.compile(r"\b(?:win(?:dows)?)\s*(\d{1,2}(?:\s*[/,&+]\s*\d{1,2})*)", re.I)


def dlink_adapter_kind(model, description):
    if not re.search(r"\b(?:adapter|card|dongle)\b", description, re.I):
        return None
    wireless = re.search(r"\b(?:wireless|wi-fi|wlan)\b", description, re.I)
    ethernet = re.search(r"\bethernet\b", description, re.I) or model.startswith("DGE-")
    if re.search(r"\bUSB\b", description, re.I):
        if wireless:
            return "usb-wifi"
        if ethernet and re.search(r"\badapter\b", description, re.I):
            return "usb-ethernet"
    if re.search(r"\bPCI(?:e| Express)?\b", description, re.I):
        if wireless:
            return "pcie-wifi" if re.search(r"\b(?:PCIe|PCI Express)\b", description, re.I) else "pci-wifi"
        if ethernet:
            return "pci-ethernet"
    return None


def dlink_revision_options(model, scratch, fetch):
    path = scratch / f"dlink-{model['modelCode']}.html"
    fetch(model["support"], path, 4 * 1024 * 1024)
    page = path.read_text(encoding="utf-8")
    selection = REVISION_SELECT.search(page)
    options = REVISION_OPTION.findall(selection[1]) if selection else []
    if not options:
        raise ValueError(f"No D-Link revisions parsed for {model['modelCode']}")
    return [(model, revision_id, revision.upper()) for revision_id, revision in options]


def dlink_revision_drivers(entry, scratch, fetch):
    model, revision_id, revision = entry
    path = scratch / f"dlink-revision-{revision_id}.json"
    query = urlencode(dict(action="productfile", lang="en-US", ver=revision_id, ac_id=1))
    fetch(f"{DLINK_SUPPORT}/ajax/ajax.ashx?{query}", path, 4 * 1024 * 1024)
    response = json.loads(path.read_bytes())
    for group in response.get("item", []):
        for row in group["file"]:
            if row["filetypename"] != "Driver":
                continue
            label = row["name"]
            systems = sorted({system for match in WINDOWS_TITLE.findall(label)
                              for system in re.findall(r"\b(?:10|11)\b", match)})
            if not systems:
                continue
            parsed = urlsplit(row["url"])
            if ((parsed.scheme, parsed.netloc) != ("https", "support.dlink.com")
                    or not parsed.path.lower().startswith("/resource/products/")
                    or not parsed.path.lower().endswith((".zip", ".exe"))):
                continue
            url = urlunsplit(parsed._replace(path=quote(parsed.path, safe="/%")))
            yield url, dict(model, label=label, listedWindows=systems, listedHardwareRevision=revision,
                            listedRevision=f"{row['id']} / {row['date']} / {label}")


def load_dlink(scratch, fetch):
    path = scratch / "dlink-products.html"
    fetch(DLINK_CATALOG, path, 4 * 1024 * 1024)
    models = {}
    for row in ROWS.findall(path.read_text(encoding="utf-8")):
        fields = PRODUCT_LINK.findall(row)
        if len(fields) != 2:
            continue
        model, description = (" ".join(unescape(field).split()) for field in fields)
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9+-]+", model):
            continue
        kind = dlink_adapter_kind(model, description)
        if kind:
            support = f"{DLINK_SUPPORT}/ProductInfo.aspx?{urlencode({'m': model})}"
            models[model] = dict(model=model, modelCode=model, deviceCategory=kind, support=support,
                                 description=description, evidence="oem-support-catalog", market="US/CA")
    if not models:
        raise ValueError("No D-Link host network adapter models were parsed")
    selected = [models[code] for code in sorted(DLINK_DRIVER_SAMPLE & models.keys())]
    listings = defaultdict(list)
    with ThreadPoolExecutor(max_workers=4) as executor:
        groups = executor.map(lambda model: dlink_revision_options(model, scratch, fetch), selected)
        revisions = [entry for group in groups for entry in group]
        records = executor.map(lambda entry: list(dlink_revision_drivers(entry, scratch, fetch)), revisions)
        for rows in records:
            for url, row in rows:
                if row not in listings[url]:
                    listings[url].append(row)
    return models, listings, 1 + len(selected) + len(revisions)
