#!/usr/bin/env python3
"""Fail deployment if verified image seeds break JavaScript or point to absent local photos."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
html = (root / "index.html").read_text(encoding="utf-8")
start = html.index("const verifiedImageSeeds = {")
end = html.index("const imageSeedBatches", start)
block = html[start:end]
matches = re.findall(r"(?m)^\\s*'([0-9]+)': \\{ src: '([^']+)', source: '[^']+' \\},?", block)
seen = set()
problems = []
for pid, src in matches:
    if pid in seen:
        problems.append("Duplicate seed id: " + pid)
    seen.add(pid)
    if src.startswith("assets/product-images/") and not (root / src).is_file():
        problems.append("Missing local image for product " + pid + ": " + src)
map_count = block.count("const imageLegacySeedSources = ")
if map_count != 1:
    problems.append("Expected one legacy migration map, found " + str(map_count))
if not matches:
    problems.append("No verified image seeds parsed")
if problems:
    raise SystemExit("\\n".join(problems[:30]))
print("PASS:", len(matches), "verified image seed entries,", map_count, "legacy migration map, local references exist")
