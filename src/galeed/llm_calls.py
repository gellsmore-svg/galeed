"""Full-fidelity LLM call capture — the debugging half of the spine.

One document per LLM call in the ``llm_calls`` collection: the COMPLETE input
(prompt string or full messages list) and COMPLETE output text, plus the
correlation ids that stitch it into the trace spine (``trace_id`` /
``session_id`` / ``source``), an optional human-readable ``step_name``
("initial_research", "refine_output", …), and ``parent_call_id`` so recursive
or chained flows form a tree.

The paired spine event (``llm.call.completed`` / ``llm.call.failed``) carries
only a one-line summary plus ``call_id``, so session/trace listings stay light
and the payloads are one indexed hop away. Viewers (``galeed trace``, ``galeed
serve`` → Mizpah) read this collection for the clean In → Out view; everything
else (model, params, timings) is metadata they reveal only on request.

Emitters:
- Hoglah records a call automatically for every job it executes.
- Any other tool wraps a direct call with :func:`capture_llm_call`, or records
  after the fact with :func:`record_llm_call`.

All persistence is best-effort: recording must never raise into the caller.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import uuid4

from galeed.events import EventType
from galeed.recorder import Tracer

LLM_CALLS_COLLECTION = "llm_calls"


def new_call_id() -> str:
    return f"call_{uuid4().hex}"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_llm_call(
    db: Any,
    *,
    trace_id: str,
    session_id: str,
    source: str,
    call_id: str | None = None,
    step_name: str | None = None,
    parent_call_id: str | None = None,
    model: str | None = None,
    prompt: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    output: str | None = None,
    error: str | None = None,
    started_at: str | None = None,
    completed_at: str | None = None,
    duration_ms: int | None = None,
    metadata: dict[str, Any] | None = None,
    emit_event: bool = True,
    tracer: Any = None,
) -> dict[str, Any]:
    """Persist one finished LLM call (full I/O) and mirror a light spine event.

    Pass the request's live ``tracer`` when you have one: the spine event then
    carries a real sequence number and shares the request's message/request ids
    (a fresh per-call Tracer always emits seq=1). Returns the stored document
    (with its ``call_id``) even when persistence fails — callers can keep
    flowing regardless.
    """
    doc: dict[str, Any] = {
        "call_id": call_id or new_call_id(),
        "trace_id": trace_id,
        "session_id": session_id,
        "source": source,
        "step_name": step_name,
        "parent_call_id": parent_call_id,
        "model": model,
        "prompt": prompt,
        "messages": messages,
        "output": output,
        "error": error,
        "status": "failed" if error else "completed",
        "started_at": started_at,
        "completed_at": completed_at or _utcnow_iso(),
        "duration_ms": duration_ms,
        "metadata": dict(metadata or {}),
    }
    if db is not None:
        try:
            db[LLM_CALLS_COLLECTION].insert_one({**doc})
        except Exception:
            pass
    if emit_event:
        try:
            if tracer is None:
                tracer = Tracer(
                    trace_id=trace_id, session_id=session_id, db=db, source=source
                )
            label = step_name or (model or "llm call")
            if error:
                tracer.emit(
                    EventType.LLM_CALL_FAILED,
                    status="failed",
                    severity="error",
                    summary=f"{label} failed: {error[:120]}",
                    call_id=doc["call_id"],
                    step_name=step_name,
                    model=model,
                )
            else:
                tracer.emit(
                    EventType.LLM_CALL_COMPLETED,
                    status="completed",
                    summary=f"{label} → {len(output or '')} chars",
                    call_id=doc["call_id"],
                    step_name=step_name,
                    model=model,
                )
        except Exception:
            pass
    return doc


class CallCapture:
    """Mutable box handed to `capture_llm_call` blocks: set ``output`` (and
    optionally ``model``/``metadata``) before the block exits."""

    def __init__(self) -> None:
        self.output: str | None = None
        self.model: str | None = None
        self.metadata: dict[str, Any] = {}
        self.call_id: str = new_call_id()


@contextmanager
def capture_llm_call(
    db: Any,
    *,
    trace_id: str,
    session_id: str,
    source: str,
    step_name: str | None = None,
    parent_call_id: str | None = None,
    model: str | None = None,
    prompt: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    tracer: Any = None,
) -> Iterator[CallCapture]:
    """Wrap a direct LLM call so its full I/O lands in ``llm_calls``.

        with capture_llm_call(db, trace_id=t, session_id=s, source="mahalath",
                              step_name="debate_critic", prompt=p) as call:
            call.output = adapter.generate(p)

    An exception inside the block records the call as failed and re-raises.
    """
    box = CallCapture()
    started_at = _utcnow_iso()
    clock = time.monotonic()
    try:
        yield box
    except Exception as exc:
        record_llm_call(
            db,
            trace_id=trace_id,
            session_id=session_id,
            source=source,
            call_id=box.call_id,
            step_name=step_name,
            parent_call_id=parent_call_id,
            model=box.model or model,
            prompt=prompt,
            messages=messages,
            error=str(exc),
            started_at=started_at,
            duration_ms=int((time.monotonic() - clock) * 1000),
            metadata=box.metadata,
            tracer=tracer,
        )
        raise
    record_llm_call(
        db,
        trace_id=trace_id,
        session_id=session_id,
        source=source,
        call_id=box.call_id,
        step_name=step_name,
        parent_call_id=parent_call_id,
        model=box.model or model,
        prompt=prompt,
        messages=messages,
        output=box.output,
        started_at=started_at,
        duration_ms=int((time.monotonic() - clock) * 1000),
        metadata=box.metadata,
        tracer=tracer,
    )


def list_llm_calls(
    db: Any,
    *,
    trace_id: str | None = None,
    session_id: str | None = None,
    source: str | None = None,
    step_name: str | None = None,
    status: str | None = None,
    call_id: str | None = None,
    since: str | None = None,
    limit: int = 200,
    include_payloads: bool = True,
) -> list[dict[str, Any]]:
    """Query captured calls, oldest → newest (natural reading order for a flow).

    ``since`` is an ISO timestamp lower bound on ``completed_at``. With
    ``include_payloads=False`` the prompt/messages/output fields are replaced
    by their character sizes (for lean list views)."""
    if db is None:
        return []
    query: dict[str, Any] = {}
    if trace_id:
        query["trace_id"] = trace_id
    if session_id:
        query["session_id"] = session_id
    if source:
        query["source"] = source
    if step_name:
        query["step_name"] = step_name
    if status:
        query["status"] = status
    if call_id:
        query["call_id"] = call_id
    if since:
        query["completed_at"] = {"$gte": since}
    try:
        cursor = db[LLM_CALLS_COLLECTION].find(query, {"_id": 0})
        try:
            # Mongo-side: newest N, then re-reverse to reading order — avoids
            # loading the full collection. Fakes without sort() fall back below.
            rows = list(cursor.sort("completed_at", -1).limit(int(limit or 0) or 500))
            rows.reverse()
            return [(_strip_payloads(r) if not include_payloads else r) for r in rows]
        except (AttributeError, TypeError):
            rows = list(cursor)
    except Exception:
        return []
    rows.sort(key=lambda row: row.get("completed_at") or "")
    if limit and len(rows) > limit:
        rows = rows[-limit:]
    if not include_payloads:
        rows = [_strip_payloads(row) for row in rows]
    return rows


def get_llm_call(db: Any, call_id: str) -> dict[str, Any] | None:
    if db is None:
        return None
    try:
        return db[LLM_CALLS_COLLECTION].find_one({"call_id": call_id}, {"_id": 0})
    except Exception:
        return None


def call_tree(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Arrange a flat call list into a parent/child forest (chained flows).

    Each returned root gains a ``children`` list (recursively). Calls whose
    ``parent_call_id`` is absent from the batch are treated as roots, so a
    filtered view still renders sensibly."""
    by_id = {call["call_id"]: {**call, "children": []} for call in calls}
    roots: list[dict[str, Any]] = []
    for call in by_id.values():
        parent = by_id.get(call.get("parent_call_id") or "")
        if parent is not None and parent is not call:
            parent["children"].append(call)
        else:
            roots.append(call)
    return roots


def _strip_payloads(row: dict[str, Any]) -> dict[str, Any]:
    lean = dict(row)
    for field in ("prompt", "output"):
        value = lean.pop(field, None)
        lean[f"{field}_chars"] = len(value) if isinstance(value, str) else 0
    messages = lean.pop("messages", None)
    lean["message_count"] = len(messages) if isinstance(messages, list) else 0
    return lean
