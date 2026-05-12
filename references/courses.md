# Tee Times — Course Directory

## Location Anchor
ZIP: 11755 (Smithtown, NY)

All course configuration lives in the `COURSES` list at the top of `scripts/search.py`.
Each entry declares its `strategy`, which the dispatcher in `main()` routes to the
matching `search_*` function.

---

## ForeUp Courses (live API, no auth)

API: `https://foreupsoftware.com/index.php/api/booking/times`

| Course | Schedule ID | Facility ID | Distance |
|--------|-------------|-------------|----------|
| Crab Meadow Golf Course | 8314 | 21593 | ~8 mi |
| Brentwood Country Club | 957 | 19105 | ~12 mi |
| Holbrook Country Club | 959 | 19107 | ~10 mi |
| Bethpage Black | 2431 | 19765 | ~20 mi |
| Bethpage Red | 2432 | 19765 | ~20 mi |
| Bethpage Blue | 2433 | 19765 | ~20 mi |
| Bethpage Green | 2434 | 19765 | ~20 mi |
| Bethpage Yellow | 2435 | 19765 | ~20 mi |
| Sunken Meadow State Park | 2437 | 19766 | ~5 mi |

**How to find a ForeUp schedule_id:** Fetch the booking page (e.g. `foreupsoftware.com/index.php/booking/{facility}/{url_id}`) and look for `DEFAULT_FILTER = {"schedule_id": N}` in the inline JS. The URL ID and the real schedule_id are often different (e.g. Brentwood URL is 19105 but real schedule_id is 957). For multi-course facilities like Bethpage, the `SCHEDULES` JS array lists every sub-schedule with its `teesheet_id` and `title`.

---

## TeeItUp Courses (live API, no auth)

API: `https://phx-api-be-east-1b.kenna.io/v2/tee-times?date=YYYY-MM-DD` with `x-be-alias` header.
**How to find the alias:** Visit the course's official tee-times page and look for the subdomain on `*.book.teeitup.golf/` or `*.book.teeitup.com/`. The subdomain IS the alias.

| Course | Alias | Distance |
|--------|-------|----------|
| Middle Island Country Club | middle-island-country-club | ~15 mi |
| Smithtown Landing CC | smithtown-landing-country-club | ~2 mi |
| Stonebridge Golf Links | stonebridge-golf-links-and-country-club | ~3 mi |

---

## Chronogolf Courses (Lightspeed; anonymous HTTP)

Strategy: Direct GET to `https://www.chronogolf.com/marketplace/v2/teetimes?course_ids=UUID,UUID&start_date=YYYY-MM-DD&affiliation_type_ids=1,2,3,4,5,6,7,8,9,18&nb_holes=18`.
**No authentication needed** — anonymous works. The trick is that `course_ids` takes
the *course* UUID(s) (from `club.courses[].uuid` in the club page's `__NEXT_DATA__`),
not the club UUID. Multi-course clubs join their sub-course UUIDs comma-separated.

| Course | Course UUID(s) | Slug | Distance |
|--------|----------------|------|----------|
| Swan Lake Golf Club | `7f42c719-...` (18) + `d2f045a1-...` (B9) | swan-lake-golf-club | ~18 mi |
| Spy Ring Golf Club | `d7b5a01d-...` (9) | spy-ring-golf-club | ~8 mi |
| Port Jefferson Country Club | `9325ab42-...` (18) | port-jefferson-country-club-at-harbor-hills | ~10 mi |
| Pine Hills Country Club | `f101336a-...` (18) | pine-hills-country-club-new-york | ~18 mi |

**Note:** Chronogolf also lists Smithtown Landing, Stonebridge, Timber Point, West Sayville, Indian Island, Bergen Point, and Long Island National — but those listings return 0 teetimes anonymously across all dates/params. Their real bookings happen on other platforms: TeeItUp for Smithtown Landing & Stonebridge; WebTrac for the 4 Suffolk County courses. Long Island National's true platform is unconfirmed (stale Chronogolf only).

**How to find course UUIDs for a new Chronogolf club:**
1. Visit `https://www.chronogolf.com/club/SLUG` in a browser
2. View source → find `<script id="__NEXT_DATA__">`
3. Look for `club.courses[].uuid` (each sub-course has its own UUID)
4. Pass them all as comma-separated `course_ids`

---

## WebTrac Courses (Suffolk County — Playwright + Green Key login)

Strategy: One shared Playwright browser logs into `nysuffolkctyweb.myvscloud.com/webtrac/web/login.html`
with stored credentials, then queries each course's `secondarycode` filter in turn.
All 4 facilities share a single login session for efficiency. Requires Suffolk County
account credentials in Keychain (`tee-times-webtrac`).

| Course | secondarycode | Distance |
|--------|---------------|----------|
| Bergen Point Golf Club | 1 | ~15 mi |
| Indian Island Country Club | 2 | ~30 mi |
| Timber Point Red (Red→Blue) | 3 | ~14 mi |
| Timber Point Blue (Blue→White) | 4 | ~14 mi |
| Timber Point White (9-hole) | 5 | ~14 mi |
| West Sayville Golf Course | 6 | ~13 mi |

**Why login is required:** WebTrac shows "no results" to anonymous users for every course/date combination. Logging in with a Suffolk County account (the same account tied to a Green Key card) unlocks the tee time grid.

---

## Link-Only / Speculative Courses

| Course | Strategy | Notes |
|--------|----------|-------|
| Spring Lake Golf Club | `clubcaddie_nav` | Playwright navigates from springlakegolfclub.com and tries to intercept Club Caddie's API. Falls back to link if interception fails. |

---

## GolfNow

GolfNow facility URLs (e.g. `/tee-times/facility/4762`) return 404 and their Cloudflare protection rejects headless browsers. The skill emits a single "All courses on GolfNow (area search)" footer entry as a catch-all — useful if the user wants to browse extra courses we don't have wired up directly.

---

## Adding a New Course

1. **Identify the booking platform** by visiting the course's website and clicking "book tee time". Inspect the URL:
   - `foreupsoftware.com/index.php/booking/F/S` → ForeUp (see "How to find a ForeUp schedule_id" above)
   - `*.book.teeitup.golf` → TeeItUp (slug is the subdomain)
   - `chronogolf.com/club/SLUG/teetimes` → Chronogolf (fetch the page and grab UUID from `__NEXT_DATA__`)
   - Otherwise → likely `link_only`
2. **Add the entry** to the `COURSES` list in `scripts/search.py` with the appropriate `strategy` and required fields.
3. **Test:** `python3 scripts/search.py --date YYYY-MM-DD --start 06:00 --end 18:00 --players 2 --course "New Course"`

## Available Strategies

| Strategy | Description | Auth | Implementation |
|----------|-------------|------|----------------|
| `foreup` | Public ForeUp API by `schedule_id` | None | `search_foreup` |
| `teeitup` | Kenna API with `x-be-alias` header | None | `search_teeitup` |
| `chronogolf` | Playwright + session cookie intercept | `tee-times-chronogolf-session` (cookie) | `search_chronogolf` |
| `webtrac` | Shared Playwright session, batch search | `tee-times-webtrac` (user/pass) | `search_webtrac_batch` |
| `clubcaddie_nav` | Navigate from course site, intercept SPA | None | `search_clubcaddie_nav` |
| `link_only` | Plain direct-link entry | None | `search_link_only` |
