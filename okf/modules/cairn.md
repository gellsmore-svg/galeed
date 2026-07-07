---
type: Module
title: cairn
description: Cairn observation bridge for emitting human-load and agent-effectiveness evidence into Galeed trace events.
resource: https://github.com/gellsmore-svg/galeed/blob/main/src/galeed/cairn.py
tags: [galeed, cairn, observation, human-load, tracing]
timestamp: 2026-07-07T00:00:00Z
---

# cairn

`emit_cairn_observation(...)` records a normal Galeed trace event with metadata
that Cairn can consume as live-observation evidence.

It keeps Galeed dependency-free and does not import Cairn. The bridge only
standardises the producer-side metadata:

- `cairn_kind`
- `tags`
- `human_systems`
- `duration_ms`
- `missing_evidence` when the tag is present
- `sufficient = false` when `missing_context` is present

Supported observation kinds are `ui_event`, `system_log`, `agent_step`,
`agent_output`, `agent_output_review`, `queue_event`, `feedback`, and
`recovery_event`.
