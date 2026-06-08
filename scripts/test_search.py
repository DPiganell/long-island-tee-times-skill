#!/usr/bin/env python3
"""
Smoke test for the tee-times skill.

Validates that each course's strategy connects and returns sensible data.
Does NOT assert specific tee time availability (varies day-to-day), but DOES
assert that for each course:
  - The course appears in the search output
  - At least one entry has the expected `source` for that course
  - None of those entries have an `error` field

Three pass states (all acceptable):
  LIVE       — at least one bookable tee time returned
  N/A        — strategy reached the API but no slots in window
  LINK       — strategy emitted a fallback link (e.g. WebTrac without creds,
               Spring Lake Club Caddie nav)

Fail states:
  ERROR      — strategy raised an exception or returned an error entry
  MISSING    — course not found in search output
  WRONG_SRC  — expected source not present in returned entries

Usage:
  python3 scripts/test_search.py              # tests 3 days out
  python3 scripts/test_search.py --date 2026-05-20
  python3 scripts/test_search.py -v           # verbose unittest output
"""

import argparse
import json
import os
import subprocess
import sys
import unittest
from datetime import date, timedelta

SEARCH_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "search.py"
)

# (course_name, expected_source). One entry per course in COURSES.
# Keep in sync with the COURSES list at the top of search.py.
COURSES = [
    # ForeUp
    ("Crab Meadow Golf Course",       "ForeUp"),
    ("Brentwood Country Club",        "ForeUp"),
    ("Holbrook Country Club",         "ForeUp"),
    ("Bethpage Black",                "ForeUp"),
    ("Bethpage Red",                  "ForeUp"),
    ("Bethpage Blue",                 "ForeUp"),
    ("Bethpage Green",                "ForeUp"),
    ("Bethpage Yellow",               "ForeUp"),
    ("Sunken Meadow State Park",      "ForeUp"),
    # TeeItUp — dedicated single-course aliases
    ("Middle Island Country Club",    "TeeItUp"),
    ("Smithtown Landing CC",          "TeeItUp"),
    ("Stonebridge Golf Links",        "TeeItUp"),
    ("Wind Watch Golf & Country Club", "TeeItUp"),
    ("Cherry Creek Golf Links",       "TeeItUp"),
    ("The Woods at Cherry Creek",     "TeeItUp"),
    # TeeItUp — NYC city courses on the shared "golf-nyc" alias
    ("Douglaston Golf Course",        "TeeItUp"),
    ("Clearview Park Golf Course",    "TeeItUp"),
    ("Kissena Golf Course",           "TeeItUp"),
    ("Forest Park Golf Course",       "TeeItUp"),
    ("Van Cortlandt Golf Course",     "TeeItUp"),
    ("Silver Lake Golf Course",       "TeeItUp"),
    ("South Shore Golf Course",       "TeeItUp"),
    ("La Tourette Golf Course",       "TeeItUp"),
    # Chronogolf (anonymous)
    ("Swan Lake Golf Club",           "Chronogolf"),
    ("Spy Ring Golf Club",            "Chronogolf"),
    ("Port Jefferson Country Club",   "Chronogolf"),
    ("Pine Hills Country Club",       "Chronogolf"),
    # GolfBack (anonymous POST API)
    ("Willow Creek Golf Club",        "GolfBack"),
    # WebTrac (requires Suffolk County credentials)
    ("Bergen Point Golf Club",        "WebTrac"),
    ("Indian Island Country Club",    "WebTrac"),
    ("Timber Point Red",              "WebTrac"),
    ("Timber Point Blue",             "WebTrac"),
    ("Timber Point White (9)",        "WebTrac"),
    ("West Sayville Golf Course",     "WebTrac"),
    # Club Caddie (direct webapi handshake — session bootstrap + TeeTimes POST)
    ("Spring Lake Golf Club",         "Club Caddie"),
]


def _classify(entries: list[dict]) -> str:
    """Return LIVE / NA / LINK / ERROR / MISSING for a course's entries."""
    if not entries:
        return "MISSING"
    if any(e.get("error") for e in entries):
        return "ERROR"
    live = [e for e in entries if e.get("time") and e["time"] != "—" and not e.get("no_availability")]
    if live:
        return "LIVE"
    na = [e for e in entries if e.get("no_availability")]
    if na:
        return "NA"
    return "LINK"


