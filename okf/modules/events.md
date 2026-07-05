---
type: Module
title: events
description: The structured event model — EventType vocabulary, TraceEvent dataclass, stable id constructors, SCHEMA_VERSION, and CORRELATION_KEYS.
resource: https://github.com/gellsmore-svg/galeed/blob/main/src/galeed/events.py
tags: [galeed, module, events]
timestamp: 2026-07-05T00:00:00Z
---

# events

`TraceEvent` is the wire shape: trace/session ids, `type`, `status`, `summary`,
`severity`, `source`, optional message/request ids, `seq`, timestamp, and a
free `metadata` dict. `to_dict()` is the JSON-safe form used for storage, API
responses, and SSE frames.

`EventType` documents the family vocabulary (see the
[spine concept](../concepts/event-spine.md)); `KNOWN_EVENT_TYPES` derives from
it and is asserted by Tirzah's seam contract for its own emissions — the
vocabulary itself stays open. Id constructors (`new_trace_id`,
`new_message_id`, `new_request_id`, `new_event_id`) give collision-safe
prefixed uuids.
