"""Collect Dell consumer driver lists through the public product driver API.

The support page loads its driver table from
``/support/driver/<locale>/dep/api/driverlist/packdriversbyproduct?productcode=...&oscode=&lob=...``
with the session cookies of an ordinary browser visit. The response is a JSON document whose
letters are shifted by three (``"DriverName"`` arrives as ``"GulyhuQdph"``); digits, punctuation and
non-ASCII text are unchanged, so the payload is decrypted by shifting ASCII letters back.

Every driver entry carries ``DriverName``, ``DellVer`` and ``AppOses``. Dell OS codes used here:
``W2021``/``W11S``/``LTSC3``/``W11SE`` are Windows 11 and ``WT64A``/``W10GE``/``EX64``/``LTSC2``/
``LTSC1`` are Windows 10. The supported-OS drawer of the same page (``/supportedos/<product>``)
lists the Windows versions Dell supports for the model.

Classification per system: ``oem-wlan-listed`` when a Wi-Fi driver names the system, ``oem-os-not-listed``
when the supported-OS list has no such Windows version, otherwise ``oem-wlan-not-listed`` when the
system appears in the driver list but no Wi-Fi driver covers it.

Usage: python scripts/collect-dell-alienware.py docs/network-rescue-model-gaps.csv \
    docs/network-rescue-dell-alienware-proof.csv --cookie-file artifacts/dell-cookie.txt [--apply]
"""
import argparse
import csv
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parent.parent
API = "https://www.dell.com/support/driver/ja-jp/dep/api/driverlist/packdriversbyproduct"
SUPPORTED = "https://www.dell.com/support/driver/ja-jp/supportedos/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/157.0.0.0 Safari/537.36 Edg/157.0.0.0")
WINDOWS_11 = {"W2021", "W11S", "LTSC3", "W11SE", "W11A6", "W11AS"}
WINDOWS_10 = {"WT64A", "W10GE", "EX64", "LTSC2", "LTSC1"}
WLAN = re.compile(r"wi-?fi|wireless|wlan", re.I)
FIELDS = ["model", "windows", "status", "evidence", "supportedOs", "url"]


def decrypt(text):
    out = []
    for char in text:
        code = ord(char)
        if 65 <= code <= 90:
            out.append(chr((code - 65 - 3) % 26 + 65))
        elif 97 <= code <= 122:
            out.append(chr((code - 97 - 3) % 26 + 97))
        else:
            out.append(char)
    return "".join(out)


def fetch(url, cookie_file):
    output = ROOT / "artifacts" / "_dell_api.txt"
    completed = subprocess.run(
        ["node", str(ROOT / "scripts" / "dell-api-fetch.mjs"), url, str(cookie_file), str(output)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if not output.is_file():
        return None
    return output.read_text(encoding="utf-8", errors="replace")


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cookie-file", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    rows = [row for row in read(args.models) if row["brand"] == "Dell" and row["type"] == "laptop"
            and (row["windows10X64Evidence"] == "pending" or row["windows11X64Evidence"] == "pending")]
    proof = []
    for row in rows:
        match = re.search(r"(?:product-support/product/|product/|manuals/[a-z]{2}-[a-z]{2}/)([a-z0-9\-]+)", row["source"] or "")
        product = match.group(1) if match else ""
        if not product:
            continue
        raw = fetch(f"{API}?productcode={product}&oscode=&lob=Alienware%20Laptop&initialload=false&dapPC=&dapOS=", args.cookie_file)
        if not raw:
            print(product, "no response")
            continue
        try:
            data = json.loads(decrypt(raw))
        except ValueError:
            print(product, "decrypt failed")
            continue
        drivers = data.get("DriverListData") or []
        wifi = [item for item in drivers if WLAN.search(item.get("DriverName") or "")]
        supported_html = fetch(SUPPORTED + product, args.cookie_file)
        supported = {"Windows 11"} if supported_html and "Windows 11" in supported_html else set()
        if supported_html and "Windows 10" in supported_html:
            supported.add("Windows 10")
        for system, codes, label in (("10", WINDOWS_10, "Windows 10"), ("11", WINDOWS_11, "Windows 11")):
            field = f"windows{system}X64Evidence"
            if row[field] != "pending":
                continue
            covered = [item for item in drivers if codes & set(item.get("AppOses") or [])]
            listed = [item for item in wifi if codes & set(item.get("AppOses") or [])]
            if label not in supported and supported:
                status, evidence = "oem-os-not-listed", "supported OS list has no " + label
            elif listed:
                item = listed[0]
                status = "oem-wlan-listed"
                evidence = f"{item.get('DriverName')} {item.get('DellVer')}"
            elif covered:
                status, evidence = "oem-wlan-not-listed", f"{len(covered)} drivers for {label}, none wireless"
            else:
                continue
            proof.append({"model": row["model"], "windows": system, "status": status,
                          "evidence": evidence[:300], "supportedOs": ",".join(sorted(supported)),
                          "url": f"{SUPPORTED}{product}" if status == "oem-os-not-listed" else API})
            print(row["model"], system, status)
    with args.output.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, FIELDS)
        writer.writeheader()
        writer.writerows(proof)
    print(f"models={len(rows)} classified={len(proof)}")
    if args.apply and proof:
        raw = args.models.read_bytes()
        with args.models.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            data, fields = list(reader), reader.fieldnames
        wanted = {(item["model"], item["windows"]): item["status"] for item in proof}
        updates = 0
        for row in data:
            if row["brand"] != "Dell":
                continue
            for system in ("10", "11"):
                field = f"windows{system}X64Evidence"
                value = wanted.get((row["model"], system))
                if row[field] == "pending" and value in {"oem-wlan-listed", "oem-os-not-listed",
                                                         "oem-wlan-not-listed"}:
                    row[field] = value
                    updates += 1
        temporary = args.models.with_suffix(args.models.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8",
                            newline="") as output:
            writer = csv.DictWriter(output, fields, quoting=csv.QUOTE_ALL,
                                    lineterminator="\r\n" if b"\r\n" in raw else "\n")
            writer.writeheader()
            writer.writerows(data)
        temporary.replace(args.models)
        print("applied:", updates)


if __name__ == "__main__":
    main()
