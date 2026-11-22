#!/usr/bin/env python3
"""Mirror already-reviewed product photos locally, without changing product identities."""
import concurrent.futures
import hashlib
import json
import pathlib
import re
import urllib.request
from collections import Counter

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
selected = [(pid, url, line) for pid, url, line in entries if url.startswith("https://") and not (DEST / (pid + ".jpg")).exists() and not (DEST / (pid + ".png")).exists() and not (DEST / (pid + ".webp")).exists()][:limit]
def download(item):
    pid, url, line = item
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0", "Accept":"image/avif,image/webp,image/png,image/jpeg,image/*"})
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read(5_000_001)
            mime = response.headers.get("Content-Type","").split(";")[0].lower()
        if len(raw) > 5_000_000 or len(raw) < 1000:
            raise ValueError("invalid size")
        if raw.startswith(b"\xff\xd8\xff"):
            ext = ".jpg"
        elif raw.startswith(b"\x89PNG\r\n\x1a\n"):
            ext = ".png"
        elif raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
            ext = ".webp"
        else:
            raise ValueError("unsupported or non-image response: " + mime)
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
report = {"attempted":len(results), "mirrored":success, "failed":len(results)-success,
          "failures":[{"id":pid,"url":url,"error":error} for pid,url,_,new,error in results if not new],
          "note":"URLs that could not be fetched are NOT represented as valid photos. Visual pack matching requires separate review."}
(ROOT/"image-mirror-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({k:v for k,v in report.items() if k!="failures"},ensure_ascii=False))
