---
name: tee-times
description: "Search and aggregate local golf tee times from public APIs (ForeUp, TeeItUp, Chronogolf) for courses near Smithtown, NY (11755). Covers Bethpage State Park, Sunken Meadow, Middle Island CC, Crab Meadow, Brentwood, Holbrook, Swan Lake, Smithtown Landing, Stonebridge, Spring Lake. Use when asking for available tee times, golf availability, or wanting to book a round. Trigger phrases: 'tee time', 'golf tomorrow', 'find golf', 'book a round', 'open tee times'."
argument-hint: "[date] [time-range] [players] [--course NAME]"
allowed-tools:
  - Bash
  - Read
---

<objective>
Search local public golf courses near Smithtown, NY for available tee times matching the user's date, time window, and player count. Each course runs its own live-data strategy (ForeUp API, TeeItUp API, Chronogolf via Playwright+session, or a direct link for courses without a usable API). Present results as a scannable table with booking links.
</objective>

<course_directory>
Covered courses (with their live-data strategy) are listed in:
~/.claude/skills/tee-times/references/courses.md
</course_directory>

<credential_setup>
Credentials are stored in macOS Keychain — never on disk.
First-run setup: `bash ~/.claude/skills/tee-times/scripts/credentials.sh`

Services stored:
  tee-times-webtrac             → Suffolk County login (for Timber Point, West Sayville, Indian Island, Bergen Point)
  tee-times-golfnow             → optional, kept for compatibility
  tee-times-nysparks            → optional, kept for compatibility

Chronogolf no longer needs a session cookie — Swan Lake works anonymously via the
public marketplace API.
</credential_setup>

<process>

## Step 1: Parse Input

Resolve the user's natural-language input to concrete values.

**Date resolution** (today is the current system date):
- "today" → today's date in YYYY-MM-DD
- "tomorrow" → tomorrow's date
- "this Saturday" / "Saturday" → next upcoming Saturday
- "May 16" / "5/16" → 2026-05-16 (current year unless past)
- Explicit YYYY-MM-DD → use as-is

**Time range resolution:**
- "morning" → 06:00–12:00
- "afternoon" → 12:00–17:00
- "early morning" / "dawn patrol" → 06:00–09:00
- "midday" → 10:00–14:00
- "8am–11am" / "8-11" → 08:00–11:00
- No time specified → 06:00–18:00 (full day)

**Players:**
- If not specified in args, ask: "How many players?"

**Holes (default depends on group size):**
- A **foursome (4 players) defaults to 18 holes** — pass `--holes 18`. A foursome wants a full round; 9-hole loops (and 9-hole-only courses) are noise.
- For 1–3 players, default to **all holes** (omit `--holes`) unless the user says otherwise.
- Explicit overrides always win: "9 holes" / "twilight 9" → `--holes 9`; "18" → `--holes 18`; "any holes" / "include 9" → omit the flag.

**Course filter (optional):**
- "--course Crab Meadow" or "just Crab Meadow" → pass `--course "Crab Meadow"` to the script
- "Bethpage" → matches all 5 Bethpage courses (Black, Red, Blue, Green, Yellow)

## Step 2: Run the Search Script

```bash
python3 ~/.claude/skills/tee-times/scripts/search.py \
  --date DATE \
  --start HH:MM \
  --end HH:MM \
  --players N \
  [--holes 18] \
  [--course "COURSE NAME"]
```

`--holes 18` drops every 9-hole result (9-hole-only courses and the 9-hole loops
of mixed courses like Spring Lake's Sandpiper or Swan Lake's back-9). Default it
on for a foursome per Step 1.

No `--headless` flag is needed — each course picks its own strategy automatically. Chronogolf courses spin up Playwright internally (~5–10s); the rest hit public APIs (~1s).

The script outputs a JSON array. Capture it.

## Step 3: Render Results

Parse the JSON and render a markdown table sorted by time. When the result count is very large (50+), it's fine to group consecutive same-course/same-price entries into ranges (e.g. "2:00pm–3:30pm").

**Table format:**
```
## Tee Times — [Day, Month D] · [H:MMam–H:MMpm] · [N] players

| Time  | Course                       | Holes | Price          | Source     | Book |
|-------|------------------------------|-------|----------------|------------|------|
| 7:30  | Bethpage Black               | 18    | $50            | ForeUp     | [Book →](url) |
| 7:42  | Crab Meadow                  | 18    | $29 + $18 cart | ForeUp     | [Book →](url) |
| 8:00  | Middle Island CC             | 18    | $87 w/cart     | TeeItUp    | [Book →](url) |
| 8:15  | Swan Lake                    | 18    | $75 + $18 cart | Chronogolf | [Book →](url) |
| —     | Spring Lake Golf Club        | 18    | see Club Caddie| Club Caddie| [View →](url) |
```

**Formatting rules:**
- Sort by time; "—" times go at the bottom.
- `price` is already formatted: e.g. `$38 + $18 cart` or `—` if not in the booking system (pay at course).
- For entries with `no_availability: true`: include the course with time "—", spots "0", and "None in window" in the Book column. Show the `detail` field (e.g., "has 14 slots at other times") as a sub-note so the user knows it's not an error — the course just doesn't have anything in the requested window.
- For entries with `error`: show below the table as `⚠ [Course] ([source]): [short error]`. Do not put error entries in the main table.
- For Spring Lake (link_only Club Caddie entry): show "see Club Caddie" in Price and link to their tee-times page — it's a fallback because Club Caddie has no stable scraping URL.
- Always include the "All courses on GolfNow (area search)" footer entry as a catch-all.

## Step 4: Offer Follow-Up

After the table, add:
```
---
Want me to search a different time, filter to one course (e.g. Bethpage), or check a different date?
```

</process>

<error_handling>
- Script exits non-zero → show stderr output, suggest re-running credentials.sh if Chronogolf is involved.
- Chronogolf entry with "Session expired" error → "Your Chronogolf session cookie has expired. Re-run `bash ~/.claude/skills/tee-times/scripts/credentials.sh` and paste a fresh _chronogolf_session value from a logged-in browser."
- All live sources error → say so explicitly and surface the "All courses on GolfNow" area-search link as the fallback.
- No results in time window → "No tee times found in that window. Want to widen the time range or check a different day?"
</error_handling>

<examples>
/tee-times tomorrow morning 2
→ Searches tomorrow 6am–12pm for 2 players across all courses

/tee-times Saturday 8am-11am 4
→ Searches next Saturday 8–11am for 4 players, 18-hole only (foursome default → --holes 18)

/tee-times Saturday morning 2 9 holes
→ Searches next Saturday 6am–12pm for 2 players, 9-hole only (--holes 9)

/tee-times 2026-05-16 afternoon 2 --course Bethpage
→ Searches May 16 afternoon for 2 across all 5 Bethpage courses

"find me a tee time this weekend morning"
→ Clarify: Saturday or Sunday? Then search that day 6am–12pm
</examples>
