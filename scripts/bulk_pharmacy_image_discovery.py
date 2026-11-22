#!/usr/bin/env python3
"""Collect pack-photo CANDIDATES from public pharmacy storefront product feeds.

Never changes index.html, never labels an unseen pack as confirmed, and never
imports an unreviewed image. Designed to handle all 4218 Arqan catalog IDs
in one scan without a separate web query per medicine.
"""
import argparse
import collections
import json
import pathlib
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

ROOT = pathlib.Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "data/arkan-all-4218-image-manifest.json"
OUTPUT = ROOT / "data/arkan-image-candidate-review.json"
UA = "ArqanPharmCatalogResearch/1.0 (public storefront product data)"
SOURCES = {
    "Lotus Pharmacies": "https://www.lotusonline.com",
    "Bloom Pharmacy": "https://www.bloompharmacy.com",
    "Re3aya Pharmacy": "https://re3ayapharmacy.com",
    "AlFouad Pharmacies": "https://alfouadpharmacies.com",
    "Kidz Market Egypt": "https://kidzmarket-eg.com",
}
FORM_TAGS = {
    "اقراص": ("tablet", "tablets", "tab", "tabs"),
    "كبسول": ("capsule", "capsules", "caps"),
    "شراب": ("syrup", "suspension"),
    "كريم": ("cream",),
    "مرهم": ("ointment",),
    "جل": ("gel",),
    "قطره": ("drop", "drops"),
    "قطرة": ("drop", "drops"),
    "لبن": ("milk", "formula", "powder"),
    "لبن اطفال": ("milk", "formula"),
    "اقماع": ("suppository", "suppositories", "supp"),
    "امبول": ("ampoule", "ampoules", "amp", "injection"),
    "بخاخ": ("spray",),
    "اكياس": ("sachet", "sachets"),
}
AR_FORMS = sorted(FORM_TAGS, key=len, reverse=True)

def normalize(value):
    s = unicodedata.normalize("NFKC", str(value or "")).casefold()
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"))
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ى", "ي"), ("ة", "ه")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9\u0621-\u064a]+", " ", s).strip()

def digits(value):
    return set(re.findall(r"\d+(?:[.,/]\d+)*", normalize(value)))

def english_tokens(value):
    return re.findall(r"[a-z]+", normalize(value))

def expected_form(arabic_name):
    name = normalize(arabic_name)
    for form in AR_FORMS:
        if normalize(form) in name:
            return FORM_TAGS[form]
    return ()

def match_score(item, product):
    title = str(product.get("title") or "")
    norm_title = normalize(title)
    if not title:
        return None
    brand = normalize(item.get("englishName"))
    brand_words = english_tokens(brand)
    ar = normalize(item.get("name"))
    title_words = norm_title.split()
    if brand_words:
        # Strong boundary on the trade brand; substring lookalikes are rejected.
        brand_len = len(brand_words)
        if title_words[:brand_len] != brand_words and not any(
            title_words[i:i + brand_len] == brand_words
            for i in range(1, min(len(title_words) - brand_len + 1, 4))
        ):
            return None
    elif ar:
        # Arabic titles only: use a whole-token brand, not fuzzy transliteration.
        ar_words = ar.split()
        if not ar_words or not title_words or ar_words[0] != title_words[0]:
            return None
    else:
        return None
    required_digits = digits(item.get("name"))
    found_digits = digits(title)
    if not required_digits.issubset(found_digits):
        return None
    form = expected_form(item.get("name"))
    if form and not any(tag in norm_title for tag in form):
        return None
    # A candidate is for review, not an approved match. The photograph itself
    # has not been visually or OCR checked.
    return round(min(0.94, 0.64 + 0.12 * bool(required_digits) +
                     0.10 * bool(form) + 0.06 * (len(brand_words) > 1)), 3)

def image_link(product):
    images = product.get("images") or []
    if not images:
        return ""
    first = images[0]
    url = first.get("src", "") if isinstance(first, dict) else first
    if not isinstance(url, str) or not url.startswith("https://"):
        return ""
    return url

