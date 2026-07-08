#!/usr/bin/env python3
"""ledger.py — the single enforced read/write path for the discipline ledger.

Design principle (from docs/design.md):
    "쓰지 않은 규칙은 규칙이 아니다" — a rule that was not written is not a rule.

Claude must never reconstruct rules from memory. Every read and every mutation
goes through this script so that structural invariants are enforced by CODE,
not by prose instructions that a model can rationalize its way around.

Hard invariants enforced here (not just advised in SKILL.md):
  1. A scenario can never jump WAITING -> ENTERING. `advance` moves one step at a
     time, so "entering without verifying" is structurally impossible.
  2. A scenario cannot enter ENTERING while any `blanks` value is still null.
  3. State only changes through explicit commands (advance / verdict / close).
     There is no command that sets an arbitrary state.

Standard library only (Python 3.8+). No third-party dependencies, on purpose:
this file is distributed inside a plugin and must run the instant it is
installed, on any machine, with no `pip install` step. Validation is done by
hand rather than pydantic for exactly that reason. See docs/design.md note.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import date, datetime
from pathlib import Path

# Force UTF-8 on stdout/stderr so non-ASCII ledger content (e.g. Korean rules)
# is emitted cleanly on every platform. Windows defaults a piped stdout to the
# locale code page (e.g. cp949), which would garble the JSON the skill reads.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):  # older Python or non-reconfigurable stream
        pass

SCHEMA_VERSION = 1

# Canonical forward path through the discipline state machine.
# See references/state-machine.md for the full transition contract.
STATES = ["WAITING", "VERIFYING", "ENTERING", "HOLDING", "REVIEW"]
RULE_KINDS = ["NO_ACTION", "ENTRY_COND", "EXIT_COND", "SIZING", "META"]
TRADE_SIDES = ["BUY", "SELL"]
VERDICT_RESULTS = ["PASS", "PARTIAL", "FAIL"]


# --------------------------------------------------------------------------- #
# Output helpers — everything Claude consumes is JSON on stdout.
# --------------------------------------------------------------------------- #
def emit(obj: dict) -> None:
    """Print a JSON result to stdout so the calling agent can parse it."""
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def die(msg: str, **extra) -> "NoReturn":  # type: ignore[valid-type]
    payload = {"ok": False, "error": msg}
    payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
    sys.exit(1)


# --------------------------------------------------------------------------- #
# Paths & persistence
# --------------------------------------------------------------------------- #
def resolve_dir(arg_dir: str | None) -> Path:
    return Path(arg_dir) if arg_dir else Path.cwd() / "discipline"


def ledger_path(base: Path) -> Path:
    return base / "ledger.json"


def load(base: Path) -> dict:
    lp = ledger_path(base)
    if not lp.exists():
        die(
            f"discipline ledger not found at {lp}. Run `ledger.py init` first.",
            code="NO_LEDGER",
        )
    try:
        data = json.loads(lp.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - corruption guard
        die(f"ledger.json is not valid JSON: {exc}", code="CORRUPT")
    if data.get("schema_version") != SCHEMA_VERSION:
        die(
            f"ledger schema_version {data.get('schema_version')} is not supported "
            f"(this ledger.py speaks v{SCHEMA_VERSION}).",
            code="SCHEMA_MISMATCH",
        )
    for key in ("scenarios", "rules", "trades", "events"):
        data.setdefault(key, [])
    return data


def save(base: Path, data: dict) -> None:
    lp = ledger_path(base)
    lp.parent.mkdir(parents=True, exist_ok=True)
    # Write atomically so a crash mid-write can never truncate the ledger.
    tmp = lp.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(lp)


# --------------------------------------------------------------------------- #
# Small utilities
# --------------------------------------------------------------------------- #
def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_id() -> str:
    return str(uuid.uuid4())


def parse_date(s: str) -> str:
    """Accept YYYY-MM-DD, MM/DD, or MMDD. Return an ISO date string (YYYY-MM-DD).

    MM/DD and MMDD infer the current year — convenient for near-term events like
    "7/29" without forcing the user to type a year.
    """
    s = s.strip()
    try:
        return datetime.strptime(s, "%Y-%m-%d").date().isoformat()
    except ValueError:
        pass
    today = date.today()
    if "/" in s:
        parts = s.split("/")
        if len(parts) == 2:
            m, d = int(parts[0]), int(parts[1])
            return date(today.year, m, d).isoformat()
    if s.isdigit() and len(s) == 4:
        return date(today.year, int(s[:2]), int(s[2:])).isoformat()
    die(f"could not parse date '{s}' (use YYYY-MM-DD, MM/DD, or MMDD).", code="BAD_DATE")


def find_scenario(data: dict, scenario_id: str) -> dict:
    """Match a scenario by full id OR unambiguous id prefix (UUIDs are long)."""
    matches = [s for s in data["scenarios"] if s["id"] == scenario_id]
    if not matches:
        matches = [s for s in data["scenarios"] if s["id"].startswith(scenario_id)]
    if not matches:
        die(f"no scenario matches id '{scenario_id}'.", code="NO_SCENARIO")
    if len(matches) > 1:
        die(
            f"scenario id prefix '{scenario_id}' is ambiguous.",
            code="AMBIGUOUS",
            candidates=[s["id"] for s in matches],
        )
    return matches[0]


def find_rule(data: dict, rule_id: str) -> dict:
    matches = [r for r in data["rules"] if r["id"] == rule_id]
    if not matches:
        matches = [r for r in data["rules"] if r["id"].startswith(rule_id)]
    if not matches:
        die(f"no rule matches id '{rule_id}'.", code="NO_RULE")
    if len(matches) > 1:
        die(
            f"rule id prefix '{rule_id}' is ambiguous.",
            code="AMBIGUOUS",
            candidates=[r["id"] for r in matches],
        )
    return matches[0]


def unfilled_blanks(scenario: dict) -> list[str]:
    """Names of scenario blanks still holding null — the plan is incomplete."""
    return [k for k, v in scenario.get("blanks", {}).items() if v in (None, "")]


def latest_verdict(scenario: dict, data: dict) -> str | None:
    """Most recent recorded verdict result for this scenario's events, or None."""
    results = [
        e["result"]
        for e in data["events"]
        if e.get("scenario_id") == scenario["id"] and e.get("result")
    ]
    return results[-1] if results else None


