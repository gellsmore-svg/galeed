"""`galeed serve` — the HTTP trace API browser viewers read (Mizpah).

A thin FastAPI layer over the family trace store: spine sessions/events (the
same response shapes Tirzah's /api/trace endpoints use, so Mizpah's existing
views work unchanged) plus the LLM debugging endpoints over ``llm_calls``
(full In→Out payloads). An SSE stream tails new spine events by polling the
store, so it works across processes (the in-process bus can't).

Read-only; bind 127.0.0.1 (no auth). Requires the ``web`` extra.
"""

from __future__ import annotations

import json
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse

from galeed.llm_calls import get_llm_call, list_llm_calls
from galeed.recorder import list_trace_events, list_trace_sessions

_INDEX_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Galeed</title>
<style>body{font-family:system-ui,sans-serif;max-width:640px;margin:3em auto;
line-height:1.6;color:#1c2128}code{background:#eef0f3;padding:2px 6px;border-radius:4px}
a{color:#2f5fd0}</style></head><body>
<h1>Galeed trace API</h1>
<p>The family debugging store is live. Browse it with <strong>Mizpah</strong>
(<code>cd Mizpah &amp;&amp; npm run dev</code>) or the CLI (<code>galeed trace</code>).</p>
<p>Endpoints: <code>/api/trace/sessions</code> · <code>/api/trace/events</code> ·
<code>/api/trace/stream</code> (SSE) · <code>/api/llm-calls</code> ·
<code>/api/llm-calls/{call_id}</code> · <code>/api/health</code></p>
</body></html>"""


def create_app(
    mongo_uri: str = "mongodb://localhost:27017",
    mongo_db: str = "mnemosyne_dev",
    db: Any = None,
) -> FastAPI:
    """Build the trace API over the family Mongo (or an injected db for tests)."""
    if db is None:
        from pymongo import MongoClient

        db = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)[mongo_db]

    app = FastAPI(title="Galeed", description="Family trace/debugging API (read-only)")
    app.state.db = db

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _INDEX_HTML

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "database": mongo_db}

    # --- spine (Tirzah-compatible shapes; Mizpah's existing views) ----------

    @app.get("/api/trace/sessions")
    def trace_sessions(limit: int = 200) -> dict[str, Any]:
        return {"ok": True, "sessions": list_trace_sessions(db, limit=limit)}

    @app.get("/api/trace/events")
    def trace_events(
        trace_id: str | None = None,
        session_id: str | None = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        events = list_trace_events(db, trace_id=trace_id, session_id=session_id, limit=limit)
        return {"ok": True, "traceId": trace_id, "sessionId": session_id, "events": events}

    @app.get("/api/trace/stream")
    def trace_stream(
        trace_id: str | None = None,
        session_id: str | None = None,
        replay: bool = True,
        poll_seconds: float = 2.0,
    ):
        """SSE tail over the store (poll-based → works across processes)."""

        def frames():
            yield ": connected\n\n"
            # Watermark instead of an ever-growing seen-set: remember the newest
            # timestamp plus only the ids AT that timestamp (ties), so memory
            # stays bounded on long-lived streams.
            watermark = ""
            at_watermark: set[str] = set()

            def advance(events):
                nonlocal watermark, at_watermark
                for event in events:
                    ts = str(event.get("timestamp") or "")
                    if ts > watermark:
                        watermark = ts
                        at_watermark = {event.get("event_id") or ""}
                    elif ts == watermark:
                        at_watermark.add(event.get("event_id") or "")

            replay_events = list_trace_events(
                db, trace_id=trace_id, session_id=session_id, limit=200
            )
            advance(replay_events)
            if replay:
                for event in replay_events:
                    yield f"data: {json.dumps(event, default=str)}\n\n"
            while True:
                time.sleep(poll_seconds)
                fresh = list_trace_events(
                    db, trace_id=trace_id, session_id=session_id, limit=200
                )
                new = [
                    e for e in fresh
                    if str(e.get("timestamp") or "") > watermark
                    or (str(e.get("timestamp") or "") == watermark
                        and (e.get("event_id") or "") not in at_watermark)
                ]
                if not new:
                    yield ": keepalive\n\n"
                    continue
                advance(new)
                for event in new:
                    yield f"data: {json.dumps(event, default=str)}\n\n"

        return StreamingResponse(frames(), media_type="text/event-stream")

    # --- LLM debugging (full In→Out) -----------------------------------------

    @app.get("/api/llm-calls")
    def llm_calls(
        trace_id: str | None = None,
        session_id: str | None = None,
        source: str | None = None,
        step_name: str | None = None,
        status: str | None = None,
        since: str | None = None,
        limit: int = 200,
        payloads: bool = True,
    ) -> dict[str, Any]:
        calls = list_llm_calls(
            db,
            trace_id=trace_id,
            session_id=session_id,
            source=source,
            step_name=step_name,
            status=status,
            since=since,
            limit=limit,
            include_payloads=payloads,
        )
        return {"ok": True, "calls": calls}

    @app.get("/api/llm-calls/{call_id}")
    def llm_call(call_id: str) -> dict[str, Any]:
        call = get_llm_call(db, call_id)
        if call is None:
            raise HTTPException(404, f"call not found: {call_id}")
        return {"ok": True, "call": call}

    return app
