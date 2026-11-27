# Bay Area AI Navigator

A timeline that compares AI developments at Stanford, in Silicon Valley and in San Francisco on one time axis.

- `index.html` is the page. It reads `developments.json` from the same folder and checks it again every 5 minutes.
- `developments.json` holds the items. Each has a title, category, area, source URL, publication date and last-verified date.
- Opened straight from disk, the page shows a saved snapshot of six items. Served over http (GitHub Pages, or `python3 -m http.server`), it shows the file's contents.

Fictional coursework site, not affiliated with any organisation named on it.

## Publish with GitHub Pages
Settings, Pages, Build and deployment, Source: Deploy from a branch, Branch: `main`, folder `/ (root)`.