def active_rules(data: dict, scenario_id: str | None = None) -> list[dict]:
    today = date.today().isoformat()
    out = []
    for r in data["rules"]:
        until = r.get("active_until")
        if until and until < today:
            continue  # expired
        if scenario_id and r.get("scenario_id") not in (None, scenario_id):
            continue
        out.append(r)
    return out


# --------------------------------------------------------------------------- #
# The transition guard — the philosophical core of the tool.
#
# This single function decides what "advancing" a scenario is allowed to do.
# It is deliberately small and readable because it encodes the whole point of
# the product: you may not skip verification, and you may not enter a position
# with an unfinished plan.
# --------------------------------------------------------------------------- #
def next_state(scenario: dict, data: dict) -> str:
    """Return the state `scenario` is allowed to advance to, or die() with why.

    Legal forward moves and their guards:
        WAITING   -> VERIFYING   (always allowed — you can always start verifying)
        VERIFYING -> ENTERING    ONLY IF a verdict exists and is PASS/PARTIAL
                                  AND every blank is filled.
        VERIFYING -> REVIEW       if the latest verdict is FAIL (thesis falsified:
                                  you review the *decision*, you do not buy).
        ENTERING  -> HOLDING     (position established)
        HOLDING   -> REVIEW      (thesis closed / exit)
        REVIEW    -> (nothing)   use `close` to finish.
    """
    s = scenario["state"]
    if s == "WAITING":
        return "VERIFYING"
    if s == "VERIFYING":
        verdict = latest_verdict(scenario, data)
        if verdict is None:
            die(
                "cannot advance a VERIFYING scenario before a verdict is recorded. "
                "Run `ledger.py verdict --scenario <id> --result PASS|PARTIAL|FAIL`.",
                code="NO_VERDICT",
            )
        if verdict == "FAIL":
            # Thesis was falsified. The disciplined move is to review the
            # decision, NOT to enter the position anyway.
            return "REVIEW"
        blanks = unfilled_blanks(scenario)
        if blanks:
            die(
                "cannot enter a position with an unfinished plan. "
                "Fill these blanks first with `ledger.py blank set`.",
                code="UNFILLED_BLANKS",
                blanks=blanks,
            )
        return "ENTERING"
    if s == "ENTERING":
        return "HOLDING"
    if s == "HOLDING":
        return "REVIEW"
    if s == "REVIEW":
        die("scenario is in REVIEW. Finish it with `ledger.py close`.", code="AT_REVIEW")
    die(f"unknown state '{s}'.", code="BAD_STATE")


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
def cmd_init(args) -> None:
    base = resolve_dir(args.dir)
    lp = ledger_path(base)
    if lp.exists():
        die(f"a ledger already exists at {lp}; refusing to overwrite.", code="EXISTS")
    (base / "reviews").mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": SCHEMA_VERSION,
        "scenarios": [],
        "rules": [],
        "trades": [],
        "events": [],
    }
    save(base, data)
    emit({"ok": True, "created": str(lp), "reviews_dir": str(base / "reviews")})


