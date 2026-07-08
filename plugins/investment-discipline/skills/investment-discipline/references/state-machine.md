# State machine & command reference

A scenario moves through five states. Transitions happen **only** through
explicit `ledger.py` commands, and the script — not this document, and not the
model — enforces every guard. If a command is rejected, relay the reason; never
edit the ledger by hand to force a state.

## States

```
WAITING ──► VERIFYING ──► ENTERING ──► HOLDING ──► REVIEW ──► (closed)
                │
                └──► REVIEW        (when the latest verdict is FAIL)
```

| State | Meaning |
|---|---|
| WAITING | Thesis exists; no verification done yet. Patience phase. |
| VERIFYING | A verification event is in progress or awaiting a verdict. |
| ENTERING | Thesis verified (PASS/PARTIAL) and the plan is complete; establishing a position. |
| HOLDING | Position established; holding against the thesis. |
| REVIEW | Thesis closed (or falsified); retrospective phase. |

## Transition guards (enforced in `ledger.py`)

- **`advance` moves exactly one step.** There is no command that sets an
  arbitrary state, so `WAITING → ENTERING` cannot happen. Verification is
  structurally unavoidable.
- **`VERIFYING → ENTERING` requires:** (1) a recorded verdict of `PASS` or
  `PARTIAL`, and (2) **every** blank filled. A missing verdict → `NO_VERDICT`;
  an unfilled blank → `UNFILLED_BLANKS` with the list.
- **`VERIFYING → REVIEW`** happens when the latest verdict is `FAIL`: a falsified
  thesis is reviewed, not bought.
- **`verdict` is only valid while `VERIFYING`** (`NOT_VERIFYING` otherwise).
- **`close` is only valid from `REVIEW`** (`NOT_AT_REVIEW` otherwise) and writes
  a retrospective markdown file under `discipline/reviews/`.

## Command reference

```bash
# Setup
ledger.py init
    # create ./discipline/ (ledger.json + reviews/). Refuses to overwrite.

# Scenario
ledger.py scenario new --title "..." --thesis "..." --falsify "..." [--verdict "..."]
    # starts in WAITING with default blanks: target_weight, stop_loss, entry_signal

# Rules
ledger.py rule add --kind NO_ACTION|ENTRY_COND|EXIT_COND|SIZING|META \
    --text "..." [--until YYYY-MM-DD|MM/DD|MMDD] [--scenario <id>]

# Trades (records an executed trade — never a recommendation)
ledger.py trade add --side BUY|SELL --ticker "..." --qty N --price N \
    [--note "..."] [--scenario <id>]

# Plan blanks
ledger.py blank set --scenario <id> --key stop_loss --value "-8%"

# Verification events
ledger.py event add --date MM/DD --title "..." --check "item1,item2,item3" \
    [--scenario <id>]
ledger.py verdict --scenario <id> --result PASS|PARTIAL|FAIL [--note "..."]
    # VERIFYING only

# State movement
ledger.py advance --scenario <id>    # one guarded step forward
ledger.py close   --scenario <id>    # REVIEW only; writes a review file

# Discipline bookkeeping
ledger.py violation bump --rule <id> # increment a rule's violation counter
ledger.py state                      # full current state as JSON (read this first)
```

`--scenario` and `--rule` accept a full id or an unambiguous id prefix.
All commands print JSON to stdout; errors print JSON to stderr and exit non-zero.
A global `--dir <path>` overrides the default `./discipline` location.

## Rule kinds

| Kind | Use |
|---|---|
| `NO_ACTION` | "Do nothing until X" (e.g. no buying before a verification date). |
| `ENTRY_COND` | A condition that must hold to enter. |
| `EXIT_COND` | A condition that governs exit. |
| `SIZING` | Position-size / tranche rules. |
| `META` | Rules about the rules — e.g. "don't change rules because of a daily move." |
