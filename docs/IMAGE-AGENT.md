# Arkan Auto Image Agent — free, unattended

## Operation
GitHub Actions schedules a run every 15 minutes, even with browsers and computers shut down. Schedules are best-effort, not exact.

1. Read the master catalog of 4,218 products, and optionally read new products from Firestore with the `FIREBASE_SERVICE_ACCOUNT_JSON` repository secret.
2. Check existing image URLs for availability.
3. Query Wikimedia Commons and Open Food Facts / Open Beauty Facts via free public APIs.
4. Match product identity and concentration/pack size, recording ambiguous results for review.
5. For only **non-pharmaceutical products** with qualifying Open Facts product-front images, exact brand/size/form metadata, suitable source and licensing metadata, and a working image, automatically publish metadata in `data/arkan-auto-published-images.json`.
6. The browser automatically loads that manifest and shows published images with source attribution. Explicitly verified administrator images always take priority.
7. Retire a previously auto-published image after three separate definite 404/410 checks; never delete a verified admin image.

## What is *not* automated
Drug packaging and medically important products are **not** auto-approved from image-search titles: one wrong medicine, form or concentration is unacceptable. They remain review candidates. A search result, external image availability, or descriptive title is not sufficient visual validation. The agent does not promise full coverage of 4,218 products, and free databases may have little coverage of Egyptian drugs.

## Setup
On GitHub, open Actions → Arkan Auto Image Agent → Run workflow. A successful run creates a report (`data/arkan-image-agent-report.json`), review queue and auto-publication manifest. Run the UI and inspect real examples.

No paid search API is required. New items added solely in Firestore are not visible to the runner until `FIREBASE_SERVICE_ACCOUNT_JSON` is securely configured as a repository Actions secret with minimum necessary permissions. **Never commit credentials or share them in chat.**

## Provenance and rights
Automatically published images remain explicitly identified as automated and not visually verified. Image source links are visible in the product modal. Comply with image-specific attribution and licensing conditions; if the source does not allow display/reuse, do not publish it.

Run regression tests with `node --test scripts/arkan-auto-publish.test.cjs`.
