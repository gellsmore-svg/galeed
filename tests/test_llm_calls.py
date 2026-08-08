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


def test_usage_tokens_aliases_and_cost() -> None:
    db = FakeDb()
    doc = record_llm_call(
        db,
        trace_id="t",
        session_id="s",
        source="hoglah",
        model="gemma3:1b",
        prompt="hi",
        output="yo",
        usage={"tokens_in": 10, "tokens_out": 5},
    )
    # Canonical keys only inside usage (review M3); aliases on the document.
    assert doc["usage"]["prompt_tokens"] == 10
    assert doc["usage"]["completion_tokens"] == 5
    assert doc["usage"]["total"] == 15
    assert "tokens_in" not in doc["usage"]
    assert doc["tokens_in"] == 10
    assert doc["tokens_out"] == 5
    assert doc["cost"] == 0.0  # gemma3:1b is explicitly free-local
    stored = db[LLM_CALLS_COLLECTION].rows[0]
    assert stored["tokens_in"] == 10
    assert stored["cost"] == 0.0


def test_estimate_cost_usd_unknown_without_tokens() -> None:
    from galeed.llm_calls import estimate_cost_usd

    assert estimate_cost_usd(None) is None
    assert estimate_cost_usd({}) is None
    # model unset → default free-local rate
    assert estimate_cost_usd({"tokens_in": 1000, "tokens_out": 0}) == 0.0
    # unpriced named model → None, not $0.00 (review H1)
    assert estimate_cost_usd(
        {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000},
        model="claude-opus-5",
    ) is None
    # explicit free local
    assert estimate_cost_usd(
        {"prompt_tokens": 1000, "completion_tokens": 0},
        model="gemma4:e2b",
    ) == 0.0
    # injectable rates for a priced model
    cost = estimate_cost_usd(
        {"prompt_tokens": 1_000_000, "completion_tokens": 0},
        model="gpt-x",
        rates={"gpt-x": {"in": 1.0, "out": 2.0}},
    )
    assert cost == 1.0


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
    record_llm_call(db, trace_id="t", session_id="s", source="m", step_name="orphan",
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


def test_usage_is_a_first_class_field():
    """Token counts are the only cost signal the family has — they must be
    queryable without digging into metadata."""
    db = FakeDb()
    row = record_llm_call(
        db, trace_id="t", session_id="s", source="hoglah",
        model="gemma3:1b", prompt="hi", output="there",
        usage={"prompt_tokens": 7, "completion_tokens": 25, "total": 32},
        emit_event=False,
    )
    assert row["usage"]["prompt_tokens"] == 7
    assert row["usage"]["completion_tokens"] == 25
    assert row["usage"]["total"] == 32
    # Canonical usage only; aliases live top-level (review M3)
    assert "tokens_in" not in row["usage"]
    assert row["tokens_in"] == 7
    assert row["cost"] == 0.0


def test_legacy_metadata_usage_is_promoted():
    """Hoglah has always reported usage inside metadata; those producers must
    gain the queryable field without changing their own code."""
    db = FakeDb()
    row = record_llm_call(
        db, trace_id="t", session_id="s", source="hoglah",
        model="gemma3:1b",
        metadata={"kind": "generate", "usage": {"prompt_tokens": 2, "completion_tokens": 5, "total": 7}},
        emit_event=False,
    )
    assert row["usage"]["prompt_tokens"] == 2
    assert row["usage"]["completion_tokens"] == 5
    assert row["usage"]["total"] == 7
    assert row["tokens_in"] == 2
    # the original metadata is left intact, not moved
    assert row["metadata"]["usage"]["total"] == 7


def test_explicit_usage_wins_over_metadata():
    db = FakeDb()
    row = record_llm_call(
        db, trace_id="t", session_id="s", source="hoglah",
        usage={"prompt_tokens": 100, "completion_tokens": 200, "total": 300},
        metadata={"usage": {"prompt_tokens": 1, "completion_tokens": 1, "total": 2}},
        emit_event=False,
    )
    assert row["usage"]["total"] == 300


def test_total_is_derived_when_producer_omits_it():
    db = FakeDb()
    row = record_llm_call(
        db, trace_id="t", session_id="s", source="x",
        usage={"prompt_tokens": 10, "completion_tokens": 15},
        emit_event=False,
    )
    assert row["usage"]["total"] == 25


def test_usage_key_always_exists_so_aggregates_can_rely_on_it():
    db = FakeDb()
    row = record_llm_call(db, trace_id="t", session_id="s", source="x", emit_event=False)
    assert row["usage"] == {}


def test_instrumentation_coverage_per_source() -> None:
    """Review H3: per-source usage/duration rates over llm_calls."""
    from galeed.llm_calls import llm_instrumentation_coverage

    db = FakeDb()
    record_llm_call(
        db, trace_id="t", session_id="s", source="hoglah",
        usage={"prompt_tokens": 10, "completion_tokens": 5},
        duration_ms=40, emit_event=False,
    )
    record_llm_call(
        db, trace_id="t", session_id="s", source="hoglah",
        usage={}, emit_event=False,
    )
    record_llm_call(
        db, trace_id="t", session_id="s", source="tirzah",
        emit_event=False,
    )
    cov = {r["source"]: r for r in llm_instrumentation_coverage(db)}
    assert cov["hoglah"]["calls"] == 2
    assert cov["hoglah"]["with_usage"] == 1
    assert cov["hoglah"]["with_duration"] == 1
    assert cov["hoglah"]["usage_rate"] == 0.5
    assert cov["tirzah"]["calls"] == 1
    assert cov["tirzah"]["with_usage"] == 0
    assert cov["tirzah"]["usage_rate"] == 0.0
