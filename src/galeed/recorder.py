"""Per-request tracer plus event persistence/query.

``Tracer`` is created once per request (anchored on the existing process-run
``run_id`` as the ``trace_id``). Each ``emit`` builds a structured
:class:`~galeed.events.TraceEvent`, appends it to an in-memory list (so the
request can return ``processEvents`` directly), persists it best-effort to the
``trace_events`` collection, and publishes it to the live bus. Emitting must
never raise into the request path.
"""

from __future__ import annotations

import logging
from typing import Any

from galeed.bus import TraceBus, get_bus
from galeed.events import (
    INFO,
    TraceEvent,
    new_message_id,
    new_request_id,
    new_trace_id,
)

TRACE_EVENTS_COLLECTION = "trace_events"

logger = logging.getLogger("galeed")


def ensure_indexes(db: Any) -> bool:
    """Best-effort create the ``trace_events`` indexes the queries here rely on.

    Idempotent and safe to call on every startup; returns ``False`` (never
    raises) when the store is absent or has no ``create_index`` — tracing must
    keep working against fakes and unindexed stores.
    """
    if db is None:
        return False
    try:
        collection = db[TRACE_EVENTS_COLLECTION]
        # session summaries: $match/$group on session_id, ordered by timestamp
        collection.create_index([("session_id", 1), ("timestamp", 1)], name="session_timeline")
        # event replay for one trace, newest-first
        collection.create_index(
            [("trace_id", 1), ("timestamp", -1), ("seq", -1)], name="trace_timeline"
        )
    except Exception:
        logger.debug("trace index creation failed (ignored)", exc_info=True)
        return False
    return True


def record_event(db: Any, event: TraceEvent) -> None:
    """Best-effort persist of one event to ``trace_events`` (never raises)."""
    if db is None:
        return
    try:
        db[TRACE_EVENTS_COLLECTION].insert_one(event.to_dict())
    except Exception:
        logger.debug("trace event persistence failed (ignored)", exc_info=True)


