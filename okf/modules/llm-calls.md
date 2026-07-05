---
type: Module
title: llm_calls
description: The full-fidelity LLM call store — record_llm_call, capture_llm_call context manager, list/get/query, and call_tree for chained flows.
resource: https://github.com/gellsmore-svg/galeed/blob/main/src/galeed/llm_calls.py
tags: [galeed, module, llm-calls, debugging]
timestamp: 2026-07-05T00:00:00Z
---

# llm_calls

One document per model call in the `llm_calls` collection (see the
[debugging concept](../concepts/llm-debugging.md)).

- `record_llm_call(db, trace_id=…, session_id=…, source=…, prompt=…/messages=…,
  output=…/error=…, step_name=…, parent_call_id=…, metadata=…)` — one-shot
  record after a call finishes; also mirrors a lean `llm.call.completed/failed`
  spine event unless `emit_event=False` (emitters whose lifecycle events
  already mark the spine, e.g. Hoglah's `job.*`, pass False).
- `capture_llm_call(db, …) as call:` — context-manager wrapper for direct
  calls: set `call.output` (and optionally `call.model`/`call.metadata`);
  an exception records the call as failed and re-raises.
- `list_llm_calls(...)` — filters (trace/session/source/step/status/call_id/
  since), oldest→newest; `include_payloads=False` returns lean rows with size
  counts. `get_llm_call`, `call_tree` (parent/child forest), `new_call_id`.

Everything is best-effort: a broken db yields empty results / silent skips,
never an exception into the caller.
