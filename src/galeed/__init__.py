"""Galeed — the cross-project trace/log spine ("heap of witness", Gen 31:48).

The shared logging capability for the family: a structured event stream that
separates *process telemetry* (structured events) from the *final answer*. Callers
emit events through :class:`~galeed.recorder.Tracer`; an in-process bus streams them
live (to a process panel / dev-log window) and a recorder persists them for later
query. Any family project (Tirzah, Mahalath, Hoglah, Cairn, Milcah) can emit into
it; Mizpah (the watchtower) is the viewer over what Galeed records.

Self-contained (no app-specific imports) so it can be a dependency of any project.
"""

from galeed.bus import TraceBus, get_bus
from galeed.events import (
    CORRELATION_KEYS,
    KNOWN_EVENT_TYPES,
    SCHEMA_VERSION,
    EventType,
    TraceEvent,
    correlation_ids,
    new_event_id,
    new_message_id,
    new_request_id,
    new_trace_id,
)
from galeed.feedback import (
    FEEDBACK_COLLECTION,
    list_feedback,
    record_feedback,
)
from galeed.recorder import (
    TRACE_EVENTS_COLLECTION,
    Tracer,
    list_trace_events,
    list_trace_sessions,
    record_event,
)

__all__ = [
    "EventType",
    "KNOWN_EVENT_TYPES",
    "SCHEMA_VERSION",
    "CORRELATION_KEYS",
    "correlation_ids",
    "TraceEvent",
    "TraceBus",
    "Tracer",
    "TRACE_EVENTS_COLLECTION",
    "FEEDBACK_COLLECTION",
    "get_bus",
    "list_trace_events",
    "list_trace_sessions",
    "record_event",
    "record_feedback",
    "list_feedback",
    "new_event_id",
    "new_message_id",
    "new_request_id",
    "new_trace_id",
]
