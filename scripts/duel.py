"""Score the interleaved duels (strategy duel1): which side's products get clicked and bought on the shared screen.

    uv run scripts/duel.py            # all duel rows, per pair, then per hour
    uv run scripts/duel.py 120        # only requests from the last 120 minutes

Counts only requests we served (served_by = 'team') whose shown list holds every credited product, so rows logged by
a shadow router or for a request that fell back are ignored. Share for B = B / (A + B); p is the two-sided sign test
against 0.5, the interval is Wilson 95%. docs/hypotheses/H-interleave.md.
"""
import math
import sys

from q2q import rt

SQL = """
WITH d AS (
    SELECT request_id::String AS rid, a::String AS a, b::String AS b, any(ts::String) AS t,
           any(a_items::Array(String)) AS ai, any(b_items::Array(String)) AS bi
    FROM {{TEAM}}.scratch
    WHERE kind::String = 'duel' AND a::String != 'selftest' {where}
    GROUP BY rid, a, b
),
f AS (
    SELECT request_id::String AS rid, any(shown::Array(String)) AS shown,
           any(clicked::String) AS c, any(purchased::String) AS p
    FROM {{TEAM}}.feedback
    WHERE served_by::String = 'team'
    GROUP BY rid
)
SELECT d.a AS a, d.b AS b, {bucket} AS bucket, count() AS requests,
       countIf(f.c != '') AS clicks, countIf(has(d.ai, f.c)) AS a_clicks, countIf(has(d.bi, f.c)) AS b_clicks,
       countIf(f.p != '') AS buys, countIf(has(d.ai, f.p)) AS a_buys, countIf(has(d.bi, f.p)) AS b_buys
FROM d INNER JOIN f ON d.rid = f.rid
WHERE hasAll(f.shown, arrayConcat(d.ai, d.bi))
GROUP BY a, b, bucket
ORDER BY a, b, bucket
"""


def sign_p(k: int, n: int) -> float:
    """Two-sided exact binomial test of k successes in n against 0.5."""
    if n == 0:
        return 1.0
    lo = min(k, n - k)
    tail = sum(math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) - n * math.log(2)) for i in range(lo + 1))
    return min(1.0, 2 * tail)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = k / n
    mid, half = (p + z * z / (2 * n)) / (1 + z * z / n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return mid - half, mid + half


def line(label: str, r: dict) -> str:
    out = f"{label:<22} {r['requests']:>7}"
    for what in ("clicks", "buys"):
        a, b = int(r[f"a_{what}"]), int(r[f"b_{what}"])
        lo, hi = wilson(b, a + b)
        share = f"{b / (a + b):.3f}" if a + b else "  -  "
        out += f" | {what} {int(r[what]):>5} A {a:>5} B {b:>5} B share {share} [{lo:.3f}, {hi:.3f}] p {sign_p(b, a + b):.3f}"
    return out


def main() -> None:
    minutes = int(sys.argv[1]) if len(sys.argv) > 1 else None
    where = f"AND ts::DateTime64(3) >= now64(3) - INTERVAL {minutes} MINUTE" if minutes else ""
    for title, bucket in (("per pair", "'all'"), ("per hour (UTC)", "substring(d.t, 1, 13)")):
        rows = rt.query(SQL.format(where=where, bucket=bucket))
        print(f"## {title}" + (f", last {minutes} min" if minutes else ""))
        for r in rows:
            print(line(f"{r['a']} vs {r['b']}" if bucket == "'all'" else f"{r['a'][:7]}/{r['b'][:7]} {r['bucket'][5:]}h", r))
        if not rows:
            print("no duel rows with feedback yet")


if __name__ == "__main__":
    main()
