# Golf Practice PWA

A small, offline-first practice tracker for putting + chipping sessions, built to be
installed on an iPhone from Safari via **Share → Add to Home Screen**. No accounts, no
backend, no analytics — everything is stored on-device in IndexedDB.

## Stack

Plain HTML/CSS/JS (ES modules), zero dependencies, no build step. Any static file host
works; the repo's GitHub Actions workflow deploys this folder to GitHub Pages.

| File | Purpose |
|---|---|
| `index.html` | App shell + bottom tab bar |
| `styles.css` | Mobile-first styles, light + dark via `prefers-color-scheme` |
| `app.js` | Screens, session flow, steppers/segments, autosave |
| `templates.js` | **Practice template registry** + metrics, comparisons, summary text |
| `db.js` | IndexedDB wrapper (`sessions` + `prefs` stores) |
| `charts.js` | Dependency-free SVG trend charts for the Progress tab |
| `sw.js` | Offline cache (bump `VERSION` on each deploy) |

## Adding a new practice template

Add an entry to `TEMPLATES` in `templates.js`. Drills are declarative:

- `kind: 'info'` — instructions only
- `kind: 'form'` — `fields` of `{type: 'stepper' | 'segment'}`, optional `sum`
  constraint (`max`, `exact`) and `live` derived stats
- `kind: 'holes'` — n score-entry rows with a three-putt flag

The drill UI, autosave, resume, history and summary all render from that shape. To
surface a new template's numbers in Progress/History, extend `computeMetrics` and
`PROGRESS_METRICS`.

## Local development

```sh
cd golf-practice
python3 -m http.server 8000
# open http://localhost:8000
```

Service workers require HTTPS or localhost. After changing any cached file, bump
`VERSION` in `sw.js` so installed clients pick up the update.
