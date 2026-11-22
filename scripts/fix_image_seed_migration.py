#!/usr/bin/env python3
"""Allow narrowly scoped catalog image source migrations without clobbering admin edits."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "index.html"
html = HTML.read_text(encoding="utf-8")
legacy = {
    "3": "Lotus Pharmacies — Ibandrocare 150 mg, 2 film-coated tablets; exact brand and strength verified",
    "36": "PharmaciaTy — Epifasi 5000 IU, 1 ampoule plus solvent; exact brand and strength verified",
    "75": "Lotus Pharmacies — Atacand 4 mg, 14 tablets; exact brand and strength verified",
    "101": "Lotus Pharmacies — Atorstat 80 mg, 10 scored tablets; exact brand, strength and pack verified",
}
# Scoped to the known historic source label ONLY. This protects manual admin changes.
mapping_line = "const imageLegacySeedSources = " + json.dumps(legacy, ensure_ascii=False) + ";"
anchor = "Object.entries(verifiedImageSeeds).forEach(([id, seed]) => {"
predicate_old = "PROD_IMG_SRC[id] === seed.source ||"
predicate_new = ("PROD_IMG_SRC[id] === seed.source || "
                 "(seed.src.startsWith('assets/product-images/') && "
                 "imageLegacySeedSources[String(id)] === PROD_IMG_SRC[id]) ||")
if mapping_line not in html:
    if html.count(anchor) != 1:
        raise SystemExit("Expected exactly one verified seed merge point; refusing unsafe edit")
    html = html.replace(anchor, mapping_line + "\n                    " + anchor, 1)
if predicate_new not in html:
    if html.count(predicate_old) != 1:
        raise SystemExit("Expected exactly one seed predicate; refusing unsafe edit")
    html = html.replace(predicate_old, predicate_new, 1)
# Guarantee migration runs even if a previous version was already marked as seeded.
if "imageLegacySeedMigrationV1" not in html:
    location = "if (localStorage.getItem(IMAGE_SEED_VERSION) !== '1') {"
    if html.count(location) != 1:
        raise SystemExit("Expected a single seed guard; refusing unsafe edit")
    html = html.replace(location,
        "if (localStorage.getItem(IMAGE_SEED_VERSION) !== '1' || "
        "localStorage.getItem('imageLegacySeedMigrationV1') !== '1') {", 1)
    # Marking the migration complete is intentionally not inserted into the existing code:
    # the added OR condition is idempotent, and avoids permanent old-source overrides.
HTML.write_text(html, encoding="utf-8")
print("Applied scoped image source migration for ids: " + ", ".join(legacy))
