# quick2query · plan (final)

Status: **final, awaiting Santi's approval.** Written Saturday 14 Nov 12:45 UTC after the initial EDA. Nothing in the repo is restructured until it is approved. Evidence: `docs/findings/00`–`07`, beliefs: `docs/SIMULATOR.md`. Times are UTC (CET = UTC + 1). The final is Sunday 09:00–11:00 UTC.

## 1. Where we stand

| | Conversion | Score |
|---|---|---|
| Baseline, and us today | 0.69% | 0 |
| Best team | 0.90% | about 7 |
| Reference | 2.10% | about 48 |
| Oracle, implied | 3.6–3.7% | 100 |

One score point is about 0.03 conversion points. The best-seller list shows 89% other-category products on product and category pages, where a same-category product converts 5 times better. **Target for tonight: above the reference.** The first rules strategy should already get most of the way.

## 2. Principles

1. **One process submits.** A single router owns `team_01.submissions`. A lease row stops a second one from starting.
2. **A strategy is one file.** New idea = new file.
3. **Understand, do not clone.** Hypotheses with verdicts accumulate in `docs/SIMULATOR.md`. Strategies are built from them.
4. **Generalise.** The final has new shoppers, products and trends. Score products from attributes (subcategory, brand, phrases, price) and shoppers from session, device and region. IDs are a bonus, never a requirement.
5. **History is a prior, live is the truth.** One effect already has opposite signs (bought products). Every history effect is checked live before it carries weight.
6. **RawTree is the system of record.** Features are SQL files. Tracking lives in `team_01.scratch`.
7. **Small code.** Seven modules, no framework, no helper used once.

## 3. Four kinds of work

| | EDA | Hypothesis | Strategy | Online |
|---|---|---|---|---|
| Question | What is in the data? | Is this one claim about the simulator true? | What do we show? | Does it work live? |
| Where | `eda/<nn>-<topic>.sql` or `.py` | `docs/hypotheses/H-<slug>.md`, `sql/hypotheses/H-<slug>.sql` | `src/q2q/strategies/<name>.py` | `arms.toml` |
| Output | `docs/findings/<nn>-<topic>.md` | verdict with effect size, then `docs/SIMULATOR.md` | offline row, then a block schedule | block readings, a line in `docs/JOURNAL.md` |

Hypothesis file: `status`, `owner`, `claim` (one falsifiable sentence), `test` (historical, live or both), `result` (one small table), `verdict` (with effect size), `next`. The open list is the "New hypotheses" table in `docs/SIMULATOR.md`.

## 4. Repo structure

```
AGENTS.md  CLAUDE.md       short rules for agents (CLAUDE.md is one line: @AGENTS.md)
pyproject.toml  uv.lock    uv project, python 3.12, package q2q, src layout
arms.toml                  traffic allocation and block schedule, the only deploy switch
src/q2q/
  rt.py                    RawTree client: query(), insert(). The only HTTP code
  data.py                  history pulls cached as parquet under data/
  state.py                 live state: catalogue, stock, prices, trends, shopper memory
  strategy.py              Strategy interface, registry, guard
  serve.py                 router: poll, assign arm, recommend, guard, push
  evaluate.py              offline checks and live block readings
  cli.py                   q2q serve | eval | blocks | pull | board
  strategies/              baseline.py, explore.py, rules.py, ranker.py, ...
eda/                       exploration scripts and SQL
sql/features/              one SELECT per feature set, run by data.py
sql/reports/               live report, reliability, cold slice
sql/hypotheses/            one file per hypothesis test
dashboard/app.py           Streamlit over team_01.scratch
docs/                      HANDOFF, PLAN, SIMULATOR, JOURNAL, JURY, findings/, hypotheses/, backlog/
scripts/                   keep_running.py, leaderboard_logger.py, q.py, probe.py
tests/                     guard and router only
starter/                   organisers' kit, untouched
data/  models/  logs/      gitignored
```

