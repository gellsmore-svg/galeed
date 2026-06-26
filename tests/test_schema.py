"""Schema/compatibility discipline for the shared trace stream (review P1-002)."""

from galeed import (
    CORRELATION_KEYS,
    SCHEMA_VERSION,
    TraceEvent,
    correlation_ids,
)


def test_events_carry_schema_version() -> None:
    event = TraceEvent(trace_id="trace_1", session_id="s1", type="process.started")
    assert event.schema_version == SCHEMA_VERSION
    assert event.to_dict()["schema_version"] == SCHEMA_VERSION


def test_correlation_ids_from_fields_and_metadata() -> None:
    event = TraceEvent(
        trace_id="trace_1",
        session_id="s1",
        type="answer.finalized",
        request_id="req_9",
        metadata={"plan_id": "plan_7", "job_id": "job_3", "irrelevant": "x"},
    )
    ids = correlation_ids(event)
    # first-class fields + metadata-borne ids, nothing extraneous
    assert ids == {
        "request_id": "req_9",
        "session_id": "s1",
        "trace_id": "trace_1",
        "plan_id": "plan_7",
        "job_id": "job_3",
    }
    # works on plain dicts too, and omits absent keys
    assert correlation_ids({"trace_id": "t", "metadata": {}}) == {"trace_id": "t"}


def test_correlation_keys_are_the_documented_set() -> None:
    assert CORRELATION_KEYS == ("request_id", "session_id", "trace_id", "plan_id", "job_id")
