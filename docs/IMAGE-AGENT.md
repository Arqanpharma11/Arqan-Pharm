# Arkan unattended image agent

Runs from GitHub Actions every 15 minutes (UTC schedule, best-effort), independently of a browser session.

## Current functionality
- Reads the 4,218 master items from `index.html`.
- Inspects 20 existing *candidate* image URLs per run, remembers 404/410 and records link health.
- With an optional **Brave Image Search API** key, searches 5 missing items per run and writes possible matches to `data/arkan-image-review-queue.json`.
- Does **not** publish unverified results as approved medical product images.
- With optional Firestore service account, reads `settings/catalog` so newly added items can be added to the review/search queue.
- Exports status to `data/arkan-image-agent-report.json`. Existing approved images in Firestore are not overwritten or deleted.

## Setup
1. In GitHub, open **Settings → Secrets and variables → Actions**.
2. Create a repository secret `BRAVE_IMAGE_API_KEY` with your paid/authorized Brave Image Search API token. Without this, the agent performs image link health checks, **not new image searches**.
3. To include products newly added in the app, create an *access-limited* Google Cloud service account permitted to read only the necessary Firestore document, and put its JSON in the secret `FIREBASE_SERVICE_ACCOUNT_JSON`. Do **not** commit this JSON or an admin login to the repository.
4. In **Actions → Arkan Auto Image Agent**, enable Actions for the repository if disabled and use **Run workflow** once. Confirm a successful run and inspect the report.

## Safety and limits
- The schedule can be delayed, and GitHub can disable it after 60 days of inactivity on public repositories.
- A search engine image result is not proof of correct drug, dosage form, pack, or copyright permission. The review queue must be validated against the actual package before approval.
- A health check cannot detect a *visually incorrect* image. Images are never automatically replaced solely on a search result, especially pharmaceuticals.
- Use image providers only under their terms and with permission to reproduce the images.
- The current architecture does not search every second or guarantee 4,218 verified photos; it provides a stable unattended processing and review pipeline.
