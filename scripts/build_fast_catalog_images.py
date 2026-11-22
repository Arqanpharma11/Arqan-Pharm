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
by_id = {}
for item in data["items"]:
    id = str(item["id"])
    # Display candidates only. No candidate here is promoted to a verified pack.
    candidates = [r for r in item.get("candidates", [])
                  if isinstance(r.get("imageUrl"), str)
                  and r["imageUrl"].startswith("https://")
                  and isinstance(r.get("title"), str)]
    # The previous feed selected the top-ranked candidate. If its repeated
    # 404/410 failures were confirmed, fall back to another candidate or none.
    chosen = max(candidates, key=lambda r: float(r.get("score") or 0)) if candidates else None
    health = checks.get(id, {})
    if chosen and health.get("failures", 0) >= 3 and health.get("lastStatus") == "gone":
        candidates = [r for r in candidates if r.get("imageUrl") != chosen["imageUrl"]]
        chosen = max(candidates, key=lambda r: float(r.get("score") or 0)) if candidates else None
    if not chosen:
        continue
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
