# Scenario template

Fill this out **while calm**, before any position exists. It is the raw material
for `ledger.py scenario new` and the rules/events you add afterward. The goal is
to make "future, emotional you" argue with "present, calm you" — in writing.

---

## 1. Title
A short handle for this thesis.
> e.g. "Semiconductor re-entry, 2026-07"

## 2. Thesis (why this could work)
One or two sentences. What is the actual bet?
> e.g. "Memory supply bottleneck + sustained hyperscaler capex."

## 3. Falsification (what would prove you wrong)
The single most important field. If you can't state what would make you record
FAIL, you don't have a thesis — you have a hope.
> e.g. "Any major hyperscaler explicitly cuts capex guidance."

## 4. Verdict criteria
What counts as PASS vs. PARTIAL vs. FAIL at the verification event?
> e.g. "PASS = HBM visibility into next year + capex flat/up; PARTIAL = mixed;
> FAIL = explicit capex cut."

## 5. Rules (the promises you make to yourself)
Add each with `ledger.py rule add`. Pick a kind:
- `NO_ACTION` — "do nothing until X"  → e.g. "No buying before the 07/29 check"
- `ENTRY_COND` — condition required to enter
- `EXIT_COND` — condition that governs exit
- `SIZING` — position size / tranche rules
- `META` — rules about the rules → e.g. "Do not change any rule because of a
  single day's move"

## 6. Plan blanks (filled before ENTERING)
These must all be non-null before the script lets you enter a position:
- `target_weight` → e.g. "15%"
- `stop_loss` → e.g. "-8%"
- `entry_signal` → e.g. "break above prior high after PASS"

## 7. Verification events
Add with `ledger.py event add`. Each is a date where reality tests the thesis.
> e.g. 07/29 — "SK Hynix earnings + Meta call" — check: HBM visibility, LTA,
> capex guidance direction.

---

### Quickstart

```bash
python ledger.py init
python ledger.py scenario new \
  --title "Semiconductor re-entry, 2026-07" \
  --thesis "Memory supply bottleneck + sustained hyperscaler capex" \
  --falsify "Any major hyperscaler explicitly cuts capex guidance" \
  --verdict "PASS = HBM visibility + capex flat/up; FAIL = explicit capex cut"

# copy the scenario id from the output, then:
python ledger.py rule add --kind NO_ACTION --text "No buying before the 07/29 check" --until 07/29 --scenario <id>
python ledger.py rule add --kind META --text "Do not change any rule because of a single day's move" --scenario <id>
python ledger.py event add --date 07/29 --title "SK Hynix earnings + Meta call" --check "HBM visibility,LTA,capex guidance direction" --scenario <id>
```
