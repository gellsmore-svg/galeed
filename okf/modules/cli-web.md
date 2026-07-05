---
type: Module
title: cli & web
description: The galeed console script (trace/sessions/events/serve) and the read-only HTTP trace API that browser viewers consume.
resource: https://github.com/gellsmore-svg/galeed/blob/main/src/galeed/cli.py
tags: [galeed, module, cli, web, viewers]
timestamp: 2026-07-05T00:00:00Z
---

# cli & web

**CLI** (`pip install galeed[cli]` → rich + pymongo):

- `galeed trace` — the debug view: In→Out per call, chains as trees,
  `--verbose` for the technical layer, filters
  (`--session/--trace/--source/--step/--call/--status/--since/--limit`),
  `--follow` (store-polling live tail), `--json` export (works core-only).
- `galeed sessions` / `galeed events` — spine rollups and raw events.
- Connection: `--mongo-uri/--mongo-db` or `GALEED_MONGO_URI`/`GALEED_MONGO_DB`
  (defaults: `mongodb://localhost:27017` / `mnemosyne_dev`).

**Web** (`pip install galeed[web]`): `galeed serve` (default `127.0.0.1:8785`)
— read-only FastAPI over the family Mongo: `/api/trace/sessions`,
`/api/trace/events`, `/api/trace/stream` (poll-based SSE, works across
processes), `/api/llm-calls[?payloads=false]`, `/api/llm-calls/{call_id}`,
`/api/health`. The `/api/trace/*` shapes match Tirzah's, so Mizpah works
against either; the llm-calls endpoints are what its LLM Calls tab reads.
