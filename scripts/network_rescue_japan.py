"""Official Japanese laptop model catalogs and WLAN driver listings."""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from html import unescape
import json
import re
from urllib.parse import urlencode, urlsplit


PANASONIC = "https://jp-pc-support.connect.panasonic.com"
PANASONIC_API = f"{PANASONIC}/ccm/pc_support/api/products"
PANASONIC_FILES = "dl-pc-support.connect.panasonic.com"
PANASONIC_DETAIL_SERIES = 6
DYNABOOK_CATALOG = "https://dynabook.com/assistpc/osup/win11_25h2/target/"
FUJITSU_CATALOG = "https://azby.fmworld.net/support/win/11/info/"
PAGE_LIMIT = 2 * 1024 * 1024
HTML_ROW = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.I | re.S)
HTML_CELL = re.compile(r"<td\b[^>]*>(.*?)</td>", re.I | re.S)
HTML_LINK = re.compile(r"""\bhref\s*=\s*["']([^"']+)["']""", re.I)
WLAN = re.compile(r"\b(?:WLAN|Wireless\s+LAN|Wi-?Fi)\s+Driver\b|無線\s*LAN\s*ドライバー?", re.I)


def _text(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def _panasonic_models(path, fetch, **query):
    fetch(f"{PANASONIC_API}?{urlencode(dict(query, limit=100))}", path, PAGE_LIMIT)
    catalog = json.loads(path.read_bytes())
    rows = catalog["data"]
    if len(rows) != catalog["meta"]["total"]:
        raise ValueError("Panasonic model catalog pagination is required")
    return rows


def _panasonic_wlan(model, support, page):
    for row in HTML_ROW.findall(page):
        cells = HTML_CELL.findall(row)
        if len(cells) < 3:
            continue
        label = _text(cells[1])
        if not WLAN.search(label):
            continue
        for link in HTML_LINK.findall(cells[2]):
            url = unescape(link)
            parsed = urlsplit(url)
            path = parsed.path.casefold()
            if (parsed.scheme, parsed.netloc) != ("https", PANASONIC_FILES):
                continue
            if not path.startswith("/public/soft_first/") or not path.endswith((".exe", ".zip")):
                continue
            os_version = re.search(r"\bwin(10|11)(?=[-_])", path)
            if not os_version or "_64_" not in path:
                continue
            filename = path.rsplit("/", 1)[-1]
            yield url, dict(model=model, support=support, label=label, listedRevision=filename,
                            listedWindows=os_version[1])


def load_panasonic(scratch, fetch):
    """Enumerate the current Let's note catalog and verify newest-series support pages."""
    series = _panasonic_models(scratch / "series.json", fetch, parent_code=101101, has_product_page=1)
    if not series:
        raise ValueError("No Panasonic Let's note series found")

    def series_models(row):
        series_id = int(row["id"])
        return _panasonic_models(scratch / f"series-{series_id}.json", fetch, parent=series_id)

    boards = {}
    priority = []
    listings = defaultdict(list)
    with ThreadPoolExecutor(max_workers=6) as executor:
        for index, (series_row, model_rows) in enumerate(zip(series, executor.map(series_models, series))):
            for row in model_rows:
                model = row["name"]
                if not re.fullmatch(r"CF-[A-Z0-9]+", model):
                    continue
                support = f"{PANASONIC}/products/{model}"
                boards[model] = dict(model=model, support=support, family=series_row["name"],
                                     productType="laptop", market="JP", wlanPageChecked=False)
                if index < PANASONIC_DETAIL_SERIES:
                    priority.append(model)

        def wlan_records(model):
            support = boards[model]["support"]
            path = scratch / f"{model}.html"
            fetch(support, path, PAGE_LIMIT)
            return list(_panasonic_wlan(model, support, path.read_text(encoding="utf-8")))

        for model, records in zip(priority, executor.map(wlan_records, priority)):
            boards[model]["wlanPageChecked"] = True
            for url, record in records:
                if record not in listings[url]:
                    listings[url].append(record)

    if not boards or not listings:
        raise ValueError("No Panasonic laptop WLAN listings were parsed")
    return boards, listings, 1 + len(series) + len(priority)


def load_dynabook(scratch, fetch):
    """Index Dynabook's JP Windows 11 compatibility list without fetching agreement-gated installers."""
    index_file = scratch / "dynabook-index.html"
    fetch(f"{DYNABOOK_CATALOG}index_j.htm", index_file, PAGE_LIMIT)
    index = index_file.read_text(encoding="utf-8")
    laptop_groups = {}
    for options in re.findall(r'<select\b[^>]*\bid="t[12]"[^>]*>(.*?)</select>', index, re.I | re.S):
        for identifier, label in re.findall(r'<option\b[^>]*\bvalue="(\d+)"[^>]*>(.*?)</option>', options, re.I | re.S):
            laptop_groups[identifier] = _text(label)
    if not laptop_groups:
        raise ValueError("No Dynabook laptop families found")

    # The selector's result document includes every group and the UI displays the selected group.
    models_file = scratch / "dynabook-models.html"
    result_page = f"{DYNABOOK_CATALOG}result_taisyo.htm?"
    fetch(result_page + next(iter(laptop_groups)), models_file, PAGE_LIMIT)
    sections = re.split(r'<div\b[^>]*\bid="m(\d+)"[^>]*>', models_file.read_text(encoding="utf-8"))
    boards = {}
    for identifier, section in zip(sections[1::2], sections[2::2]):
        if identifier not in laptop_groups:
            continue
        for row in HTML_ROW.findall(section):
            cells = [_text(cell) for cell in HTML_CELL.findall(row)]
            if len(cells) < 3 or not cells[0].casefold().startswith("dynabook "):
                continue
            model_code = cells[1]
            if not re.fullmatch(r"[A-Z0-9][A-Z0-9*]{5,19}", model_code):
                continue
            boards[model_code] = dict(model=cells[0], modelCode=model_code,
                                      modelCodeKind="pattern" if "*" in model_code else "exact",
                                      support=result_page + identifier, family=laptop_groups[identifier],
                                      productType="laptop", market="JP", listedWindows="11",
                                      windowsRelease="25H2", wlanPageChecked=False)
    if not boards:
        raise ValueError("No Dynabook laptop models found")
    return boards, {}, 2


def load_fujitsu(scratch, fetch):
    """Read FMV's consumer Windows 11 upgrade list and its exact retail model codes."""
    path = scratch / "fujitsu.html"
    fetch(FUJITSU_CATALOG, path, PAGE_LIMIT)
    models = {}
    for row in HTML_ROW.findall(path.read_text(encoding="utf-8")):
        title = re.search(r"<th\b[^>]*>(.*?)</th>", row, re.I | re.S)
        cells = HTML_CELL.findall(row)
        if not title or len(cells) != 1:
            continue
        name = _text(title[1])
        codes = [code.strip() for code in _text(cells[0]).split("、")]
        if not re.match(r"(?:LIFEBOOK|ESPRIMO|FMV Lite|arrows Tab)\b", name, re.I):
            continue
        exact_codes = [code for code in codes if re.fullmatch(r"FMV[A-Z0-9-]+", code)]
        if not exact_codes:
            continue
        product_type = "laptop" if name.startswith(("LIFEBOOK", "FMV Lite")) else "desktop"
        tags = ["windows-tablet"] if name.casefold().startswith("arrows tab") else ["branded-desktop"]
        model = models.setdefault(name, dict(model=name, support=FUJITSU_CATALOG, market="JP",
                                            productType=product_type, deviceTags=tags if product_type != "laptop" else [],
                                            evidence="oem-os-upgrade-catalog", modelAliases=[]))
        model["modelAliases"] = sorted(set(model["modelAliases"]) | set(exact_codes))
    if not models:
        raise ValueError("No Fujitsu FMV retail model codes were parsed")
    return models, {}, 1
