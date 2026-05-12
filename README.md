# long-island-tee-times-skill

A Claude Code skill that aggregates live tee times from public golf booking
platforms — ForeUp, TeeItUp, Chronogolf, and Suffolk County WebTrac (authenticated) —
for ~20 public courses near Smithtown, NY (11755). One natural-language search
returns a consolidated table with live prices, available spots, and deep booking links.

## What it does

Invoke `/tee-times Saturday morning 2` from Claude Code and get back something like:

| Time | Course | Holes | Price | Source |
|------|--------|-------|-------|--------|
| 6:16am | Middle Island CC | 18 | $97 w/cart | TeeItUp |
| 7:12am | Spy Ring | 9 | $60 + $14 cart | Chronogolf |
| 10:40am | Timber Point White (9) | 9 | — (pay at course) | WebTrac |
| ... | ... | ... | ... | ... |

Each row links directly to the course's booking page, deep-linked to the selected date/time where the platform supports it.

## Quick start

```bash
# Clone to your Claude Code skills directory
git clone https://github.com/DPiganell/long-island-tee-times-skill ~/.claude/skills/tee-times

# Set up credentials & headless browser (optional but recommended)
bash ~/.claude/skills/tee-times/scripts/credentials.sh
```

Then in Claude Code:

```
/tee-times Saturday morning 2
/tee-times tomorrow afternoon 4 --course Bethpage
/tee-times 2026-06-15 8am-11am 2
```

## Supported courses (23 across 5 strategies)

| Strategy | Auth | Courses |
|----------|------|---------|
| **ForeUp** (public API) | none | Bethpage Black/Red/Blue/Green/Yellow, Sunken Meadow, Crab Meadow, Brentwood CC, Holbrook CC |
| **TeeItUp** (Kenna API) | none | Middle Island CC, Smithtown Landing, Stonebridge |
| **Chronogolf** (anonymous marketplace) | none | Swan Lake, Spy Ring, Pine Hills, Port Jefferson |
| **WebTrac** (Suffolk County) | login | Bergen Point, Indian Island, Timber Point Red/Blue/White, West Sayville |
| **Club Caddie nav** | none | Spring Lake (link fallback) |

Full course directory with IDs and how-to-find-them: [`references/courses.md`](references/courses.md).

## Architecture

Each course in [`scripts/search.py`](scripts/search.py) declares a `strategy`, and the dispatcher in `main()` routes it to the matching `search_*` function. All strategies share a common output shape (`time`, `course`, `holes`, `price`, `available_spots`, `source`, `booking_url`), with optional sentinel fields:

- `no_availability: true` — strategy reached the API but no slots in window (not an error)
- `error: "..."` — actual integration failure

Most strategies run in parallel via a thread pool. WebTrac batches all 6 Suffolk County courses through one shared Playwright login session for efficiency.

## Credentials & security

All credentials are stored in **macOS Keychain** — never on disk, never in this repo.

| Service | Required for | Type |
|---------|--------------|------|
| `tee-times-webtrac` | Suffolk County courses | Username + password |

ForeUp, TeeItUp, and Chronogolf all work anonymously — no credentials needed.

`scripts/credentials.sh` is idempotent (re-runnable) and uses delete-then-add to handle the macOS `security` CLI's quirky update behavior.

## Testing

Smoke test all 23 courses in ~60s:

```bash
python3 scripts/test_search.py        # one line per course
python3 scripts/test_search.py -v     # verbose unittest output
python3 scripts/test_search.py --date 2026-06-15
```

Sample output:

```
============================================================
  Tee Times Smoke Test
  Date: 2026-05-15  ·  Window: 06:00–20:00  ·  Players: 2
  Courses tested: 23
============================================================

  [LIVE ] Bergen Point Golf Club               [WebTrac    ]  32 live
  [LIVE ] Bethpage Red                         [ForeUp     ]  6 live
  [LIVE ] Middle Island Country Club           [TeeItUp    ]  25 live
  [LIVE ] Swan Lake Golf Club                  [Chronogolf ]  22 live
  [LINK ] Spring Lake Golf Club                [Club Caddie]  1 link
  ...
Ran 23 tests in 60.164s — OK
```

Three pass states: `LIVE` (bookable slots), `NA` (API reached, no slots in window), `LINK` (fallback link entry). Failures: `ERROR` (integration broken), `MISSING` (course absent from output), `WRONG_SRC` (wrong strategy used).

## Adding a course

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the per-platform recipe (how to find ForeUp `schedule_id`s, TeeItUp aliases, Chronogolf course UUIDs, WebTrac `secondarycode`s).

## Limitations

- **Geographic scope:** ZIP `11755` (Smithtown, NY) is hardcoded. Forking for other regions is straightforward — replace `COURSES` in `scripts/search.py` and the GolfNow area-search ZIP.
- **macOS only** for credential storage (uses `security` CLI / Keychain).
- **Playwright required** for WebTrac (6 courses) and Spring Lake nav.
- **Suffolk County WebTrac** requires a real account — `scripts/credentials.sh` walks through setup.
- **Spring Lake** uses Club Caddie's session-rotated URLs; we fall back to a direct link to their tee-times page.

## License

[MIT](LICENSE). No warranty — platform APIs can change at any time and break specific strategies. Run the smoke test (`python3 scripts/test_search.py`) to catch breakage early.
