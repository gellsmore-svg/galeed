# Changelog

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
