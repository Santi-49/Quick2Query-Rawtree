# Handoff · start here

For the Claude Code session taking over. Written Saturday 14 Nov 2026, ~13:10 CET, by a planning session that could **not** reach `api.rawtree.com` (network allowlist). You can. Your job is the part that needs data.

Read in this order: this file → `README.md` (the challenge, by the organisers) → `docs/PLAN.md` (draft plan) → `docs/SIMULATOR.md` (what we believe about the hidden model).

## Situation

- Team `team_01`, name **quick2query** (we own quick2query.com). Santi is the developer; a second developer may join. Both can launch several agent sessions.
- Challenge: answer each request in `shop.requests` with 10 product IDs within 3 s. Only Sunday 10:00–12:00 CET counts. Practice until then.
- Credentials are in `.env` (`TEAM_ID`, `RAWTREE_API_KEY`). Never print, commit or copy the key.
- The repo is still the organisers' starter clone. `origin` points at their repo. Nothing has been restructured.
- Added so far: `docs/` (these files) and `scripts/probe.py` (written blind, never run; expect to fix a few queries).

## Facts from the public leaderboard (12:56 CET, last-hour window)

| | Conversion (expected purchases / 100 requests) |
|---|---|
| Baseline | 0.63% |
| Most teams (running the starter) | 0.64% |
| Best team | 0.74% |
| Organisers' reference | **2.11%** |
| Oracle | not shown |

- **team_01 was on time for only 16.5% of requests in that hour.** The starter baseline is not running reliably. Fix this first.
- Conversion is under 1%. At ~10,800 requests/hour that is about 70 purchases/hour in total. Purchases in our own feedback are far too sparse to compare strategies quickly.
- The leaderboard shows *expected* conversion (the hidden model's probability, no coin flip) for our traffic over the last hour, refreshed every 10 minutes, plus baseline and reference on the same stream. **It is the lowest-noise measurement we have.** The draft plan is built around this.
- The page loads its table with JavaScript. Find the JSON endpoint it calls.

## Decisions already taken by Santi

- Use `uv`. `src/` layout, package `q2q`. Good practice, but optimised for fast iteration.
- Santi creates his own repo. You switch the remote to it and keep the organisers' repo as `upstream`. Proposed repo name: `quick2query`.
- **Do not clone the simulator.** We want to understand how it works and what it reacts to, and use that knowledge in strategies. Subagents that "rebuild the simulator from the README" are allowed only as a source of hypotheses.
- Run a small random-exploration arm from today.
- Models must generalise to new shoppers and new products (the final brings both). Hypotheses should feed this cold-start branch.
- Rehearse a restart before the final.
- No MLflow. Tracking lives in RawTree tables and is shown in one dashboard (Streamlit or plain HTML) with strategy descriptions and live progress.
- The jury matters: use RawTree the way the product is meant to be used (SQL features, `rtree`, MCP, scheduled SQL) and be able to show why it helped.

## Your tasks, in order

**A. Keep us answering** (minutes)
1. Check whether `starter/recommender.py` is running and why on-time is 16.5% (stopped, laptop asleep, latency). Get it running and leave it running. It stays the only submitter until the router replaces it.

**B. Housekeeping** (minutes)
2. Fix `.env`: `TEAM_ID` has trailing spaces and the file has CRLF line endings.
3. Add `.gitattributes` (`* text=auto eol=lf`). Every file currently shows as modified because of line endings.
4. Ask Santi for the new repo URL. Then `git remote rename origin upstream`, add the new `origin`, push.
5. Install `rtree` (`curl -fsSL https://rawtree.com/install.sh | bash`; on Windows use WSL or Git Bash). Verify with `rtree query --api-key ... --database team_01 "SELECT count() FROM shop.requests"`. Register the RawTree MCP server (`https://mcp.rawtree.com/mcp`, bearer key) for agent sessions.

**C. Initial EDA** (the main job; 1–2 hours)
6. Run `uv run scripts/probe.py`, fix what fails, read `docs/findings/00-probe.md`.
7. Explore, one short findings file per topic in `docs/findings/` (numbers, a small table, one-line takeaways):
   - Tables: real columns and types, sizes, time ranges, query speed, API limits (max rows per query, rate limits).
   - Catalogue: categories, subcategories, brands, prices, what descriptions look like.
   - Carousel history: click and purchase base rates, by slot, page, device, region, hour; propensity distribution; how many products were ever shown.
   - Organic history: events per user and session, purchase funnel, repeat purchases.
   - Live stream: share of new shoppers, empty `recent_views`, cold requests, rates of new products, price changes and stock-outs, overlap of live users with history.
   - Our feedback so far: click and purchase rates, latency, fallback reasons.
8. What our key may do in RawTree: create tables in `team_01`, `INSERT ... SELECT`, SQL workflows (scheduled SQL), restricted read-only keys.
9. Start logging the leaderboard (all teams, baseline, reference) every 10 minutes.
10. Turn what you saw into the first verdicts in `docs/SIMULATOR.md` and a list of new hypotheses.

**D. Come back with the final plan**
11. Rewrite `docs/PLAN.md` as final: framework, repo structure, way of working, evaluation, deployment. Resolve every **[open]** item in the draft with what you measured. Keep it short enough to implement from.
12. **Stop and ask Santi to approve it before implementing.** Do not restructure the repo before that.

## Rules

- Exactly one process writes to `team_01.submissions`. If two answers arrive for a request only one counts, and we do not know which.
- Read-heavy SQL is fine; do not write anywhere except `team_01.*`.
- Prefer SQL in RawTree over pulling raw rows. Pull aggregates.
- Short files, plain code, no speculative abstractions.

## Still to be decided by Santi

- VM or desktop as the always-on machine (the draft recommends a small Linux VM, no GPU).