```python
class Strategy:
    name: str
    def fit(self, data) -> None: ...                  # offline, optional
    def recommend(self, req, state) -> list[str]: ... # up to 10 IDs, best first
    def learn(self, feedback_rows) -> None: ...       # optional online update
```

## 5. Router and state

**Router (`serve.py`).** Three threads: poll `shop.requests`, refresh state, push. No sleep between polls.

- Arm per request: explore share by `hash(user_id + salt)`, everything else to the arm that owns the current 10-minute block (section 7).
- **Guard:** drops inactive, out-of-stock and duplicate IDs, pads with in-stock best sellers, and uses the baseline list if a strategy throws or takes over 50 ms per batch. A broken experiment cannot cost a request.
- `model_version = <strategy>@<git sha>`.
- **Lease:** a `kind = 'lease'` row in `team_01.scratch` every 5 s with host and start time. A router refuses to start while another host's lease is under 20 s old. This replaces the test of which answer counts when two arrive. We never send two.
- Latency budget: p95 under 1.5 s from the laptop, under 1.0 s from a machine near RawTree. Today: p50 1.4 s, p95 2.3 s, of which 0.4 s is network distance and 0.3 s is the starter's sleep.

**State (`state.py`).** Loaded at start, then refreshed every 2–5 s from live tables.

| State | Source | Rule |
|---|---|---|
| Catalogue and attributes | `shop.catalog` + `shop.catalog_updates` | new products become candidates at once, scored from subcategory, brand and phrases |
| Stock | `shop.catalog_updates` | out at once; back in only 60 s after the row |
| Prices | `shop.catalog_updates` | small boost for a cut |
| Trend | `shop.events`, last 15 minutes against the last 2 hours, per subcategory | multiplier, capped |
| Product appeal | history, updated with live views and purchases | shrunk towards the attribute prediction |
| Shopper memory | history aggregates + live events + our feedback | bought set, viewed-not-bought counts, category shares |
| Segment priors | device × region × category | used for every shopper, the only memory for new ones |

A restart rebuilds all of it from RawTree and the parquet cache. Target: answering again within 60 s.

## 6. Strategies

