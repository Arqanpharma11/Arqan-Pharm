#!/usr/bin/env python3
"""Validate startup-critical inline JavaScript in the pharmacy portal.

Fail before publishing broken catalog image updates. Does not modify index.html.
"""
import pathlib
import re
import subprocess
import tempfile

root = pathlib.Path(__file__).resolve().parents[1]
html = (root / "index.html").read_text(encoding="utf-8")
tags = list(re.finditer(r"<script\\b([^>]*)>([\\s\\S]*?)</script\\s*>", html, re.I))
if not tags:
    raise SystemExit("ERROR: No script tags in pharmacy portal; cannot smoke-check JS")

checked = 0
failures = []
for number, match in enumerate(tags, start=1):
    attributes = match.group(1)
    js = match.group(2)
    if re.search(r"\\bsrc\\s*=", attributes, re.I) or not js.strip():
        continue
    kind = re.search(r"\\btype\\s*=\\s*['\\\"]?([^\\s'\\\">]+)", attributes, re.I)
    script_type = kind.group(1).lower() if kind else "text/javascript"
    if script_type not in ("module", "text/javascript", "application/javascript"):
        continue
    extension = ".mjs" if script_type == "module" else ".js"
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / ("inline_script_" + str(number) + extension)
        path.write_text(js, encoding="utf-8")
        run = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True, timeout=35)
        checked += 1
        if run.returncode:
            failures.append("Script " + str(number) + ": " + run.stderr[-1600:])
if checked == 0:
    raise SystemExit("ERROR: No inline executable JavaScript was checked")
if failures:
    raise SystemExit("Portal JavaScript syntax ERROR:\\n" + "\\n".join(failures))
print("PASS: checked", checked, "inline JavaScript blocks for syntax errors")
