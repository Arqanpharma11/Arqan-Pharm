#!/usr/bin/env python3
"""Explain whether a successful bot job ACTUALLY published new image assets.

GitHub Actions success means the workflow ran; publication is a separate fact.
Read-only checker, with machine-readable JSON output and Actions job summary.
"""
import json
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "data"

def load(name):
    return json.loads((root / name).read_text(encoding="utf-8"))

candidates = load("arkan-auto-published-images.json").get("byId", {})
agent = load("arkan-image-agent-report.json")
visual = load("arkan-visual-publish-report.json")
if not isinstance(candidates, dict):
    raise SystemExit("Invalid auto-publish manifest: byId is not a map")
eligible = len(candidates)
scanned = int(visual.get("scanned", 0)) if eligible else 0
published = int(visual.get("published", 0)) if eligible else 0
if not eligible:
    state = "blocked_no_eligible_image_records"
    message = "No eligible images reached OCR. The workflow succeeded but no pack photo could be published."
elif published:
    state = "published_ocr_screened_images"
    message = f"{published} image(s) passed the OCR packaging screen and were written as product image seeds."
elif scanned:
    state = "ocr_screened_none_accepted"
    message = f"OCR inspected {scanned} pack(s), but none passed the exact packaging checks."
else:
    state = "waiting_for_ocr_review"
    message = "Eligible image records exist, but OCR has not inspected any in this report."
out = {
    "status": state,
    "eligibleImageRecords": eligible,
    "ocrScanned": scanned,
    "newImagesPublished": published,
    "lastDiscoveryRun": agent.get("runAt"),
    "searchErrors": agent.get("searchErrors", 0),
    "sourceCooldowns": {
        host: row.get("retryAt")
        for host, row in (agent.get("providerHealth") or {}).items()
        if row.get("retryAt")
    },
}
print(json.dumps(out, ensure_ascii=False))
print(message)
if published == 0:
    print("::warning::Image publishing has not produced a new OCR-screened product image")
path = os.getenv("GITHUB_STEP_SUMMARY")
if path:
    summary = (
        "## Arkan real product-image publication status\n\n"
        "| Metric | Actual count |\n|---|---:|\n"
        f"| Images entering OCR | {eligible} |\n"
        f"| Images scanned by OCR | {scanned} |\n"
        f"| **New product images published** | **{published}** |\n\n"
        f"Status: \`{state}\`\n\n{message}\n"
    )
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(summary)
