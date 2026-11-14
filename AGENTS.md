# quick2query · rules for agents

Datathon FME 2026, RawTree challenge, `team_01`. Read `docs/PLAN.md` and `docs/SIMULATOR.md` before working.

## Never

- Never print, commit or copy the key in `.env`.
- **Never start a second writer to `team_01.submissions`.** Only `q2q serve` on the prod machine submits. Use `q2q serve --shadow` anywhere else.
- Never write outside `team_01.*`. Our key can only insert into `submissions` and `scratch`.
- Never clone the simulator. Record what it reacts to in `docs/SIMULATOR.md`.
- Only `/api/state` may be called on datathon.rawtree.dev.
- Do not edit `starter/`.

## Layout

| Path | What |
|---|---|
| `arms.toml` | traffic allocation and block schedule. The only deploy switch, hot-reloaded |
| `src/q2q/rt.py` | RawTree client, the only HTTP code |
| `src/q2q/state.py`, `data.py` | live state and cached history pulls |
| `src/q2q/strategy.py` | `Request`, `Strategy`, `guard` |
| `src/q2q/strategies/<name>.py` | one strategy per file, with a module-level `STRATEGY` |
| `src/q2q/serve.py` | the router |
| `sql/features/`, `sql/reports/`, `sql/hypotheses/` | SQL run in RawTree |
| `eda/`, `docs/findings/` | exploration and what it found |
| `docs/hypotheses/H-<slug>.md` | one hypothesis: status, owner, claim, test, result, verdict, next |

## Commands

```
uv run q2q serve --shadow     # compute answers, write nothing
uv run q2q pull               # rebuild the history caches under data/
uv run pytest -q
uv run scripts/q.py "SELECT ..."   # ad hoc SQL; also rtree and the RawTree MCP server
```

## SQL in RawTree

Every column is `Dynamic`. Cast before use: `x::String`, `ts::DateTime64(3)`, `shown::Array(String)`, `is_new_user::Bool`. An unmatched LEFT JOIN returns defaults, not NULL. Prefer aggregates in SQL over pulling rows. Details: `docs/findings/01-tables-api.md`.

## Style

Short files, plain code, no speculative abstractions, no helper used once. A new idea is a new strategy file. Offline results filter; the leaderboard blocks decide (PLAN section 7). Every promotion is a dated line in `docs/JOURNAL.md`.
