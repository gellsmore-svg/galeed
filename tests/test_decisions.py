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


def test_record_open_question_event() -> None:
    from galeed import record_open_question_event

    db = FakeDb()
    tracer = Tracer(trace_id="t3", session_id="s3", db=db, source="deborah")
    record_open_question_event(
        tracer=tracer,
        open_question_id="oq_1",
        question="Is X true?",
        reason="no evidence",
        plan_id="p",
    )
    assert any(e.type == EventType.OPEN_QUESTION_RECORDED for e in tracer.events)


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


def test_record_negotiation_post_retrieve_note() -> None:
    tracer = Tracer(trace_id="t4", session_id="s4", db=None, source="deborah")
    record_negotiation(
        tracer=tracer,
        phase="finished",
        status="partial",
        note="post_retrieve",
        rounds_used=1,
        max_rounds=1,
        plan_id="p",
        metadata={"evidence_count": 0, "novel_detected": True},
    )
    ev = tracer.events[-1]
    assert ev.type == EventType.NEGOTIATION_FINISHED
    assert ev.metadata.get("note") == "post_retrieve"
    assert ev.metadata.get("negotiation_phase") == "post_retrieve"
    assert ev.metadata.get("evidence_count") == 0
    assert "post_retrieve" in ev.summary
