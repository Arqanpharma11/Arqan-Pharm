#!/usr/bin/env python3
"""Generate the Arqan admin's native ONE-FILE 4218-image upload template.

Only records explicitly approved after package review will be imported by the
existing admin import function; unverified candidates remain false.
"""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
index = json.loads((root / "data/arkan-all-4218-image-manifest.json").read_text(encoding="utf-8"))
candidates = json.loads((root / "data/arkan-image-candidate-review.json").read_text(encoding="utf-8"))
assert index["total"] == candidates["totalCatalogItems"] == 4218
by_id = {int(x["id"]): x for x in candidates["items"]}
rows = []
for item in index["items"]:
    id = int(item["id"])
    matching = by_id[id].get("candidates", [])
    recommended = matching[0] if matching else {}
    rows.append({
        "id": id,
        "name": item["name"],
        "category": item["category"],
        "englishName": by_id[id].get("englishName", "") or item.get("englishName", ""),
        "barcode": item.get("barcode", ""),
        "imageUrl": recommended.get("imageUrl", "") if not item.get("localImagePath") else "",
        "sourceName": recommended.get("sourceName", "") if not item.get("localImagePath") else "",
        "exactMatchConfirmed": False,
        "localImagePath": item.get("localImagePath", ""),
        "reviewStatus": ("already_hosted" if item.get("localImagePath") else
                         ("candidate_requires_package_review" if matching else "missing_image")),
        "candidateProductPage": recommended.get("productPage", ""),
        "candidateTitle": recommended.get("title", ""),
        "candidateScore": recommended.get("score"),
        "otherCandidates": matching[1:],
    })
assert len(rows) == len({x["id"] for x in rows}) == 4218
payload = {
    "format": "arkan-product-image-manifest", "version": 1,
    "total": 4218,
    "instruction": "For new product photos, confirm brand + strength + dosage form + pack size visually, then set exactMatchConfirmed=true. The admin import ignores all unapproved candidates. Existing local images remain untouched.",
    "items": rows,
}
target = root / "data/arkan-4218-bulk-image-upload-template.json"
target.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("Created admin-compatible 4218-row batch image file; candidate matches:",
      sum(x["reviewStatus"] == "candidate_requires_package_review" for x in rows),
      "; approved without review: 0")
