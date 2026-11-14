# H-cold-prior · a new shopper behaves like the average of their device × region segment
- **status**: confirmed for android-south; no other segment found.
- **owner**: agent
- **claim**: for shoppers without history, the purchase probability of a category depends on device × region.
- **test**: `sql/hypotheses/H-cold-prior.sql`, run 14 Nov ~16:20 UTC. History carousel (one category per request, slot-1 category), and live feedback.

## result
| history, purchase % per request (buys) | all | Books | Fashion | Electronics | Kitchen | Computers | Toys |
|---|---|---|---|---|---|---|---|
| android-south (Andalucía, Canarias, Murcia) | 3.09 (5,971) | 4.06 | **8.08** | 3.93 | 3.70 | 2.93 | 4.24 |
| android elsewhere | 0.95 (4,458) | 2.24 | 1.21 | 0.81 | 0.27 | 0.46 | 1.69 |
| ios | 1.25 (8,378) | 3.36 | 1.19 | 1.05 | 0.21 | 0.62 | 2.19 |
| web | 1.38 (9,246) | 4.11 | 0.79 | 0.84 | 0.26 | 0.70 | 2.34 |

- The same holds on each user's first request (android-south 2.88%, 168 buys; others 0.97–1.46%) and on home (0.55% vs 0.09–0.11%).
- Per region: android Murcia 3.81%, Andalucía 3.08%, Canarias 2.65%; every other android region 0.76–1.09%. iOS and web flat across regions (0.91–1.59%).
- No hour or weekday effect (home 0.12–0.19% by 4-hour block, 0.137–0.153% by weekday).
- Live, per request: android-south new shoppers 4.35% off home (68 / 1,562), 1.84% on home (7 / 381); others 1.53% and 0.49%.
  Live new shoppers android-south by category, weighted: Fashion 1.68 (15 buys), Computers 1.63 (8), Kitchen 1.35 (11) vs Books 0.19, Toys 0.18.

## verdict
Confirmed: one segment, android in three southern regions, ×3 overall and ×5–30 in Fashion, Kitchen, Computers, Electronics; history and live agree. `state.segment` already carries it.

## next
None beyond keeping the segment lift in every cold strategy (cold1, cold2).
