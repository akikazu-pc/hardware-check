"""Official Chinese laptop support sources for the network rescue updater."""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import json
import re
from urllib.parse import urlencode, urlsplit


XIAOMI_CATALOG = "https://www.mi.com/service/notebook/drivers"
XIAOMI_MODEL_PATH = re.compile(r"service/notebook/drivers/([A-Za-z0-9-]+)")
XIAOMI_ARCHIVE_HOSTS = {"cdn.cnbj1.fds.api.mi-img.com", "mibook.cdn.pc.mi.com"}
XIAOMI_LAPTOP_TITLE = re.compile(r"book|笔记本|游戏本|^redmi g(?:\b|$)", re.IGNORECASE)
WLAN_TITLE = re.compile(r"无线网卡|无线网络|\b(?:intel|realtek|qualcomm|mediatek|mtk|amd)?wlan\b|"
                        r"\bwi[- ]?fi\b|wireless\s+(?:lan|network)", re.IGNORECASE)


def xiaomi_sections(page):
    marker = re.search(r"\$GLOBAL_PAGE\s*=\s*\{\s*PageData:\s*", page)
    if not marker:
        raise ValueError("Xiaomi support page does not expose PageData")
    data, _ = json.JSONDecoder().raw_decode(page, marker.end())
    return data["main_body"]["section"]


def xiaomi_models(page):
    models = {}
    for block in xiaomi_sections(page):
        if block["view_type"] != "driver_list":
            continue
        for row in block["body"]["section"]:
            match = XIAOMI_MODEL_PATH.fullmatch(row["action"]["path"])
            title = row["title"].strip()
            if not match or not XIAOMI_LAPTOP_TITLE.search(title):
                continue
            model_code = match[1]
            models[model_code] = dict(model=title, modelCode=model_code, sku=row.get("sku", []),
                                      support=f"{XIAOMI_CATALOG}/{model_code}")
    if not models:
        raise ValueError("No Xiaomi laptop support models were parsed")
    return models


def xiaomi_wlan_listings(page, model):
    sections = [block["body"] for block in xiaomi_sections(page) if block["view_type"] == "driver_info"]
    if not sections:
        raise ValueError(f"No Xiaomi driver table found for {model['modelCode']}")
    for section in sections:
        windows = re.findall(r"Windows\s*(10|11)(?![0-9])", section.get("sub_title", ""), re.IGNORECASE)
        for group in section["section"]:
            for row in group.get("items", []):
                title = row.get("title", "").strip()
                if not WLAN_TITLE.search(title):
                    continue
                url = row.get("download_url", "")
                parsed = urlsplit(url)
                if (parsed.scheme != "https" or parsed.netloc not in XIAOMI_ARCHIVE_HOSTS
                        or not parsed.path.lower().endswith((".zip", ".exe"))):
                    continue
                yield url, dict(model, label=title, listedWindows=windows,
                                listedRevision=str(row.get("id", "")))


def load_xiaomi(scratch, fetch):
    catalog = scratch / "xiaomi-catalog.html"
    fetch(XIAOMI_CATALOG, catalog, 4 * 1024 * 1024)
    models = xiaomi_models(catalog.read_text(encoding="utf-8"))

    def load_model(model):
        path = scratch / f"xiaomi-{model['modelCode']}.html"
        fetch(model["support"], path, 4 * 1024 * 1024)
        return list(xiaomi_wlan_listings(path.read_text(encoding="utf-8"), model))

    listings = defaultdict(list)
    with ThreadPoolExecutor(max_workers=4) as executor:
        for rows in executor.map(load_model, models.values()):
            for url, row in rows:
                if row not in listings[url]:
                    listings[url].append(row)
    if not listings:
        raise ValueError("No Xiaomi laptop WLAN listings were parsed")
    return models, listings, 1 + len(models)


HONOR_SUPPORT = "https://www.honor.com/cn/support/downloads/"
HONOR_API = "https://selfservice-cn.honor.com/ccpcmd/services/dispatch/secured/CCPC/EN"
HONOR_ARCHIVE_HOSTS = {"iknow-dl.service.hihonor.com"}
HONOR_COMMODITY = "ccpc/queryNewCommodityList/1000"


def load_honor(scratch, fetch):
    def request(endpoint, key, params):
        query = urlencode(dict(params, jsonp="callback"))
        path = scratch / f"honor-{key}.json"
        fetch(f"{HONOR_API}/{endpoint}?{query}", path, 4 * 1024 * 1024, referer=HONOR_SUPPORT)
        body = path.read_text(encoding="utf-8").strip()
        if body.startswith("callback(") and body.rstrip(";").endswith(")"):
            body = body[len("callback("):].rstrip(";")[:-1]
        response = json.loads(body)
        if response["responseCode"] != "200":
            raise ValueError(f"HONOR support request failed for {key}")
        return response["responseData"]

    def products(level, product_id):
        params = dict(channelCode="MYHONORWEB", countryCode="CN", langCode="zh-cn", country="CN",
                      language="zh-cn", siteCode="zh_CN_X", productLevel=level, productId=product_id)
        return request(HONOR_COMMODITY, product_id, params)["productList"] or []

    def network_drivers(model):
        code = model["modelCode"]
        # Category 634 is 网络 (network) in the public download center.
        params = dict(areaCode="CN", langCode="zh-cn", knowTypeId=634, orderType=1, page=1,
                      pageSize=999, offeringCode=code, driverDown="true", cflag=1)
        detail = request("knowledgeBase/getServicePolicy/1000", code, params)
        rows = []
        for row in detail.get("detailList") or []:
            title = (row.get("resourceTitle") or "").strip()
            if not WLAN_TITLE.search(title):
                continue
            url = row.get("downloadUrl") or ""
            parsed = urlsplit(url)
            if (parsed.scheme != "https" or parsed.netloc not in HONOR_ARCHIVE_HOSTS
                    or not parsed.path.startswith("/ctkbfm/servlet/download/downloadServlet/")
                    or not parsed.path.lower().endswith((".zip", ".exe"))):
                continue
            revision = " / ".join(str(row[field]) for field in ("versionNumber", "updateTime") if row.get(field))
            rows.append((url, dict(model, label=title, listedWindows=row.get("systemVersion") or "",
                                   listedRevision=revision)))
        return rows

    series = [row["productId"] for row in products("lv3", "CMCG10000120")
              if re.fullmatch(r"CMCG[0-9]+", row["productId"])]
    models = {}
    listings = defaultdict(list)
    with ThreadPoolExecutor(max_workers=4) as executor:
        for offerings in executor.map(lambda series_id: products("lv5", series_id), series):
            for row in offerings:
                code = row.get("offeringCode") or ""
                title = (row.get("displayName") or row.get("productName") or "").strip()
                if re.fullmatch(r"OFFE[0-9]+", code) and title:
                    models[code] = dict(model=title, modelCode=code, support=HONOR_SUPPORT)
        for rows in executor.map(network_drivers, models.values()):
            for url, row in rows:
                if row not in listings[url]:
                    listings[url].append(row)
    if not models or not listings:
        raise ValueError("No HONOR laptop WLAN listings were parsed")
    return models, listings, 1 + len(series) + len(models)
