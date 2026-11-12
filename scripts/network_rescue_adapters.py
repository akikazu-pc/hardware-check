"""Original network adapter driver listings by TP-Link hardware revision."""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from html import unescape
import re
from urllib.parse import quote, urlsplit, urlunsplit


TPLINK = "https://www.tp-link.com"
SUPPORT_PATH = "/us/support/download/"
CATALOG_SECTIONS = {"PCIe Adapters", "USB Adapters", "USB Converters"}
SUPPORT_LINK = re.compile(r'<a\b[^>]*href="(/us/support/download/[a-z0-9-]+/)"[^>]*>(.*?)</a>', re.S | re.I)
REVISION_LINK = re.compile(r'<a\b[^>]*href="(https://www\.tp-link\.com/us/support/download/[a-z0-9-]+/v[0-9.]+/)"[^>]*>\s*(V\d+(?:\.\d+)?)\s*</a>', re.I)
SELECTED_REVISION = re.compile(r'''\bid=['"]verison-hidden['"][^>]*>\s*(V\d+(?:\.\d+)?)\s*<''', re.I)
DRIVER_TABLE = re.compile(r'<table\b[^>]*class="download-resource-table"[^>]*>(.*?)</table>', re.S | re.I)
DRIVER_LINK = re.compile(r'<a\b[^>]*data-vars-event-category="Download-Detail-Driver_[^"]+"[^>]*href="([^"]+)"', re.I)
WIN_VERSION = re.compile(r"win(?:dows)?\s*(10|11|7|8(?:\.1)?)(?=\D|$)", re.I)
X64 = re.compile(r"x64|x86[_-]64|amd64|(?<!arm)(?<!aarch)64[ -]?bit", re.I)
OTHER_ARCH = re.compile(r"x86(?![_-]?64)|32[ -]?bit|arm64|aarch64", re.I)


def _text(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def _models(page):
    models = {}
    for section in re.split(r"<h2\b[^>]*>", page, flags=re.I)[1:]:
        heading, _, body = section.partition("</h2>")
        category = _text(heading.split("</span>", 1)[0]).rsplit(">", 1)[-1].strip()
        if category not in CATALOG_SECTIONS:
            continue
        for path, label in SUPPORT_LINK.findall(body):
            model = _text(label)
            if category == "PCIe Adapters":
                if model.startswith(("Archer ", "TL-W")):
                    kind = "pcie-wifi"
                elif re.fullmatch(r"(?:TX\d+|TG-\d+|TF-[A-Z0-9]+)", model):
                    kind = "pci-ethernet"
                else:
                    continue
            elif model.startswith(("Archer ", "TL-W")):
                kind = "usb-wifi"
            elif re.fullmatch(r"UE\d+[A-Z]*", model):
                kind = "usb-ethernet"
            else:
                continue
            models[path] = dict(model=model, deviceCategory=kind, support=TPLINK + path, market="US")
    if not models:
        raise ValueError("No TP-Link US network adapter model pages found")
    return models


def _drivers(page, model):
    records = []
    for table in DRIVER_TABLE.findall(page):
        link = DRIVER_LINK.search(table)
        title = re.search(r'<th\b[^>]*class="download-resource-name"[^>]*>(.*?)</th>', table, re.S | re.I)
        date = re.search(r"Published Date:\s*</span>\s*<span>\s*(\d{4}-\d{2}-\d{2})", table)
        if not (link and title and date):
            continue
        label = _text(title[1])
        if re.search(r"\bbeta\b", label, re.I):
            continue
        os_field = re.search(r'<td\b[^>]*class="os"[^>]*>(.*?)</td>', table, re.S | re.I)
        platform = _text(os_field[1]) if os_field else label
        # Some support pages publish equally dated 32-bit and 64-bit packages separately.
        os_versions = list(WIN_VERSION.finditer(platform))
        systems = set()
        for index, match in enumerate(os_versions):
            details = platform[match.end():os_versions[index + 1].start()] if index + 1 < len(os_versions) else platform[match.end():]
            if OTHER_ARCH.search(details) and not X64.search(details):
                continue
            if match[1] in {"10", "11"}:
                systems.add(match[1])
            systems.update(re.findall(r"(?:/|&|\band\b|_|,|\+)\s*(10|11)(?=\D|$)", details, re.I))
        if not systems:
            continue
        parsed = urlsplit(unescape(link[1]))
        if ((parsed.scheme, parsed.netloc) != ("https", "static.tp-link.com")
                or not parsed.path.startswith("/upload/driver/")
                or not parsed.path.casefold().endswith((".zip", ".exe"))):
            continue
        url = urlunsplit(parsed._replace(path=quote(parsed.path, safe="/%")))
        records.append((date[1], url, systems, dict(model, label=label, listedRevision=f"{date[1]} / {label}",
                                                   listedPlatform=platform)))
    chosen = {}
    for _, url, systems, row in sorted(records, key=lambda record: record[0], reverse=True):
        for system in sorted(systems):
            chosen.setdefault(system, (url, row))
    for url in dict.fromkeys(url for url, _ in chosen.values()):
        systems = [system for system, (candidate, _) in chosen.items() if candidate == url]
        yield url, dict(chosen[systems[0]][1], listedWindows=sorted(systems))


def load_tplink(scratch, fetch):
    """Read the official US catalog and each advertised hardware revision."""
    def get(url, name):
        path = scratch / f"tplink-{name}.html"
        fetch(url, path, 8 * 1024 * 1024)
        return path.read_text(encoding="utf-8")

    products = _models(get(TPLINK + SUPPORT_PATH, "catalog"))

    def get_revisions(product):
        path, model = product
        slug = path.rstrip("/").rsplit("/", 1)[1]
        page = get(model["support"], slug)
        revisions = [(url, version.upper()) for url, version in REVISION_LINK.findall(page)
                     if url.startswith(model["support"])]
        return slug, model, page, dict(revisions)

    models = {}
    listings = defaultdict(list)
    with ThreadPoolExecutor(max_workers=6) as executor:
        revision_pages = []
        for slug, model, page, revisions in executor.map(get_revisions, products.items()):
            # The selected revision is shown in the heading. A base page with no selector is indexed as-is.
            current = SELECTED_REVISION.search(page)
            default = current[1].upper() if current else None
            if not revisions:
                models[slug] = dict(model, hardwareRevision=default)
                for url, row in _drivers(page, models[slug]):
                    listings[url].append(row)
            for support, version in revisions.items():
                key = f"{slug}-{version.lower()}"
                models[key] = dict(model, hardwareRevision=version, support=support)
                if default == version:
                    for url, row in _drivers(page, models[key]):
                        listings[url].append(row)
                else:
                    revision_pages.append((key, support))

        def get_drivers(entry):
            key, support = entry
            page = get(support, key)
            selected = SELECTED_REVISION.search(page)
            if not selected or selected[1].upper() != models[key]["hardwareRevision"]:
                raise ValueError(f"TP-Link support page returned a different hardware revision for {key}")
            return list(_drivers(page, models[key]))

        for rows in executor.map(get_drivers, revision_pages):
            for url, row in rows:
                listings[url].append(row)

    if not listings:
        raise ValueError("No TP-Link Win10 or Win11 network adapter packages found")
    return models, listings, 1 + len(products) + len(revision_pages)
