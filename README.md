# Bay Area AI Navigator

A timeline that compares AI developments at Stanford, in Silicon Valley and in San Francisco on one time axis.

- `index.html` is the page. It reads `developments.json` from the same folder and checks it again every 5 minutes.
- `developments.json` holds the items. Each has a title, category, area, source URL, publication date and last-verified date.
- Opened straight from disk, the page shows a saved snapshot of six items. Served over http (GitHub Pages, or `python3 -m http.server`), it shows the file's contents.

Fictional coursework site, not affiliated with any organisation named on it.

## Automatic updates (GitHub Actions)
`.github/workflows/update-developments.yml` runs every hour (and on demand from the Actions tab). It runs `scripts/update_developments.py`, which reads the feeds listed in `sources.json`, keeps AI stories that name Stanford, Silicon Valley or San Francisco, scores them with the rubric in `developments.json` (admission threshold 50), adds at most three, and commits the result. Items it adds are labelled `assessed_by: automated`: the script cannot check that a story supports its headline. Each run prints how many stories every feed returned, so a wrong feed address shows up in the run log. If an address is an ordinary web page, the script follows the feed link the page advertises. Test offline with `python3 tests/test_update.py`.

## Publish with GitHub Pages
Settings, Pages, Build and deployment, Source: Deploy from a branch, Branch: `main`, folder `/ (root)`.
