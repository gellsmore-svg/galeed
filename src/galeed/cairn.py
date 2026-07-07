"""Helpers for emitting Cairn-compatible observation events into Galeed."""

from __future__ import annotations

from typing import Any

from galeed.events import INFO, TraceEvent


CAIRN_OBSERVATION_KINDS = {
    "ui_event",
    "system_log",
    "agent_step",
    "agent_output",
    "agent_output_review",
    "queue_event",
    "feedback",
    "recovery_event",
}


def emit_cairn_observation(
    tracer: Any,
    *,
    kind: str,
    message: str,
    severity: str = INFO,
    tags: list[str] | None = None,
    human_systems: list[str] | None = None,
    duration_ms: int | None = None,
    status: str | None = None,
    **metadata: Any,
) -> TraceEvent:
    """Emit a Galeed trace event that Cairn can read as live-observation evidence."""
    if kind not in CAIRN_OBSERVATION_KINDS:
        raise ValueError(f"Unsupported Cairn observation kind: {kind}")

    normalized_tags = _unique(tags or [])
    event_metadata = dict(metadata)
    event_metadata.update(
        {
            "cairn_kind": kind,
            "tags": normalized_tags,
            "human_systems": _unique(human_systems or []),
            "duration_ms": int(duration_ms or 0),
        }
    )
    if "missing_evidence" in normalized_tags:
        event_metadata["missing_evidence"] = True
    if "missing_context" in normalized_tags:
        event_metadata["sufficient"] = False

    return tracer.emit(
        _event_type_for_kind(kind),
        status=status or _status_for_severity(severity),
        summary=message,
        severity=severity,
        **_drop_empty(event_metadata),
    )


def _event_type_for_kind(kind: str) -> str:
    if kind == "ui_event":
        return "message.user.observed"
    if kind == "feedback":
        return "feedback.submitted"
    if kind == "queue_event":
        return "job.observed"
    if kind == "agent_step":
        return "process.step.observed"
    if kind == "agent_output":
        return "llm.call.completed"
    if kind == "agent_output_review":
        return "answer.reviewed"
    if kind == "recovery_event":
        return "process.recovery.observed"
    return "system.log.observed"


def _status_for_severity(severity: str) -> str:
    if severity in {"error", "critical"}:
        return "failed"
    if severity == "warning":
        return "warning"
    return "ok"


def _unique(items: list[str]) -> list[str]:
    return sorted({str(item) for item in items if str(item).strip()})


def _drop_empty(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value not in (None, {}, [])}
