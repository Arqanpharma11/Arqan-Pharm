# Arkan Python image v2 — integration and measured assessment

Date: 2026-11-23

## What is connected
- User-supplied Python image finder: `scripts/product_images_v2.py`
- Arabic catalog and English trade-name bridge: `scripts/arkan-v2-bridge.cjs`
- Offline bilingual regression tests: `scripts/test_product_images_v2.py`
- Separate, unattended GitHub Actions workflow: `.github/workflows/arkan-python-image-v2.yml`
- Independent existing publication gate: `scripts/arkan-visual-publish.py`

The storefront **never runs image search or OCR**. Search happens in GitHub Actions; only photos that pass the separate source-eligibility and OCR review can be inserted into `verifiedImageSeeds`. Unknown or rejected images remain in Actions artifacts, not the pharmacist portal.

## What was fixed
- Arabic diacritics, Hamza, numeric and Arabic-to-English brand comparisons already existed in the uploaded script and were kept.
- Unsafe private-network URLs and redirections are rejected during downloads.
- Generic direct image URLs cannot skip independent verification.
- Medicine-strength and formulation mismatches are rejected.
- **10 tablets and 20 tablets** must not be auto-treated as the same retail package.
- A matching barcode cannot bypass other required match checks.
- Search result dimensions that appear as strings are parsed safely.
- Reserved IDs for PDF catalog additions are recognized in the existing visual publisher.

## Measured results vs unproven claims
- Deterministic offline regression tests passed for Arabic/English trade names, concentration, formulations, variants, pack quantities and unsafe URLs.
- The first 12-product GitHub run completed successfully as a workflow but returned **7 TypeError and 5 not_found; zero published**.
- A later 12-product run returned **11 TypeError and 1 not_found; zero published**.
- Following the pack-matching corrections another 12-product run returned **12 not_found; zero published**.
- A TypeError diagnostic and DDGS size parsing fix were subsequently committed; further runs must be examined independently.
- These tests do **not** establish real-world precision/recall or a 100% product-photo guarantee.

## Time and coverage outlook
Schedule: one batch of up to 12 eligible, uncovered products every three hours (up to **96 initial attempts per day**, before GitHub scheduler delays and source errors).
At this ceiling, 4,489 items would require about **47 days for one search pass**. The actual number of missing images and replenishment of new products can change the count.
This is **not** a prediction that 4,489 real, correctly verified photos will be published in 47 days: the observed first batches published zero. Full coverage has no reliable end date without a sufficiently broad licensed supplier image database and higher verified match yield.

## How to monitor
GitHub Actions > **Arkan bilingual Python image discovery**. Each run exposes `arkan-bilingual-image-review` (CSV plus non-published review images), and publishing reports at `data/arkan-visual-publish-report.json`.
The approval gate does not auto-publish ordinary medicines using search-engine results alone.