def cmd_scenario_new(args) -> None:
    base = resolve_dir(args.dir)
    data = load(base)
    scenario = {
        "id": new_id(),
        "title": args.title,
        "state": "WAITING",
        "thesis": args.thesis,
        "falsification": args.falsify,
        "verdict_criteria": args.verdict or None,
        # Default plan blanks. Users can add/rename their own via `blank set`.
        "blanks": {"target_weight": None, "stop_loss": None, "entry_signal": None},
        "created_at": now_iso(),
        "closed_at": None,
    }
    data["scenarios"].append(scenario)
    save(base, data)
    emit({"ok": True, "created": scenario})


def cmd_rule_add(args) -> None:
    base = resolve_dir(args.dir)
    data = load(base)
    if args.kind not in RULE_KINDS:
        die(f"--kind must be one of {RULE_KINDS}.", code="BAD_KIND")
    scenario_id = None
    if args.scenario:
        scenario_id = find_scenario(data, args.scenario)["id"]
    rule = {
        "id": new_id(),
        "text": args.text,
        "kind": args.kind,
        "active_from": now_iso(),
        "active_until": parse_date(args.until) if args.until else None,
        "scenario_id": scenario_id,
        "violation_count": 0,
    }
    data["rules"].append(rule)
    save(base, data)
    emit({"ok": True, "created": rule})


def cmd_trade_add(args) -> None:
    base = resolve_dir(args.dir)
    data = load(base)
    if args.side.upper() not in TRADE_SIDES:
        die(f"--side must be one of {TRADE_SIDES}.", code="BAD_SIDE")
    scenario_id = None
    if args.scenario:
        scenario_id = find_scenario(data, args.scenario)["id"]
    trade = {
        "id": new_id(),
        "ts": now_iso(),
        "ticker": args.ticker,
        "side": args.side.upper(),
        "qty": args.qty,
        "price": args.price,
        "scenario_id": scenario_id,
        "note": args.note,
    }
    data["trades"].append(trade)
    save(base, data)
    emit({"ok": True, "created": trade})


def cmd_blank_set(args) -> None:
    base = resolve_dir(args.dir)
    data = load(base)
    scenario = find_scenario(data, args.scenario)
    scenario.setdefault("blanks", {})[args.key] = args.value
    save(base, data)
    emit(
        {
            "ok": True,
            "scenario_id": scenario["id"],
            "blanks": scenario["blanks"],
            "remaining": unfilled_blanks(scenario),
        }
    )


def cmd_event_add(args) -> None:
    base = resolve_dir(args.dir)
    data = load(base)
    scenario_id = None
    if args.scenario:
        scenario_id = find_scenario(data, args.scenario)["id"]
    check_items = [c.strip() for c in args.check.split(",") if c.strip()] if args.check else []
    event = {
        "id": new_id(),
        "date": parse_date(args.date),
        "title": args.title,
        "check_items": check_items,
        "scenario_id": scenario_id,
        "result": None,
        "result_note": None,
    }
    data["events"].append(event)
    save(base, data)
    emit({"ok": True, "created": event})


def cmd_verdict(args) -> None:
    base = resolve_dir(args.dir)
    data = load(base)
    scenario = find_scenario(data, args.scenario)
    if scenario["state"] != "VERIFYING":
        die(
            f"verdict is only allowed while a scenario is VERIFYING "
            f"(this one is {scenario['state']}).",
            code="NOT_VERIFYING",
        )
    if args.result not in VERDICT_RESULTS:
        die(f"--result must be one of {VERDICT_RESULTS}.", code="BAD_RESULT")
    # Attach the verdict to the most recent unresolved event for this scenario,
    # otherwise record it on the scenario alone.
    target = None
    for e in data["events"]:
        if e.get("scenario_id") == scenario["id"] and e.get("result") is None:
            target = e
    if target is not None:
        target["result"] = args.result
        target["result_note"] = args.note
    scenario["verification_result"] = args.result
    scenario["verification_note"] = args.note
    save(base, data)
    emit(
        {
            "ok": True,
            "scenario_id": scenario["id"],
            "result": args.result,
            "event": target["id"] if target else None,
            "hint": "run `ledger.py advance --scenario <id>` to move to the next state.",
        }
    )


