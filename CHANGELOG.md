# Changelog

## [Unreleased]
- `record_llm_call` gains a first-class `usage` field (token counts). Previously
  Hoglah reported usage inside `metadata`, where no aggregate query could reach
  it — cost was recorded but not measurable. Legacy producers are promoted
  automatically, so no caller has to change; the explicit argument wins when
  both are present, and `total` is derived when only the components are given.
  The key always exists (`{}` when unknown) so aggregates can rely on it.
- Followed the Cairn split in docs only: the analyser on the other end of the
  observation bridge is now **Huldah** (`cairn` became `deborah` + `huldah` at
  Deborah v0.9.0). The `cairn` module, `emit_cairn_observation`,
  `CAIRN_OBSERVATION_KINDS` and `metadata.cairn_kind` are **unchanged** — they
  name the observation *format*, not the analyser, and renaming them would be a
  breaking wire change requiring a lockstep Huldah release. A new test pins the
  contract and the round-trip is verified against Huldah's adapter.
- `galeed serve` closes its `MongoClient` on shutdown via a FastAPI lifespan hook
  — but only one it opened itself; an injected `db` belongs to the caller.
- `list_trace_sessions` now groups Mongo-side (`$group`) instead of loading the
  whole `trace_events` collection into the client (#14). Stores without
  `aggregate` (the test fakes) fall back to the identical Python aggregation.
- New `ensure_indexes(db)` creates the `session_timeline` and `trace_timeline`
  indexes; called best-effort on `galeed serve` and CLI startup (#14).
- `limit=0` is documented as "unspecified" and resolves to the same default on
  every query path (#15). It previously returned *no* sessions from the Python
  path.

## [0.2.0] - 2026-07-04
- **LLM debugging layer**: `llm_calls` collection stores the complete In→Out per
  model call (prompt/messages, output, step_name, parent_call_id chains);
  `record_llm_call` / `capture_llm_call` APIs; spine events stay lean and link by
  `call_id`.
- **`galeed` CLI** (`cli` extra: rich + pymongo): `trace` (In→Out tree, filters,
  `--verbose`, `--follow`, `--json`), `sessions`, `events`.
- **`galeed serve`** (`web` extra): read-only HTTP trace API (Tirzah-compatible
  `/api/trace/*`, `/api/llm-calls`, SSE tail) — what Mizpah reads.
- Documented family vocabulary grew: `job.*` (queues), Mahalath pipeline events,
  Milcah coherence-run events, `llm.call.completed/failed`.

## [0.1.0] - 2026-06-26
- Initial extraction from `tirzah.trace`: events (`EventType`, `TraceEvent`),
  recorder (`Tracer` + query helpers), in-process bus, feedback records.