def list_trace_events(
    db: Any,
    *,
    trace_id: str | None = None,
    session_id: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Replay events for a trace or session (for the dev-log window initial load).

    ``limit=0`` means "unspecified", not "unbounded": it falls back to the same
    500-row cap as :func:`galeed.llm_calls.list_llm_calls`, so no caller can
    accidentally pull the whole collection."""
    if db is None:
        return []
    query: dict[str, Any] = {}
    if trace_id:
        query["trace_id"] = trace_id
    if session_id:
        query["session_id"] = session_id
    try:
        cursor = db[TRACE_EVENTS_COLLECTION].find(query, {"_id": 0})
        try:
            # Mongo-side newest-N (re-reversed to reading order) so the full
            # collection never loads; fakes without sort() fall back below.
            rows = list(cursor.sort([("timestamp", -1), ("seq", -1)]).limit(int(limit or 0) or 500))
            rows.reverse()
            return rows
        except (AttributeError, TypeError):
            rows = list(cursor)
    except Exception:
        return []
    rows.sort(key=lambda row: (row.get("timestamp") or "", row.get("seq") or 0))
    if limit and len(rows) > limit:
        rows = rows[-limit:]
    return rows


def _sessions_pipeline(limit: int) -> list[dict[str, Any]]:
    """Mongo ``$group`` pipeline behind :func:`list_trace_sessions`.

    ``first_query``/``last_answer`` ride along as ``[timestamp, value]`` pairs so
    a plain ``$min``/``$max`` picks the earliest/latest one — both accumulators
    ignore the ``None`` emitted for non-matching events, so no per-event arrays
    are accumulated.
    """
    return [
        {"$match": {"session_id": {"$nin": [None, ""]}}},
        {
            "$group": {
                "_id": "$session_id",
                "event_count": {"$sum": 1},
                "sources": {"$addToSet": "$source"},
                "traces": {"$addToSet": "$trace_id"},
                "started_at": {"$min": "$timestamp"},
                "updated_at": {"$max": "$timestamp"},
                "first_query": {
                    "$min": {
                        "$cond": [
                            {"$eq": ["$type", "message.user.submitted"]},
                            [
                                {"$ifNull": ["$timestamp", ""]},
                                {"$ifNull": ["$metadata.query", None]},
                            ],
                            None,
                        ]
                    }
                },
                "last_answer": {
                    "$max": {
                        "$cond": [
                            {"$eq": ["$type", "answer.finalized"]},
                            [
                                {"$ifNull": ["$timestamp", ""]},
                                {"$ifNull": ["$metadata.answer", None]},
                            ],
                            None,
                        ]
                    }
                },
            }
        },
        {"$sort": {"updated_at": -1}},
        {"$limit": int(limit or 0) or 200},
    ]


def _session_row_from_group(group: dict[str, Any]) -> dict[str, Any]:
    """Shape one ``$group`` output document like the Python-path summary rows."""
    first_query = group.get("first_query") or []
    last_answer = group.get("last_answer") or []
    answer = last_answer[1] if len(last_answer) > 1 else None
    return {
        "session_id": group.get("_id"),
        "event_count": group.get("event_count") or 0,
        "sources": sorted(s for s in (group.get("sources") or []) if s),
        "trace_count": len([t for t in (group.get("traces") or []) if t]),
        "started_at": group.get("started_at"),
        "updated_at": group.get("updated_at"),
        "first_query": first_query[1] if len(first_query) > 1 else None,
        "last_answer_preview": answer[:160] if isinstance(answer, str) else None,
    }


def list_trace_sessions(db: Any, *, limit: int = 200) -> list[dict[str, Any]]:
    """Summarise distinct sessions in the trace store (for the log browser).

    One row per ``session_id`` with its sources, event/request counts, time span,
    the first user query, and a preview of the last answer. Grouped Mongo-side so
    the full collection never loads; the in-memory test fakes have no
    ``aggregate``, so they fall through to the equivalent Python aggregation.
    """
    if db is None:
        return []
    try:
        groups = list(db[TRACE_EVENTS_COLLECTION].aggregate(_sessions_pipeline(limit)))
    except (AttributeError, TypeError):
        pass  # fake/limited collection — aggregate in Python below
    except Exception:
        return []
    else:
        return [_session_row_from_group(group) for group in groups]
    try:
        rows = list(db[TRACE_EVENTS_COLLECTION].find({}, {"_id": 0}))
    except Exception:
        return []
    sessions: dict[str, dict[str, Any]] = {}
    for event in rows:
        session_id = event.get("session_id")
        if not session_id:
            continue
        summary = sessions.setdefault(
            session_id,
            {
                "session_id": session_id,
                "event_count": 0,
                "_sources": set(),
                "_traces": set(),
                "started_at": None,
                "updated_at": None,
                "first_query": None,
                "last_answer_preview": None,
            },
        )
        summary["event_count"] += 1
        if event.get("source"):
            summary["_sources"].add(event["source"])
        if event.get("trace_id"):
            summary["_traces"].add(event["trace_id"])
        timestamp = event.get("timestamp")
        if timestamp:
            if summary["started_at"] is None or timestamp < summary["started_at"]:
                summary["started_at"] = timestamp
            if summary["updated_at"] is None or timestamp > summary["updated_at"]:
                summary["updated_at"] = timestamp
        metadata = event.get("metadata") or {}
        if event.get("type") == "message.user.submitted" and summary["first_query"] is None:
            summary["first_query"] = metadata.get("query")
        if event.get("type") == "answer.finalized":
            answer = metadata.get("answer")
            if isinstance(answer, str):
                summary["last_answer_preview"] = answer[:160]
    result = []
    for summary in sessions.values():
        result.append(
            {
                "session_id": summary["session_id"],
                "event_count": summary["event_count"],
                "sources": sorted(summary["_sources"]),
                "trace_count": len(summary["_traces"]),
                "started_at": summary["started_at"],
                "updated_at": summary["updated_at"],
                "first_query": summary["first_query"],
                "last_answer_preview": summary["last_answer_preview"],
            }
        )
    result.sort(key=lambda row: row.get("updated_at") or "", reverse=True)
    return result[: int(limit or 0) or 200]


class Tracer:
    """Emits structured trace events for a single request lifecycle."""

    def __init__(
        self,
        *,
        trace_id: str | None = None,
        session_id: str,
        db: Any = None,
        bus: TraceBus | None = None,
        source: str = "tirzah",
        message_id: str | None = None,
        request_id: str | None = None,
        persist: bool = True,
    ) -> None:
        self.trace_id = trace_id or new_trace_id()
        self.session_id = session_id
        self.source = source
        self.message_id = message_id
        self.request_id = request_id or new_request_id()
        self._db = db
        self._bus = bus if bus is not None else get_bus()
        self._persist = persist
        self._seq = 0
        self.events: list[TraceEvent] = []

    def emit(
        self,
        type: str,
        *,
        status: str = "ok",
        summary: str = "",
        severity: str = INFO,
        message_id: str | None = None,
        **metadata: Any,
    ) -> TraceEvent:
        self._seq += 1
        event = TraceEvent(
            trace_id=self.trace_id,
            session_id=self.session_id,
            type=type,
            status=status,
            summary=summary,
            severity=severity,
            source=self.source,
            message_id=message_id or self.message_id,
            request_id=self.request_id,
            seq=self._seq,
            metadata=dict(metadata),
        )
        self.events.append(event)
        if self._persist:
            record_event(self._db, event)
        if self._bus is not None:
            try:
                self._bus.publish(event)
            except Exception:
                logger.debug("trace bus publish failed (ignored)", exc_info=True)
        return event

    # Convenience wrappers for the common status triplet.
    def started(self, type: str, summary: str = "", **metadata: Any) -> TraceEvent:
        return self.emit(type, status="started", summary=summary, **metadata)

    def completed(self, type: str, summary: str = "", **metadata: Any) -> TraceEvent:
        return self.emit(type, status="completed", summary=summary, **metadata)

    def failed(self, type: str, summary: str = "", **metadata: Any) -> TraceEvent:
        return self.emit(type, status="failed", severity="error", summary=summary, **metadata)

    def new_message_id(self) -> str:
        self.message_id = new_message_id()
        return self.message_id

    def as_dicts(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.events]
