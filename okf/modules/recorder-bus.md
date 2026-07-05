---
type: Module
title: recorder & bus
description: Tracer (per-request emitter that appends, persists best-effort, and publishes live) plus the query helpers and the in-process TraceBus.
resource: https://github.com/gellsmore-svg/galeed/blob/main/src/galeed/recorder.py
tags: [galeed, module, recorder, bus]
timestamp: 2026-07-05T00:00:00Z
---

# recorder & bus

`Tracer` is created once per request/operation (`trace_id` often anchored on an
existing run/job id). Each `emit()` builds a `TraceEvent`, appends it to
`tracer.events` (so a request can return its `processEvents` directly),
persists it best-effort to `trace_events`, and publishes it to the bus —
never raising into the caller. Convenience wrappers: `started` / `completed`
/ `failed`.

Query helpers: `list_trace_events(db, trace_id=…, session_id=…)` (replay for
dev-log windows) and `list_trace_sessions(db)` (per-session rollups: sources,
counts, first query, last answer preview).

`TraceBus` (`get_bus()`) is in-process pub/sub keyed by trace/session/`*` —
what powers live SSE process panels. Cross-process live tails poll the store
instead (`galeed serve`'s SSE endpoint, `galeed trace --follow`).
