from __future__ import annotations

import pytest

from galeed import CAIRN_OBSERVATION_KINDS, Tracer, emit_cairn_observation


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


def test_observation_contract_is_stable_across_the_deborah_huldah_split():
    """`cairn_kind` and the kind vocabulary are a wire contract — do not rename.

    `huldah.galeed_adapter` classifies an event by reading
    `metadata.cairn_kind` and matching it against these exact kind strings.
    Renaming either side needs a lockstep release, and any mismatch drops
    observations silently rather than failing loudly — hence this guard.
    """
    assert CAIRN_OBSERVATION_KINDS == {
        "ui_event",
        "system_log",
        "agent_step",
        "agent_output",
        "agent_output_review",
        "queue_event",
        "feedback",
        "recovery_event",
    }

    tracer = Tracer(session_id="s", db=None)
    for kind in sorted(CAIRN_OBSERVATION_KINDS):
        event = emit_cairn_observation(tracer, kind=kind, message="probe")
        assert event.to_dict()["metadata"]["cairn_kind"] == kind
