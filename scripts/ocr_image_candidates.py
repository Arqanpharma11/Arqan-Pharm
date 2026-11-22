#!/usr/bin/env python3
"""Read package-front lettering from reviewed shortlist images using Tesseract.

This is a *triage* step, not a visual approval or an upload operation. No changes
to the pharmacy UI or current product-image seeds.
"""
import concurrent.futures
import hashlib
import io
import json
import pathlib
import re
import subprocess
import tempfile
import urllib.request
from collections import Counter
from PIL import Image, ImageOps, UnidentifiedImageError
import pillow_avif  # register AVIF for pharmacy CDN image responses

ROOT = pathlib.Path(__file__).resolve().parents[1]
IN = ROOT / "data/arkan-image-approval-worklist.json"
OUT = ROOT / "data/arkan-image-ocr-review.json"
MAX_ITEMS = 900
def ocr(item):
    candidate = item["reviewCandidates"][0]
    url = candidate["imageUrl"]
    row = {
        "id": item["id"], "name": item["name"],
        "title": candidate.get("title"), "source": candidate.get("sourceName"),
        "url": url, "photoVerified": False, "status": "ocr_unchecked",
    }
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                                      "Accept": "image/avif,image/webp,image/jpeg,image/png,*/*"})
        with urllib.request.urlopen(req, timeout=16) as response:
            buf = response.read(4_000_001)
        if len(buf) < 1024 or len(buf) > 4_000_000:
            raise ValueError("invalid photo byte count")
        with Image.open(io.BytesIO(buf)) as im:
            im.load()
            if min(im.size) < 120 or im.width * im.height > 20_000_000:
                raise ValueError("invalid photo dimensions")
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((1400, 1400))
            with tempfile.TemporaryDirectory() as td:
                p = pathlib.Path(td) / "input.png"
                im.save(p, format="PNG")
                process = subprocess.run(
                    ["tesseract", str(p), "stdout", "-l", "eng", "--psm", "11"],
                    capture_output=True, text=True, timeout=25)
            if process.returncode:
                raise ValueError("OCR engine failed")
        ocr_text = re.sub(r"\s+", " ", process.stdout).strip().lower()
        name = re.sub(r"[^a-z0-9]", "", str(item.get("englishName", "")).lower())
        visible = re.sub(r"[^a-z0-9]", "", ocr_text)
        brand = bool(name and len(name) >= 4 and name in visible)
        # Use strength values only, not catalog index/product code: OCR may
        # contain manufacturer codes, serials and unrelated numbers.
        requested = re.findall(r"(?<!\d)\d+(?:\.\d+|/\d+)?(?!\d)", str(item.get("name", "")))
        ocr_numbers = set(re.findall(r"(?<!\d)\d+(?:\.\d+|/\d+)?(?!\d)", ocr_text))
        strength = bool(requested and all(x in ocr_numbers for x in requested))
        row.update({"ocrBrandVisible": brand, "ocrCatalogNumbersVisible": strength,
                    "imageHash": hashlib.sha256(buf).hexdigest()[:24],
                    "ocrPreview": ocr_text[:380],
                    "status": ("ocr_brand_and_numbers_visible_NEEDS_VISUAL_CONFIRMATION"
                               if brand and strength else "manual_visual_review_required")})
    except Exception as e:
        row.update({"status": "download_or_ocr_failed", "error": str(e)[:180]})
    return row
def main():
    data = json.loads(IN.read_text(encoding="utf-8"))
    pending = [x for x in data["items"] if x["status"] == "metadata_pass_needs_visual_review"]
    selected = pending[:MAX_ITEMS]
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(ocr, selected))
    # Detect identical candidate image used for distinct IDs/strengths.
    by_hash = {}
    for entry in results:
        if entry.get("imageHash"):
            by_hash.setdefault(entry["imageHash"], []).append(entry["id"])
    duplicates = {key: ids for key, ids in by_hash.items() if len(set(ids)) > 1}
    suspicious = set(x for ids in duplicates.values() for x in ids)
    for entry in results:
        if entry["id"] in suspicious:
            entry["status"] = "duplicate_image_across_products_REJECT_PENDING_REVIEW"
    summary = dict(Counter(x["status"] for x in results))
    result = {
        "format": "arkan-image-ocr-audit", "version": 1, "totalCandidateItems": len(pending),
        "tested": len(results), "summary": summary,
        "duplicateImageGroups": duplicates,
        "note": "OCR is only an aid to human pack review. No row is approved or uploaded by this script.",
        "items": results,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("OCR complete:", summary, "duplicate image groups:", len(duplicates))
if __name__ == "__main__":
    main()
