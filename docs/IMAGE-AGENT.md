# Arkan Auto Image Agent — free version

## Cost and runtime
The agent runs in GitHub Actions every 15 minutes, independently from visitors and browsers. Public GitHub repositories are eligible for free GitHub-hosted runner minutes subject to GitHub's current conditions. The schedule is **best effort**, not a guaranteed exact timer.

It checks existing candidate image URLs, and searches free public APIs:
- Wikimedia Commons: media search plus image-specific attribution and license metadata
- Open Food Facts: food, milk and some nutritional products
- Open Beauty Facts: cosmetics and beauty products

There is **no paid image-search API key** required for these searches. Follow each provider's API limits, licenses, and attribution rules.

## What it does
- Reads 4,218 master items from `index.html`
- Checks up to 20 existing candidate URLs each run, logging health results
- Searches up to five missing items per run, saving possible matches in `data/arkan-image-review-queue.json`
- Generates `data/arkan-image-agent-report.json`
- Never treats search matches as verified product packaging and never overwrites approved images
- Does not guarantee photos for all Egyptian medicines

## Start and observe
Open GitHub → Actions → **Arkan Auto Image Agent**, ensure Actions are enabled, click **Run workflow**, then inspect the report in `data/arkan-image-agent-report.json`. New queue results require human review of strength, dosage form, package and licensing.

## New products stored in Firestore
To discover products added from the admin UI when the browser is closed, the agent optionally reads `settings/catalog` using a scoped service-account credential named `FIREBASE_SERVICE_ACCOUNT_JSON` in GitHub Actions secrets. **Never commit credentials.** Without this setup, the agent continues processing the original 4,218 master items but cannot discover Firestore-only additions.

## Limits
The project cannot safely guarantee a new correct image every second or 100% image coverage. Wikimedia, food and cosmetics databases have incomplete Egyptian pharma catalog coverage. A successful URL fetch is not visual verification. Use authoritative licensed product images or a permissioned industry feed to scale pharmaceutical coverage.
