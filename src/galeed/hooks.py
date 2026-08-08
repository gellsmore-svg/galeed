"""Galeed hook bridges for external agents (Codex CLI, Claude Code, etc.).

Codex (and similar) support lifecycle hooks that run external commands.
This module provides small handlers that Codex can invoke. They read a JSON
payload (typically on stdin) and emit structured TraceEvents into the Galeed
spine so the entire run is visible in `galeed trace` / Mizpah.

Usage in ~/.codex/config.toml (or equivalent for Claude Code):

[hooks]
SessionStart = ["galeed-codex-hook", "SessionStart"]
PreToolUse   = ["galeed-codex-hook", "PreToolUse"]
PostToolUse  = ["galeed-codex-hook", "PostToolUse"]
Stop         = ["galeed-codex-hook", "Stop"]

The handler receives the hook name as argv[1] (optional) and the full payload
as JSON on stdin. It maps to Galeed event types with source="codex".

This is the "Galeed hook bridge" described in the integration plan.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from galeed.events import TraceEvent, new_trace_id
from galeed.recorder import record_event

# Use the same env-driven defaults as the rest of Galeed
DEFAULT_MONGO_URI = os.environ.get("GALEED_MONGO_URI", "mongodb://localhost:27017")
DEFAULT_MONGO_DB = os.environ.get("GALEED_MONGO_DB", "mnemosyne_dev")

TRACE_EVENTS_COLLECTION = "trace_events"

# Hook path: fail fast. Local Mongo answers in single-digit ms; 2 s per hook
# invocation (review F3/H2) is blocking in practice when the host is down.
_HOOK_SERVER_SELECTION_MS = 250
# Cross-process breadcrumb so subsequent hook processes skip the probe for a
# short window rather than each re-paying the timeout (each hook is a fresh
# process — nothing learns Mongo is down without this).
_UNREACHABLE_BREADCRUMB = Path.home() / ".galeed" / "mongo-unreachable"
_UNREACHABLE_TTL_S = 60.0


def _mongo_recently_unreachable() -> bool:
    try:
        if not _UNREACHABLE_BREADCRUMB.is_file():
            return False
        age = time.time() - _UNREACHABLE_BREADCRUMB.stat().st_mtime
        return age < _UNREACHABLE_TTL_S
    except OSError:
        return False


def _mark_mongo_unreachable() -> None:
    try:
        _UNREACHABLE_BREADCRUMB.parent.mkdir(parents=True, exist_ok=True)
        _UNREACHABLE_BREADCRUMB.write_text(str(time.time()), encoding="utf-8")
    except OSError:
        pass


def _clear_mongo_unreachable() -> None:
    try:
        if _UNREACHABLE_BREADCRUMB.is_file():
            _UNREACHABLE_BREADCRUMB.unlink()
    except OSError:
        pass


def _get_client_and_db():
    """Best-effort Mongo connection for hooks.

    Returns ``(client, db)`` or ``(None, None)``. Client must be closed by the
    caller (review M4). Short selection timeout + unreachable breadcrumb so a
    down Mongo does not add ~2 s per hook invocation (review H2/F3).
    """
    if _mongo_recently_unreachable():
        return None, None
    try:
        from pymongo import MongoClient  # type: ignore

        uri = DEFAULT_MONGO_URI
        db_name = DEFAULT_MONGO_DB
        client = MongoClient(uri, serverSelectionTimeoutMS=_HOOK_SERVER_SELECTION_MS)
        client.admin.command("ping")
        _clear_mongo_unreachable()
        return client, client[db_name]
    except Exception:
        _mark_mongo_unreachable()
        return None, None


def _get_db():
    """Best-effort Mongo connection. Returns None if unavailable.

    Prefer :func:`_get_client_and_db` when you can close the client. This
    helper is kept for tests and simple callers; the client is not retained.
    """
    client, db = _get_client_and_db()
    if client is not None and db is None:
        try:
            client.close()
        except Exception:
            pass
    return db


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
    client, db = _get_client_and_db()
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
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def _load_payload() -> dict[str, Any]:
    """Read hook payload. Codex typically sends JSON on stdin.
    Falls back to empty dict if nothing readable."""
    try:
        data = sys.stdin.read()
        if data.strip():
            payload = json.loads(data)
            if isinstance(payload, dict):
                return payload
            return {"payload": payload}
    except Exception:
        pass
    return {}


def _tool_name_from_payload(payload: dict[str, Any]) -> str | None:
    tool = payload.get("tool")
    if payload.get("tool_name"):
        return str(payload["tool_name"])
    if payload.get("toolName"):
        return str(payload["toolName"])
    if isinstance(tool, dict) and tool.get("name"):
        return str(tool["name"])
    if isinstance(tool, str) and tool:
        return tool
    return None


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
    try:
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

        reserved = {"trace_id", "session_id", "type", "status", "summary", "source", "hook", "message_id", "request_id"}
        _emit_event(
            trace_id=trace_id,
            session_id=session_id,
            type=event_type,
            status=status,
            summary=summary,
            source="codex",
            hook=hook_name,
            **{k: v for k, v in payload.items() if k not in reserved},
        )

        # For tool hooks, also emit more structured tool events if tool info present
        if hook_name in ("PreToolUse", "PostToolUse", "pre_tool", "post_tool"):
            tool_name = _tool_name_from_payload(payload)
            if tool_name:
                tool_type = "codex.tool.started" if "Pre" in hook_name or "pre" in hook_name else "codex.tool.completed"
                tool_meta = {k: v for k, v in payload.items() if k not in reserved}
                tool_meta["tool_name"] = tool_name
                _emit_event(
                    trace_id=trace_id,
                    session_id=session_id,
                    type=tool_type,
                    summary=f"tool: {tool_name}",
                    source="codex",
                    **tool_meta,
                )
    except Exception as e:
        # CRITICAL: Codex hooks must NEVER raise or return non-zero.
        # Log for debugging and always succeed.
        try:
            log_path = os.path.expanduser("~/.codex/galeed-codex-hook-errors.log")
            with open(log_path, "a") as f:
                import datetime
                f.write(f"{datetime.datetime.now()}: {type(e).__name__}: {e}\n")
        except Exception:
            pass
        return 0

    return 0


def main() -> None:
    """Console script entry point (galeed-codex-hook)."""
    raise SystemExit(codex_hook())


if __name__ == "__main__":
    main()
