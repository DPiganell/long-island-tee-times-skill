#!/usr/bin/env python3
"""
Tee time aggregator for Smithtown, NY (11755) area golf courses.
Queries ForeUp API (live), GolfNow facility pages (best-effort), and
generates static NYS Parks links.

Usage:
  python3 search.py --date 2026-05-16 --start 08:00 --end 11:00 --players 2
  python3 search.py --date 2026-05-16 --start 08:00 --end 11:00 --players 2 --course "Crab Meadow"

Output: JSON array of tee time objects, one per available slot.
"""

import argparse
import json
import os
import re
import ssl
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

EDT = timezone(timedelta(hours=-4))  # Eastern Daylight Time (May–Nov)

# Use system CA bundle — Python's bundled cert store on macOS is often stale
_CA_CANDIDATES = [
    "/etc/ssl/cert.pem",
    "/opt/homebrew/etc/openssl@3/cert.pem",
    "/usr/local/etc/openssl/cert.pem",
]
_CA_FILE = next((p for p in _CA_CANDIDATES if os.path.exists(p)), None)


def _ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context(cafile=_CA_FILE)
    return ctx

ZIP_CODE = "11755"

# Unified course directory. Each entry declares its live `strategy`, picked up by main().
#
# Strategies:
#   "foreup"     — public ForeUp API (no auth needed)
#   "teeitup"    — public TeeItUp/Kenna API (x-be-alias header)
#   "chronogolf" — Chronogolf (Lightspeed); Playwright + stored session cookie
#   "clubcaddie" — Club Caddie SPA; Playwright + response interception (auto-headless)
COURSES = [
    # --- ForeUp (Town of Huntington / Town of Islip / NYS Parks) ------------
    {"name": "Crab Meadow Golf Course",   "strategy": "foreup", "schedule_id": "8314", "facility_id": "21593"},
    {"name": "Brentwood Country Club",    "strategy": "foreup", "schedule_id": "957",  "facility_id": "19105"},
    {"name": "Holbrook Country Club",     "strategy": "foreup", "schedule_id": "959",  "facility_id": "19107"},
    # Bethpage State Park — 5 main courses on ForeUp (facility 19765, schedule IDs from JS SCHEDULES)
    {"name": "Bethpage Black",            "strategy": "foreup", "schedule_id": "2431", "facility_id": "19765"},
    {"name": "Bethpage Red",              "strategy": "foreup", "schedule_id": "2432", "facility_id": "19765"},
    {"name": "Bethpage Blue",             "strategy": "foreup", "schedule_id": "2433", "facility_id": "19765"},
    {"name": "Bethpage Green",            "strategy": "foreup", "schedule_id": "2434", "facility_id": "19765"},
    {"name": "Bethpage Yellow",           "strategy": "foreup", "schedule_id": "2435", "facility_id": "19765"},
    # Sunken Meadow State Park — 18-hole on ForeUp
    {"name": "Sunken Meadow State Park",  "strategy": "foreup", "schedule_id": "2437", "facility_id": "19766"},

    # --- TeeItUp (Kenna) ----------------------------------------------------
    {"name": "Middle Island Country Club", "strategy": "teeitup",
     "alias": "middle-island-country-club",
     "booking_url": "https://middle-island-country-club.book.teeitup.golf"},
    {"name": "Smithtown Landing CC", "strategy": "teeitup",
     "alias": "smithtown-landing-country-club",
     "booking_url": "https://smithtown-landing-country-club.book.teeitup.com"},
    {"name": "Stonebridge Golf Links", "strategy": "teeitup",
     "alias": "stonebridge-golf-links-and-country-club",
     "booking_url": "https://stonebridge-golf-links-and-country-club.book.teeitup.golf"},

    # --- Chronogolf (Lightspeed) — anonymous HTTP, no auth needed ----------
    # Use COURSE UUIDs (from club.courses[].uuid in the club page __NEXT_DATA__),
    # NOT the club UUID. Multi-course clubs combine sub-course UUIDs comma-separated.
    {"name": "Swan Lake Golf Club",       "strategy": "chronogolf",
     "course_ids": [
         "7f42c719-4d75-4e47-8d52-b464cc1c0842",  # 18-hole regulation
         "d2f045a1-32de-4129-b144-da1713a81a98",  # B9 ONLY (back-9 only)
     ],
     "chronogolf_slug": "swan-lake-golf-club",
     "url": "https://www.chronogolf.com/club/swan-lake-golf-club/teetimes",
     "note": "Manorville · 27 holes"},
    {"name": "Spy Ring Golf Club",         "strategy": "chronogolf",
     "course_ids": ["d7b5a01d-6a8e-4909-84fd-5b7b5f44bfbc"],
     "chronogolf_slug": "spy-ring-golf-club",
     "url": "https://www.chronogolf.com/club/spy-ring-golf-club/teetimes",
     "note": "Setauket · 9 holes",
     "holes": 9},
    {"name": "Port Jefferson Country Club","strategy": "chronogolf",
     "course_ids": ["9325ab42-eeb1-439d-9737-a6ebd42b2c63"],
     "chronogolf_slug": "port-jefferson-country-club-at-harbor-hills",
     "url": "https://www.chronogolf.com/club/port-jefferson-country-club-at-harbor-hills/teetimes",
     "note": "Port Jefferson · 18 holes"},
    {"name": "Pine Hills Country Club",    "strategy": "chronogolf",
     "course_ids": ["f101336a-f518-44a3-9a0a-51382615ba9b"],
     "chronogolf_slug": "pine-hills-country-club-new-york",
     "url": "https://www.chronogolf.com/club/pine-hills-country-club-new-york/teetimes",
     "note": "Manorville · 18 holes"},

    # --- Suffolk County WebTrac — Playwright + Green Key login ----------------
    # `secondarycode` is the WebTrac course filter value.
    # All 4 facilities share one login session — main() batches them together.
    {"name": "Bergen Point Golf Club",     "strategy": "webtrac",
     "secondarycode": "1",
     "note": "West Babylon · Town of Babylon"},
    {"name": "Indian Island Country Club", "strategy": "webtrac",
     "secondarycode": "2",
     "note": "Riverhead · Suffolk County"},
    {"name": "Timber Point Red",           "strategy": "webtrac",
     "secondarycode": "3",
     "note": "Great River · 18 holes Red→Blue"},
    {"name": "Timber Point Blue",          "strategy": "webtrac",
     "secondarycode": "4",
     "note": "Great River · 18 holes Blue→White"},
    {"name": "Timber Point White (9)",     "strategy": "webtrac",
     "secondarycode": "5",
     "note": "Great River · 9 holes only",
     "holes": 9},
    {"name": "West Sayville Golf Course",  "strategy": "webtrac",
     "secondarycode": "6",
     "note": "West Sayville · Suffolk County"},

    # --- Club Caddie — Playwright nav from course site, then intercept --------
    # Spring Lake's Club Caddie URLs are session-rotated. Strategy: load the
    # course's own tee-times page, click the booking link, then intercept the
    # API call the resulting SPA makes. Marked "speculative" — may degrade
    # to link-only if Club Caddie still 404s after navigation.
    {"name": "Spring Lake Golf Club",      "strategy": "clubcaddie_nav",
     "url": "https://springlakegolfclub.com/golf/tee-times",
     "platform": "Club Caddie",
     "intercept_patterns": ["apirest", "clubcaddie.com", "teetime"],
     "note": "Middle Island · Championship public course"},
]

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