def cmd_advance(args) -> None:
    base = resolve_dir(args.dir)
    data = load(base)
    scenario = find_scenario(data, args.scenario)
    target = next_state(scenario, data)  # dies with a reason if the move is illegal
    prev = scenario["state"]
    scenario["state"] = target
    save(base, data)
    emit(
        {
            "ok": True,
            "scenario_id": scenario["id"],
            "from": prev,
            "to": target,
        }
    )


def cmd_violation_bump(args) -> None:
    base = resolve_dir(args.dir)
    data = load(base)
    rule = find_rule(data, args.rule)
    rule["violation_count"] = rule.get("violation_count", 0) + 1
    save(base, data)
    emit(
        {
            "ok": True,
            "rule_id": rule["id"],
            "text": rule["text"],
            "violation_count": rule["violation_count"],
        }
    )


def cmd_state(args) -> None:
    base = resolve_dir(args.dir)
    data = load(base)
    today = date.today().isoformat()
    open_scenarios = [s for s in data["scenarios"] if not s.get("closed_at")]
    view = []
    for s in open_scenarios:
        future_events = sorted(
            [
                e
                for e in data["events"]
                if e.get("scenario_id") == s["id"] and e.get("result") is None
            ],
            key=lambda e: e["date"],
        )
        view.append(
            {
                "id": s["id"],
                "title": s["title"],
                "state": s["state"],
                "thesis": s.get("thesis"),
                "falsification": s.get("falsification"),
                "active_rules": [
                    {"id": r["id"], "kind": r["kind"], "text": r["text"],
                     "active_until": r.get("active_until"),
                     "violation_count": r.get("violation_count", 0)}
                    for r in active_rules(data, s["id"])
                ],
                "unfilled_blanks": unfilled_blanks(s),
                "next_event": future_events[0] if future_events else None,
            }
        )
    emit(
        {
            "ok": True,
            "today": today,
            "schema_version": data["schema_version"],
            "global_rules": [
                {"id": r["id"], "kind": r["kind"], "text": r["text"],
                 "active_until": r.get("active_until"),
                 "violation_count": r.get("violation_count", 0)}
                for r in active_rules(data)
                if r.get("scenario_id") is None
            ],
            "scenarios": view,
        }
    )


def cmd_close(args) -> None:
    base = resolve_dir(args.dir)
    data = load(base)
    scenario = find_scenario(data, args.scenario)
    if scenario["state"] != "REVIEW":
        die(
            f"a scenario is only closed from REVIEW (this one is {scenario['state']}). "
            f"Advance it to REVIEW first.",
            code="NOT_AT_REVIEW",
        )
    scenario["closed_at"] = now_iso()
    review_file = _write_review(base, data, scenario)
    save(base, data)
    emit({"ok": True, "scenario_id": scenario["id"], "review": str(review_file)})


