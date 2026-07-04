"""Full-fidelity LLM call capture (galeed.llm_calls) — the debugging spine."""

from __future__ import annotations

import pytest

from galeed import (
    LLM_CALLS_COLLECTION,
    call_tree,
    capture_llm_call,
    get_llm_call,
    list_llm_calls,
    record_llm_call,
)


class FakeCollection:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def insert_one(self, row):
        self.rows.append(dict(row))

    def _matches(self, row, query):
        for key, cond in (query or {}).items():
            if isinstance(cond, dict) and "$gte" in cond:
                if not (row.get(key) or "") >= cond["$gte"]:
                    return False
            elif row.get(key) != cond:
                return False
        return True

    def find(self, query=None, projection=None):
        return [
            {k: v for k, v in row.items() if k != "_id"}
            for row in self.rows
            if self._matches(row, query)
        ]

    def find_one(self, query=None, projection=None):
        rows = self.find(query, projection)
        return rows[0] if rows else None


class FakeDb:
    def __init__(self) -> None:
        self._collections: dict[str, FakeCollection] = {}

    def __getitem__(self, name):
        return self._collections.setdefault(name, FakeCollection())


def test_record_persists_full_io_and_mirrors_light_spine_event() -> None:
    db = FakeDb()
    doc = record_llm_call(
        db,
        trace_id="job-1",
        session_id="sess-1",
        source="hoglah",
        step_name="initial_research",
        model="gemma3:1b",
        prompt="What is a vorton?",
        output="A vorton is…",
    )
    stored = db[LLM_CALLS_COLLECTION].rows[0]
    assert stored["prompt"] == "What is a vorton?"
    assert stored["output"] == "A vorton is…"
    assert stored["status"] == "completed"
    assert stored["call_id"] == doc["call_id"]

    events = db["trace_events"].rows
    assert len(events) == 1
    assert events[0]["type"] == "llm.call.completed"
    assert events[0]["metadata"]["call_id"] == doc["call_id"]
    # The spine event stays light: no payloads ride along.
    assert "prompt" not in events[0]["metadata"]
    assert "output" not in events[0]["metadata"]


def test_record_failed_call_emits_failed_event() -> None:
    db = FakeDb()
    record_llm_call(
        db,
        trace_id="t",
        session_id="s",
        source="mahalath",
        error="connection refused",
    )
    assert db[LLM_CALLS_COLLECTION].rows[0]["status"] == "failed"
    assert db["trace_events"].rows[0]["type"] == "llm.call.failed"


def test_capture_context_manager_success_and_failure() -> None:
    db = FakeDb()
    with capture_llm_call(
        db, trace_id="t", session_id="s", source="tirzah", step_name="answer", prompt="hi"
    ) as call:
        call.output = "hello"
        call.model = "gemma3:1b"

    row = db[LLM_CALLS_COLLECTION].rows[0]
    assert row["output"] == "hello"
    assert row["model"] == "gemma3:1b"
    assert row["duration_ms"] is not None

    with pytest.raises(RuntimeError):
        with capture_llm_call(db, trace_id="t", session_id="s", source="tirzah") as call:
            raise RuntimeError("model exploded")
    failed = db[LLM_CALLS_COLLECTION].rows[1]
    assert failed["status"] == "failed"
    assert "model exploded" in failed["error"]


def test_list_filters_order_and_lean_mode() -> None:
    db = FakeDb()
    for i, step in enumerate(["one", "two", "three"]):
        record_llm_call(
            db,
            trace_id="t1" if step != "three" else "t2",
            session_id="s",
            source="hoglah",
            step_name=step,
            prompt=f"p{i}",
            output="x" * (i + 1),
            completed_at=f"2026-07-04T10:0{i}:00+00:00",
        )
    t1 = list_llm_calls(db, trace_id="t1")
    assert [c["step_name"] for c in t1] == ["one", "two"]  # oldest → newest
    since = list_llm_calls(db, since="2026-07-04T10:01:00+00:00")
    assert [c["step_name"] for c in since] == ["two", "three"]
    lean = list_llm_calls(db, trace_id="t1", include_payloads=False)
    assert "prompt" not in lean[0] and lean[1]["output_chars"] == 2


def test_get_and_tree() -> None:
    db = FakeDb()
    root = record_llm_call(db, trace_id="t", session_id="s", source="m", step_name="root",
                           completed_at="2026-07-04T10:00:00+00:00")
    child = record_llm_call(db, trace_id="t", session_id="s", source="m", step_name="child",
                            parent_call_id=root["call_id"],
                            completed_at="2026-07-04T10:01:00+00:00")
    orphan = record_llm_call(db, trace_id="t", session_id="s", source="m", step_name="orphan",
                             parent_call_id="call_not_in_batch",
                             completed_at="2026-07-04T10:02:00+00:00")

    assert get_llm_call(db, child["call_id"])["step_name"] == "child"

    forest = call_tree(list_llm_calls(db, trace_id="t"))
    roots = {c["step_name"] for c in forest}
    assert roots == {"root", "orphan"}  # orphaned parent → treated as root
    root_node = next(c for c in forest if c["step_name"] == "root")
    assert [c["step_name"] for c in root_node["children"]] == ["child"]


def test_broken_db_never_raises() -> None:
    class BrokenDb:
        def __getitem__(self, name):
            raise RuntimeError("db down")

    doc = record_llm_call(BrokenDb(), trace_id="t", session_id="s", source="x", output="y")
    assert doc["call_id"]  # caller still gets the document back
    assert list_llm_calls(BrokenDb()) == []
    assert get_llm_call(BrokenDb(), "nope") is None