# ---------------------------------------------------------------------------
# Credential helpers
# ---------------------------------------------------------------------------

def get_keychain_password(service: str) -> str | None:
    """Retrieve a password from macOS Keychain without printing it."""
    result = subprocess.run(
        ["security", "find-generic-password", "-s", service, "-w"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def get_keychain_account(service: str) -> str | None:
    """Retrieve the account (email/username) for a Keychain entry."""
    result = subprocess.run(
        ["security", "find-generic-password", "-s", service],
        capture_output=True,
        text=True,
    )
    match = re.search(r'"acct"<blob>="([^"]+)"', result.stdout)
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# ForeUp
# ---------------------------------------------------------------------------

def _to_foreup_date(date_str: str) -> str:
    """Convert YYYY-MM-DD to MM-DD-YYYY (ForeUp API format)."""
    y, m, d = date_str.split("-")
    return f"{m}-{d}-{y}"


def search_foreup(course: dict, date_str: str, start_h: int, end_h: int, players: int) -> list[dict]:
    """Query ForeUp's public API for available tee times."""
    params = {
        "schedule_id": course["schedule_id"],
        "date": _to_foreup_date(date_str),  # ForeUp requires MM-DD-YYYY
        "players": players,
        "holes": 18,
        "time": "all",
    }
    url = "https://foreupsoftware.com/index.php/api/booking/times?" + urlencode(params)
    req = Request(url, headers={**BROWSER_HEADERS, "X-Requested-With": "XMLHttpRequest"})

    try:
        with urlopen(req, timeout=12, context=_ssl_ctx()) as resp:
            raw = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (HTTPError, URLError, json.JSONDecodeError) as e:
        return [_error_entry(course["name"], "ForeUp", str(e))]

    slots = raw if isinstance(raw, list) else raw.get("times", raw.get("data", []))
    if not isinstance(slots, list):
        return [_error_entry(course["name"], "ForeUp", f"Unexpected response shape: {type(raw)}")]

    results = []
    for slot in slots:
        raw_time = slot.get("time", "")
        if not raw_time:
            continue
        # ForeUp returns "YYYY-MM-DD HH:MM" — extract just "HH:MM" for filtering/display
        time_part = str(raw_time).split(" ")[-1][:5]  # "HH:MM"
        try:
            t = datetime.strptime(time_part, "%H:%M")
            if t.hour < start_h or t.hour >= end_h:
                continue
        except ValueError:
            pass

        # Build price string: green fee + cart fee if both are available
        green = slot.get("green_fee_18") or slot.get("green_fee") or 0
        cart = slot.get("cart_fee_18") or slot.get("cart_fee") or 0
        try:
            green = float(green)
            cart = float(cart)
            if green > 0 and cart > 0:
                price = f"${green:.0f} + ${cart:.0f} cart"
            elif green > 0:
                price = f"${green:.0f}"
            else:
                price = "—"  # Price not in system; pay at course
        except (ValueError, TypeError):
            price = "—"

        booking_url = (
            f"https://foreupsoftware.com/index.php/booking/"
            f"{course.get('facility_id', course['schedule_id'])}/{course['schedule_id']}"
        )
        results.append({
            "time": time_part,
            "course": course["name"],
            "holes": slot.get("holes", 18),
            "price": price,
            "available_spots": slot.get("available_spots_18", slot.get("available_spots", players)),
            "source": "ForeUp",
            "booking_url": booking_url,
        })

    if not results:
        # API succeeded but nothing in the requested window
        total = len([s for s in slots if s.get("time")])
        msg = f"No times in window (course has {total} slot{'s' if total != 1 else ''} on other times)"
        return [_no_availability_entry(course["name"], "ForeUp",
                                       f"https://foreupsoftware.com/index.php/booking/"
                                       f"{course.get('facility_id', course['schedule_id'])}/{course['schedule_id']}",
                                       msg)]
    return results


# ---------------------------------------------------------------------------
# GolfNow
# ---------------------------------------------------------------------------

def _golfnow_search_url(date_str: str, start_h: int, end_h: int, players: int) -> str:
    """Build a GolfNow search URL for the area (fallback link, not scraped)."""
    fragment = urlencode({
        "sortby": "Date",
        "view": "list",
        "holes": 3,
        "min-players": players,
        "max-players": players,
        "address": ZIP_CODE,
        "date": date_str,
        "min-time": f"{start_h:02d}:00",
        "max-time": f"{end_h:02d}:00",
        "min-price": 0,
        "max-price": 500,
    })
    return f"https://www.golfnow.com/tee-times/search#{fragment}"


# ---------------------------------------------------------------------------
# Link-only strategy — direct link entry, no live fetch attempted
# ---------------------------------------------------------------------------

def search_link_only(course: dict, date_str: str, start_h: int, end_h: int, players: int) -> list[dict]:
    """Emit a direct-link entry for courses whose booking platform has no usable API."""
    return [{
        "time": "—",
        "course": course["name"],
        "holes": 18,
        "price": f"see {course.get('platform','site')}",
        "available_spots": "?",
        "source": course.get("platform", "Link"),
        "booking_url": course["url"],
        "note": course.get("note", "Book directly on course site"),
    }]


# ---------------------------------------------------------------------------
# TeeItUp (public API via phx-api-be-east-1b.kenna.io)
# ---------------------------------------------------------------------------

def search_teeitup(course: dict, date_str: str, start_h: int, end_h: int, players: int) -> list[dict]:
    """Query TeeItUp's Kenna API for available tee times."""
    url = f"https://phx-api-be-east-1b.kenna.io/v2/tee-times?date={date_str}"
    req = Request(url, headers={
        **BROWSER_HEADERS,
        "Accept": "application/json",
        "Origin": f"https://{course['alias']}.book.teeitup.golf",
        "x-be-alias": course["alias"],
    })
    try:
        with urlopen(req, timeout=12, context=_ssl_ctx()) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (HTTPError, URLError, json.JSONDecodeError) as e:
        return [_error_entry(course["name"], "TeeItUp", str(e))]

    results = []
    for day in data if isinstance(data, list) else [data]:
        for slot in day.get("teetimes", []):
            # "teetime" is UTC ISO — convert to Eastern time
            raw_ts = slot.get("teetime", "")
            try:
                dt_utc = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                dt_et = dt_utc.astimezone(EDT)
                time_part = dt_et.strftime("%H:%M")
                if dt_et.hour < start_h or dt_et.hour >= end_h:
                    continue
            except (ValueError, AttributeError):
                time_part = raw_ts[:5] if raw_ts else "?"

            # players filter: slot must have capacity for requested group size
            max_p = slot.get("maxPlayers", 4)
            booked = slot.get("bookedPlayers", 0)
            available = max_p - booked
            if players and available < players:
                continue

            # Price: first rate's greenFeeCart is in cents
            price = "?"
            rates = slot.get("rates", [])
            if rates:
                r0 = rates[0]
                cents = r0.get("greenFeeCart", 0)
                try:
                    if float(cents) > 0:
                        price = f"${float(cents)/100:.0f} w/cart"
                    else:
                        price = "—"
                except (ValueError, TypeError):
                    price = "?"
            holes = rates[0].get("holes", 18) if rates else 18

            results.append({
                "time": time_part,
                "course": course["name"],
                "holes": holes,
                "price": price,
                "available_spots": available,
                "source": "TeeItUp",
                "booking_url": f"{course['booking_url']}",
            })

    if not results:
        total = sum(len(day.get("teetimes", [])) for day in (data if isinstance(data, list) else [data]))
        msg = f"No times in window (course has {total} slot{'s' if total != 1 else ''} on other times)"
        return [_no_availability_entry(course["name"], "TeeItUp", course["booking_url"], msg)]
    return results



# ---------------------------------------------------------------------------
# Chronogolf (Swan Lake) — authenticated API using stored session cookie
# ---------------------------------------------------------------------------

def _parse_chronogolf_teetimes(raw: list, start_h: int, end_h: int, course: dict,
                                players: int = 1) -> list[dict]:
    """Parse Chronogolf tee time objects into standardized dicts.
    Field reference (from live intercept):
      starts_at: "2026-05-16T09:45:00Z" (UTC ISO)
      start_time: "5:45" (local time, already EDT)
      max_player_size: int — max group size for this slot
      default_price.green_fee: float (dollars)
      default_price.half_cart: float (dollars, per person)
      course.holes: int
    """
    results = []
    for slot in raw:
        # Skip slots that can't accommodate the group size
        max_p = slot.get("max_player_size") or slot.get("maxPlayerSize") or 4
        if players and int(max_p) < players:
            continue

        # Time — prefer start_time (already local) over parsing starts_at (UTC)
        local_time = slot.get("start_time", "")
        if local_time:
            try:
                parts = local_time.split(":")
                h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
                if h < start_h or h >= end_h:
                    continue
                time_str = f"{h:02d}:{m:02d}"
            except (ValueError, IndexError):
                time_str = local_time
        else:
            raw_ts = slot.get("starts_at", "")
            try:
                dt = datetime.fromisoformat(raw_ts.replace("Z", "+00:00")).astimezone(EDT)
                if dt.hour < start_h or dt.hour >= end_h:
                    continue
                time_str = dt.strftime("%H:%M")
            except (ValueError, AttributeError):
                time_str = "?"

        # Price — default_price contains green_fee and cart fields
        pricing = slot.get("default_price") or {}
        green = pricing.get("green_fee") or 0
        cart = pricing.get("half_cart") or pricing.get("one_person_cart") or 0
        try:
            green, cart = float(green), float(cart)
            if green > 0 and cart > 0:
                price = f"${green:.0f} + ${cart:.0f} cart"
            elif green > 0:
                price = f"${green:.0f}"
            else:
                price = "—"
        except (ValueError, TypeError):
            price = "?"

        course_info = slot.get("course", {})
        holes = course_info.get("holes", slot.get("holes", 18))
        slot_uuid = slot.get("uuid", "")
        book_url = (
            f"https://www.chronogolf.com/club/{course['chronogolf_slug']}/teetimes/{slot_uuid}"
            if slot_uuid else course["url"]
        )
        results.append({
            "time": time_str,
            "course": course["name"],
            "holes": holes,
            "price": price,
            "available_spots": max_p,
            "source": "Chronogolf",
            "booking_url": book_url,
        })
    return results


def search_chronogolf(course: dict, date_str: str, start_h: int, end_h: int, players: int) -> list[dict]:
    """
    Fetch tee times from Chronogolf's public /marketplace/v2/teetimes API.
    NO auth required — pass course UUIDs (not the club UUID) and the API returns
    teetimes anonymously. The session cookie / Playwright dance from earlier
    versions turned out to be unnecessary once we used `course_ids` instead of
    the club UUID.

    Required course config fields:
      - course_ids: list[str]      # 1+ course UUIDs from club.courses[].uuid
      - chronogolf_slug: str       # for building the public booking URL
    """
    course_ids = course.get("course_ids") or []
    if not course_ids:
        return [_error_entry(course["name"], "Chronogolf",
                             "Missing 'course_ids' in course config")]

    params = {
        "start_date": date_str,
        "course_ids": ",".join(course_ids),
        # Affiliation set seen in the live anonymous request — covers public bookings
        "affiliation_type_ids": "1,2,3,4,5,6,7,8,9,18",
        "nb_holes": "18",
    }
    api_url = "https://www.chronogolf.com/marketplace/v2/teetimes?" + urlencode(params)
    req = Request(api_url, headers={**BROWSER_HEADERS, "Accept": "application/json"})

    try:
        with urlopen(req, timeout=12, context=_ssl_ctx()) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except HTTPError as e:
        return [_error_entry(course["name"], "Chronogolf", f"HTTP {e.code}")]
    except (URLError, json.JSONDecodeError) as e:
        return [_error_entry(course["name"], "Chronogolf", str(e))]

    teetimes = (
        data.get("teetimes")
        or data.get("data", {}).get("teetimes")
        or (data if isinstance(data, list) else [])
    )

    results = _parse_chronogolf_teetimes(teetimes, start_h, end_h, course, players)
    if not results:
        return [_no_availability_entry(
            course["name"], "Chronogolf", course["url"],
            f"No times in window (course has {len(teetimes)} slot{'s' if len(teetimes) != 1 else ''} at other times)",
        )]
    return results


# ---------------------------------------------------------------------------
# Playwright headless fallback (last resort — requires: pip3 install playwright
#                                                         playwright install chromium)
# ---------------------------------------------------------------------------

def search_playwright(course: dict, date_str: str, start_h: int, end_h: int, players: int) -> list[dict]:
    """
    Last-resort headless tee time fetch for courses without a public API.
    Uses response interception to capture the JSON the booking page fetches,
    rather than parsing HTML — more resilient to DOM changes.
    Requires: pip3 install playwright && playwright install chromium
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        return [_error_entry(
            course["name"], course["platform"],
            "Playwright not installed. Run: pip3 install playwright && playwright install chromium",
        )]

    # Build the URL with date / player params injected
    base_url = course.get("headless_url", course["url"])
    extra = course.get("headless_params", {})
    params = {"date": date_str, "nb_players": str(players), **extra}
    full_url = base_url + "?" + urlencode(params)

    patterns = [p.lower() for p in course.get("intercept_patterns", [])]
    captured: list[dict] = []

    def on_response(response):
        if not any(pat in response.url.lower() for pat in patterns):
            return
        ct = response.headers.get("content-type", "")
        if "json" not in ct:
            return
        try:
            data = response.json()
            if data:
                captured.append({"url": response.url, "data": data})
        except Exception:
            pass

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=BROWSER_HEADERS["User-Agent"],
                locale="en-US",
            )
            page = ctx.new_page()
            page.on("response", on_response)
            page.goto(full_url, timeout=30000, wait_until="networkidle")
            browser.close()
    except PWTimeout:
        return [_error_entry(course["name"], course["platform"],
                             "Headless browser timed out (30s). Site may be slow or blocking.")]
    except Exception as e:
        return [_error_entry(course["name"], course["platform"], f"Headless browser error: {e}")]

    if not captured:
        return [_no_availability_entry(
            course["name"], course["platform"], course["url"],
            "Headless: no tee time API calls captured — site may have changed",
        )]

    return _parse_playwright_responses(course, captured, start_h, end_h, players)


def _parse_playwright_responses(
    course: dict, captured: list[dict], start_h: int, end_h: int, players: int
) -> list[dict]:
    """Parse raw JSON responses captured during headless browsing into TeeTime dicts."""
    platform = course["platform"]
    results = []
    total_raw = 0

    for entry in captured:
        data = entry["data"]

        if platform == "Chronogolf":
            # Same shape as /marketplace/v2/teetimes: {data: {teetimes: [...]}}
            teetimes = (
                data.get("data", {}).get("teetimes")
                or data.get("teetimes")
                or (data if isinstance(data, list) else [])
            )
            total_raw += len(teetimes)
            for slot in teetimes:
                raw_time = slot.get("startsAt") or slot.get("start_at") or slot.get("time", "")
                try:
                    dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00")).astimezone(EDT)
                    time_str = dt.strftime("%H:%M")
                    if dt.hour < start_h or dt.hour >= end_h:
                        continue
                except (ValueError, AttributeError):
                    time_str = raw_time[:5] if raw_time else "?"

                green = slot.get("greenFee") or slot.get("green_fee") or 0
                try:
                    price = f"${float(green):.0f}" if float(green) > 0 else "—"
                except (ValueError, TypeError):
                    price = "?"

                spots = slot.get("availableSpots", slot.get("available_spots", "?"))
                results.append({
                    "time": time_str,
                    "course": course["name"],
                    "holes": slot.get("holes", 18),
                    "price": price,
                    "available_spots": spots,
                    "source": platform,
                    "booking_url": course["url"],
                })

        elif platform == "Club Caddie":
            # Club Caddie API shape is unknown until captured; try common patterns
            rows = (
                data.get("tee_times") or data.get("teeTimes") or data.get("times")
                or data.get("data") or (data if isinstance(data, list) else [])
            )
            if not isinstance(rows, list):
                continue
            total_raw += len(rows)
            for slot in rows:
                raw_time = (
                    slot.get("tee_time") or slot.get("teeTime") or slot.get("time") or ""
                )
                try:
                    # Try ISO first, then HH:MM
                    if "T" in raw_time:
                        dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00")).astimezone(EDT)
                        time_str = dt.strftime("%H:%M")
                        h = dt.hour
                    else:
                        time_str = raw_time[:5]
                        h = int(time_str.split(":")[0])
                    if h < start_h or h >= end_h:
                        continue
                except (ValueError, AttributeError, IndexError):
                    time_str = raw_time[:5] if raw_time else "?"

                fee = slot.get("green_fee") or slot.get("greenFee") or slot.get("price") or 0
                try:
                    price = f"${float(fee):.0f}" if float(fee) > 0 else "—"
                except (ValueError, TypeError):
                    price = "?"

                results.append({
                    "time": time_str,
                    "course": course["name"],
                    "holes": slot.get("holes", 18),
                    "price": price,
                    "available_spots": slot.get("available_spots", "?"),
                    "source": platform,
                    "booking_url": course["url"],
                })

    if not results:
        detail = f"No times in window" + (f" (captured {total_raw} raw slots)" if total_raw else "")
        return [_no_availability_entry(course["name"], platform, course["url"], detail)]
    return results


# ---------------------------------------------------------------------------
# Suffolk County WebTrac — Playwright with shared login session
# (Bergen Point, Indian Island, Timber Point R/B/W, West Sayville)
# ---------------------------------------------------------------------------

WEBTRAC_BASE = "https://nysuffolkctyweb.myvscloud.com/webtrac/web"


def search_webtrac_batch(
    courses: list[dict], date_str: str, start_h: int, end_h: int, players: int
) -> list[dict]:
    """
    Run a single Playwright session for all WebTrac courses.
    Logs in once, then submits the search form per-course.
    Requires Suffolk County credentials in Keychain (service: tee-times-webtrac).
    """
    username = get_keychain_account("tee-times-webtrac")
    password = get_keychain_password("tee-times-webtrac")
    if not username or not password:
        # No creds — emit link-only entries for each
        webtrac_search_url = f"{WEBTRAC_BASE}/search.html?display=detail&module=GR"
        return [
            {
                "time": "—", "course": c["name"], "holes": c.get("holes", 18),
                "price": "see WebTrac", "available_spots": "?", "source": "WebTrac",
                "booking_url": webtrac_search_url,
                "note": c.get("note", "") + " · (store WebTrac creds via credentials.sh for live data)",
            }
            for c in courses
        ]

    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        return [_error_entry(c["name"], "WebTrac",
                             "Playwright not installed. Run: pip3 install playwright && playwright install chromium")
                for c in courses]

    # Convert YYYY-MM-DD → MM/DD/YYYY for WebTrac
    y, m, d = date_str.split("-")
    wt_date = f"{m}/{d}/{y}"

    all_results: list[dict] = []

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=BROWSER_HEADERS["User-Agent"],
                viewport={"width": 1280, "height": 900},
            )
            page = ctx.new_page()

            # --- LOGIN ---
            page.goto(f"{WEBTRAC_BASE}/login.html", timeout=20000, wait_until="networkidle")
            page.fill("#weblogin_username", username)
            page.fill("#weblogin_password", password)
            page.click("#weblogin_buttonlogin")
            page.wait_for_load_state("networkidle", timeout=15000)

            # Verify login succeeded: check for the login form still being present
            if page.locator("#weblogin_username").count() > 0:
                browser.close()
                return [_error_entry(c["name"], "WebTrac",
                                     "Login failed — check stored Suffolk County credentials")
                        for c in courses]

            # --- SEARCH each course ---
            for course in courses:
                holes = course.get("holes", 18)
                params = {
                    "display": "detail",
                    "module": "GR",
                    "secondarycode": course["secondarycode"],
                    "begindate": wt_date,
                    "numberofplayers": str(players),
                    "numberofholes": str(holes),
                }
                from urllib.parse import urlencode as _ue
                search_url = f"{WEBTRAC_BASE}/search.html?{_ue(params)}"
                try:
                    page.goto(search_url, timeout=20000, wait_until="networkidle")
                    page.click("#grwebsearch_buttonsearch", timeout=8000)
                    page.wait_for_load_state("networkidle", timeout=15000)
                    page.wait_for_timeout(1500)
                except PWTimeout:
                    all_results.append(_error_entry(course["name"], "WebTrac", "Search timed out"))
                    continue

                # Detect "no results" first
                no_results = page.locator("#grwebsearch_noresultsmessage").count() > 0
                if no_results:
                    visible_text = page.locator("#grwebsearch_noresultsmessage").inner_text()
                    if "did not return" in visible_text.lower():
                        all_results.append(_no_availability_entry(
                            course["name"], "WebTrac", search_url,
                            "No times in window",
                        ))
                        continue

                # Parse tee time rows — real bookable rows are <tr> elements whose
                # text starts with "Add To Cart" followed by a time and date.
                # Example: "Add To Cart 3:00 pm 05/16/2026 18 (Front) Bergen Point Golf Course"
                slots = page.evaluate("""() => {
                    const rows = document.querySelectorAll('tr');
                    const found = [];
                    rows.forEach(r => {
                        const txt = r.innerText.replace(/\\s+/g, ' ').trim();
                        // Must say "Add To Cart" AND contain a time. This filters out
                        // header rows, dropdown options, and structural scaffolding.
                        if (/Add To Cart/i.test(txt) && /\\b\\d{1,2}:\\d{2}\\s*(AM|PM)\\b/i.test(txt)) {
                            found.push(txt);
                        }
                    });
                    return found;
                }""")

                if not slots:
                    all_results.append(_no_availability_entry(
                        course["name"], "WebTrac", search_url,
                        "No bookable rows found in window",
                    ))
                    continue

                # Parse each slot row's text for time / price
                for raw in slots:
                    parsed = _parse_webtrac_row(raw, course, search_url, start_h, end_h, players)
                    if parsed:
                        all_results.append(parsed)

            browser.close()
    except Exception as e:
        return [_error_entry(c["name"], "WebTrac", str(e)) for c in courses]

    if not all_results:
        # Last-resort fallback per course
        return [_no_availability_entry(c["name"], "WebTrac",
                                       f"{WEBTRAC_BASE}/search.html?display=detail&module=GR",
                                       "Logged in but no results")
                for c in courses]
    return all_results


def _parse_webtrac_row(raw: str, course: dict, booking_url: str,
                       start_h: int, end_h: int, players: int) -> dict | None:
    """Extract time/price/spots from a WebTrac result row's text."""
    # Time — match first "HH:MM AM/PM" pattern in the row
    m_time = re.search(r"\b(\d{1,2}):(\d{2})\s*(AM|PM)\b", raw, re.I)
    if not m_time:
        return None
    hr = int(m_time.group(1))
    mn = int(m_time.group(2))
    ampm = m_time.group(3).upper()
    if ampm == "PM" and hr != 12:
        hr += 12
    if ampm == "AM" and hr == 12:
        hr = 0
    if hr < start_h or hr >= end_h:
        return None
    time_str = f"{hr:02d}:{mn:02d}"

    # Price — look for $NN.NN or $NN pattern
    m_price = re.search(r"\$\s?(\d+(?:\.\d{2})?)", raw)
    price = f"${float(m_price.group(1)):.0f}" if m_price else "—"

    # Spots — look for "N Available" or "Spots: N"
    m_spots = re.search(r"(\d+)\s*(?:available|spots?|left|open)", raw, re.I)
    spots = m_spots.group(1) if m_spots else "?"

    return {
        "time": time_str,
        "course": course["name"],
        "holes": course.get("holes", 18),
        "price": price,
        "available_spots": spots,
        "source": "WebTrac",
        "booking_url": booking_url,
    }


# ---------------------------------------------------------------------------
# Club Caddie via navigation (Spring Lake)
# ---------------------------------------------------------------------------

def search_clubcaddie_nav(
    course: dict, date_str: str, start_h: int, end_h: int, players: int
) -> list[dict]:
    """
    Navigate from the course's own tee-times page, click their booking link,
    and intercept the Club Caddie SPA's tee time API response.
    Falls back to a link entry if the navigation doesn't yield a usable response.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        return [_error_entry(course["name"], "Club Caddie",
                             "Playwright not installed. Run: pip3 install playwright && playwright install chromium")]

    patterns = [p.lower() for p in course.get("intercept_patterns", [])]
    captured: list[dict] = []

    def on_response(response):
        if not any(p in response.url.lower() for p in patterns):
            return
        ct = response.headers.get("content-type", "")
        if "json" not in ct:
            return
        try:
            data = response.json()
            if data:
                captured.append({"url": response.url, "data": data})
        except Exception:
            pass

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=BROWSER_HEADERS["User-Agent"],
                viewport={"width": 1280, "height": 900},
            )
            page = ctx.new_page()
            page.on("response", on_response)

            page.goto(course["url"], timeout=30000, wait_until="networkidle")
            # Click any anchor whose text suggests booking
            book_btn = page.locator(
                "a:has-text('Book'), a:has-text('Reserve'), a:has-text('Tee Time'), a[href*=teetime]"
            ).first
            try:
                with page.expect_navigation(timeout=20000, wait_until="networkidle"):
                    book_btn.click(timeout=5000)
            except (PWTimeout, Exception):
                # Maybe the link opens in a new tab — try alternative
                pass

            page.wait_for_timeout(4000)  # Give SPA time to fetch data
            browser.close()
    except Exception as e:
        return [_error_entry(course["name"], "Club Caddie", f"Headless error: {e}")]

    if not captured:
        return [{
            "time": "—", "course": course["name"], "holes": 18,
            "price": f"see {course.get('platform','site')}", "available_spots": "?",
            "source": course.get("platform", "Club Caddie"),
            "booking_url": course["url"],
            "note": course.get("note", "") + " · (navigation didn't surface a tee time API call)",
        }]

    # Try to parse — Club Caddie response format unknown until first capture
    results = []
    for entry in captured:
        data = entry["data"]
        rows = (
            data.get("tee_times") or data.get("teeTimes") or data.get("times")
            or data.get("data") or (data if isinstance(data, list) else [])
        )
        if not isinstance(rows, list):
            continue
        for slot in rows:
            raw_time = slot.get("tee_time") or slot.get("teeTime") or slot.get("time") or ""
            try:
                if "T" in raw_time:
                    dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00")).astimezone(EDT)
                    time_str = dt.strftime("%H:%M")
                    h = dt.hour
                else:
                    time_str = raw_time[:5]
                    h = int(time_str.split(":")[0])
                if h < start_h or h >= end_h:
                    continue
            except (ValueError, AttributeError, IndexError):
                time_str = raw_time[:5] if raw_time else "?"

            fee = slot.get("green_fee") or slot.get("greenFee") or slot.get("price") or 0
            try:
                price = f"${float(fee):.0f}" if float(fee) > 0 else "—"
            except (ValueError, TypeError):
                price = "?"

            results.append({
                "time": time_str, "course": course["name"],
                "holes": slot.get("holes", 18), "price": price,
                "available_spots": slot.get("available_spots", "?"),
                "source": "Club Caddie", "booking_url": course["url"],
            })

    if not results:
        return [_no_availability_entry(course["name"], "Club Caddie", course["url"],
                                       f"Captured {len(captured)} responses but no parseable tee times")]
    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error_entry(course_name: str, source: str, err: str) -> dict:
    return {
        "time": "—",
        "course": course_name,
        "holes": "?",
        "price": "?",
        "available_spots": "?",
        "source": source,
        "booking_url": "",
        "error": err,
    }


def _no_availability_entry(course_name: str, source: str, booking_url: str, detail: str = "") -> dict:
    return {
        "time": "—",
        "course": course_name,
        "holes": 18,
        "price": "—",
        "available_spots": 0,
        "source": source,
        "booking_url": booking_url,
        "no_availability": True,
        "detail": detail,
    }


def _parse_time_24h(t: str) -> int:
    """Return hour as int from HH:MM string."""
    return int(t.split(":")[0])


def _sort_key(entry: dict) -> tuple:
    t = entry.get("time", "—")
    if t == "—":
        return (25, entry.get("course", ""))
    try:
        return (int(t.split(":")[0]) * 60 + int(t.split(":")[1]), entry.get("course", ""))
    except (ValueError, IndexError):
        return (24 * 60, entry.get("course", ""))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Search tee times near Smithtown, NY")
    parser.add_argument("--date", required=True, help="Date in YYYY-MM-DD format")
    parser.add_argument("--start", required=True, help="Start time HH:MM (24h)")
    parser.add_argument("--end", required=True, help="End time HH:MM (24h)")
    parser.add_argument("--players", required=True, type=int, help="Number of players")
    parser.add_argument(
        "--course",
        default=None,
        help="Filter to a specific course name (partial match, case-insensitive)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Deprecated no-op; auto-headless is now built into per-course strategies.",
    )
    args = parser.parse_args()

    start_h = _parse_time_24h(args.start)
    end_h = _parse_time_24h(args.end)

    course_filter = args.course.lower() if args.course else None

    def matches(name: str) -> bool:
        return course_filter is None or course_filter in name.lower()

    # Dispatch each matching course to its strategy's search function.
    # WebTrac courses share one login session — handled separately as a batch.
    STRATEGY_DISPATCH = {
        "foreup":         search_foreup,
        "teeitup":        search_teeitup,
        "chronogolf":     search_chronogolf,
        "clubcaddie":     search_playwright,
        "clubcaddie_nav": search_clubcaddie_nav,
        "link_only":      search_link_only,
    }

    pending = [c for c in COURSES if matches(c["name"])]
    webtrac_courses = [c for c in pending if c["strategy"] == "webtrac"]
    other_courses   = [c for c in pending if c["strategy"] != "webtrac"]
    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {}

        # WebTrac batch — one task running all matching WebTrac courses in shared session
        if webtrac_courses:
            f = pool.submit(search_webtrac_batch, webtrac_courses,
                            args.date, start_h, end_h, args.players)
            futures[f] = "WebTrac batch"

        # Per-course tasks for everything else
        for course in other_courses:
            fn = STRATEGY_DISPATCH.get(course["strategy"])
            if not fn:
                results.append(_error_entry(course["name"], course["strategy"],
                                            f"unknown strategy '{course['strategy']}'"))
                continue
            f = pool.submit(fn, course, args.date, start_h, end_h, args.players)
            futures[f] = course["name"]

        for future in as_completed(futures):
            try:
                results.extend(future.result())
            except Exception as e:
                results.append(_error_entry(futures[future], "unknown", str(e)))

    results.sort(key=_sort_key)

    # Also surface the GolfNow area search URL as a convenience
    if not course_filter:
        golfnow_area_url = _golfnow_search_url(args.date, start_h, end_h, args.players)
        results.append({
            "time": "—",
            "course": "All courses on GolfNow (area search)",
            "holes": "18",
            "price": "varies",
            "available_spots": "?",
            "source": "GolfNow",
            "booking_url": golfnow_area_url,
            "note": "Full GolfNow search for 11755 →",
        })

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