def _write_review(base: Path, data: dict, scenario: dict) -> Path:
    """Emit a retrospective markdown file when a scenario is closed."""
    reviews = base / "reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    safe_title = "".join(c if c.isalnum() or c in "-_ " else "_" for c in scenario["title"]).strip()
    fname = f"{date.today().isoformat()}-{safe_title or scenario['id'][:8]}.md"
    path = reviews / fname

    trades = [t for t in data["trades"] if t.get("scenario_id") == scenario["id"]]
    rules = [r for r in data["rules"] if r.get("scenario_id") == scenario["id"]]
    events = [e for e in data["events"] if e.get("scenario_id") == scenario["id"]]
    total_violations = sum(r.get("violation_count", 0) for r in rules)

    lines = [
        f"# Review: {scenario['title']}",
        "",
        f"- Closed: {date.today().isoformat()}",
        f"- Closed from state: REVIEW",
        f"- Thesis: {scenario.get('thesis') or '—'}",
        f"- Falsification condition: {scenario.get('falsification') or '—'}",
        f"- Verification result: {scenario.get('verification_result') or '—'}",
        f"- Total rule-violation attempts: {total_violations}",
        "",
        "## Rules",
    ]
    lines += [f"- [{r['kind']}] {r['text']} ({r.get('violation_count', 0)} violation attempts)" for r in rules] or ["- (none)"]
    lines += ["", "## Verification events"]
    lines += [
        f"- {e['date']} {e['title']} -> {e.get('result') or 'unjudged'}"
        f"{' — ' + e['result_note'] if e.get('result_note') else ''}"
        for e in events
    ] or ["- (none)"]
    lines += ["", "## Trades"]
    lines += [
        f"- {t['ts'][:10]} {t['side']} {t['ticker']} {t['qty']} @ {t['price']}"
        f"{' — ' + t['note'] if t.get('note') else ''}"
        for t in trades
    ] or ["- (none)"]
    lines += [
        "",
        "## Retrospective, Annie Duke style (judge the DECISION, not the outcome)",
        "",
        "- Given only what you knew at the time, was this a good decision? (Separate it from the result.)",
        "- If there were violation attempts, what was the trigger? (A daily candle? News? Boredom?)",
        "- Is there a rule to add or fix for the next cycle?",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Argument parser
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ledger.py",
        description="Enforced read/write path for the investment-discipline ledger.",
    )
    p.add_argument("--dir", help="path to the discipline/ directory (default ./discipline)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", help="initialize discipline/ in the current directory")
    sp.set_defaults(func=cmd_init)

    # scenario new
    sc = sub.add_parser("scenario", help="scenario operations")
    scsub = sc.add_subparsers(dest="sub", required=True)
    scn = scsub.add_parser("new", help="create a new scenario (starts in WAITING)")
    scn.add_argument("--title", required=True)
    scn.add_argument("--thesis", required=True)
    scn.add_argument("--falsify", required=True, help="the falsification condition")
    scn.add_argument("--verdict", help="verdict criteria (pass/partial/fail definition)")
    scn.set_defaults(func=cmd_scenario_new)

    # rule add
    rl = sub.add_parser("rule", help="rule operations")
    rlsub = rl.add_subparsers(dest="sub", required=True)
    rla = rlsub.add_parser("add", help="add a rule")
    rla.add_argument("--kind", required=True, choices=RULE_KINDS)
    rla.add_argument("--text", required=True)
    rla.add_argument("--until", help="active_until date (YYYY-MM-DD, MM/DD, or MMDD)")
    rla.add_argument("--scenario", help="scenario id to bind this rule to")
    rla.set_defaults(func=cmd_rule_add)

    # trade add
    tr = sub.add_parser("trade", help="trade operations")
    trsub = tr.add_subparsers(dest="sub", required=True)
    tra = trsub.add_parser("add", help="record an executed trade")
    tra.add_argument("--side", required=True)
    tra.add_argument("--ticker", required=True)
    tra.add_argument("--qty", required=True, type=float)
    tra.add_argument("--price", required=True, type=float)
    tra.add_argument("--note")
    tra.add_argument("--scenario")
    tra.set_defaults(func=cmd_trade_add)

    # blank set
    bl = sub.add_parser("blank", help="scenario blank operations")
    blsub = bl.add_subparsers(dest="sub", required=True)
    bls = blsub.add_parser("set", help="fill in a scenario blank")
    bls.add_argument("--scenario", required=True)
    bls.add_argument("--key", required=True)
    bls.add_argument("--value", required=True)
    bls.set_defaults(func=cmd_blank_set)

    # event add
    ev = sub.add_parser("event", help="verification event operations")
    evsub = ev.add_subparsers(dest="sub", required=True)
    eva = evsub.add_parser("add", help="add a verification event")
    eva.add_argument("--date", required=True, help="YYYY-MM-DD, MM/DD, or MMDD")
    eva.add_argument("--title", required=True)
    eva.add_argument("--check", help="comma-separated check items")
    eva.add_argument("--scenario")
    eva.set_defaults(func=cmd_event_add)

    # verdict
    vd = sub.add_parser("verdict", help="record a verification verdict (VERIFYING only)")
    vd.add_argument("--scenario", required=True)
    vd.add_argument("--result", required=True, choices=VERDICT_RESULTS)
    vd.add_argument("--note")
    vd.set_defaults(func=cmd_verdict)

    # advance
    ad = sub.add_parser("advance", help="advance a scenario one step (guards enforced)")
    ad.add_argument("--scenario", required=True)
    ad.set_defaults(func=cmd_advance)

    # violation bump
    vi = sub.add_parser("violation", help="violation operations")
    visub = vi.add_subparsers(dest="sub", required=True)
    vib = visub.add_parser("bump", help="increment a rule's violation counter")
    vib.add_argument("--rule", required=True)
    vib.set_defaults(func=cmd_violation_bump)

    # state
    st = sub.add_parser("state", help="print current state as JSON")
    st.set_defaults(func=cmd_state)

    # close
    cl = sub.add_parser("close", help="close a scenario (REVIEW only) + write a review")
    cl.add_argument("--scenario", required=True)
    cl.set_defaults(func=cmd_close)

    return p


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
