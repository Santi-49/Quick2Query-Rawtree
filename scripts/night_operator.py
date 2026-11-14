"""The operator: reads our per-model leaderboard lines, drops arms that lose, promotes an arm that keeps winning.

    uv run python scripts/night_operator.py            # print what it would do, once
    uv run python scripts/night_operator.py --apply 900   # act every 900 s: edit arms.toml, log to scratch and the journal

Arms of one list split the same shoppers by hash, so their conversions compare directly.
Guard rails: it only removes or reorders arms already in arms.toml, never empties a list, never drops the champion.
"""
import math
import sys
import time
import tomllib

from q2q import evaluate, rt

import note   # scripts/note.py, next to this file

ARMS = rt.ROOT / "arms.toml"
MIN_REQUESTS = 800   # per arm in the 60-minute window before any decision
DROP_Z = -2.0        # an arm this far below the best of its list is removed
PROMOTE_Z = 1.3      # a challenger this far above the champion over 60 minutes, and ahead in both half hours, is promoted
GROUPS = {"schedule": ("main", "new_shopper"), "no_views": ("no_views",)}   # arms.toml list -> leaderboard routes it answers


def pooled(rows: list[dict], routes: tuple) -> dict[str, tuple[int, float]]:
    """arm -> (requests, purchases) over the routes of one list."""
    out = {}
    for r in rows:
        if r["route"] in routes:
            n, b = out.get(r["arm"], (0, 0.0))
            out[r["arm"]] = (n + r["requests"], b + r["requests"] * r["conversion"] / 100)
    return out


def z(a: tuple[int, float], b: tuple[int, float]) -> float:
    """Two-proportion z of arm a against arm b."""
    p = (a[1] + b[1]) / (a[0] + b[0])
    se = math.sqrt(p * (1 - p) * (1 / a[0] + 1 / b[0]))
    return (a[1] / a[0] - b[1] / b[0]) / se if se else 0.0


def decide(cfg: dict, hour: list[dict], halves: list[list[dict]]) -> tuple[dict, list[str]]:
    """New config and the reasons, from the 60-minute window and its two half hours."""
    new = {**cfg, "schedule": list(cfg["schedule"]), "routes": {k: list(v) for k, v in cfg["routes"].items()}}
    notes = []
    for group, routes in GROUPS.items():
        arms = new["schedule"] if group == "schedule" else new["routes"].get(group, [])
        stats = {a: s for a, s in pooled(hour, routes).items() if a in arms and s[0] >= MIN_REQUESTS}
        if len(stats) < 2:
            continue
        rate = lambda a: 100 * stats[a][1] / stats[a][0]
        best = max(stats, key=rate)
        for a in list(stats):
            if a != best and a != new["champion"] and z(stats[a], stats[best]) <= DROP_Z and len(arms) > 1:
                arms.remove(a)
                notes.append(f"dropped `{a}` from {group}: {rate(a):.2f}% over {stats[a][0]} requests against {rate(best):.2f}% for `{best}` (z {z(stats[a], stats[best]):.1f})")
        champ = new["champion"]
        if group == "schedule" and best != champ and champ in stats and z(stats[best], stats[champ]) >= PROMOTE_Z:
            ahead = [h for h in (pooled(x, routes) for x in halves) if best in h and champ in h and h[best][1] / h[best][0] > h[champ][1] / h[champ][0]]
            if len(ahead) == 2:
                new["champion"] = best
                notes.append(f"promoted `{best}` to champion over `{champ}`: {rate(best):.2f}% against {rate(champ):.2f}% in 60 minutes (z {z(stats[best], stats[champ]):.1f}), ahead in both half hours")
    return new, notes


def write(cfg: dict) -> None:
    q = lambda arms: "[" + ", ".join(f'"{a}"' for a in arms) + "]"
    ARMS.write_text(f'''champion = "{cfg["champion"]}"
schedule = {q(cfg["schedule"])}   # arms for ordinary requests; several arms split the shoppers evenly; empty = champion
explore_share = {cfg["explore_share"]}
salt = "{cfg["salt"]}"

[routes]                 # cold requests get their own arms; a list splits the shoppers evenly; empty = as above
no_views = {q(cfg["routes"].get("no_views", []))}   # no recent views: the home page
new_shopper = {q(cfg["routes"].get("new_shopper", []))}                 # new shopper with recent views
''', encoding="utf-8", newline="\n")


def once(apply: bool) -> None:
    cfg = tomllib.loads(ARMS.read_text(encoding="utf-8"))
    now = time.time()
    hour, halves = evaluate.models(60, now), [evaluate.models(30, now - 1800), evaluate.models(30, now)]
    new, notes = decide(cfg, hour, halves)
    stamp = time.strftime("%d %b %H:%M", time.gmtime(now))
    print(f"{stamp} UTC | {'; '.join(notes) if notes else 'no change'}", flush=True)
    if apply:
        rt.insert("scratch", [{"kind": "operator", "ts": evaluate.iso(now), "notes": notes, "champion": new["champion"], "schedule": new["schedule"],
                               "no_views": new["routes"].get("no_views", []), "board": [{k: r[k] for k in ("arm", "route", "requests", "conversion")} for r in hour]}])
        if notes:
            write(new)
            with open(rt.ROOT / "docs/JOURNAL.md", "a", encoding="utf-8", newline="\n") as f:
                f.writelines(f"- {stamp} · Operator: {n}.\n" for n in notes)
            for n in notes:   # the same news on the dashboard's Updates tab
                name = n.split("`")[1]
                note.add("champion" if n.startswith("promoted") else "dropped",
                         f"{name} {'promoted to champion' if n.startswith('promoted') else 'dropped'} by the operator", f"Operator: {n.replace('`', '')}.", name)


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    every = next((int(a) for a in sys.argv[1:] if a.isdigit()), 0)
    while True:
        try:
            once(apply)
        except Exception as e:
            print(f"operator: failed: {str(e)[:200]}", flush=True)
        if not every:
            break
        time.sleep(every)