def fetch_public_products(source_name, base, pages, delay):
    parsed = urllib.parse.urlparse(base)
    robot = urllib.robotparser.RobotFileParser()
    robot.set_url(base + "/robots.txt")
    try:
        robot.read()
    except Exception as ex:
        print(source_name, "robots.txt not verified; skipping:", str(ex)[:100])
        return
    for page in range(1, pages + 1):
        url = base + "/products.json?" + urllib.parse.urlencode({"limit": 250, "page": page})
        if not robot.can_fetch(UA, url):
            print(source_name, "robots policy disallows feed; skipping")
            return
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=16) as response:
                raw = response.read(9_000_001)
            if len(raw) >= 9_000_000:
                print(source_name, "oversized response; stopping")
                return
            parsed_data = json.loads(raw.decode("utf-8"))
            products = parsed_data.get("products", [])
            if not isinstance(products, list) or not products:
                return
            for product in products:
                if isinstance(product, dict):
                    yield product
            if len(products) < 250:
                return
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                ValueError, json.JSONDecodeError) as ex:
            print(source_name, "feed unavailable:", str(ex)[:130])
            return
        time.sleep(delay)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pages", type=int, default=16,
                    help="up to 4000 public products per source (16 pages)")
    ap.add_argument("--delay", type=float, default=0.7)
    args = ap.parse_args()
    data = json.loads(INVENTORY.read_text(encoding="utf-8"))
    items = data["items"]
    if len(items) != 4218 or len({x["id"] for x in items}) != 4218:
        raise SystemExit("Catalog changed; regenerate source inventory first")
    todo = [x for x in items if not x.get("localImagePath")]
    # Index possible brands to avoid quadratic comparison with large retailer feeds.
    index = collections.defaultdict(list)
    for item in todo:
        brand = english_tokens(item.get("englishName"))
        if brand:
            index[brand[0]].append(item)
        else:
            ar_tokens = normalize(item["name"]).split()
            if ar_tokens:
                index[ar_tokens[0]].append(item)
    found = collections.defaultdict(list)
    source_stats = {}
    for source_name, base in SOURCES.items():
        count = 0
        for product in fetch_public_products(source_name, base, max(1, min(args.max_pages, 60)), max(args.delay, 0.4)):
            count += 1
            title = str(product.get("title") or "")
            image = image_link(product)
            if not image:
                continue
            first_tokens = normalize(title).split()[:4]
            candidate_items = {x["id"]: x for token in first_tokens for x in index.get(token, [])}
            for item in candidate_items.values():
                score = match_score(item, product)
                if score is None:
                    continue
                purl = urllib.parse.urljoin(base, "/products/" + str(product.get("handle") or ""))
                found[item["id"]].append({
                    "title": title, "imageUrl": image, "sourceName": source_name,
                    "productPage": purl, "score": score, "status": "needs_visual_pack_review",
                })
        source_stats[source_name] = count
        print(source_name, "products indexed:", count)
    results = []
    for item in items:
        options = sorted(found.get(item["id"], []), key=lambda x: x["score"], reverse=True)
        unique = []
        seen_urls = set()
        for option in options:
            if option["imageUrl"] not in seen_urls:
                seen_urls.add(option["imageUrl"])
                unique.append(option)
            if len(unique) == 3:
                break
        results.append({
            "id": item["id"], "name": item["name"],
            "englishName": item.get("englishName", ""),
            "currentLocalImage": item.get("localImagePath", ""),
            "candidates": unique,
            "exactMatchConfirmed": bool(item.get("localImagePath")),
        })
    output = {
        "format": "arkan-image-candidate-review", "version": 1,
        "totalCatalogItems": 4218, "storefrontSourceCounts": source_stats,
        "existingLocalImageRefs": sum(bool(i.get("localImagePath")) for i in items),
        "productsWithCandidates": sum(bool(r["candidates"]) for r in results),
        "note": "Image candidates are NOT visually confirmed; never import until pack, strength, dosage form and count are checked.",
        "items": results,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("Candidate review written:", OUTPUT, "matched IDs:", output["productsWithCandidates"])

if __name__ == "__main__":
    main()
