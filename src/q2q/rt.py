"""RawTree client. The only HTTP code in the package.

    query("SELECT ... FROM {TEAM}.feedback")  -> list of dicts
    insert("scratch", [{"kind": "lease", ...}])
"""
import os
import threading
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
if (ROOT / ".env").exists():
    for line in (ROOT / ".env").read_text().splitlines():
        key, _, value = line.partition("=")
        if value and not key.startswith("#"):
            os.environ.setdefault(key.strip(), value.strip())
API = os.environ.get("RAWTREE_API_URL", "https://api.rawtree.com")
TEAM = os.environ["TEAM_ID"]
_local = threading.local()


def _http() -> requests.Session:
    """One keep-alive session per thread."""
    if not hasattr(_local, "http"):
        _local.http = requests.Session()
        _local.http.headers["Authorization"] = f"Bearer {os.environ['RAWTREE_API_KEY']}"
    return _local.http


def query(sql: str, timeout: float = 30) -> list[dict]:
    r = _http().post(f"{API}/v1/query", json={"sql": sql.replace("{TEAM}", TEAM)}, timeout=timeout)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:500]}")
    return r.json()["data"]


def insert(table: str, rows: list[dict], timeout: float = 10) -> None:
    """Insert rows into one of our tables: submissions or scratch."""
    r = _http().post(f"{API}/v1/tables/{table}", params={"database": TEAM}, json=rows, timeout=timeout)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:500]}")
