---
type: Module Index
title: Galeed Modules
description: The code map — events, recorder/bus, llm_calls, feedback, and the CLI/web viewers.
resource: https://github.com/gellsmore-svg/galeed/tree/main/src/galeed
tags: [galeed, modules]
timestamp: 2026-07-05T00:00:00Z
---

# Modules

- **[events](events.md)** — vocabulary, `TraceEvent`, ids, schema/correlation.
- **[recorder & bus](recorder-bus.md)** — `Tracer`, persistence/query helpers,
  and the in-process `TraceBus` for live streaming.
- **[llm_calls](llm-calls.md)** — the full-fidelity debugging store and its API.
- **[cli & web](cli-web.md)** — `galeed trace|sessions|events|serve` and the
  HTTP trace API.
- **feedback** — feedback records tied to a trace (`record_feedback`,
  `list_feedback`), mirrored as `feedback.submitted` events.
