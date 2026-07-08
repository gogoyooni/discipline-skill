# Design — investment-discipline

> A Claude Code **skill plugin**, distributed through a GitHub-based plugin
> marketplace. There is no bot, no server, no monorepo. The conversation is the
> only runtime.

## 1. Product definition

An **investment decision-discipline coach.** The user records the rules they set
while calm into a file ledger. Later, in ordinary conversation with Claude, if a
message contradicts those rules ("should I buy?", "should I average down?",
"should I change the rule?"), the skill — and only then — challenges the user in
the voice of a master investor appropriate to the current phase.

### Does / does not

| Does | Never (permanent limits) |
|---|---|
| Record trades, rules, scenarios, events (file ledger) | Recommend tickers; make buy/sell decisions |
| Judge message vs. rule for contradiction | Forecast markets; predict prices |
| On a violation, reflect in a persona quoting the rule verbatim | Quote live prices / compute returns (KPI is rule-adherence) |
| Check the verification-event calendar | Push notifications (no server) |

### Core principles

1. **Intervention is valuable because it is rare** — a persona speaks only on a
   `VIOLATION`.
2. **Ledger writes are forced through a script** — `ledger.py` is the only
   read/write path, so the model can never reconstruct rules from memory. "A rule
   that was not written is not a rule," as code.
3. **Judge first, answer second** — every investing message is reconciled against
   the ledger before a reply is composed.
4. **The no-ticker-opinion ban is a legal defense** — it is never softened.

## 2. Repository layout (the repo *is* the marketplace)

```
discipline-skill/
├── .claude-plugin/marketplace.json        # repo = installable marketplace
├── plugins/investment-discipline/
│   ├── .claude-plugin/plugin.json
│   └── skills/investment-discipline/
│       ├── SKILL.md                        # workflow body (< 500 lines)
│       ├── references/                     # personas, judgment, state machine
│       ├── scripts/                        # ledger.py, check_events.py
│       └── assets/scenario-template.md
├── examples/discipline/                    # fabricated example ledger
├── tests/golden-set.json                   # 30 judgment eval cases
├── docs/design.md                          # this file
├── DISCLAIMER.md · LICENSE · README.md · .gitignore
```

## 3. Data model — file ledger

Created as a `discipline/` folder in the user's working directory. Single
`ledger.json` (schema-versioned) plus a `reviews/` folder for retrospectives.
Validation is done by `ledger.py` using the **standard library only** — no
third-party dependency — so the tool runs the moment it is installed, on any
machine, with no `pip install` step. (The original design considered pydantic;
stdlib was chosen to remove install friction for a distributed plugin.)

Entities: `scenarios`, `rules`, `trades`, `events`. See
`skills/investment-discipline/references/state-machine.md` for the full command
reference and every enforced invariant.

### Invariants the script enforces (code, not prose)

- `advance` moves exactly one state at a time, so `WAITING → ENTERING`
  (entering without verifying — the exact behavior this tool exists to stop) is
  structurally impossible.
- Entering `ENTERING` is refused while any plan blank is null; the missing blanks
  are listed.
- State changes only through explicit commands (`verdict`, `advance`, `close`).
  There is no command that sets an arbitrary state.

## 4. Judgment

The skill classifies every investing message into `VIOLATION`, `COMPLIANT`,
`STATE_CHANGE`, or `IRRELEVANT` (see `references/judgment-criteria.md`). **Recall
on VIOLATION is the priority: a missed violation is worse than a false alarm.**
On a violation, the current state's persona reflects the rule back verbatim,
names the bias, and offers exactly one alternative action — with no market view.

## 5. Quality — the golden set

`tests/golden-set.json` holds 30 `utterance → expected classification` cases
across several languages. Verification method: install locally with
`claude --plugin-dir ./plugins/investment-discipline`, replay the utterances as a
conversation, and confirm the classification and persona output by hand. Every
false positive / false negative found in real use is added back to the set.

## 6. Distribution

Users install with two lines (see README). Plugin names are kebab-case (required
for claude.ai marketplace sync); versions are semver and updated in both
`plugin.json` and `marketplace.json` together. A `.skill` package is attached to
GitHub Releases as a secondary channel for claude.ai-only users.

## 7. Roadmap

- **Build** — scripts + invariants, SKILL.md + references, examples, local
  verification against the golden set.
- **Dogfood (one full cycle)** — run a real WAITING → … → REVIEW cycle. The key
  question is whether the skill auto-triggers on impulsive messages.
- **Publish** — only *after* one dogfooding cycle. Shipping a discipline tool the
  author has never lived through would contradict the tool's own philosophy
  ("judged by adherence, not by outcome"). The README's first testimonial must be
  the author's own cycle data.
