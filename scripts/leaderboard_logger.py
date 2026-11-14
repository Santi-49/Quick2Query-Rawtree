# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Log every public leaderboard refresh into team scratch (kind = 'leaderboard').

    uv run scripts/keep_running.py scripts/leaderboard_logger.py

One row per team, plus 'baseline' and 'reference', per refresh (every 10 minutes).
The raw JSON is also kept under data/leaderboard/ as a backup. Run it on one machine only.
"""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
for line in (ROOT / ".env").read_text().splitlines():
    key, _, value = line.partition("=")
    if value and not key.startswith("#"):
        os.environ.setdefault(key.strip(), value.strip())
API = os.environ.get("RAWTREE_API_URL", "https://api.rawtree.com")
TEAM = os.environ["TEAM_ID"]
STATE_URL = "https://datathon.rawtree.dev/api/state"
RAW = ROOT / "data" / "leaderboard"
http = requests.Session()
http.headers["Authorization"] = f"Bearer {os.environ['RAWTREE_API_KEY']}"


def iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def rows(state: dict) -> list[dict]:
    window = state.get("window") or [None, None]
    common = {"kind": "leaderboard", "ts": iso(state["updated_at"]), "mode": state["mode"],
              "window_start": iso(window[0]) if window[0] else None, "window_end": iso(window[1]) if window[1] else None}
    teams = list(state.get("teams") or []) + [t for t in (state.get("baseline"), state.get("reference")) if t]
    lights = [{"team_id": x["team_id"], "green": x["green"]} for x in state.get("lights") or []]
    progress = state.get("progress") or {}
    return [{**common, **t, "progress": progress.get(t["team_id"], [])} for t in teams + lights]


def last_logged() -> str:
    r = http.post(f"{API}/v1/query", json={"sql": f"SELECT max(ts::String) AS ts FROM {TEAM}.scratch WHERE kind::String = 'leaderboard'"}, timeout=30)
    return (r.json()["data"][0]["ts"] or "") if r.ok else ""


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    seen = last_logged()
    print(f"last logged refresh: {seen or 'none'}", flush=True)
    while True:
        try:
            state = requests.get(STATE_URL, timeout=20).json()
            stamp = iso(state["updated_at"])
            if stamp > seen:
                (RAW / f"{stamp.replace(':', '').replace(' ', 'T')}.json").write_text(json.dumps(state), encoding="utf-8")
                batch = rows(state)
                http.post(f"{API}/v1/tables/scratch", params={"database": TEAM}, json=batch, timeout=30).raise_for_status()
                seen = stamp
                print(f"{stamp} logged {len(batch)} rows ({state['mode']})", flush=True)
        except Exception as e:  # keep logging
            print(f"error: {e}", flush=True)
        time.sleep(60)


if __name__ == "__main__":
    main()
