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
    "85": "Al-Dawaa Pharmacy — Atrovent 500 mcg/2 ml, 20 unit-dose inhalation vials; exact strength and pack verified",
    "86": "Al-Dawaa Pharmacy — Atrovent 250 mcg/2 ml, 20 unit-dose inhalation vials; exact strength and pack verified",
}
# Scoped to the known historic source label ONLY. This protects manual admin changes.
mapping_line = "const imageLegacySeedSources = " + json.dumps(legacy, ensure_ascii=False) + ";"
anchor = "Object.entries(verifiedImageSeeds).forEach(([id, seed]) => {"
predicate_old = "PROD_IMG_SRC[id] === seed.source ||"
predicate_new = ("PROD_IMG_SRC[id] === seed.source || "
                 "(seed.src.startsWith('assets/product-images/') && "
                 "Object.prototype.hasOwnProperty.call(imageLegacySeedSources, String(id)) && "
                 "imageLegacySeedSources[String(id)] === PROD_IMG_SRC[id]) ||")
if mapping_line not in html:
    # Update a previous migration mapping in place instead of declaring the same const twice.
    existing = re.search(r"const imageLegacySeedSources = \\{[^;]*\\};", html)
    if existing:
        html = html[:existing.start()] + mapping_line + html[existing.end():]
    else:
        if html.count(anchor) != 1:
            raise SystemExit("Expected exactly one verified seed merge point; refusing unsafe edit")
        html = html.replace(anchor, mapping_line + "\n                    " + anchor, 1)
if predicate_new not in html:
    if html.count(predicate_old) != 1:
        raise SystemExit("Expected exactly one seed predicate; refusing unsafe edit")
    html = html.replace(predicate_old, predicate_new, 1)
# Version the existing one-shot seed merge; do not reseed on every page load.
version = re.search(r"arkan_verified_image_seed_v(\d+)", html)
if not version:
    raise SystemExit("Seed version marker not found")
if predicate_new in html:
    # The marker is introduced only once into the script's own anchor,
    # and prevents repeated version bumps on subsequent runs.
    marker = "// imageLegacySeedMigrationV1: source-specific upgrade"
    if marker not in html:
        html = html.replace(mapping_line, marker + "\n                    " + mapping_line, 1)
        html = html.replace(version.group(0), "arkan_verified_image_seed_v" + str(int(version.group(1))+1), 1)
HTML.write_text(html, encoding="utf-8")
print("Applied scoped image source migration for ids: " + ", ".join(legacy))
