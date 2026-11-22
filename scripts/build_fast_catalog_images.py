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
state_path = root / "data/arkan-image-agent-state.json"
state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
checks = state.get("checks", {})
# A shared image URL across different products is ambiguous even if the
# metadata score is high. Prefer unique alternatives instead of showing an
# identical carton for two different strengths or dosage forms.
candidate_rows = {}
url_product_ids = {}
for item in data["items"]:
    pid = str(item["id"])
    rows = [r for r in item.get("candidates", [])
            if isinstance(r, dict)
            and isinstance(r.get("imageUrl"), str)
            and r["imageUrl"].startswith("https://")
            and isinstance(r.get("title"), str)]
    candidate_rows[pid] = sorted(rows, key=lambda r: float(r.get("score") or 0), reverse=True)
    for row in rows:
        url_product_ids.setdefault(row["imageUrl"], set()).add(pid)

previous = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
previous_urls = {str(pid): row[0] for pid, row in previous.get("byId", {}).items()
                 if isinstance(row, list) and row}
by_id = {}
ambiguous_urls = sum(len(ids) > 1 for ids in url_product_ids.values())
for item in data["items"]:
    pid = str(item["id"])
    health = checks.get(pid, {})
    chosen = None
    for row in candidate_rows[pid]:
        url = row["imageUrl"]
        if len(url_product_ids[url]) > 1:
            continue
        if (health.get("failures", 0) >= 3 and health.get("lastStatus") == "gone"
                and previous_urls.get(pid) == url):
            continue
        chosen = row
        break
    if not chosen:
        continue
    by_id[pid] = [chosen["imageUrl"], chosen["title"],
                  str(chosen.get("sourceName", "")),
                  str(chosen.get("productPage", ""))]
result = {
    "version": 2, "total": 4218, "count": len(by_id),
    "excludedSharedUrlGroups": ambiguous_urls,
    "notice": "UNVERIFIED unique-url candidate images. Shared product photos are withheld; remaining catalog rows receive labeled illustration and web image search.",
    "byId": by_id
}
output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("Fast image candidates:", len(by_id), "/ 4218; no official images overwritten")
