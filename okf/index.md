---
type: Project
title: Galeed
description: The family's cross-project trace/log spine and LLM debugging layer — structured events (Tracer/bus) plus full In→Out capture of every model call (llm_calls), with CLI and HTTP viewers.
resource: https://github.com/gellsmore-svg/galeed
tags: [galeed, tracing, observability, llm-debugging, event-stream, local-first]
timestamp: 2026-07-05T00:00:00Z
---

# Galeed

Galeed ("heap of witness", Gen 31:48) is the family's shared logging capability:
a structured event stream separating **process telemetry** from the **final
answer**, plus the **LLM debugging layer** — one full In→Out document per model
call. Galeed *records*; Mizpah (the "watchtower") *views*.

## Map

- **[Concepts](concepts/index.md)** — the spine's design rules and the LLM
  debugging model.
- **[Modules](modules/index.md)** — events, recorder/bus, llm_calls, feedback,
  and the CLI/web viewers.

- **events** — the documented, extensible event vocabulary (`EventType`,
  `TraceEvent`, `SCHEMA_VERSION`, `CORRELATION_KEYS`).
- **recorder** — `Tracer` (per-request emitter: persist + bus) and the query
  helpers (`list_trace_events`, `list_trace_sessions`).
- **bus** — in-process pub/sub for live streaming (SSE process panels).
- **llm_calls** — full-fidelity call capture (`record_llm_call`,
  `capture_llm_call`, `list_llm_calls`, `call_tree`); payloads live here, spine
  events link by `call_id`.
- **cli** — `galeed trace | sessions | events | serve` (extras: `cli`, `web`).
- **web** — `galeed serve`, the read-only trace API browser viewers consume.

## Emitters

Hoglah (jobs, automatic), Tirzah (answer path + request traces), Mahalath
(ontology pipeline), Milcah (coherence runs) — all opt-in via config/env flags,
all best-effort: emission never raises into a pipeline.
