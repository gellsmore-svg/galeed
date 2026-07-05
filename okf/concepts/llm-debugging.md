---
type: Concept
title: LLM debugging — full In→Out capture
description: The debugging half of the spine — one llm_calls document per model call holding the complete prompt/messages and output, chained by parent_call_id; spine events stay lean and link by call_id.
resource: https://github.com/gellsmore-svg/galeed/blob/main/src/galeed/llm_calls.py
tags: [galeed, llm-debugging, llm_calls, observability]
timestamp: 2026-07-05T00:00:00Z
---

# LLM debugging

Debugging an LLM system means seeing **exactly what context went into each
call and what text came out**. That material is deliberately kept OUT of spine
events (session listings must stay light), so it has its own home: the
`llm_calls` collection — one document per call with the COMPLETE `prompt` or
`messages` list, the COMPLETE `output` (or `error`), a human `step_name`, the
correlation ids, and `parent_call_id` so recursive/chained flows form a tree
(`call_tree`). Technical detail (model, timing, usage) rides in `metadata`,
which viewers reveal only in an advanced mode — the default view is pure
In→Out.

Emitters: **Hoglah records every generate job automatically** (call_id =
job_id; thread `metadata.trace_id` through a multi-step flow to join it into
one trace); **Tirzah** records every answer-adapter call; any other tool wraps
a direct call in `capture_llm_call(...)` or records after the fact with
`record_llm_call(...)`.

Viewers: `galeed trace` (CLI tree), `galeed serve` + **Mizpah's LLM Calls tab**
(browser).
