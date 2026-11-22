#!/usr/bin/env python3
"""Mirror already-reviewed product photos locally, without changing product identities."""
import concurrent.futures
import json
import pathlib
import re
import urllib.request
from io import BytesIO
from PIL import Image, ImageOps, UnidentifiedImageError

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
# Do not overwrite an already saved image, or replace unverified URLs with unrelated packs.
limit = 100
# Keep previous failures in a persistent report so later batches advance rather than
# spending their entire budget on the same dead/blocked links.
REPORT = ROOT / "image-mirror-report.json"
previous = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else {}
failed_urls = {str(row.get("id")): row.get("url") for row in previous.get("failures", [])}
already_failed = lambda pid,url: failed_urls.get(pid) == url
selected = [(pid, url, line) for pid, url, line in entries
            if url.startswith("https://") and not already_failed(pid,url)
            and not any((DEST / (pid + ext)).exists() for ext in (".jpg", ".png", ".webp"))][:limit]
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
                if canonical.mode == "RGBA":
                    ext = ".png"
                    canonical.save(out, format="PNG", optimize=True)
                else:
                    ext = ".jpg"
                    canonical.save(out, format="JPEG", quality=88, optimize=True)
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
for pid,url,line,new,error in results:
    if new:
        old = next(m.group(0) for m in pattern.finditer(block) if m.group(2)==pid and m.group(3)==url)
        new_line = old.replace("src: '"+url+"'", "src: '"+new+"'")
        block = block.replace(old, new_line, 1)
html = html[:begin] + block + html[end:]
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
report = {"attempted":len(results), "mirrored":success,
          "failed":len(new_failures), "total_mirrored_in_previous_runs":previous.get("total_mirrored_in_previous_runs",0)+success,
          "unresolved_failed_urls":len(failures), "failures":list(failures.values()),
          "note":"URLs that could not be fetched are NOT represented as valid photos. Visual pack matching requires separate review."}
(ROOT/"image-mirror-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({k:v for k,v in report.items() if k!="failures"},ensure_ascii=False))
