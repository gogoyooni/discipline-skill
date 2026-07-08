#!/usr/bin/env python3
"""check_events.py — report verification events that have come due.

Because there is no server and no push notification, "the conversation itself is
the trigger." At the start of a session, the skill runs this to surface any
verification event that is due today or overdue and still has no recorded
result — so the user is prompted to record a verdict at exactly the moment a
thesis was supposed to be tested.

Standard library only. Reads the ledger produced by ledger.py; never writes.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# Force UTF-8 output so non-ASCII event titles render cleanly on Windows too.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def resolve_dir(arg_dir):
    return Path(arg_dir) if arg_dir else Path.cwd() / "discipline"


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="check_events.py",
        description="List verification events due today or overdue (unresolved).",
    )
    parser.add_argument("--dir", help="path to discipline/ (default ./discipline)")
    args = parser.parse_args(argv)

    base = resolve_dir(args.dir)
    lp = base / "ledger.json"
    if not lp.exists():
        print(json.dumps({"ok": False, "error": "no ledger", "code": "NO_LEDGER"},
                         ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

    data = json.loads(lp.read_text(encoding="utf-8"))
    today = date.today().isoformat()
    scenarios = {s["id"]: s for s in data.get("scenarios", [])}

    due_today, overdue = [], []
    for e in data.get("events", []):
        if e.get("result") is not None:
            continue  # already judged
        ev = {
            "id": e["id"],
            "date": e["date"],
            "title": e["title"],
            "check_items": e.get("check_items", []),
            "scenario_id": e.get("scenario_id"),
            "scenario_title": scenarios.get(e.get("scenario_id"), {}).get("title"),
        }
        if e["date"] == today:
            due_today.append(ev)
        elif e["date"] < today:
            overdue.append(ev)

    due_today.sort(key=lambda x: x["date"])
    overdue.sort(key=lambda x: x["date"])

    print(json.dumps(
        {
            "ok": True,
            "today": today,
            "due_today": due_today,
            "overdue": overdue,
            "has_action": bool(due_today or overdue),
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
