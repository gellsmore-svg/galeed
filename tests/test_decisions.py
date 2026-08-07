"""Stage 0 decision / negotiation spine events."""

from galeed import EventType, record_decision, record_negotiation
from galeed.recorder import Tracer
from tests.test_llm_calls import FakeDb


def test_record_decision_on_tracer() -> None:
    db = FakeDb()
    tracer = Tracer(trace_id="t1", session_id="s1", db=db, source="deborah")
    out = record_decision(
        tracer=tracer,
        selected="open",
        rejected=["accept", "reject"],
        basis="no cited evidence",
        plan_id="plan_x",
        confidence="low",
    )
    assert out["selected"] == "open"
    assert tracer.events[-1].type == EventType.DECISION_RECORDED
    assert tracer.events[-1].metadata["plan_id"] == "plan_x"
    # persisted
    assert any(
        r.get("type") == EventType.DECISION_RECORDED for r in db["trace_events"].rows
    )


def test_record_negotiation_started_and_finished() -> None:
    db = FakeDb()
    tracer = Tracer(trace_id="t2", session_id="s2", db=db, source="deborah")
    record_negotiation(tracer=tracer, phase="started", plan_id="p", max_rounds=4)
    record_negotiation(
        tracer=tracer,
        phase="finished",
        status="agreed",
        rounds_used=1,
        max_rounds=4,
        plan_id="p",
    )
    types = [e.type for e in tracer.events]
    assert EventType.NEGOTIATION_STARTED in types
    assert EventType.NEGOTIATION_FINISHED in types
