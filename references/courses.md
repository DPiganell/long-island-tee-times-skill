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
| Wind Watch Golf & Country Club | wind-watch-golf-and-country-club | ~6 mi |
| Cherry Creek Golf Links | cherry-creek-golf-links | ~30 mi |
| The Woods at Cherry Creek | the-woods-at-cherry-creek | ~30 mi |

**Cherry Creek note:** the club's two courses (the par-73 Links + the shorter par-71 Woods) are **separate TeeItUp aliases**, each serving exactly one facility — so no `facility_id` filter is needed, same as Middle Island. The Links runs thin/late inventory (often only a couple morning slots, frequently 2-player-capped); the Woods carries the bulk of bookable foursomes.

### Multi-course alias: GolfNYC (`golf-nyc`)

All NYC city courses share **one** TeeItUp alias, `golf-nyc`, on `*.book.teeitup.com`
(note: `.com`, not `.golf`). A bare `tee-times?date=...` call with `x-be-alias: golf-nyc`
returns **all 9 courses** as separate list elements (each with its own 24-hex `courseId`).
To get a single course, append `&facilityIds=<id>&returnPromotedRates=true` — the id is
the course's GolfNow facility id, which also forms the booking deep-link
(`golf-nyc.book.teeitup.com/teetimes?course=<id>`).

`search_teeitup` keys off the per-course `facility_id` field: when present it filters the
API and derives the `Origin` header from `booking_url`'s host (so `.com` vs `.golf` is
handled automatically). NYC courses don't expose price in the API (resident/non-resident
rates are paid at the course), so `price` renders as `—`.

**How to find facility ids + names:** load `golf-nyc.book.teeitup.com` in a browser and
read `GET https://phx-api-be-east-1b.kenna.io/facilities` (with `x-be-alias: golf-nyc`).
It returns `{id, name, courseId}` for all 9.

| Course | facility_id | Borough | Distance |
|--------|-------------|---------|----------|
| Douglaston Golf Course | 5044 | Queens (Little Neck) | ~35 mi |
| Clearview Park Golf Course | 4047 | Queens (Bayside) | ~37 mi |
| Kissena Golf Course | 5046 | Queens (Flushing) | ~38 mi |
| Forest Park Golf Course | 5045 | Queens (Woodhaven) | ~42 mi |
| Van Cortlandt Golf Course | 5043 | Bronx | ~45 mi |
| Silver Lake Golf Course | 4757 | Staten Island | ~55 mi |
| South Shore Golf Course | 4051 | Staten Island | ~58 mi |
| La Tourette Golf Course | 4049 | Staten Island | ~57 mi |

**Not on `golf-nyc`:** Dyker Beach & Marine Park (Brooklyn) and Pelham/Split Rock & Mosholu
(Bronx) are run by a different concessionaire and not wired up — check GolfNow for those.
Flushing Meadows Pitch & Putt (id 16016) is on the alias but excluded (not a full round).
The Queens four are the natural meet-in-the-middle for a city friend + a Smithtown drive.

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

## GolfBack Courses (live API, no auth)

API: `POST https://api.golfback.com/api/v1/courses/{course_id}/date/{YYYY-MM-DD}/teetimes`
with body `{}`. Anonymous works (the real client posts `{sessionId}`, null when logged out).
The endpoint is **POST-only** — a GET returns 405.

| Course | course_id (UUID) | Distance |
|--------|------------------|----------|
| Willow Creek Golf Club | `3ac7c8dc-1b2b-4da8-9cf3-c874f999358e` | ~15 mi |

**Response shape:** `{"data": [ teetime, … ]}`. Each teetime has `id` (for the booking
deep-link), `localDateTime` (already local, no tz suffix), `isAvailable`, `playersMin`/
`playersMax` (booking group-size range, **not** open-spot count), and `rates[]` with
`{holes, hasCartIncluded, price, basePrice, name}`. Booking deep-link:
`https://golfback.com/course/{course_id}/date/{date}/teetime/{teeTimeId}`.

