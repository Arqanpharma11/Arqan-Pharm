#!/usr/bin/env python3
"""Migrate known old package image sources without overwriting pharmacy admin changes."""
import hashlib
import json
import pathlib
import re

root = pathlib.Path(__file__).resolve().parents[1]
index = root / "index.html"
html = index.read_text(encoding="utf-8")
legacy = {
    "3": "Lotus Pharmacies — Ibandrocare 150 mg, 2 film-coated tablets; exact brand and strength verified",
    "36": "PharmaciaTy — Epifasi 5000 IU, 1 ampoule plus solvent; exact brand and strength verified",
    "75": "Lotus Pharmacies — Atacand 4 mg, 14 tablets; exact brand and strength verified",
    "101": "Lotus Pharmacies — Atorstat 80 mg, 10 scored tablets; exact brand, strength and pack verified",
    "85": "Al-Dawaa Pharmacy — Atrovent 500 mcg/2 ml, 20 unit-dose inhalation vials; exact strength and pack verified",
    "86": "Al-Dawaa Pharmacy — Atrovent 250 mcg/2 ml, 20 unit-dose inhalation vials; exact strength and pack verified",
}
anchor = "Object.entries(verifiedImageSeeds).forEach(([id, seed]) => {"
predicate_old = "PROD_IMG_SRC[id] === seed.source ||"
predicate_new = (
    "PROD_IMG_SRC[id] === seed.source || "
    "(seed.src.startsWith('assets/product-images/') && "
    "Object.prototype.hasOwnProperty.call(imageLegacySeedSources, String(id)) && "
    "imageLegacySeedSources[String(id)] === PROD_IMG_SRC[id]) ||"
)
line = "const imageLegacySeedSources = " + json.dumps(legacy, ensure_ascii=False) + ";"
# One declared map, even when this script is run many times.
existing = re.search(r"const imageLegacySeedSources = \{[^;]*\};", html)
changed = False
if existing:
    if existing.group(0) != line:
        html = html[:existing.start()] + line + html[existing.end():]
        changed = True
else:
    if html.count(anchor) != 1:
        raise SystemExit("Cannot safely locate verified seed merge")
    html = html.replace(anchor, line + "\n                    " + anchor, 1)
    changed = True
if predicate_new not in html:
    if html.count(predicate_old) != 1:
        raise SystemExit("Cannot safely locate seed source predicate")
    html = html.replace(predicate_old, predicate_new, 1)
    changed = True
# A hash in the source is only updated when the migration set really changes.
fingerprint = hashlib.sha256(line.encode("utf-8")).hexdigest()[:12]
marker = "// imageSeedMigrationHash: "
marker_pattern = re.compile(r"// imageSeedMigrationHash: [0-9a-f]{12}")
found = marker_pattern.search(html)
if not found or found.group(0) != marker + fingerprint:
    html = marker_pattern.sub("", html, count=1)
    html = html.replace(line, marker + fingerprint + "\n                    " + line, 1)
    changed = True
if changed:
    version = re.search(r"arkan_verified_image_seed_v(\d+)", html)
    if not version:
        raise SystemExit("Image seed version is missing")
    html = html.replace(version.group(0), "arkan_verified_image_seed_v" + str(int(version.group(1)) + 1), 1)
    index.write_text(html, encoding="utf-8")
print("Migration source map updated" if changed else "Migration source map already current")
