# H-slot-order · are rules2 and jasper lists sorted?
- **status**: confirmed for rules2 down to slot 7, with one misplaced type: later recent views sit too high, same-subcategory products too low. jasper sorts slot 1 only; too few clicks to say more.
- **owner**: agent
- **claim**: a well-sorted list has a click rate per slot that falls faster than the attention curve 1/log2(slot+1); where it does not, a relation type is placed too high or too low.
- **test**: `sql/hypotheses/H-slot-order.sql`, run 14 Nov 16:20 UTC. rules2 = rules2|slate|m202e1|romesco (all routes, 10,914 lists, 516 clicks, 181 buys); jasper = ranker (1,663 lists, 63 clicks). Ratio = click rate per slot over the list mean, divided by the attention weight (1 = attention only).

## 1 · Slot curve
| slot | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| rules2 clicks | 170 | 87 | 67 | 45 | 30 | 33 | 20 | 22 | 22 | 20 |
| rules2 ratio | 1.50 | 1.21 | 1.18 | 0.92 | 0.68 | 0.82 | 0.53 | 0.61 | 0.64 | 0.61 |
| jasper clicks † | 28 | 7 | 5 | 5 | 4 | 2 | 6 | 4 | 2 | 0 |
| jasper ratio † | 2.02 | 0.80 | 0.72 | 0.84 | 0.75 | 0.40 | 1.30 | 0.91 | 0.48 | 0 |
rules2 falls from 1.5 to 0.6 by slot 7 and is flat below: slots 7–10 hold interchangeable products. jasper's slot 1 is strong, slots 2–10 are flat around 0.8: it orders the first product only.

## 2 · Where each relation type is placed (rules2; jasper all † except the totals)
| type | imps | in slots 1–3 | slots 1–3: clicks / ctr_w | slots 4–10: clicks / ctr_w | buys / conv_w |
|---|---|---|---|---|---|
| only view | 1,368 | 75% | 29 / 3.32 | 1 / 0.79 | 14 / 1.40 |
| first of 2+ views | 2,919 | 70% | 37 / 2.14 | 5 / 1.60 | 20 / 0.98 |
| **later view** | 4,878 | **62%** | 26 / **1.09** | 3 / 0.45 | 12 / **0.39** |
| **subcategory of the last view** | 9,105 | **22%** | 43 / **3.18** | 33 / 1.36 | 32 / **0.85** |
| main category | 41,898 | 25% | 105 / 1.49 | 82 / 0.76 | 64 / 0.36 |
| other viewed category | 8,132 | 25% | 17 / 1.26 | 14 / 0.67 | 15 / 0.44 |
| other | 23,060 | 29% | 37 / 0.79 | 37 / 0.66 | 13 / 0.13 |
- Later recent views take a top-3 place 62% of the time and convert there at a third of the same-subcategory products placed in the top 3 (1.09 against 3.18 clicks, 26 against 43). Moving them below the best same-subcategory products is the largest ordering fix.
- "Other" products (favourite category, segment) at slots 1–3 convert like those below (0.79 against 0.66): placed too high, but only 13 buys; no change yet.
- jasper: first of 2+ views 6 clicks at slots 1–3, later views 4, subcategory of the last view 3 at slots 1–3 against 7 below. Same direction as rules2, too few clicks.

## verdict
- rules2 is sorted down to slot 7. The one clear misorder is a type, not a slot: later recent views above same-subcategory products. rules4 lowers later views to OTHER_VIEW 5 (from 12), below 4.5 × a higher appeal.
- No reason to re-sort slots 7–10.

## next
- Re-run section 2 on rules4 lists; expect later views at ~30% in slots 1–3 and same-subcategory products up. jasper: re-read at 300 clicks.