**Quirk — 2-some minimum:** Willow Creek (Invited/ClubCorp semi-private) enforces
`playersMin: 2` on most slots, so a 1-player search can find slots in-window that nobody
can solo-book. `search_golfback` reports this explicitly (e.g. "34 slots in window, but none
allow 1-player bookings (min 2-some)") rather than a misleading "no times" message.

**History:** Willow Creek previously appeared on Chronogolf (`hamlet-willow-creek-golf-country-club`)
but that listing now returns `{"status":"closed"}` for all dates — they migrated to GolfBack.

**How to find a GolfBack course_id:** the UUID is right in the course URL —
`https://golfback.com/course/<course_id>`. Endpoints live in the site's `js/app.min.js` +
`js/site.min.js` (`golfBackApiClient` wrapper); `baseUrl = https://api.golfback.com/`.

**CA note:** `api.golfback.com` chains through Sectigo Root R46, which the macOS system
bundle (`/etc/ssl/cert.pem`) can lack → `CERTIFICATE_VERIFY_FAILED`. `_resolve_ca_file()`
prefers the `certifi` Mozilla bundle, which includes R46.

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

## Club Caddie Courses (direct webapi handshake, no auth, no browser)

| Course | apikey | CourseId | Host | Distance |
|--------|--------|----------|------|----------|
| Spring Lake Golf Club | `ijfdabab` | `103499` | apimanager-cc37.clubcaddie.com | ~12 mi |

Spring Lake's booking SPA bootstraps a session, then fetches slots as an HTML
fragment. `search_clubcaddie_api` reproduces that with two plain HTTP calls:

1. **Bootstrap:** `GET {host}/webapi/view/{apikey}/slots?date=MM/DD/YYYY&player=N&ratetype=any&SetSessionIdInLocalStorage=true`
   → read the **`Session-Id`** response header. No cookie jar needed.
2. **Fetch:** `POST {host}/webapi/TeeTimes` (form-encoded) with
   `date, player, holes=any, fromtime=4, totime=23, minprice=0, maxprice=9999, ratetype=, HoleGroup=all, CourseId, apikey, Interaction=<Session-Id>`.
   The session is validated purely by the `Interaction` param echoing the bootstrapped id.

The response is HTML; each tee time is a **URL-encoded JSON object** embedded in a
row attribute (`%7B%22…%7D`). Decode with `urllib.parse.unquote` + `json.loads`.
Useful fields: `StartTime` (local `HH:MM:SS`), `PlayersAvailable`,
`MinimumPlayersAvailable` (booking floor — some slots are 2-some min),
`LowestPrice`/`HighestPrice`, `LowestPriceHoleRate_18`/`_9` (which determines
9 vs 18 holes), `HoleGroupAlias` (e.g. "Thunderbird 18", "Sandpiper 9").

**How to find apikey + CourseId for a new Club Caddie course:** open the course's
"book a tee time" page. The host + path give the apikey (`/webapi/view/<apikey>/slots`);
the CourseId is a hidden `<input name="CourseId" value="…">` in that page's HTML.
These can rotate — if the API breaks, switch the course's `strategy` back to
`clubcaddie_nav` (the Playwright fallback below, retained for that reason).

## Link-Only / Speculative Courses

| Course | Strategy | Notes |
|--------|----------|-------|
| _(none currently)_ | `clubcaddie_nav` | Playwright fallback: navigates from a course site and intercepts Club Caddie's API. Retained as a fallback for `clubcaddie_api` courses if their apikey/CourseId rotate. |

---

## GolfNow

GolfNow facility URLs (e.g. `/tee-times/facility/4762`) return 404 and their Cloudflare protection rejects headless browsers. The skill emits a single "All courses on GolfNow (area search)" footer entry as a catch-all — useful if the user wants to browse extra courses we don't have wired up directly.

---

## Adding a New Course

1. **Identify the booking platform** by visiting the course's website and clicking "book tee time". Inspect the URL:
   - `foreupsoftware.com/index.php/booking/F/S` → ForeUp (see "How to find a ForeUp schedule_id" above)
   - `*.book.teeitup.golf` → TeeItUp (slug is the subdomain)
   - `chronogolf.com/club/SLUG/teetimes` → Chronogolf (fetch the page and grab UUID from `__NEXT_DATA__`)
   - `golfback.com/course/UUID` → GolfBack (UUID is in the URL; POST API, no auth)
   - `apimanager-*.clubcaddie.com/webapi/view/<apikey>/slots` → Club Caddie (`clubcaddie_api`; apikey in URL, CourseId in a hidden input — see the Club Caddie section above)
   - Otherwise → likely `link_only`
2. **Add the entry** to the `COURSES` list in `scripts/search.py` with the appropriate `strategy` and required fields.
3. **Test:** `python3 scripts/search.py --date YYYY-MM-DD --start 06:00 --end 18:00 --players 2 --course "New Course"`

## Available Strategies

| Strategy | Description | Auth | Implementation |
|----------|-------------|------|----------------|
| `foreup` | Public ForeUp API by `schedule_id` | None | `search_foreup` |
| `teeitup` | Kenna API with `x-be-alias` header | None | `search_teeitup` |
| `chronogolf` | Public marketplace API by course UUID | None | `search_chronogolf` |
| `golfback` | Public GolfBack POST API by course UUID | None | `search_golfback` |
| `webtrac` | Shared Playwright session, batch search | `tee-times-webtrac` (user/pass) | `search_webtrac_batch` |
| `clubcaddie_api` | Club Caddie session bootstrap + `webapi/TeeTimes` POST | None | `search_clubcaddie_api` |
| `clubcaddie_nav` | Navigate from course site, intercept SPA (fallback) | None | `search_clubcaddie_nav` |
| `link_only` | Plain direct-link entry | None | `search_link_only` |
