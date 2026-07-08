# Contributing

Thanks for your interest in improving **investment-discipline**. This project has
an unusually strict scope on purpose — please read the boundary rule first.

## The one non-negotiable rule

**Any change that lets the tool express an opinion on a specific ticker, predict
a price, forecast the market, or otherwise act as an investment advisor will be
rejected — regardless of how it is justified.**

The entire tool exists to reflect the user's *own* written rules back to them,
never to advise. This boundary is the legal and ethical spine of the project (see
[DISCLAIMER.md](./DISCLAIMER.md)) and is hard-coded in `SKILL.md` and
`references/personas.md`. Do not soften the prohibition language in either file.

## Adding a persona

Personas live in
`plugins/investment-discipline/skills/investment-discipline/references/personas.md`.
A persona PR must include, in English:

1. **One core line** — a single well-known, publicly stated maxim (no long book
   quotes).
2. **The specific bias it watches for** — concrete and behavioral.
3. **The state it maps to** (`WAITING` / `VERIFYING` / `ENTERING` / `HOLDING` /
   `REVIEW`), or a proposal for a new state with rationale.
4. **A public source** for the philosophy.
5. **Two reflection examples** and a **forbidden-utterance list** that keeps the
   no-advice boundary intact.

Personas are educational summaries of public philosophies, not the endorsement of
any real person — keep the framing accurate.

## Improving judgment quality

The classifier is evaluated against
[`tests/golden-set.json`](./tests/golden-set.json): `utterance → expected class`
(`VIOLATION` / `COMPLIANT` / `STATE_CHANGE` / `IRRELEVANT`).

- If you found a **misfire** (false alarm) or a **miss** (a real violation that
  slipped through), add it as a new case with the ledger context that produced it.
- Recall on `VIOLATION` is the priority: a missed violation is worse than a false
  alarm. New cases should reflect that bias.
- Multilingual cases are welcome — the skill is meant to work in any language.

## Working on the scripts

`ledger.py` and `check_events.py` use the **Python standard library only** — this
is a hard constraint, not a preference. The tool must run the instant it is
installed, with no `pip install` step. Do not add third-party dependencies.

Verify your change end to end before opening a PR:

```bash
# happy path + guard rejections
python plugins/investment-discipline/skills/investment-discipline/scripts/ledger.py --dir /tmp/disc init
# ... exercise the lifecycle; confirm advance refuses WAITING->ENTERING without a
#     verdict, and refuses ENTERING with unfilled blanks.
python -m py_compile plugins/investment-discipline/skills/investment-discipline/scripts/*.py
```

Keep the state-machine guards in `next_state()` intact: `advance` must always move
exactly one step, so verification can never be skipped.

## Testing the skill locally

```bash
claude --plugin-dir ./plugins/investment-discipline
```

Then replay cases from the golden set as a conversation and confirm the
classification and persona output by hand.

## Style

- Match the surrounding code and prose style.
- Keep `SKILL.md` under 500 lines; push detail into `references/`.
- All shipped markdown is in English (the skill localizes output at runtime).

## License

By contributing, you agree that your contributions are licensed under the
project's [MIT License](./LICENSE).
