# Contributing

## Adding a new course

1. **Identify the booking platform** by visiting the course's official website and clicking "book tee time". Inspect the resulting URL:

| URL pattern | Platform | Strategy | What to extract |
|-------------|----------|----------|-----------------|
| `foreupsoftware.com/index.php/booking/F/S` | ForeUp | `foreup` | `schedule_id` from inline JS `DEFAULT_FILTER = {"schedule_id": NNN}` (the URL ID and real schedule_id often differ — e.g. Brentwood's URL is 19105 but real schedule_id is 957). For multi-course facilities, the `SCHEDULES` JS array lists every sub-schedule with its `teesheet_id` and `title`. |
| `*.book.teeitup.golf` or `*.book.teeitup.com` | TeeItUp | `teeitup` | The subdomain IS the `alias` (e.g. `middle-island-country-club`) |
| `chronogolf.com/club/SLUG/teetimes` | Chronogolf | `chronogolf` | Fetch the page → `<script id="__NEXT_DATA__">` → `pageProps.club.courses[].uuid` (each sub-course has its own UUID; pass all comma-separated as `course_ids`) |
| `nysuffolkctyweb.myvscloud.com/webtrac` | Suffolk County | `webtrac` | The `secondarycode` value from the course dropdown on the WebTrac search form |
| `clubcaddie.com` | Club Caddie | `clubcaddie_nav` | No clean ID — set `intercept_patterns` and let Playwright capture API responses |
| Anything else | — | `link_only` | Just a direct URL |

2. **Add an entry to `COURSES`** in `scripts/search.py` (single source of truth). Match the existing format for the strategy.

3. **Add a `(name, source)` tuple** to `COURSES` in `scripts/test_search.py` so the smoke test covers it.

4. **Verify:** `python3 scripts/test_search.py` — expect 24/24 OK (or more).

5. **Update `references/courses.md`** with the new course's IDs and any platform-specific notes for future maintainers.

## Running tests

```bash
python3 scripts/test_search.py                  # one-line-per-course summary
python3 scripts/test_search.py -v               # verbose unittest output
python3 scripts/test_search.py --date 2026-06-15
python3 scripts/test_search.py TeeTimeStrategyTest.test_swan_lake_golf_club -v
```

The test is intentionally tolerant of empty-availability days. It only fails when:
- A course is missing from the search output (`MISSING`)
- A course returns an `error` entry (`ERROR`)
- A course returns from the wrong source (`WRONG_SRC`)

Tee time counts vary by day and time of day — that's not a regression.

## Reporting issues

When filing an issue, please include:
- The full test output: `python3 scripts/test_search.py -v 2>&1`
- The date and player count you tested with
- The platform that's misbehaving (one of: ForeUp / TeeItUp / Chronogolf / WebTrac / Club Caddie)
- Any error message from the JSON output (`error` field)

## Style

- Pure Python stdlib for HTTP where possible (search.py has no `requests` dependency)
- Playwright only for strategies that genuinely need a browser (WebTrac auth, Club Caddie nav)
- Each course is one row in `COURSES` — no per-course classes or files
- Strategies are pure functions: `search_X(course, date, start_h, end_h, players) -> list[dict]`

## Platform changes

When a platform changes its API surface, the symptom is usually all courses on that strategy flipping to `ERROR` in the test. To debug:

- Re-run the platform's known-working URL by hand
- Compare the response shape to what `search_X` expects
- If the shape changed, update the parser; if the endpoint changed, update the URL builder

The smoke test is the regression detector — run it before merging changes.