| Strategy | What it does | When |
|---|---|---|
| `baseline` | the starter's logic. Also the guard's fallback | first |
| `explore` | 3% of traffic. Picks a stratum at random (recent views, same subcategory, same category, shopper's favourites, new products, anything), then products at random inside it. Logs the propensity | first |
| `rules` | score = appeal × relation to the shopper × segment × trend, 0 if bought. Candidates: recent views, viewed-not-bought, the session's subcategory and category, the shopper's top categories, the segment's top categories. Sorted by score | first real strategy |
| `ranker` | gradient-boosted trees on the same factors as features. Trained on history within category, then on live feedback and explore data | tonight |

- **Cold branch, inside every strategy.** No recent views: shopper's top categories and viewed-not-bought products. New shopper: segment prior, then session. New shopper with no views (6% of requests): segment best sellers. New product: attribute appeal.
- Multipliers in `rules` start from the effect sizes in `docs/SIMULATOR.md` and are re-estimated from live data.
- The explore arm is stratified because a uniformly random product converts at 0.04% per impression and would teach nothing. **This refines "small random-exploration arm". Say if you prefer plain uniform.**
- More ideas go to `docs/backlog/<slug>.md`: brand and phrase affinity, shopper clusters, a bandit over strategies. One radical idea in play at a time, after `rules` is champion.

## 7. Evaluation

| Level | Instrument | Speed | Use |
|---|---|---|---|
| 1. Offline | `q2q eval`: validity, latency, within-category replay on the history log with its propensities, next-view hit@10 on organic sessions, replay on our own explore data | minutes | filter only |
| 2. Live clicks | our feedback by `model_version` | 1,000 requests per arm for ×2, 16,000 for +20% | kill switch, hypothesis probes |
| 3. Leaderboard blocks | `q2q blocks` | 10 minutes | **the decision metric** |

**Offline is blind** to cross-category lists, the home page, repeat purchases and new products, because the old carousel showed one category per request, was not personalised, and put 96% of impressions on 1,000 products. It filters out broken strategies. It does not pick winners.

**Blocks.** The leaderboard refreshes every 10 minutes with an exact one-hour window. Consecutive windows differ by one block entering and one leaving, so `conversion × requests` differenced gives our lift over the baseline for each 10-minute block, on the same shoppers, with no coin flips.

- The router switches arms only at refresh times. `arms.toml` holds the schedule, for example `rules, ranker, rules, ranker`.
- Alternating blocks cancels drift. Measured floor: about 1 score point per block.
- Our lift divided by 2.95 (oracle minus baseline) is our score on that block. The same works for cold requests, with the cold request count taken from `shop.requests`.
- The chain breaks if a refresh is missed. The logger runs on two machines and rows are deduplicated on read.
- Purchases in our feedback cannot rank strategies: 75 per hour, 57,000 requests per arm for +20%.

**Promotion.** A challenger becomes champion when it wins three alternated block pairs, with valid answers ≥ 99%. **Kill, automatic:** valid < 98% over 5 minutes, or p95 over 2.5 s. Every promotion is a dated line in `docs/JOURNAL.md`.

**Final round.** The leaderboard is hidden, so blocks stop. The champion runs alone with 1% explore. State keeps learning: trends, new products, bought sets, segment priors. Our own clicks are the only alarm.

## 8. Tracking and dashboard

Our key can query and insert into existing tables only. It cannot create tables, run `INSERT ... SELECT` or create scheduled SQL. So all tracking is rows in `team_01.scratch` with a `kind` field:

| `kind` | Content | Written by |
|---|---|---|
| `leaderboard` | every team, baseline, reference, each refresh | logger (running now) |
| `lease` | host, start time, sha, champion | router |
| `arms` | block start, arm shares, sha | router |
| `block` | per block and arm: lift over baseline, score, cold lift | `q2q blocks` |
| `explore` | request, stratum, propensities | router |
| `offline_eval` | one row per `q2q eval` run | CLI |
| `live_report` | per arm and block: requests, valid %, p95, click rate | router timer |

- Features are `SELECT` files in `sql/features/`, run in RawTree and cached by `data.py`. A timer in the router replaces scheduled SQL.
- `dashboard/app.py` (Streamlit) reads only these rows: our score per block against baseline and reference with the schedule underneath, one card per strategy, reliability and latency, the hypothesis board.
- Without a read-only key the dashboard stays on our machine. For quick2query.com we export a static page.
- **Ask the organisers:** a key that can create tables and scheduled SQL, and a read-only key. Both help the jury score for RawTree use.

## 9. Deployment

**Recommended: one small VM in AWS US East (4 vCPU, 16 GB), no GPU.** RawTree's API appears to be hosted there: the address is in AWS and the round-trip time fits. From Barcelona each round trip costs 110–130 ms and an answer needs three or four. Measure `SELECT 1` from the VM first: under 30 ms confirms it. Fallback: Santi's desktop with sleep disabled. **Santi decides.**

| Machine | Runs | Never |
|---|---|---|
| Prod | `q2q serve` under systemd (`Restart=always`), leaderboard logger, dashboard | hand-edited code |
| Dev | EDA, hypotheses, `q2q eval`, `q2q serve --shadow` (computes, does not push), second logger | submits |

- Until prod is proven, the laptop keeps the starter running under `scripts/keep_running.py`. Closing the lid still suspends it.
- Switchover: stop the starter, start the router, watch 5 minutes of valid answers. A few seconds of fallback is acceptable.
- Sync is git. Prod tracks `main`. The router hot-reloads `arms.toml` and the strategies folder.
- **Sunday 07:00:** restart prod on purpose and confirm the router returns alone. **08:30:** freeze. Champion alone, explore 1%, no agents, no deploys.

## 10. Way of working

- Own private repo as `origin` (`quick2query`), organisers' repo as `upstream`.
- One git worktree and branch per agent, `agent/<slug>`. An agent owns the files it creates. Shared modules under `src/q2q/` change through a short reviewed PR.
- Claim work by setting `owner:` in a hypothesis or backlog file and pushing. Merge to `main` small and often.
- `arms.toml` is edited by a human, or by the night operator within its budget.
- Every session starts with `AGENTS.md`, `docs/SIMULATOR.md` and `q2q board`.
- Agents reach RawTree through `rtree` and the RawTree MCP server. Both still need installing by Santi (section 13).
- **Night.** The router runs the block schedule and the kill rules alone. A headless Claude Code session every 30 minutes reads the block table, writes verdicts, and may queue a strategy that passed offline and shadow. Its budget: challengers hold at most half of the blocks. A morning summary goes to `docs/JOURNAL.md`.
- **Hypothesis generator.** Three fresh subagents design the simulator from the public README only. Mechanisms that recur become hypotheses. Their code is not used.
- **Models.** Fable: synthesis into `SIMULATOR.md`, strategy design, the jury story. Opus: implementing strategies and hypothesis tests, night operator. Sonnet or Haiku: SQL-only tests and monitoring.

## 11. Jury

| Criterion | Evidence |
|---|---|
| Method (10) | block design on the leaderboard, promotion rule, journal, the offline-blind finding |
| Learning from the stream (10) | stratified explore arm, trend and price features, live shopper memory, segment priors for cold shoppers, the history-against-live reversal |
| Use of RawTree (5) | features as SQL, all tracking in RawTree, agents on `rtree` and MCP. Pitch: RawTree was the shared memory between people, agents and the router |
| Communication (5) | one slide per confirmed hypothesis ("believed, tested, changed") and the dashboard |

## 12. Order of work

| When (UTC) | What |
|---|---|
| On approval, 2 h | skeleton: `rt`, `state`, `strategy`, `serve`, `baseline`, `explore`, `AGENTS.md`, tests for the guard. Shadow run, then switch over from the starter |
| +2 h | `rules` live, alternated against `baseline` in blocks. `q2q blocks` |
| Saturday evening | prod machine. Live checks of history effects. `ranker`. Dashboard |
| Night | block schedule with challengers, night operator, hypothesis sprint |
| Sunday 06:00 | review, pick champion, write `docs/JURY.md` |
| Sunday 07:00 | restart rehearsal |
| Sunday 08:30 | freeze |
| Sunday 09:00–11:00 | final. Watch the status light and our click rate |
| Sunday afternoon | presentation |

## 13. Open items from the draft, resolved

| Draft question | Answer |
|---|---|
| Live click rate per arm | 2.4% on best sellers. Clicks confirm a ×2 effect within an hour on a 10% arm. +20% needs 16,000 requests per arm |
| Can a challenger's conversion be solved from the blend? | Not for a small share: the error grows by (1 − share) / share. Replaced by 10-minute blocks with one arm each |
| Is the oracle visible? | No. Implied by the hourly scores: 3.6–3.7%. The reference is at about 48 of 100 |
| Can the key create tables and scheduled SQL? | No. `team_01.scratch` with `kind`, and our own timer |
| Which answer counts when two arrive? | Not tested, on purpose. The lease guarantees one writer |

## 14. Needed from Santi

1. **Approve this plan**, or mark changes.
2. **The new repo URL.** Then `origin` becomes `upstream`, the new `origin` is added, and the work so far is committed and pushed.
3. **Prod machine:** VM in AWS US East, or the desktop.
4. **Install `rtree` and register the MCP server.** The session was not permitted to. A verified `rtree` 0.8.4 binary is downloaded and waiting.
5. **Ask the organisers** for a key with create-table and scheduled-SQL rights, and a read-only key.
6. Stratified explore arm, or plain uniform.
