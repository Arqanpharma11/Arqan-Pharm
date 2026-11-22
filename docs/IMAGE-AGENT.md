# Arkan Auto Image Agent — free, unattended

## Operation
GitHub Actions schedules a run every 15 minutes, even with browsers and computers shut down. Schedules are best-effort, not exact.

1. Read the master catalog of 4,218 products, and optionally read new products from Firestore with the `FIREBASE_SERVICE_ACCOUNT_JSON` repository secret.
2. Check existing image URLs for availability.
3. For Egyptian medicines, look up an exact Arabic-name match in the free Egyptian Drug Database to obtain a more reliable English trade name and barcode. This database supplies **metadata, not photos**; ambiguous matches are ignored. Credit: Egyptian Drug Database by Mahmoud Mohamed, CC BY 4.0.
4. Query Wikimedia Commons and Open Food Facts / Open Beauty Facts via free public APIs.
5. Match product identity and concentration/pack size, recording ambiguous results for review.
6. For only **non-pharmaceutical products** with qualifying Open Facts product-front images, exact brand/size/form metadata, suitable source and licensing metadata, and a working image, automatically publish metadata in `data/arkan-auto-published-images.json`.
7. The browser automatically loads that manifest and shows published images with source attribution. Explicitly verified administrator images always take priority.
8. Retire a previously auto-published image after three separate definite 404/410 checks; never delete a verified admin image.

## What is *not* automated
Drug packaging and medically important products are **not** auto-approved from image-search titles: one wrong medicine, form or concentration is unacceptable. They remain review candidates. A search result, external image availability, or descriptive title is not sufficient visual validation. The agent does not promise full coverage of 4,218 products, and free databases may have little coverage of Egyptian drugs.

## Setup
On GitHub, open Actions → Arkan Auto Image Agent → Run workflow. A successful run creates a report (`data/arkan-image-agent-report.json`), review queue and auto-publication manifest. Run the UI and inspect real examples.

No paid search API is required. New items added solely in Firestore are not visible to the runner until `FIREBASE_SERVICE_ACCOUNT_JSON` is securely configured as a repository Actions secret with minimum necessary permissions. **Never commit credentials or share them in chat.**

## Provenance and rights
Automatically published images remain explicitly identified as automated and not visually verified. Image source links are visible in the product modal. Comply with image-specific attribution and licensing conditions; if the source does not allow display/reuse, do not publish it.

Run regression tests with `node --test scripts/arkan-auto-publish.test.cjs`.

## Full coverage limitation
Last confirmed report counted 1,335 existing external candidate links, 2,883 products with no external candidate link, and zero automatically published images. Those are **not** counts of independently verified photos. A genuine 100% package-photo library requires licensed images for each exact SKU plus visual/package verification; the free metadata sources alone cannot supply that.

## Full-coverage tracking (added November 2026)
Every scheduled run exports `data/arkan-image-coverage.csv`, one row per master-catalog SKU, and summary `data/arkan-image-coverage-report.json`.
Statuses distinguish candidates, missing images, broken candidate links, and automatically published images. **These are not equivalent to administrator-verified true pack photos.** The report intentionally does not count Firestore-admin-approved images since the hosted workflow cannot currently read that dataset without read-only credentials.

The search worker now prioritizes missing-image SKUs and also revisits uncertain/failed candidate-image entries. Search results are reconsidered after seven days (polite source limits apply); this avoids abandoning a product permanently after one empty query.

**To reach actual complete coverage**, obtain product pack assets from permitted manufacturers/distributors or another licensed package-image feed, with stable SKU identifiers and dosage form/strength and a review process. Free Commons/Open Facts data by itself is not comprehensive for Egypt's pharma market. Do not fabricate substitute package graphics or claim 100% from search-link count.
