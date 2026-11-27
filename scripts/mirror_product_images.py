#!/usr/bin/env python3
"""Mirror already-reviewed product photos locally, without changing product identities."""
import concurrent.futures
import csv
import json
import pathlib
import re
import urllib.request
from urllib.parse import urlparse
from io import BytesIO
from PIL import Image, ImageOps, UnidentifiedImageError
import pillow_avif  # enable AVIF decoding for CDN responses

ROOT = pathlib.Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
DEST = ROOT / "assets" / "product-images"
DEST.mkdir(parents=True, exist_ok=True)
html = INDEX.read_text(encoding="utf-8")
begin = html.index("const verifiedImageSeeds = {")
end = html.index("const imageSeedBatches", begin)
block = html[begin:end]
pattern = re.compile(r"(?m)^(\s*'(\d+)': \{ src: ')([^']+)(', source: '[^']+' \},?)")
entries = [(m.group(2), m.group(3), m.group(0)) for m in pattern.finditer(block)]
REPLACEMENTS = ROOT / "scripts" / "verified_image_replacements.json"
replacements = json.loads(REPLACEMENTS.read_text(encoding="utf-8")) if REPLACEMENTS.exists() else {}
# Try independently reviewed replacement candidates before ordinary external URLs.
# Keep original entry text so we can safely replace the exact existing seed only on success.
candidates = [(pid, replacements[pid]["url"], line) for pid, old_url, line in entries
              if pid in replacements and old_url != replacements[pid]["url"]]

# Do not overwrite an already saved image, or replace unverified URLs with unrelated packs.
limit = 150
# Keep previous failures in a persistent report so later batches advance rather than
# spending their entire budget on the same dead/blocked links.
REPORT = ROOT / "image-mirror-report.json"
previous = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {}
failed_urls = {str(row.get("id")): row.get("url") for row in previous.get("failures", [])
               if "unsupported or non-image response: image/avif" not in str(row.get("error",""))}
already_failed = lambda pid,url: failed_urls.get(pid) == url
# Candidate replacements take priority, with Aptamil 2 first. Never let a stale
# original URL overwrite a reviewed candidate during de-duplication.
selected = []
queued_ids = set()
for pid, url, line in sorted(candidates + entries, key=lambda row: row[0] != "5"):
    if pid in queued_ids or not url.startswith("https://") or already_failed(pid, url):
        continue
    if pid in replacements and url != replacements[pid]["url"]:
        continue  # Never fall back to the known broken old link for a replacement candidate
    if any((DEST / (pid + ext)).exists() for ext in (".jpg", ".png", ".webp")):
        continue
    selected.append((pid, url, line))
    queued_ids.add(pid)
    if len(selected) >= limit:
        break
def download(item):
    pid, url, line = item
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0", "Accept":"image/jpeg,image/png,image/webp,image/*;q=0.8"})
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read(5_000_001)
            mime = response.headers.get("Content-Type","").split(";")[0].lower()
        if len(raw) > 5_000_000 or len(raw) < 500:
            raise ValueError("invalid image size")
        # Decode every format instead of trusting a .jpg suffix or response MIME.
        # Browsers/sites often negotiate AVIF even when the URL ends in .jpg.
        try:
            with Image.open(BytesIO(raw)) as image:
                image.load()
                width, height = image.size
                if width < 100 or height < 100 or width * height > 20_000_000:
                    raise ValueError("implausible photo dimensions")
                canonical = ImageOps.exif_transpose(image)
                if canonical.mode not in ("RGB", "RGBA"):
                    canonical = canonical.convert("RGBA" if "A" in canonical.getbands() else "RGB")
                out = BytesIO()
                # Limit browse photo dimensions while preserving the full carton.
                canonical.thumbnail((640, 640), Image.Resampling.LANCZOS)
                ext = ".webp"
                canonical.save(out, format="WEBP", quality=85, method=4)
                raw = out.getvalue()
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("image decode failed") from exc
        target = DEST / (pid + ext)
        target.write_bytes(raw)
        return pid, url, line, "assets/product-images/" + target.name, ""
    except Exception as exc:
        return pid, url, line, None, str(exc)[:150]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    results = list(pool.map(download, selected))
LEGACY_SOURCES_FILE = ROOT / "scripts" / "image_legacy_source_map.json"
legacy_sources = json.loads(LEGACY_SOURCES_FILE.read_text(encoding="utf-8")) if LEGACY_SOURCES_FILE.exists() else {}
for pid,url,line,new,error in results:
    if new:
        old = line
        new_line = re.sub(r"src: '[^']+'", "src: '"+new+"'", old, count=1)
        if pid in replacements and replacements[pid]["url"] == url:
            old_source_match = re.search(r"source: '([^']+)'", old)
            if old_source_match:
                legacy_sources[pid] = old_source_match.group(1)
            new_line = re.sub(r"source: '[^']+'", "source: '"+replacements[pid]["source"]+"'", new_line, count=1)
        if old not in block:
            raise RuntimeError("Seed changed while mirroring image id " + pid)
        block = block.replace(old, new_line, 1)
html = html[:begin] + block + html[end:]
if legacy_sources:
    LEGACY_SOURCES_FILE.write_text(json.dumps(legacy_sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
success = sum(bool(x[3]) for x in results)
if success:
    # Existing users have a saved localStorage seed flag. Force seed refresh on the next load.
    html, n = re.subn(r"arkan_verified_image_seed_v(\d+)", lambda m:"arkan_verified_image_seed_v"+str(int(m.group(1))+1), html, count=1)
    if n != 1: raise RuntimeError("Image seed version not found")
    INDEX.write_text(html, encoding="utf-8")
new_failures = [{"id":pid,"url":url,"error":error} for pid,url,_,new,error in results if not new]
# Retain only the current failure for a URL; retry is possible after its source is corrected.
failures = {str(row["id"]): row for row in previous.get("failures", [])}
for row in new_failures:
    failures[str(row["id"])] = row
for pid, url, line, new, error in results:
    if new:
        failures.pop(str(pid), None)
local_ids = {p.stem for p in DEST.iterdir() if p.is_file() and p.suffix.lower() in (".jpg", ".png", ".webp")}
local_references = set(re.findall(r"assets/product-images/([0-9]+)\.(?:jpg|png|webp)", block))
seed_sources = {pid: source for pid, url, source in re.findall(
    r"'([0-9]+)': \{ src: '([^']+)', source: '([^']+)'", block
)}
with (ROOT / "image-replacement-queue.csv").open("w", newline="", encoding="utf-8-sig") as output:
    writer = csv.DictWriter(output, fieldnames=["id", "source", "domain", "failure", "url"])
    writer.writeheader()
    for item in sorted(failures.values(), key=lambda row: int(row["id"])):
        writer.writerow({"id": item["id"], "source": seed_sources.get(str(item["id"]), ""),
                         "domain": urlparse(item["url"]).hostname or "", "failure": item.get("error", ""),
                         "url": item["url"]})
report = {"attempted":len(results), "mirrored":success,
          "failed":len(new_failures), "locally_stored_unique_product_ids":len(local_ids),
          "locally_referenced_seed_ids":len(local_references), "verified_seed_ids":len({pid for pid, _, _ in entries}),
          "unresolved_failed_urls":len(failures), "failures":list(failures.values()),
          "note":"URLs that could not be fetched are NOT represented as valid photos. Visual pack matching requires separate review."}
(ROOT/"image-mirror-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({k:v for k,v in report.items() if k!="failures"},ensure_ascii=False))
