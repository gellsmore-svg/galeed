"""Tests for Galeed hook bridges (codex etc.)."""

from __future__ import annotations

import json
import os
from io import StringIO

import pytest

from galeed.hooks import _load_payload, codex_hook


def test_load_payload_reads_stdin(monkeypatch):
    payload = {"hook_event_name": "SessionStart", "session_id": "s1"}
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(payload)))
    got = _load_payload()
    assert got == payload


def test_codex_hook_emits_events(monkeypatch, tmp_path):
    # Force a db that will be None (no real mongo) but still exercise emit path
    monkeypatch.setenv("GALEED_MONGO_URI", "mongodb://localhost:1/nonexistent")
    monkeypatch.setenv("GALEED_MONGO_DB", "test")

    # Capture what would be recorded (we monkey the record path lightly)
    recorded = []

    def fake_record(db, event):
        recorded.append(event.to_dict())

    monkeypatch.setattr("galeed.hooks.record_event", fake_record)

    payload = {
        "hook_event_name": "PostToolUse",
        "session_id": "codex-sess-123",
        "tool_name": "edit_file",
        "tool": {"name": "edit_file", "input": {"path": "foo.py"}},
    }
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(payload)))

    # Call via the function (not sys.argv)
    exit_code = codex_hook(["galeed-codex-hook", "PostToolUse"])

    assert exit_code == 0
    assert len(recorded) >= 1
    ev = recorded[0]
    assert ev["source"] == "codex"
    assert "codex.posttooluse" in ev["type"] or "codex.post_tool_use" in ev["type"]
    assert ev["session_id"] == "codex-sess-123"
    assert "tool_name" in ev["metadata"] or any("tool" in str(v) for v in ev["metadata"].values())


def test_codex_hook_graceful_no_payload(monkeypatch):
    monkeypatch.setattr("sys.stdin", StringIO(""))
    # Should not crash
    code = codex_hook(["galeed-codex-hook", "Stop"])
    assert code == 0
