---
type: Concept
title: The trace spine
description: A single structured event stream for the whole family — an open vocabulary with schema discipline, correlation ids for cross-repo joins, and per-request Tracers that persist and publish live.
resource: https://github.com/gellsmore-svg/galeed/blob/main/src/galeed/events.py
tags: [galeed, events, tracing, schema]
timestamp: 2026-07-05T00:00:00Z
---

# The trace spine

Every family project emits structured events into one stream (the
`trace_events` collection plus a live in-process bus). The vocabulary
(`EventType`) is **documented but open**: emitters may add types without a
schema bump; `SCHEMA_VERSION` changes only on a backwards-incompatible shape
change.

The documented sets: request lifecycle (`process.*`, `message.*`,
`answer.finalized`), retrieval/model steps, background jobs (`job.*` — Hoglah),
the Mahalath ontology pipeline (`document.ingested`, `debate.completed`,
`proposal.*`), Milcah coherence runs (`orchestration.*`, `snapshot.saved`),
plan interpretation (`plan.step.*`, emitted live by Tirzah's executor), and
`llm.call.completed/failed`.

**Correlation**: populate `CORRELATION_KEYS` (`request_id`, `session_id`,
`trace_id`, `plan_id`, `job_id` — the last two ride in metadata) so a flow can
be stitched across repos; `correlation_ids(event)` reads them back.

**Emission is best-effort by contract**: `Tracer.emit` and `record_event`
swallow persistence failures. A tool must behave identically with the spine
up, down, or absent.
