"""galeed serve — the trace/debugging API (galeed.web)."""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi", reason="web extra not installed")

from fastapi.testclient import TestClient  # noqa: E402

from galeed import record_llm_call
from galeed.web import create_app
from tests.test_llm_calls import FakeDb  # reuse the $gte-aware fake


@pytest.fixture()
def client():
    db = FakeDb()
    record_llm_call(db, trace_id="t1", session_id="s1", source="hoglah",
                    step_name="one", prompt="in one", output="out one",
                    completed_at="2026-07-04T10:00:00+00:00")
    record_llm_call(db, trace_id="t1", session_id="s1", source="hoglah",
                    step_name="two", prompt="in two", output="out two",
                    completed_at="2026-07-04T10:01:00+00:00")
    return TestClient(create_app(db=db))


def test_llm_calls_listing_and_filters(client) -> None:
    calls = client.get("/api/llm-calls?trace_id=t1").json()["calls"]
    assert [c["step_name"] for c in calls] == ["one", "two"]
    assert calls[0]["prompt"] == "in one"
    lean = client.get("/api/llm-calls?trace_id=t1&payloads=false").json()["calls"]
    assert "prompt" not in lean[0] and lean[0]["prompt_chars"] == 6


def test_llm_call_detail_and_404(client) -> None:
    call_id = client.get("/api/llm-calls").json()["calls"][0]["call_id"]
    assert client.get(f"/api/llm-calls/{call_id}").json()["call"]["output"] == "out one"
    assert client.get("/api/llm-calls/nope").status_code == 404


def test_spine_endpoints_match_family_shapes(client) -> None:
    sessions = client.get("/api/trace/sessions").json()
    assert sessions["ok"] and any(s["session_id"] == "s1" for s in sessions["sessions"])
    events = client.get("/api/trace/events?session_id=s1").json()
    assert events["ok"] and len(events["events"]) == 2  # the llm.call spine events
    assert client.get("/api/health").json()["ok"] is True
