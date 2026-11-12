"""Intel Mac identifiers and the official Windows 10 Boot Camp scope."""

from concurrent.futures import ThreadPoolExecutor
from html import unescape
import re


APPLE_SUPPORT = "https://support.apple.com/en-us"
BOOT_CAMP = f"{APPLE_SUPPORT}/102622"
BOOT_CAMP_DRIVERS = f"{APPLE_SUPPORT}/102465"
MODEL_PAGES = {
    "MacBook": "103257",
    "MacBook Air": "102869",
    "MacBook Pro": "108052",
    "Mac mini": "102852",
    "iMac": "108054",
    "Mac Pro": "102887",
}
PAGE_LIMIT = 2 * 1024 * 1024


def plain_text(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def boot_camp_ranges(page):
    sections = re.split(r"(<h2\b[^>]*>.*?</h2>)", page, flags=re.S)
    scope = next((section for title, section in zip(sections[1::2], sections[2::2])
                  if plain_text(title) == "What you need to install Windows 10 on Mac"), "")
    ranges = {}
    for row in re.findall(r"<li\b[^>]*>(.*?)</li>", scope, re.S):
        match = re.fullmatch(
            r"(.*?) introduced in (20\d\d) (?:through|to) (20\d\d)(?:, excluding .+| \d+)?",
            plain_text(row),
        )
        if match and match[1] in MODEL_PAGES:
            ranges[match[1]] = (int(match[2]), int(match[3]))
    if ranges.keys() != MODEL_PAGES.keys() or "iMac Pro (all models)" not in plain_text(scope):
        raise ValueError("Apple Boot Camp model scope could not be parsed")
    return ranges


def apple_model_rows(family, page, year_range):
    sections = re.split(r"(<h[23]\b[^>]*>.*?</h[23]>)", page, flags=re.S)
    prefix = family.replace(" ", "")
    prefixes = (prefix, "iMacPro") if family == "iMac" else (prefix,)
    identifier = re.compile(rf"\b(?:{'|'.join(prefixes)})\d+,\d+\b")
    for heading, section in zip(sections[1::2], sections[2::2]):
        title = plain_text(heading)
        if family == "MacBook" and re.fullmatch(r"20\d\d", title):
            title = f"MacBook ({title})"
            named = re.search(r"<p\b[^>]*>\s*<b>(MacBook\s*\([^<]+\))</b>\s*</p>", section)
            if named:
                title = plain_text(named[1])
        year = re.search(r"\b20\d\d\b", title)
        if not title.startswith(family) or not year or re.search(r"\bM[1-9]\b", title):
            continue
        if not title.startswith("iMac Pro") and not year_range[0] <= int(year[0]) <= year_range[1]:
            continue
        for paragraph in re.findall(r"<p\b[^>]*>(.*?)</p>", section, re.S):
            text = plain_text(paragraph)
            if text.startswith("Model Identifier:"):
                for model_id in identifier.findall(text):
                    yield model_id, title, int(year[0])


def load_apple(scratch, fetch):
    scope_path = scratch / "apple-boot-camp.html"
    fetch(BOOT_CAMP, scope_path, PAGE_LIMIT)
    ranges = boot_camp_ranges(scope_path.read_text(encoding="utf-8"))

    def load_family(family):
        page_id = MODEL_PAGES[family]
        path = scratch / f"apple-{page_id}.html"
        support = f"{APPLE_SUPPORT}/{page_id}"
        fetch(support, path, PAGE_LIMIT)
        rows = list(apple_model_rows(family, path.read_text(encoding="utf-8"), ranges[family]))
        if not rows:
            raise ValueError(f"No Boot Camp identifiers parsed from Apple's {family} page")
        return support, rows

    models = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        for support, rows in executor.map(load_family, MODEL_PAGES):
            for model_id, title, year in rows:
                model = models.setdefault(model_id, dict(
                    model=title, modelCode=model_id, support=support, deviceCategory="Other", deviceTag="Mac",
                    listedWindows="10", architecture="x64", installation="Boot Camp",
                    compatibilitySource=BOOT_CAMP, driverInstructions=BOOT_CAMP_DRIVERS, modelVariants=[],
                ))
                variant = dict(model=title, yearIntroduced=year)
                if variant not in model["modelVariants"]:
                    model["modelVariants"].append(variant)
    return models, {}, 1 + len(MODEL_PAGES)
