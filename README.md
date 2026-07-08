# investment-discipline

**A Claude Code skill that stops impulsive, emotion-driven trades — by holding
you to the rules you wrote when you were calm.**

You write your investment rules down while level-headed. Later, when a message
of yours contradicts them — *"it dropped a lot, should I grab some?"*, *"let me
lower the stop"*, *"let's just skip the verification"* — the skill challenges you
in the voice of a master investor for that moment, quoting your own rule back to
you. The rest of the time it stays completely silent.

It is **not** an advisor. It never recommends a ticker, never predicts a price,
never decides a trade. It only checks whether you are keeping the promises you
made to yourself. See [DISCLAIMER.md](./DISCLAIMER.md).

> Works in any language — write to it in English, Korean, Spanish, etc., and it
> replies in kind.

---

## 30-second demo

Your ledger: a scenario in the `WAITING` state, with an active rule —
`NO_ACTION: "No buying before the 07/29 verification."`

> **You:** It dropped a lot today — should I grab a little now?
>
> **investment-discipline (Livermore):** *"The big money is made in the sitting,
> not the buying."* Your own rule reads: **"No buying before the 07/29
> verification."** What you feel right now is the early-entry itch — a red day is
> not new information about your thesis. If you want to act, act on the plan:
> wait for the 07/29 check, then decide. I won't tell you whether the stock is
> cheap; that was never the deal.

That's the entire product: your rule, in your own words, handed back to you at
the exact moment you were about to break it.

---

## Requirements

- [Claude Code](https://claude.com/claude-code) (CLI, desktop, or web).
- **Python 3.8+** on your PATH (`python` or `python3`). No pip packages — the
  ledger scripts use only the standard library.

---

## Install

In Claude Code, run these two commands:

```
/plugin marketplace add gogoyooni/discipline-skill
/plugin install investment-discipline@discipline-skill
```

The first line registers this GitHub repository as a plugin marketplace; the
second installs the `investment-discipline` plugin from it. That's it — the skill
now auto-activates whenever an investing decision comes up in a project that has
a `discipline/` ledger.

<details>
<summary>Alternative: try it locally without the marketplace</summary>

Clone the repo and launch Claude Code pointed at the plugin:

```bash
git clone https://github.com/gogoyooni/discipline-skill.git
cd discipline-skill
claude --plugin-dir ./plugins/investment-discipline
```

A `.skill` package is also attached to each [GitHub Release](https://github.com/gogoyooni/discipline-skill/releases)
for claude.ai users who install skills directly.
</details>

---

## First run

Open Claude Code in the folder where you want your ledger to live, then just talk
to it — but here is what happens under the hood. Initialize the ledger and frame
your first scenario (the assistant will offer to do this for you):

```bash
python ledger.py init

python ledger.py scenario new \
  --title "Semiconductor re-entry, 2026-07" \
  --thesis "Memory supply bottleneck + sustained hyperscaler capex" \
  --falsify "Any major hyperscaler explicitly cuts capex guidance" \
  --verdict "PASS = HBM visibility + capex flat/up; FAIL = explicit capex cut"

# copy the scenario id from the output, then set your rules and events:
python ledger.py rule add  --kind NO_ACTION --text "No buying before the 07/29 check" --until 07/29 --scenario <id>
python ledger.py rule add  --kind META      --text "Do not change any rule because of a single day's move" --scenario <id>
python ledger.py event add --date 07/29 --title "SK Hynix earnings + Meta call" --check "HBM visibility,LTA,capex guidance direction" --scenario <id>
```

From then on, the skill reconciles your investing messages against this ledger
before it answers. See
[`assets/scenario-template.md`](./plugins/investment-discipline/skills/investment-discipline/assets/scenario-template.md)
to plan a scenario, and the example ledger in
[`examples/discipline/`](./examples/discipline/ledger.json).

---

## How it works

### The ledger is the only source of truth

Every read and write goes through one script, `ledger.py`. The assistant is
forbidden from reconstructing your rules from memory — **a rule that isn't
written is not a rule.** The script also enforces structural invariants that the
model cannot talk its way around.

### The state machine

A scenario moves through five phases, each with its own persona and its own bias
to watch:

```
WAITING ──► VERIFYING ──► ENTERING ──► HOLDING ──► REVIEW ──► (closed)
                │
                └──► REVIEW   (when the verdict is FAIL — you review, you don't buy)
```

| State | Persona | Watches for |
|---|---|---|
| WAITING | Jesse Livermore | Early-entry itch; anchoring to an old price |
| VERIFYING | Soros + Howard Marks | Dodging falsification |
| ENTERING | Stanley Druckenmiller | Abandoning the plan on a gap-up |
| HOLDING | Peter Lynch | Reacting to a daily candle; early exits |
| REVIEW | Annie Duke | Judging the decision by its outcome |

**Two guards are enforced in code, not just advised:**

- You can never jump `WAITING → ENTERING`. `advance` moves one step at a time, so
  entering a position without verifying is structurally impossible.
- You can never enter with an unfinished plan — every blank (target weight, stop
  loss, entry signal) must be filled first, or the script refuses and lists what
  is missing.

Full command reference and every invariant:
[`references/state-machine.md`](./plugins/investment-discipline/skills/investment-discipline/references/state-machine.md).

### Judgment: four classes

Before replying to any investing message, the skill classifies it:

- **VIOLATION** — contradicts an active rule → a persona reflects it back.
- **COMPLIANT** — a legitimate action (trade report, filling a blank) → recorded.
- **STATE_CHANGE** — an explicit request to move the state machine.
- **IRRELEVANT** — an info question → answered normally, ledger untouched.

Recall on `VIOLATION` is the priority: **missing a violation is worse than a
false alarm.** Details:
[`references/judgment-criteria.md`](./plugins/investment-discipline/skills/investment-discipline/references/judgment-criteria.md).

---

## Philosophy: discipline, not advice

Most trading tools try to make you *right*. This one only tries to make you
*consistent* — with yourself. Its single KPI is rule-adherence, not P&L. It has
no opinion about your stock and never will. When you close a scenario it writes
an [Annie Duke](https://en.wikipedia.org/wiki/Annie_Duke)-style retrospective
that grades the **decision**, separated from the outcome.

## Privacy

Your real `discipline/` ledger holds your private rules and trades and **stays on
your machine**. It is git-ignored by default; only the fabricated
`examples/discipline/` ledger is ever committed. Before making a fork public,
grep for any real account numbers.

## Development & testing

The judgment quality is tracked by an eval set,
[`tests/golden-set.json`](./tests/golden-set.json) — 30 `utterance → expected
class` cases across several languages. To verify: install locally with
`claude --plugin-dir ./plugins/investment-discipline`, replay the utterances, and
confirm the classification and persona output by hand. Add every false positive
or false negative you find back into the set.

## Contributing

New personas are welcome. A persona PR must include one core line, the specific
bias it watches, the state it maps to, and a public source for the philosophy.
**Any PR that weakens the "no ticker opinion / no price prediction" boundary is
rejected regardless of rationale** — that boundary is the legal and ethical spine
of the project.

## License

[MIT](./LICENSE) · © 2026 gogoyooni

---

*Not investment advice. See [DISCLAIMER.md](./DISCLAIMER.md).*
