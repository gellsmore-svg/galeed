# Changelog

## [Unreleased]

## [0.4.0] — 2026-08-08

Review action for `docs/review-2026-08-08.md` (0.3.x baseline).

### Fixed
- **H1 / F1**: `estimate_cost_usd` returns `None` for unpriced models (no more
  silent `$0.00`). Explicit free rates only for listed local models +
  `default` when `model` is unset.
- **H2 / F3**: hook Mongo probe uses 250 ms timeout and a 60 s
  `~/.galeed/mongo-unreachable` breadcrumb so a down host does not add ~2 s
  per hook process.
- **M3**: `usage` stores only canonical keys (`prompt_tokens`,
  `completion_tokens`, `total`); aliases remain on top-level document fields.
- **M4**: hooks and CLI close their `MongoClient` after use.

### Added
- **H3**: `llm_instrumentation_coverage` + `galeed sessions` table — per-source
  usage/duration rates over `llm_calls`.
- **M1**: `list_trace_events` warns on unrecognised major `schema_version`.
- **M2**: `TraceBus.dropped` counter for full-queue drops; shown in sessions.
- `record_negotiation(..., note=)` (landed from 0.3.2 WIP).

## [0.3.2] — 2026-08-07

### Added
- ``record_negotiation(..., note=)`` — labels pre-plan vs mid-slice
  (e.g. ``post_retrieve``); stored as ``metadata.note`` /
  ``negotiation_phase`` and reflected in the summary for Mizpah chips

## [0.3.1] — 2026-08-07

### Added
- `open_question.recorded` event type + `record_open_question_event` helper

## [0.3.0] — 2026-08-07

### Added
- Stage 0: `tokens_in` / `tokens_out` aliases on `record_llm_call` (+ first-class
  `cost` with `estimate_cost_usd` for local-zero defaults)
- `decision.recorded`, `negotiation.started`, `negotiation.finished` event types
- `galeed.decisions.record_decision` / `record_negotiation` helpers

### Prior unreleased
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
