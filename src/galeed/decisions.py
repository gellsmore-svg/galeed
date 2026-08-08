"""Decision and negotiation spine events (Stage 0).

Record *why* a framed run chose accept / reject / open, and the bounded
negotiation that preceded execution. These are first-class Galeed events —
not buried only inside plan step metadata — so Mizpah and ``galeed trace``
can filter them.
"""

from __future__ import annotations

from typing import Any

from galeed.events import EventType
from galeed.recorder import Tracer, record_event
from galeed.events import TraceEvent


def record_decision(
    db: Any = None,
    *,
    tracer: Any = None,
    trace_id: str | None = None,
    session_id: str | None = None,
    source: str = "deborah",
    selected: str,
    rejected: list[str] | None = None,
    basis: str | None = None,
    plan_id: str | None = None,
    confidence: str | None = None,
    open_question_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Emit ``decision.recorded`` on the spine. Best-effort; never raises."""
    meta = {
        "selected": selected,
        "rejected": list(rejected or []),
        "basis": basis,
        "plan_id": plan_id,
        "confidence": confidence,
        "open_question_id": open_question_id,
        **(metadata or {}),
    }
    summary = f"decision → {selected}"
    if basis:
        summary = f"{summary}: {basis[:80]}"
    try:
        if tracer is not None:
            tracer.emit(
                EventType.DECISION_RECORDED,
                summary=summary,
                status="ok",
                **{k: v for k, v in meta.items() if v is not None},
            )
        elif db is not None and (trace_id or session_id):
            t = Tracer(
                trace_id=trace_id or "decision",
                session_id=session_id or "session",
                db=db,
                source=source,
            )
            t.emit(
                EventType.DECISION_RECORDED,
                summary=summary,
                status="ok",
                **{k: v for k, v in meta.items() if v is not None},
            )
        elif db is not None:
            record_event(
                db,
                TraceEvent(
                    type=EventType.DECISION_RECORDED,
                    summary=summary,
                    source=source,
                    trace_id=trace_id or "decision",
                    session_id=session_id or "session",
                    metadata={k: v for k, v in meta.items() if v is not None},
                ),
            )
    except Exception:
        pass
    return {"type": EventType.DECISION_RECORDED, "summary": summary, **meta}


def record_negotiation(
    db: Any = None,
    *,
    tracer: Any = None,
    trace_id: str | None = None,
    session_id: str | None = None,
    source: str = "deborah",
    phase: str = "finished",  # started | finished
    status: str | None = None,
    rounds_used: int | None = None,
    max_rounds: int | None = None,
    plan_id: str | None = None,
    reason: str | None = None,
    note: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Emit negotiation.started / negotiation.finished. Best-effort.

    ``note`` is a short phase label (e.g. ``post_retrieve``) stored in metadata
    so viewers (Mizpah) can distinguish pre-plan vs mid-slice gates.
    """
    etype = (
        EventType.NEGOTIATION_STARTED
        if phase == "started"
        else EventType.NEGOTIATION_FINISHED
    )
    # Use negotiation_status in metadata — `status` is reserved for TraceEvent.status.
    meta = {
        "negotiation_status": status,
        "rounds_used": rounds_used,
        "max_rounds": max_rounds,
        "plan_id": plan_id,
        "reason": reason,
        "note": note,
        "negotiation_phase": note,  # alias for UI filters
        **(metadata or {}),
    }
    label = note or "negotiation"
    summary = f"{label} {phase}" if note else f"negotiation {phase}"
    if status:
        summary = f"{summary} → {status}"
    event_status = "ok" if status in {None, "agreed", "partial"} else "error"
    payload = {k: v for k, v in meta.items() if v is not None}
    try:
        if tracer is not None:
            tracer.emit(etype, summary=summary, status=event_status, **payload)
        elif db is not None:
            t = Tracer(
                trace_id=trace_id or "negotiation",
                session_id=session_id or "session",
                db=db,
                source=source,
            )
            t.emit(etype, summary=summary, status=event_status, **payload)
    except Exception:
        pass
    return {"type": etype, "summary": summary, **meta}


def record_open_question_event(
    db: Any = None,
    *,
    tracer: Any = None,
    trace_id: str | None = None,
    session_id: str | None = None,
    source: str = "deborah",
    open_question_id: str,
    question: str,
    reason: str | None = None,
    plan_id: str | None = None,
    run_terminal: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Emit ``open_question.recorded`` on the spine. Best-effort; never raises."""
    meta = {
        "open_question_id": open_question_id,
        "question": question,
        "reason": reason,
        "plan_id": plan_id,
        "run_terminal": run_terminal,
        **(metadata or {}),
    }
    summary = f"open_question {open_question_id}"
    if reason:
        summary = f"{summary}: {str(reason)[:80]}"
    payload = {k: v for k, v in meta.items() if v is not None}
    try:
        if tracer is not None:
            tracer.emit(
                EventType.OPEN_QUESTION_RECORDED,
                summary=summary,
                status="ok",
                **payload,
            )
        elif db is not None:
            t = Tracer(
                trace_id=trace_id or "open-question",
                session_id=session_id or "session",
                db=db,
                source=source,
            )
            t.emit(
                EventType.OPEN_QUESTION_RECORDED,
                summary=summary,
                status="ok",
                **payload,
            )
    except Exception:
        pass
    return {"type": EventType.OPEN_QUESTION_RECORDED, "summary": summary, **meta}
