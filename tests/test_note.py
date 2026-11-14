import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("note", Path(__file__).parents[1] / "scripts" / "note.py")
note = importlib.util.module_from_spec(spec)
spec.loader.exec_module(note)


def test_add_appends_one_line(tmp_path, monkeypatch):
    monkeypatch.setattr(note, "FILE", tmp_path / "updates.jsonl")
    note.add("building", "first", "text one")
    note.add("champion", "second", "text, two", strategy="rules5")
    lines = (tmp_path / "updates.jsonl").read_bytes().decode("utf-8").split("\n")
    assert lines[-1] == "" and len(lines) == 3
    item = json.loads(lines[1])
    assert item["kind"] == "champion" and item["strategy"] == "rules5" and item["ts"].endswith("Z")


def test_unknown_kind(tmp_path, monkeypatch):
    monkeypatch.setattr(note, "FILE", tmp_path / "updates.jsonl")
    with pytest.raises(ValueError):
        note.add("news", "t", "x")
