#!/usr/bin/env python3
"""Enrich ONLY image-search aliases from a CC0 Egyptian medicine-name dataset.

Does not overwrite the Arqan catalog or approve photographs.
Dataset: https://github.com/karem505/egyptian-drug-database (CC0).
"""
import collections
import csv
import io
import json
import pathlib
import re
import urllib.request
from bulk_pharmacy_image_discovery import normalize, digits

ROOT = pathlib.Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/arkan-all-4218-image-manifest.json"
OUTPUT = ROOT / "data/arkan-english-image-search-aliases.json"
SOURCE = "https://raw.githubusercontent.com/karem505/egyptian-drug-database/main/data/egyptian-drugs.csv"

def first_arabic_word(text):
    value = normalize(text)
    m = re.search(r"[\u0621-\u064a]+", value)
    return m.group(0) if m else ""

def main():
    request = urllib.request.Request(SOURCE, headers={"User-Agent":"ArqanPharmCatalogResearch/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        content = response.read(7_000_001)
    if len(content) > 7_000_000:
        raise SystemExit("Oversized external CSV; skip rather than processing unexpected input")
    meds = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    aliases = collections.defaultdict(list)
    for row in meds:
        first = first_arabic_word(row.get("commercial_name_ar"))
        label = str(row.get("commercial_name_en") or "").strip()
        if not first or len(first) < 3 or not re.match(r"^[A-Z][A-Z0-9 -]{2,}", label.upper()):
            continue
        aliases[first].append((row.get("commercial_name_ar") or "", label))
    catalog = json.loads(INPUT.read_text(encoding="utf-8"))["items"]
    out = {}
    for item in catalog:
        if item["category"] != "أدوية" or item.get("englishName"):
            continue
        name = normalize(item["name"])
        possible = aliases.get(first_arabic_word(name), [])
        if not possible:
            continue
        matches = []
        for arabic, english in possible:
            if not digits(item["name"]).issubset(digits(english)):
                continue
            # Avoid a compound brand name not appearing in the Arabic item.
            ar_words = normalize(arabic).split()
            if len(ar_words) >= 2 and len(name.split()) >= 2:
                if ar_words[1].isalpha() and ar_words[1] not in name:
                    continue
            head = re.match(r"^[A-Z][A-Z -]*", english.upper())
            brand = head.group(0).strip(" -.") if head else ""
            if brand and len(brand) >= 3:
                matches.append(brand)
        if matches:
            # Distinct candidates: only use a shared, identical first brand token.
            first_tokens = {m.split()[0] for m in matches}
            if len(first_tokens) == 1:
                out[str(item["id"])] = {
                    "brand": next(iter(first_tokens)).title(),
                    "matchedRecords": len(matches),
                    "reference": "karem505/egyptian-drug-database CC0",
                    "status": "search_alias_only_not_image_approval",
                }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("Added", len(out), "Egyptian market English search aliases; no products or images approved")

if __name__ == "__main__":
    main()
