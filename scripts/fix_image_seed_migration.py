#!/usr/bin/env python3
"""Keep precisely one locally verified image migration map in the pharmacy portal."""
import json
import pathlib
import re

root = pathlib.Path(__file__).resolve().parents[1]
index = root / "index.html"
original = index.read_text(encoding="utf-8")
legacy = {
    "3": "Lotus Pharmacies — Ibandrocare 150 mg, 2 film-coated tablets; exact brand and strength verified",
    "36": "PharmaciaTy — Epifasi 5000 IU, 1 ampoule plus solvent; exact brand and strength verified",
    "75": "Lotus Pharmacies — Atacand 4 mg, 14 tablets; exact brand and strength verified",
    "101": "Lotus Pharmacies — Atorstat 80 mg, 10 scored tablets; exact brand, strength and pack verified",
    "85": "Al-Dawaa Pharmacy — Atrovent 500 mcg/2 ml, 20 unit-dose inhalation vials; exact strength and pack verified",
    "86": "Al-Dawaa Pharmacy — Atrovent 250 mcg/2 ml, 20 unit-dose inhalation vials; exact strength and pack verified",
}
history_path = root / "scripts" / "image_legacy_source_map.json"
if history_path.exists():
    legacy.update(json.loads(history_path.read_text(encoding="utf-8")))
anchor = "Object.entries(verifiedImageSeeds).forEach(([id, seed]) => {"
if original.count(anchor) != 1:
    raise SystemExit("Unsafe: expected exactly one image seed merge")
start = original.index("const verifiedImageSeeds = {")
end = original.index("const imageSeedBatches", start)
prefix = original[:start]
block = original[start:end]
suffix = original[end:]
# Avoid bumping the image seed version on every scheduled run.
wanted_line = "const imageLegacySeedSources = " + json.dumps(legacy, ensure_ascii=False) + ";"
existing_maps = re.findall(r"const imageLegacySeedSources = \{[^;]*\};", block)
already_current = (
    existing_maps == [wanted_line]
    and "Object.prototype.hasOwnProperty.call(imageLegacySeedSources, String(id))" in block
    and "// imageLegacySeedMigrationV1: source-specific upgrade" not in block
)
if already_current:
    print("Migration map already current; no cache version change")
    raise SystemExit(0)
# Remove EVERY historical migration declaration, including duplicates that can stop JS startup.
block = re.sub(r"(?m)^[ \t]*const imageLegacySeedSources = \{[^\n;]*\};[ \t]*\n?", "", block)
block = re.sub(r"(?m)^[ \t]*// imageSeedMigrationHash: [0-9a-f]{12}[ \t]*\n?", "", block)
block = re.sub(r"(?m)^[ \t]*// imageLegacySeedMigrationV1: source-specific upgrade[ \t]*\n?", "", block)
line = "const imageLegacySeedSources = " + json.dumps(legacy, ensure_ascii=False) + ";"
block = block.replace(anchor, "                    " + line + "\n                    " + anchor, 1)
predicate_old = "PROD_IMG_SRC[id] === seed.source ||"
predicate_new = (
    "PROD_IMG_SRC[id] === seed.source || "
    "(seed.src.startsWith('assets/product-images/') && "
    "Object.prototype.hasOwnProperty.call(imageLegacySeedSources, String(id)) && "
    "imageLegacySeedSources[String(id)] === PROD_IMG_SRC[id]) ||"
)
if predicate_new not in block:
    if block.count(predicate_old) != 1:
        raise SystemExit("Unsafe: verified seed merge condition not found")
    block = block.replace(predicate_old, predicate_new, 1)
if block.count("const imageLegacySeedSources = ") != 1:
    raise SystemExit("Unsafe: multiple image legacy maps remain")
updated = prefix + block + suffix
if updated != original:
    version = re.search(r"arkan_verified_image_seed_v(\d+)", updated)
    if not version:
        raise SystemExit("Seed version marker missing")
    updated = updated.replace(version.group(0), "arkan_verified_image_seed_v" + str(int(version.group(1)) + 1), 1)
    index.write_text(updated, encoding="utf-8")
print("Image migration map normalized to exactly one declaration")
