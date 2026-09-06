#!/usr/bin/env python3
"""Poll search.py for a date/time window and push an ntfy alert on new slots.

Wraps scripts/search.py (no duplication of course logic) and diffs each run's
bookable results against a small JSON state file so only *new* slots trigger
a notification — re-running on a schedule won't re-spam the same tee time.

Usage:
    python3 scripts/monitor.py \
        --date 2026-09-08 --start 06:00 --end 09:00 --players 1 \
        --ntfy-topic li-teetimes-XXXXXXXX \
        --state /path/to/state.json

Exit code is always 0 on a normal run (including "0 in window" or every
source erroring) so it's safe to call from a scheduler; only argument errors
or an ntfy push failure raise non-zero.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SEARCH_PY = SCRIPT_DIR / "search.py"


def run_search(date: str, start: str, end: str, players: int, course: str | None) -> list[dict]:
    cmd = [
        sys.executable, str(SEARCH_PY),
        "--date", date, "--start", start, "--end", end,
        "--players", str(players),
    ]
    if course:
        cmd += ["--course", course]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"search.py exited {proc.returncode}: {proc.stderr}", file=sys.stderr)
        return []
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        print(f"could not parse search.py output: {e}\n{proc.stdout[:500]}", file=sys.stderr)
        return []


def bookable(entries: list[dict]) -> list[dict]:
    """Entries with a real time, no error, and not a no-availability placeholder."""
    return [
        e for e in entries
        if e.get("time") and e["time"] != "—"
        and not e.get("error")
        and not e.get("no_availability")
    ]


def slot_key(e: dict) -> str:
    return f"{e.get('course')}|{e.get('time')}|{e.get('price')}"


def load_state(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text()))
    except (json.JSONDecodeError, OSError):
        return set()


def save_state(path: Path, keys: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(keys)))


def send_ntfy(topic: str, title: str, body: str, click_url: str = "") -> None:
    url = f"https://ntfy.sh/{topic}"
    headers = {
        "Title": title.encode("utf-8"),
        "Priority": "high",
        "Tags": "golf",
    }
    if click_url:
        headers["Click"] = click_url.encode("utf-8")
    req = urllib.request.Request(url, data=body.encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()


def format_slot(e: dict) -> str:
    return f"{e['time']} {e['course']} — {e.get('price', '?')} ({e.get('source', '?')})"


def main() -> None:
    parser = argparse.ArgumentParser(description="Poll tee times and push new slots via ntfy")
    parser.add_argument("--date", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--players", required=True, type=int)
    parser.add_argument("--course", default=None)
    parser.add_argument("--ntfy-topic", required=True)
    parser.add_argument("--state", required=True, help="Path to a JSON file tracking seen slots")
    parser.add_argument("--test-push", action="store_true",
                         help="Send a one-off confirmation push and exit, skipping the search")
    args = parser.parse_args()

    if args.test_push:
        send_ntfy(
            args.ntfy_topic,
            "⛳ Tee-time watcher connected",
            f"You'll get alerts here for new {args.date} {args.start}-{args.end} "
            f"tee times ({args.players} player).",
        )
        print("Test push sent.")
        return

    state_path = Path(args.state)
    entries = run_search(args.date, args.start, args.end, args.players, args.course)
    current = bookable(entries)
    current_keys = {slot_key(e): e for e in current}

    seen = load_state(state_path)
    new_keys = [k for k in current_keys if k not in seen]

    if not new_keys:
        print(f"No new slots ({len(current)} bookable, {len(seen)} previously seen).")
        return

    new_entries = [current_keys[k] for k in new_keys]
    new_entries.sort(key=lambda e: e.get("time", ""))

    lines = [format_slot(e) for e in new_entries[:6]]
    if len(new_entries) > 6:
        lines.append(f"...and {len(new_entries) - 6} more")
    body = "\n".join(lines)
    click_url = new_entries[0].get("booking_url") or ""

    title = f"⛳ {len(new_entries)} new tee time{'s' if len(new_entries) != 1 else ''} — {args.date}"
    try:
        send_ntfy(args.ntfy_topic, title, body, click_url)
    except (urllib.error.URLError, OSError) as e:
        print(f"ntfy push failed: {e}", file=sys.stderr)
        sys.exit(1)

    save_state(state_path, seen | current_keys.keys())
    print(f"Pushed {len(new_entries)} new slot(s):\n{body}")


if __name__ == "__main__":
    main()
