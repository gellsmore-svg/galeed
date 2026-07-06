"""Galeed hook bridges for external agents (Codex CLI, Claude Code, etc.).

Codex (and similar) support lifecycle hooks that run external commands.
This module provides small handlers that Codex can invoke. They read a JSON
payload (typically on stdin) and emit structured TraceEvents into the Galeed
spine so the entire run is visible in `galeed trace` / Mizpah.

Usage in ~/.codex/config.toml (or equivalent for Claude Code):

[hooks]
SessionStart = ["galeed-codex-hook", "session-start"]
PreToolUse   = ["galeed-codex-hook", "pre-tool"]
PostToolUse  = ["galeed-codex-hook", "post-tool"]
Stop         = ["galeed-codex-hook", "stop"]

The handler receives the hook name as argv[1] (optional) and the full payload
as JSON on stdin. It maps to Galeed event types with source="codex".

This is the "Galeed hook bridge" described in the integration plan.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from galeed.events import TraceEvent, new_trace_id
from galeed.recorder import record_event

# Use the same env-driven defaults as the rest of Galeed
DEFAULT_MONGO_URI = os.environ.get("GALEED_MONGO_URI", "mongodb://localhost:27017")
DEFAULT_MONGO_DB = os.environ.get("GALEED_MONGO_DB", "mnemosyne_dev")

TRACE_EVENTS_COLLECTION = "trace_events"


def _get_db():
    """Best-effort Mongo connection. Returns None if pymongo unavailable or
    connection fails (hooks must be best-effort and never block the agent)."""
    try:
        from pymongo import MongoClient  # type: ignore

        uri = DEFAULT_MONGO_URI
        db_name = DEFAULT_MONGO_DB
        client = MongoClient(uri, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")  # quick check
        return client[db_name]
    except Exception:
        # pymongo not installed, no mongo, or unreachable — silently skip
        return None


def _emit_event(
    *,
    trace_id: str,
    session_id: str,
    type: str,
    status: str = "ok",
    summary: str = "",
    source: str = "codex",
    **metadata: Any,
) -> None:
    """Create and record a TraceEvent (best effort)."""
    db = _get_db()
    event = TraceEvent(
        trace_id=trace_id,
        session_id=session_id,
        type=type,
        status=status,
        summary=summary,
        source=source,
        metadata=metadata,
    )
    try:
        record_event(db, event)
    except Exception:
        pass  # never let hook failures affect the coding agent


def _load_payload() -> dict[str, Any]:
    """Read hook payload. Codex typically sends JSON on stdin.
    Falls back to empty dict if nothing readable."""
    try:
        data = sys.stdin.read()
        if data.strip():
            return json.loads(data)
    except Exception:
        pass
    return {}


def codex_hook(argv: list[str] | None = None) -> int:
    """Main entry point for the codex hook handler.

    Invoked by Codex as:
        galeed-codex-hook [hook_name]

    The payload (with fields like session_id, transcript_path, tool_name, etc.)
    is expected on stdin as JSON.

    Examples of hook names (from Codex):
      - SessionStart
      - PreToolUse
      - PostToolUse
      - Stop
    """
    argv = argv or sys.argv
    hook_name = argv[1] if len(argv) > 1 else "unknown"

    payload = _load_payload()

    # Common fields Codex / similar tools provide
    session_id = (
        payload.get("session_id")
        or payload.get("cwd")
        or payload.get("transcript_path")
        or os.environ.get("CODEX_SESSION_ID")
        or "codex-session"
    )

    # Try to reuse or generate a stable trace for the run
    # Codex doesn't always give us a trace_id, so we derive one from session
    # or let the first event create one. For correlation we prefer stable.
    trace_id = payload.get("trace_id") or os.environ.get("GALEED_TRACE_ID") or new_trace_id()

    # Map Codex hook names to Galeed event types (extensible)
    event_type = f"codex.{hook_name.lower().replace('-', '_')}"
    summary = payload.get("summary") or f"codex hook: {hook_name}"

    status = "ok"
    if "error" in payload or hook_name.lower().endswith("failed"):
        status = "failed"

    _emit_event(
        trace_id=trace_id,
        session_id=session_id,
        type=event_type,
        status=status,
        summary=summary,
        source="codex",
        hook=hook_name,
        **{k: v for k, v in payload.items() if k not in ("session_id", "trace_id")},
    )

    # For tool hooks, also emit more structured tool events if tool info present
    if hook_name in ("PreToolUse", "PostToolUse", "pre_tool", "post_tool"):
        tool_name = payload.get("tool_name") or (payload.get("tool") or {}).get("name")
        if tool_name:
            tool_type = "codex.tool.started" if "Pre" in hook_name or "pre" in hook_name else "codex.tool.completed"
            tool_meta = {k: v for k, v in payload.items() if k not in ("session_id", "trace_id")}
            tool_meta["tool_name"] = tool_name
            _emit_event(
                trace_id=trace_id,
                session_id=session_id,
                type=tool_type,
                summary=f"tool: {tool_name}",
                source="codex",
                **tool_meta,
            )

    return 0


def main() -> None:
    """Console script entry point (galeed-codex-hook)."""
    raise SystemExit(codex_hook())


if __name__ == "__main__":
    main()
