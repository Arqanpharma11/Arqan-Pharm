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

## Latest operational checks
- A subsequent 12-product run completed successfully with **12 image candidates sent to review**, no Python errors, and **zero automatic publications**. Ten conflicted across sources, one failed OCR, one was insufficiently confirmed.
- The catalog export was corrected to follow the **294 excluded master positions** defined by `PDF_EXCLUDED_MASTER_POSITIONS`, not the older 314-ID set. This aligns the search target with the same **4,489 approved PDF items** used by the live catalog.
- The strict publisher also recognizes the reserved IDs of products appended after index 4,218.
- No completion probability can be credibly quantified from a sample with no approved publication; **47 days refers to one pass of search attempts only** at 96 attempts/day.

## Final verified run after exact 4,489-product export
- Workflow: https://github.com/Arqanpharma11/Arqan-Pharm/actions/runs/45213620173
- GitHub Actions result: **success**.
- Catalog source: **4,783 master records**, minus **294 excluded PDF positions**, producing **4,489 approved records**.
- Search queue remaining relative to **embedded approved photo seeds**: **3,900** (this does not include independent Firestore photos).
- This run searched 12 products: **3 review** (conflicting photographs), **9 not_found**, **0 newly published**.
- Synthetic bilingual tests and portal JavaScript syntax checks passed.
- A 3-hour/12-product cadence takes about **41 days for a single pass across 3,900 uncovered records**, without claiming all will yield valid reusable photos.
