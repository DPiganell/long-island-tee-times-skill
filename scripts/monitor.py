#!/usr/bin/env python3
"""
Tee time watcher: polls search.py for a date/time window and pushes an ntfy.sh
notification the moment a new bookable slot appears. Designed to be called
repeatedly (e.g. every 15 min via a scheduler) — it tracks previously-seen
slots in a state file so it only notifies once per new slot.

Usage:
  python3 monitor.py --date 2026-09-08 --start 06:00 --end 09:00 --players 1 \
      --ntfy-topic li-teetimes-abcd1234 --state /tmp/tee_state.json
"""

import argparse
import json
import os
import ssl
import subprocess
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

SEARCH_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "search.py")


def _resolve_ca_file():
    try:
        import certifi
        return certifi.where()
    except ImportError:
        return None


def _ssl_ctx() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=_resolve_ca_file())


def run_search(date: str, start: str, end: str, players: int) -> list[dict]:
    proc = subprocess.run(
        [sys.executable, SEARCH_PY, "--date", date, "--start", start,
         "--end", end, "--players", str(players)],
        capture_output=True, text=True, timeout=180,
    )
    if proc.returncode != 0:
        print(f"WARNING: search.py exited {proc.returncode}: {proc.stderr}", file=sys.stderr)
        return []
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        print(f"WARNING: could not parse search.py output: {e}", file=sys.stderr)
        return []


def bookable_slots(results: list[dict]) -> list[dict]:
    return [
        r for r in results
        if r.get("time") and r["time"] != "—" and "error" not in r and not r.get("no_availability")
    ]


def all_sources_errored(results: list[dict]) -> bool:
    course_results = [r for r in results if r.get("source") != "GolfNow"]
    if not course_results:
        return True
    return all("error" in r for r in course_results)


def slot_key(slot: dict) -> str:
    return f"{slot['course']}|{slot['time']}|{slot.get('price', '')}"


def load_state(path: str) -> set:
    if not os.path.exists(path):
        return set()
    try:
        with open(path) as f:
            return set(json.load(f))
    except (json.JSONDecodeError, OSError):
        return set()


def save_state(path: str, keys: set) -> None:
    with open(path, "w") as f:
        json.dump(sorted(keys), f, indent=2)


def send_ntfy(topic: str, new_slots: list[dict]) -> None:
    n = len(new_slots)
    title = f"⛳ {n} new Monday tee time{'s' if n != 1 else ''}"
    lines = []
    for s in new_slots[:6]:
        lines.append(f"{s['time']} {s['course']} {s.get('price', '?')} → {s.get('booking_url', '')}")
    body = "\n".join(lines)
    best_url = new_slots[0].get("booking_url", "") or "https://www.google.com"

    req = Request(
        f"https://ntfy.sh/{topic}",
        data=body.encode("utf-8"),
        method="POST",
        headers={
            "Title": title,
            "Priority": "high",
            "Click": best_url,
            "Content-Type": "text/plain; charset=utf-8",
        },
    )
    try:
        with urlopen(req, timeout=15, context=_ssl_ctx()) as resp:
            resp.read()
    except (HTTPError, URLError) as e:
        print(f"WARNING: failed to send ntfy notification: {e}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Poll for new tee times and push ntfy alerts")
    parser.add_argument("--date", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--players", required=True, type=int)
    parser.add_argument("--ntfy-topic", required=True)
    parser.add_argument("--state", required=True, help="Path to JSON state file")
    args = parser.parse_args()

    results = run_search(args.date, args.start, args.end, args.players)

    if results and all_sources_errored(results):
        print("WARNING: every source errored this run — skipping notification, not updating state.")
        sys.exit(0)

    bookable = bookable_slots(results)
    seen = load_state(args.state)
    current_keys = {slot_key(s) for s in bookable}
    new_keys = current_keys - seen
    new_slots = [s for s in bookable if slot_key(s) in new_keys]

    if new_slots:
        print(f"Found {len(new_slots)} new slot(s):")
        for s in new_slots:
            print(f"  {s['time']} {s['course']} {s.get('price', '?')} -> {s.get('booking_url', '')}")
        send_ntfy(args.ntfy_topic, new_slots)
    else:
        print(f"No new slots ({len(bookable)} bookable slot(s) currently known, all previously seen).")

    save_state(args.state, current_keys)
    sys.exit(0)


if __name__ == "__main__":
    main()
