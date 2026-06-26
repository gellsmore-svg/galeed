# Galeed

**The cross-project trace/log spine — "heap of witness" (Genesis 31:48).**

Galeed is the family's shared *logging capability*: a structured event stream that
separates **process telemetry** (what the system did, step by step) from the
**final output** (the answer). It is intentionally dependency-free (pure stdlib) so
any project can adopt it.

In Genesis 31, Laban and Jacob raise one memorial heap and give it two names —
**Galeed** ("heap of witness", the record itself) and **Mizpah** ("watchtower",
the one who watches over it). The family keeps the pair: **Galeed records; Mizpah
views.**

## What it provides

- **`events`** — a structured event vocabulary (`EventType`, `TraceEvent`, stable
  ids). Self-contained and extensible.
- **`recorder`** — `Tracer`: created once per request/operation; emits events,
  persists them, and exposes query helpers.
- **`bus`** — a process-wide in-process pub/sub (`TraceBus`) for live streaming
  (e.g. SSE to a process panel or a dev-log window).
- **`feedback`** — lightweight feedback events tied to a trace.

```python
from galeed import Tracer, EventType, get_bus
```

## Who emits into it

Any family project — Tirzah, Mahalath, Hoglah, Cairn, Milcah — emits its process
telemetry through Galeed. **Mizpah** is the viewer over what Galeed records.

## Develop

```bash
pip install -e .
pytest
```
