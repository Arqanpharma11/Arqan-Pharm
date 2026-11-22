#!/usr/bin/env python3
"""Build compact browse-time candidate image map without changing index.html."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / "data/arkan-image-candidate-review.json"
output = root / "data/arkan-quick-image-candidates.json"
data = json.loads(source.read_text(encoding="utf-8"))
if data.get("totalCatalogItems") != 4218 or len(data.get("items", [])) != 4218:
    raise SystemExit("STOP: expected a 4218-item catalog review file")
by_id = {}
for item in data["items"]:
    id = str(item["id"])
    # Display candidates only. No candidate here is promoted to a verified pack.
    candidates = [r for r in item.get("candidates", [])
                  if isinstance(r.get("imageUrl"), str)
                  and r["imageUrl"].startswith("https://")
                  and isinstance(r.get("title"), str)]
    if not candidates:
        continue
    chosen = max(candidates, key=lambda r: float(r.get("score") or 0))
    by_id[id] = [chosen["imageUrl"], chosen["title"],
                 str(chosen.get("sourceName", "")),
                 str(chosen.get("productPage", ""))]
result = {
    "version": 1, "total": 4218, "count": len(by_id),
    "notice": "UNVERIFIED candidate images. All remaining catalog rows receive labeled illustration and web image search.",
    "byId": by_id
}
output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("Fast image candidates:", len(by_id), "/ 4218; no official images overwritten")
