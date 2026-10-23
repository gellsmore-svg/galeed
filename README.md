# Galeed

**Galeed records what your LLM system did, step by step, separately from the
answer it gave.** Each request gets a trace of structured events (retrieval
ran, the planner chose X, the critic rejected Y), and each model call gets one
record holding its complete prompt and complete output. When an answer is
wrong, you can see why.

The core is pure Python stdlib, so any project can adopt it. Its companion
**[Mizpah](https://github.com/gellsmore-svg/Mizpah)** is the browser that
views what Galeed records. The names come from Genesis 31:48: one memorial
heap called *Galeed* ("heap of witness") and *Mizpah* ("watchtower"). Galeed
records; Mizpah views.

## Is it for you?

**Good fit:** you build multi-step or recursive LLM flows (agents, retrieval,
debate, pipelines) and need to replay exactly what each step saw and produced,
or stitch one trace across several services.

**Not a fit:** you want a hosted observability product, metrics dashboards, or
general application logging. Galeed stores traces in your own MongoDB and is
built for debugging LLM flows.

## Try it

```bash
pip install "galeed[cli]"          # core + the `galeed` CLI (adds rich, pymongo)
```

```python
from pymongo import MongoClient
from galeed import Tracer, EventType, capture_llm_call

db = MongoClient()["mnemosyne_dev"]          # the CLI's default database
t = Tracer(session_id="demo", source="my-app", db=db)

t.emit(EventType.PROCESS_STARTED, summary="answer a question")
with capture_llm_call(db, trace_id=t.trace_id, session_id="demo",
                      source="my-app", step_name="draft", prompt="Hi") as call:
    call.output = my_model("Hi")             # your model call
t.emit(EventType.PROCESS_COMPLETED)
```

```bash
galeed trace --session demo        # the In→Out call tree; --verbose for timings and metadata
```

Point anything at another store with `GALEED_MONGO_URI` / `GALEED_MONGO_DB`
(defaults: `mongodb://localhost:27017` / `mnemosyne_dev`).

## How it works

There are two layers, so traces stay light while full detail stays available:

- **Spine events** (`trace_events`) are small, ordered, typed records:
  `process.started`, a retrieval step, a decision. A `Tracer` is created once
  per request or operation and stamps every event with the trace, session and
  request ids.
- **LLM call records** (`llm_calls`) hold the heavy payloads: the complete
  prompt or messages, the complete output, a human `step_name`, usage and
  duration, and a `parent_call_id` so recursive flows form a tree.

**Tracing never breaks your application.** Persistence is best effort: a store
failure is swallowed and logged at DEBUG, and `db=None` keeps events in memory
only. Events also go to an in-process bus (`get_bus()`) for live streaming,
such as SSE to a process panel.

## What's in the box

| Module | Purpose |
|---|---|
| `events` | The event vocabulary (`EventType`, `TraceEvent`), extensible |
| `recorder` | `Tracer` plus query helpers over stored traces |
| `llm_calls` | `capture_llm_call(...)` / `record_llm_call(...)` for full model-call I/O |
| `bus` | Process-wide pub/sub (`TraceBus`) for live tails |
| `decisions` | Events recording *why* a run chose accept / reject / open |
| `feedback` | Lightweight feedback events tied to a trace |
| `cairn` | `emit_cairn_observation(...)`: events that [Huldah](https://github.com/gellsmore-svg/Huldah) can analyse as human-load and agent-effectiveness evidence |
| `hooks` | `galeed-codex-hook`, which streams a coding agent's lifecycle into the spine |

## Viewing traces

- `galeed trace`: call trees for every source. Filter with
  `--session/--trace/--source/--step/--call/--status/--since`, tail live with
  `--follow`, export with `--json` (which works without the `cli` extra).
- `galeed sessions` / `galeed events`: session summaries, including which
  calls lack usage or duration data, and raw events.
- `galeed serve` (`pip install "galeed[web]"`, port 8785): the HTTP trace API
  that browser viewers read. [Mizpah](https://github.com/gellsmore-svg/Mizpah)
  points here by default.

## Tracing a coding agent

`galeed-codex-hook` maps **Codex CLI** lifecycle hooks into Galeed events
(`source="codex"`). In `~/.codex/config.toml`:

```toml
[hooks]
SessionStart = ["galeed-codex-hook", "SessionStart"]
PreToolUse   = ["galeed-codex-hook", "PreToolUse"]
PostToolUse  = ["galeed-codex-hook", "PostToolUse"]
Stop         = ["galeed-codex-hook", "Stop"]
```

The handler reads the hook payload as JSON on stdin and uses the same
`GALEED_MONGO_*` variables. Other agents with command hooks can call it too,
but only the Codex payload shape is mapped today. Rollout plan:
[Noa codex-integration-plan](https://github.com/gellsmore-svg/Noa/blob/main/docs/codex-integration-plan.md).

## Joining traces across projects

Populate the standard `CORRELATION_KEYS` (`request_id`, `session_id`,
`trace_id`, `plan_id`, `job_id`). `galeed.correlation_ids(event)` reads them
back from fields and metadata, so one trace can be stitched across services.
Hoglah, Tirzah, Mahalath, Deborah, Huldah and Milcah all emit into the same
spine this way.

Events carry `schema_version` (`galeed.SCHEMA_VERSION`). It is bumped only for
a backwards-incompatible change to the event shape; new event types are
additive.

## Develop

Stdlib-only, so it behaves the same on Linux and WSL.

```bash
pip install -e ".[dev]"
pytest
```

[CHANGELOG](CHANGELOG.md) · [2026-08-08 review](docs/review-2026-08-08.md) ·
[SECURITY](SECURITY.md) · Apache 2.0, see [LICENSE](LICENSE).
