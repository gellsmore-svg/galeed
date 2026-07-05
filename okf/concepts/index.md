---
type: Concept Index
title: Galeed Concepts
description: The design ideas behind the family trace spine — lean events with correlation ids, heavy payloads quarantined into llm_calls, best-effort emission, and the records/views split with Mizpah.
resource: https://github.com/gellsmore-svg/galeed
tags: [galeed, concepts, tracing, observability]
timestamp: 2026-07-05T00:00:00Z
---

# Concepts

- **[The spine](event-spine.md)** — one structured, extensible event stream for
  every family project; process telemetry separated from the final answer.
- **[LLM debugging](llm-debugging.md)** — full In→Out per model call in
  `llm_calls`; the spine stays lean and links by `call_id`.

Two rules govern everything: **emission is best-effort** (a broken trace store
must never break a pipeline), and **Galeed records, Mizpah views** (Gen 31:48–49).
