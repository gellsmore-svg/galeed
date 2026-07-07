from __future__ import annotations

import pytest

from galeed import Tracer, emit_cairn_observation


def test_emit_cairn_observation_writes_cairn_metadata():
    tracer = Tracer(trace_id="trace_1", session_id="sess_1", request_id="req_1", db=None, source="tirzah")

    event = emit_cairn_observation(
        tracer,
        kind="agent_output",
        message="Generated recommendation without authority citation.",
        tags=["missing_evidence", "missing_evidence"],
        human_systems=["trust calibration", "uncertainty management"],
        duration_ms=4200,
    )
    data = event.to_dict()

    assert data["type"] == "llm.call.completed"
    assert data["summary"] == "Generated recommendation without authority citation."
    assert data["metadata"]["cairn_kind"] == "agent_output"
    assert data["metadata"]["tags"] == ["missing_evidence"]
    assert data["metadata"]["missing_evidence"] is True
    assert data["metadata"]["duration_ms"] == 4200
    assert data["trace_id"] == "trace_1"
    assert data["request_id"] == "req_1"


def test_emit_cairn_observation_rejects_unknown_kind():
    tracer = Tracer(session_id="sess_1", db=None)

    with pytest.raises(ValueError, match="Unsupported Cairn observation kind"):
        emit_cairn_observation(tracer, kind="person_score", message="nope")
