"""Official model evidence for rescue catalog categories without a broad OEM index."""

from html import unescape
import re
from urllib.parse import urljoin


LATTEPANDA = "https://docs.lattepanda.com/"
BEEBOX = "https://www.asrock.com/news/index.asp?iD=3033"
LUMIA = "https://news.microsoft.com/en-in/lumia-950-and-lumia-950-xl-launch-in-india/"
PAGE_LIMIT = 4 * 1024 * 1024


def _text(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def _lattepanda_models(page):
    models = {}
    for table in re.findall(r"<table\b[^>]*>(.*?)</table>", page, re.I | re.S):
        headings = re.findall(r'<th\b[^>]*>\s*<a href="(content/[^"?#]+)">([^<]+)</a>\s*</th>', table)
        if not headings or not all(name.startswith("LattePanda ") for _, name in headings):
            continue
        for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", table, re.I | re.S):
            cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.I | re.S)
            if len(cells) != len(headings):
                continue
            for (link, heading), cell in zip(headings, cells):
                family = unescape(heading).removesuffix("(Discontinued)").strip()
                for code in re.findall(r"\b(DFR\d{4}(?:-[A-Z]+)?):", _text(cell)):
                    models[code] = dict(brand="LattePanda", model=f"{family} ({code})", modelCode=code,
                                        support=urljoin(LATTEPANDA, link), family=family, modelAliases=[family],
                                        deviceTags=["single-board-computer"], evidence="oem-model-catalog")
    if not models:
        raise ValueError("No LattePanda model codes found in the official catalog")
    return models


def load_special(scratch, fetch):
    """Collect official product records while leaving driver compatibility to verification."""
    def page(url, filename):
        path = scratch / filename
        fetch(url, path, PAGE_LIMIT)
        return path.read_text(encoding="utf-8", errors="replace")

    models = _lattepanda_models(page(LATTEPANDA, "lattepanda.html"))
    # The archived launch explicitly lists these Windows 10 HTPC models.
    # ASRock does not currently serve the article to the updater's HTTP client.
    for code in ("N3150", "N3050"):
        name = f"Beebox {code}"
        models[name] = dict(brand="ASRock", model=name, support=BEEBOX, family="Beebox",
                            deviceTags=["htpc"], evidence="oem-model-catalog")

    lumia = _text(page(LUMIA, "lumia.html"))
    if "Lumia 950 and Lumia 950 XL" not in lumia or "Continuum for phones" not in lumia:
        raise ValueError("No Microsoft Windows Phone announcement found")
    for name in ("Lumia 950", "Lumia 950 XL"):
        models[name] = dict(brand="Microsoft", model=name, support=LUMIA, family="Windows 10 Mobile",
                            deviceTags=["windows-phone"], evidence="outside-x64-record")
    return models, {}, 2
