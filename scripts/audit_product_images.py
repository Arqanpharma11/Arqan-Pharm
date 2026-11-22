#!/usr/bin/env python3
"""Audit Arqan pharmacy package URLs. Does not rewrite the catalog or mark a photo verified."""
import concurrent.futures, csv, hashlib, io, json, pathlib, re, sys, urllib.request, urllib.error
from collections import Counter
ROOT = pathlib.Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")
start = HTML.index("const verifiedImageSeeds = {")
end = HTML.index("const imageSeedBatches", start)
block = HTML[start:end]
entries = re.findall(r"^\s*'(\d+)': \{ src: '([^']+)', source: '([^']+)' \},?", block, re.M)
rows = {}
duplicate_ids = []
for pid, url, source in entries:
    if pid in rows: duplicate_ids.append(pid)
    rows[pid] = {"id": pid, "url": url, "source": source}
UA = "Mozilla/5.0 (compatible; ArqanProductImageAudit/1.0)"
def check(row):
    result = dict(row, status="unknown", http_status="", bytes="", mime="", reason="")
    try:
        req = urllib.request.Request(row["url"], headers={"User-Agent": UA, "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8,*/*;q=0.5"})
        with urllib.request.urlopen(req, timeout=14) as resp:
            raw = resp.read(5 * 1024 * 1024)
            result["http_status"] = resp.status
            result["mime"] = resp.headers.get("Content-Type", "").split(";")[0].lower()
            result["bytes"] = len(raw)
            if not result["mime"].startswith("image/"):
                result["status"] = "invalid"
                result["reason"] = "response_is_not_an_image"
            elif len(raw) < 1000:
                result["status"] = "review"
                result["reason"] = "tiny_image_or_truncated"
            else:
                result["status"] = "loaded"
                result["reason"] = "image_downloaded_not_visually_approved"
    except Exception as err:
        result["status"] = "failed"
        result["reason"] = str(err)[:180]
    return result
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
    checked = sorted(pool.map(check, rows.values()), key=lambda r: int(r["id"]))
output = ROOT / "image-audit-report.csv"
with output.open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["id","status","http_status","bytes","mime","reason","source","url"])
    writer.writeheader()
    writer.writerows(checked)
counts = Counter(x["status"] for x in checked)
summary = {"unique_product_ids": len(rows), "duplicate_source_entries": sorted(set(duplicate_ids)), "counts": dict(counts), "note": "A loaded image is not necessarily the correct product: review placeholders and packaging visually."}
(ROOT / "image-audit-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
