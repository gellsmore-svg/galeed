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
- **`llm_calls`** — the **LLM debugging layer**: one document per model call with
  the COMPLETE input (prompt or messages list) and COMPLETE output, a human
  `step_name`, and `parent_call_id` chains for recursive flows. Spine events stay
  lean; the heavy payloads live here. Wrap direct calls with
  `capture_llm_call(...)`; Hoglah records every job automatically.

```python
from galeed import Tracer, EventType, get_bus, record_llm_call, capture_llm_call
```

## Viewers

- **`galeed trace`** (CLI, `pip install galeed[cli]`) — the clean In→Out call
  tree for every source: chains nested, `--verbose` for the technical layer,
  filters (`--session/--trace/--source/--step/--call/--status/--since`),
  `--follow` live tail, `--json` export (works without the extra).
- **`galeed sessions` / `galeed events`** — spine summaries and raw events.
- **`galeed serve`** (`pip install galeed[web]`, default port 8785) — the HTTP
  trace API browser viewers read: Tirzah-compatible `/api/trace/*` shapes,
  `/api/llm-calls`, and an SSE tail. **Mizpah** points here by default.

Connection: `--mongo-uri/--mongo-db` or `GALEED_MONGO_URI` / `GALEED_MONGO_DB`
(default `mongodb://localhost:27017` / `mnemosyne_dev`).

## Who emits into it

Any family project — Tirzah, Mahalath, Hoglah, Cairn, Milcah — emits its process
telemetry through Galeed. **Mizpah** is the viewer over what Galeed records.

## Schema discipline

Events carry a `schema_version` (`galeed.SCHEMA_VERSION`); bump it only on a
backwards-incompatible change to the event shape (new event *types* are additive and
need no bump). For cross-repo joins, populate the standard `CORRELATION_KEYS`
(`request_id`, `session_id`, `trace_id`, `plan_id`, `job_id`) — `galeed.correlation_ids(event)`
reads them back from fields + metadata so a trace can be stitched across projects.

## Develop

Works the same on native Linux and WSL — stdlib-only, no platform-specific steps.

```bash
pip install -e ".[dev]"   # pytest lives in the dev extra
pytest
```
