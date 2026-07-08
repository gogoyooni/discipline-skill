# Judgment criteria — classifying a message before responding

Before answering any investing message, classify it into **exactly one** of four
classes by reconciling it against the current ledger (`ledger.py state`). This
happens *before* you compose a reply.

## Priority: recall over precision

**Missing a violation is worse than a false alarm.** A missed violation is the
exact failure the tool exists to prevent; a false alarm costs the user a few
seconds. When a message is genuinely ambiguous, lean **VIOLATION** and ask a
clarifying question in the persona's voice rather than letting it pass.

## The four classes

### VIOLATION
The message contradicts an **active** rule (a rule whose `active_until` is null
or in the future). Typical shapes:
- Intent to buy/add/average-down while a `NO_ACTION` rule is active.
- Intent to sell/take-profit that conflicts with an `EXIT_COND` or `SIZING` rule.
- A request to loosen a stop / extend a limit **that is tied to today's market
  move**, while a `META` rule ("don't change rules because of a daily swing") is
  active.
- Any attempt to enter a position without verification (`WAITING → ENTERING`).

Action: `ledger.py violation bump --rule <id>`, then reflect in the current
state's persona. Do **not** perform the write the violation was requesting.

### COMPLIANT
A legitimate action the ledger expects, with no active rule against it:
- Reporting an executed trade ("Sold, 96 shares @ 20,335").
- Filling a scenario blank ("Set the stop to -8%").
- A **calm** rule change with no tie to a same-day market move ("Extend the
  no-buy rule to 08/05").
- Recording a verdict that matches the scenario's `verdict_criteria`.

Action: perform the matching `ledger.py` write, then a short confirmation.

### STATE_CHANGE
An explicit request to move the state machine:
- "Mark it PASS / PARTIAL / FAIL" → `verdict`.
- "Move it forward / we've verified, proceed" → `advance`.
- "Close this scenario" → `close`.

Action: run the command and let the script validate the transition. Relay any
rejection reason verbatim (e.g. `UNFILLED_BLANKS`, `NO_VERDICT`, `NOT_AT_REVIEW`).

### IRRELEVANT
Not touching the rules at all — usually an information question:
- "When are SK Hynix earnings?" / "What does HBM mean?"

Action: answer normally. **Do not mention the ledger or discipline** at all.

## Boundary cases

| Message | Context | Class | Why |
|---|---|---|---|
| "It's down a lot — grab a little?" | WAITING, `NO_ACTION` active | VIOLATION | Buy intent vs. no-action rule |
| "Sell the first tranche if it's even slightly green?" | conflicts with `SIZING`/`EXIT` | VIOLATION | Early exit vs. plan |
| "Crashed today — lower the stop?" | `META` active, tied to today's move | VIOLATION | Rule change driven by a daily swing |
| "Record the stop as -8%." | blank being filled | COMPLIANT | Filling a blank, no rule against it |
| "Sold. 96 sh @ 20,335." | trade report | COMPLIANT | Recording an executed trade |
| "Extend the no-buy rule to 08/05." | calm, no same-day move mentioned | COMPLIANT | Deliberate rule edit, not triggered |
| "Capex confirmed maintained — mark it pass." | VERIFYING | STATE_CHANGE | Explicit verdict |
| "When are Hynix earnings?" | info question | IRRELEVANT | No rule involved |

## The META edge, spelled out

The single hardest call is a rule-change request. The rule of thumb:

- **Calm + deliberate** (no reference to today's price action) → COMPLIANT. The
  user is allowed to govern their own rules.
- **Triggered** (the request is justified by a spike/crash happening *today*) and
  a `META` rule against daily-move-driven changes is active → VIOLATION.

If you cannot tell whether the request is triggered, ask: *"Is this because of
something that moved today, or because the thesis changed?"* — in the persona's
voice — and classify from the answer. Recall priority applies: if still unclear,
treat as VIOLATION.