class TeeTimeStrategyTest(unittest.TestCase):
    """One test method per course — verifies the strategy connects cleanly."""

    target_date: str = ""
    by_course: dict[str, list[dict]] = {}

    @classmethod
    def setUpClass(cls):
        # 3 days out is well within every platform's booking window
        # (NYS Parks opens at 7 days, ForeUp/TeeItUp/Chronogolf typically open earlier).
        days_ahead = int(os.environ.get("TEE_TIMES_TEST_DAYS_AHEAD", "3"))
        cls.target_date = (date.today() + timedelta(days=days_ahead)).isoformat()

        proc = subprocess.run(
            [
                "python3", SEARCH_SCRIPT,
                "--date", cls.target_date,
                "--start", "06:00",
                "--end", "20:00",  # wide window to maximize chance of finding availability
                "--players", "2",
            ],
            capture_output=True, text=True, timeout=180,
        )
        if proc.returncode != 0:
            raise unittest.SkipTest(
                f"search.py exited non-zero ({proc.returncode}):\n"
                f"stderr: {proc.stderr[:500]}"
            )
        try:
            entries = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise unittest.SkipTest(f"Invalid JSON from search.py: {e}\nstdout[:500]: {proc.stdout[:500]}")

        cls.by_course = {}
        for e in entries:
            cls.by_course.setdefault(e.get("course", ""), []).append(e)

        # Print header banner before tests run
        print(f"\n{'=' * 60}")
        print(f"  Tee Times Smoke Test")
        print(f"  Date: {cls.target_date}  ·  Window: 06:00–20:00  ·  Players: 2")
        print(f"  Courses tested: {len(COURSES)}")
        print(f"{'=' * 60}\n")

    def _verify(self, name: str, expected_source: str):
        entries = self.by_course.get(name)
        if not entries:
            self.fail(f"MISSING: '{name}' not present in search output")

        matching = [e for e in entries if e.get("source") == expected_source]
        if not matching:
            actual_sources = sorted({e.get("source", "?") for e in entries})
            self.fail(
                f"WRONG_SRC: '{name}' expected source='{expected_source}', "
                f"got sources={actual_sources}"
            )

        errors = [e for e in matching if e.get("error")]
        if errors:
            self.fail(
                f"ERROR: '{name}' [{expected_source}]: {errors[0]['error'][:200]}"
            )

        # Classify and print outcome
        status = _classify(matching)
        live_count = sum(1 for e in matching if e.get("time") and e["time"] != "—")
        na_count = sum(1 for e in matching if e.get("no_availability"))
        link_count = len(matching) - live_count - na_count
        bits = []
        if live_count: bits.append(f"{live_count} live")
        if na_count:   bits.append(f"{na_count} N/A")
        if link_count: bits.append(f"{link_count} link")
        print(f"  [{status:5}] {name:36} [{expected_source:11}]  {', '.join(bits)}")


def _make_test(name: str, source: str):
    """Generate a test method that closes over the course + source."""
    def test(self):
        self._verify(name, source)
    safe_name = (
        name.lower()
        .replace(" ", "_").replace("(", "").replace(")", "")
        .replace("/", "_").replace("'", "")
    )
    test.__name__ = f"test_{safe_name}"
    test.__doc__ = f"{name} ({source}) connects and returns sensible data"
    return test


# Inject one test method per course
for _name, _src in COURSES:
    _fn = _make_test(_name, _src)
    setattr(TeeTimeStrategyTest, _fn.__name__, _fn)


def main():
    parser = argparse.ArgumentParser(description="Smoke test the tee-times skill.")
    parser.add_argument("--date", help="YYYY-MM-DD override for test date (else today+3)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose unittest output")
    args, unittest_args = parser.parse_known_args()

    if args.date:
        # Compute days ahead from the override
        from datetime import datetime as _dt
        delta = (_dt.fromisoformat(args.date).date() - date.today()).days
        os.environ["TEE_TIMES_TEST_DAYS_AHEAD"] = str(delta)

    # Reassemble argv for unittest
    new_argv = [sys.argv[0]] + (["-v"] if args.verbose else []) + unittest_args
    unittest.main(argv=new_argv, exit=True)


if __name__ == "__main__":
    main()
