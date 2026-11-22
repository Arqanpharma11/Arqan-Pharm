#!/usr/bin/env python3
"""Emergency fix for a frozen Arqan portal: deduplicate image migration declarations.

Only touches the extra const declarations; preserves the product catalog and all
pharmacist/admin, authentication and ordering code.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
html = INDEX.read_text(encoding="utf-8")
needle = "const imageLegacySeedSources = "
matches = list(re.finditer(r"(?m)^[ \t]*const imageLegacySeedSources = \\{[^;\\n]*\\};[ \t]*\\n?", html))
if not matches:
    raise SystemExit("STOP: expected legacy image declaration, none found; no changes")
# This is a conservative edit: keep the last declaration, which has the most
# recent migrated product ids, and remove all earlier duplicates.
if len(matches) > 1:
    for m in reversed(matches[:-1]):
        html = html[:m.start()] + html[m.end():]
    # The exact image-seed source map was changed; force a one-time refresh.
    version = re.search(r"arkan_verified_image_seed_v(\\d+)", html)
    if version:
        html = html[:version.start()] + "arkan_verified_image_seed_v" + str(int(version.group(1)) + 1) + html[version.end():]
    INDEX.write_text(html, encoding="utf-8")
    print(f"FIXED: removed {len(matches)-1} duplicate image migration declaration(s)")
else:
    print("OK: exactly one image migration declaration")
assert html.count(needle) == 1, "Image migration identifier still declared more than once"
