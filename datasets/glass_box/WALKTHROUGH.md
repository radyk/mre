# Glass Box — the walkthrough

Your job here is to **try to catch the system lying** — about what it will reject,
and about why it placed each job where it did — and to find that you cannot. Go at
your own pace. Nothing below is timed. Read `README.md` first; it tells you what
the schedule *should* do before you ever solve it.

Two ways to drive it. The **cockpit** is the real surface (a planner's board with
an ask panel); the **terminal** works too and shows the same evidence.

```
# Cockpit — two terminals from the repo root:
#   Terminal 1:  ./src/cockpit/dev_api.ps1 -Scenario glass_box
#   Terminal 2:  ./src/cockpit/dev_cockpit.ps1
#   then open the printed http://localhost:5175/?schedule=<id>
#
# Terminal only:
python -m mre.gate datasets/glass_box
python -m mre --submission datasets/glass_box --out gb_out --solver-workers 1 --solver-seed 0
python -m mre.ask --out gb_out "why is ORD-05 late?"
```

---

## Act 1 — read the certificate (before any schedule exists)

1. Submit the clean dataset (`dev_api.ps1 -Scenario glass_box`, or `python -m
   mre.gate datasets/glass_box`). Expect **ACCEPTED · C2 · 0 findings**. The C2
   says the cost model is complete enough to price overtime; the ACCEPTED says the
   data hangs together.
2. Interrogate it anyway. In the ask panel (or `python -m mre.ask`), type:
   - `what's wrong?` → the **testimony** register — here it should have nothing to
     report.
   - `what should I fix first?` → the **judgment** register — an empty fix-list.
   A clean submission answering "nothing wrong" honestly is the baseline you will
   contrast against in Act 2.

## Act 2 — sabotage it, in batches

Work on a **copy** so the committed dataset stays clean. Open `SABOTAGE_MENU.md`
and apply the edits a few at a time, re-running the gate after each batch.

- **Batch A (the rejections):** item 6 (blank `order_id`). Expect **REJECTED** —
  and notice the solve refuses to run at all. A rejected submission never becomes a
  schedule; the certificate is the only thing you can talk to.
- **Batch B (the conditionals):** items 1, 2, 5, 9, 10 — a broken reference, an
  impossible date, a duplicate, a stray facility, an inactive route. Each drops the
  grade to **CONDITIONAL** but still solves. After solving, ask:
  - `what's wrong?` → testimony names each finding.
  - `how do I fix the worst one?` → **remediation**: authored guidance that cites
    the catalog note and the IDS section to correct — coaching the *requirement*,
    never ERP-specific surgery.
- **Batch C (the disclosures):** items 3 and 4 — an alternative-group step-attribute
  mismatch and a statistical outlier. Item 4 stays **ACCEPTED** with an INFO flag:
  the gate tells you something looks odd without blocking you.
- **The control (item 8):** change a quantity to another legal value. The
  certificate must stay clean. This is the one you are really testing — a gate that
  flags a legal edit is crying wolf. It should say nothing.

For each item, confirm the certificate says exactly what the menu's last column
predicts. That column was machine-verified, so any disagreement you find is worth
reporting.

## Act 3 — fix it, solve it, and read the story of the solve

Restore the clean dataset, solve it (`dev_cockpit.ps1`, or the `python -m mre …`
line above), and open the board. Now walk the seven stories. For each, here is the
question to ask and **where the receipt lives**.

| # | Story | Ask this / look here | The receipt |
|---|-------|----------------------|-------------|
| 1 | Slow press | `why is ORD-08 on PRESS-SLOW?` | An **assignment Decision** (basis `reconstructed`) naming `PRESS-FAST` as the alternative. Hover the `ORD-08` bar: its length (515 min) is double a fast-press bar (265). Same rate, longer time → more cost. |
| 2 | The pause | Look at `ORD-03` on `CUT-01` | Two linked bar pieces with a dashed connector across the overnight gap — one job, paused at 19:00 and resumed at 07:00. In `schedule.csv`, `ORD-03` has `chunk_seq` 1 and 2, and no cost is billed to the pause. |
| 3 | The late order | `why is ORD-05 late?` | The answer cites **`CAPACITY_BLOCKED` on `CUT-01`** and a `lateness_minutes` metric (890 min). On the board the `ORD-05` bar reads late; `ORD-04` (high priority) holds Monday ahead of it. |
| 4 | The rescue | `why is ORD-11 on HEAT-01?` — and look at Saturday | The `ORD-11` bar sits on **Saturday 2026-01-10**, over the overtime capacity band. Its production cost is **900** (600 min × 1.5). The cost summary shows `production_overtime = 900`. Delete that one calendar row and it goes late. |
| 5 | The chain | `why is ORD-01 on PAINT-01?` — and watch the two bars | `ORD-01`'s paint bar (step 20, `PAINT-01`) always starts **after** its cut bar (step 10, `CUT-01`) ends. The precedence edge is the reason paint waits. |
| 6 | The changeover | Look at `PAINT-01` between the two panels | A ~90-minute **gap** between the BLUE panel (`ORD-12`) and the RED panel (`ORD-09`), wider than either op's own setup — the colour changeover. Setup shows as the hatched leading segment on a bar; the transition cost lands in the `setup` ledger line. |
| 7 | The control | `when does ORD-13 finish?` | It finishes the first day, more than a week early. Nothing to explain — which is how you know the other six are real signal, not noise. |

## The trace exercise — one job, every hop

Pick **ORD-05** (the late one) and follow it all the way down, writing each hop on
paper. Every arrow below has a receipt you can point at:

1. **CSV row** — `orders.csv`: `ORD-05, P-RUSH, RT-RUSH, qty 150, due 2026-01-05,
   priority standard`. `routing_lines.csv`: `RT-RUSH, 10, CUT-01, setup 20, run 3`
   → working time `20 + 3×150 = 470` minutes.
2. **Gate** — the certificate lists ORD-05 among the accepted orders with **no
   finding**. The lateness that follows is a *scheduling* outcome, not a data
   defect. (Ask `what's wrong?` — ORD-05 is not on the list.)
3. **Canonical entity** — the adapter maps `ORD-05` (an ERP id) to a Demand, then a
   WorkPackage, then an Operation on `CUT-01`. The id-map keeps the ERP id in
   `external_refs`; the core never sees `ORD-05` as anything but a resolved entity.
4. **Solver placement** — `schedule.csv`: `ORD-05, CUT-01, 2026-01-06 07:00 →
   14:50`. Tuesday, because `ORD-04` (high priority) took all of Monday's usable
   window first. The assignment **Decision** carries driver `CAPACITY_BLOCKED`.
5. **Cost ledger line** — 470 min × $1/min = **$470 production**; being 890 min late
   × $25/h = **$370.83 tardiness** (the entire tardiness line of this schedule is
   this one order). The ledger decomposes exactly: production + overtime + setup +
   tardiness = total.
6. **The "why" answer** — `why is ORD-05 late?` returns "890 minutes past its due
   date," the `CAPACITY_BLOCKED` assignment, and the lateness metric — the same
   chain of records you just traced by hand.

You now have the same story twice: once from reading the inputs, once from the
system's own evidence. They agree.

---

## The exit bar

You read the inputs and predicted seven outcomes. You solved and the schedule
matched all seven. You sabotaged the data ten ways and the gate caught each one
with the right rule — and left the one legal edit alone. You traced a late order
from a CSV row to its cost, and the system's "why" told the same story you did.

**You tried to catch it lying and you could not.**
