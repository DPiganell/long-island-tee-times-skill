# long-island-tee-times-skill

A Claude Code skill that aggregates live tee times from public golf booking
platforms — ForeUp, TeeItUp, Chronogolf, GolfBack, Club Caddie, and Suffolk
County WebTrac (authenticated) — for ~35 public courses near Smithtown, NY
(11755). One natural-language search returns a consolidated table with live
prices, available spots, and deep booking links.

## What it does

Invoke `/tee-times Saturday morning 2` from Claude Code and get back something like:

| Time | Course | Holes | Price | Source |
|------|--------|-------|-------|--------|
| 6:06am | Spring Lake (Sandpiper) | 9 | $37–$51 | Club Caddie |
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

## Supported courses (35 across 6 strategies)

| Strategy | Auth | Courses |
|----------|------|---------|
| **ForeUp** (public API) | none | Bethpage Black/Red/Blue/Green/Yellow, Sunken Meadow, Crab Meadow, Brentwood CC, Holbrook CC |
| **TeeItUp** (Kenna API) | none | Middle Island CC, Smithtown Landing, Stonebridge, Wind Watch, Cherry Creek Links, The Woods at Cherry Creek, + 8 NYC city courses on the shared `golf-nyc` alias (Douglaston, Clearview, Kissena, Forest Park, Van Cortlandt, Silver Lake, South Shore, La Tourette) |
| **Chronogolf** (anonymous marketplace) | none | Swan Lake, Spy Ring, Pine Hills, Port Jefferson |
| **GolfBack** (anonymous POST API) | none | Willow Creek |
| **Club Caddie** (direct webapi handshake) | none | Spring Lake |
| **WebTrac** (Suffolk County) | login | Bergen Point, Indian Island, Timber Point Red/Blue/White, West Sayville |

Full course directory with IDs and how-to-find-them: [`references/courses.md`](references/courses.md).

## Architecture

Each course in [`scripts/search.py`](scripts/search.py) declares a `strategy`, and the dispatcher in `main()` routes it to the matching `search_*` function. All strategies share a common output shape (`time`, `course`, `holes`, `price`, `available_spots`, `source`, `booking_url`), with optional sentinel fields:

- `no_availability: true` — strategy reached the API but no slots in window (not an error)
- `error: "..."` — actual integration failure

Most strategies run in parallel via a thread pool. A few notes on the trickier ones:

- **TeeItUp** serves both single-course aliases and multi-course aliases — the NYC `golf-nyc` alias returns all 8 city courses at once, filtered per course by GolfNow `facility_id`.
- **GolfBack** is a POST-only API; `api.golfback.com` chains through a newer CA root (Sectigo R46), so the script prefers the `certifi` bundle when resolving TLS.
- **Club Caddie** (Spring Lake) needs no browser: it bootstraps a session at `/webapi/view/{apikey}/slots` (reading the `Session-Id` response header), then POSTs the search form to `/webapi/TeeTimes` and decodes the URL-encoded JSON slot blobs from the HTML. A legacy Playwright nav strategy (`clubcaddie_nav`) is retained as a fallback if the apikey/CourseId ever rotate.
- **WebTrac** batches all 6 Suffolk County courses through one shared Playwright login session for efficiency.

## Credentials & security

All credentials are stored in **macOS Keychain** — never on disk, never in this repo.

| Service | Required for | Type |
|---------|--------------|------|
| `tee-times-webtrac` | Suffolk County courses | Username + password |

ForeUp, TeeItUp, Chronogolf, GolfBack, and Club Caddie all work anonymously — no credentials needed.

`scripts/credentials.sh` is idempotent (re-runnable) and uses delete-then-add to handle the macOS `security` CLI's quirky update behavior.

## Testing

Smoke test all 35 courses in ~60s:

```bash
python3 scripts/test_search.py        # one line per course
python3 scripts/test_search.py -v     # verbose unittest output
python3 scripts/test_search.py --date 2026-06-15
```

Sample output:

```
============================================================
  Tee Times Smoke Test
  Date: 2026-06-15  ·  Window: 06:00–20:00  ·  Players: 2
  Courses tested: 35
============================================================

  [LIVE ] Bergen Point Golf Club               [WebTrac    ]  32 live
  [LIVE ] Bethpage Red                         [ForeUp     ]  6 live
  [LIVE ] Cherry Creek Golf Links              [TeeItUp    ]  22 live
  [LIVE ] Middle Island Country Club           [TeeItUp    ]  25 live
  [LIVE ] Spring Lake Golf Club                [Club Caddie]  20 live
  [LIVE ] Swan Lake Golf Club                  [Chronogolf ]  22 live
  [LIVE ] Willow Creek Golf Club               [GolfBack   ]  14 live
  ...
Ran 35 tests in 60.164s — OK
```

Three pass states: `LIVE` (bookable slots), `NA` (API reached, no slots in window), `LINK` (fallback link entry). Failures: `ERROR` (integration broken), `MISSING` (course absent from output), `WRONG_SRC` (wrong strategy used).

## Adding a course

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the per-platform recipe (how to find ForeUp `schedule_id`s, TeeItUp aliases, Chronogolf course UUIDs, GolfBack course UUIDs, Club Caddie apikey/CourseId, WebTrac `secondarycode`s).

## Limitations

- **Geographic scope:** ZIP `11755` (Smithtown, NY) is hardcoded. Forking for other regions is straightforward — replace `COURSES` in `scripts/search.py` and the GolfNow area-search ZIP.
- **macOS only** for credential storage (uses `security` CLI / Keychain).
- **Playwright required** only for WebTrac (6 Suffolk County courses) and the legacy Club Caddie nav fallback. Every other strategy is plain HTTP.
- **Suffolk County WebTrac** requires a real account — `scripts/credentials.sh` walks through setup.
- **Platform APIs drift:** booking platforms can change endpoints or tokens at any time (Club Caddie's apikey/CourseId in particular can rotate). Run the smoke test to catch breakage early.

## License

[MIT](LICENSE). No warranty — platform APIs can change at any time and break specific strategies. Run the smoke test (`python3 scripts/test_search.py`) to catch breakage early.
