# Security

## Reporting

Report vulnerabilities via GitHub issues (or privately to the repository owner
for sensitive reports). This is a local-first family project; there is no bug
bounty.

## Data sensitivity: `llm_calls` stores complete prompts and outputs

The LLM debugging layer is **full-fidelity by design**: every captured call's
COMPLETE prompt/messages and COMPLETE output are persisted to the `llm_calls`
collection. Anything a tool puts into a prompt — retrieved memory, user
questions, session history, document excerpts — ends up readable there.

Operational guidance:

- Treat the trace database (`mnemosyne_dev` by default) with the same
  sensitivity as the source data it summarises.
- `galeed serve` is **read-only but unauthenticated**; it binds `127.0.0.1`
  by default and must not be exposed beyond localhost without an
  authenticating proxy.
- Capture is opt-in per emitter (e.g. Hoglah's `galeed_capture_io`), and can be
  disabled while keeping lean lifecycle events.
- To purge captured payloads: drop or TTL-index the `llm_calls` collection —
  spine events are unaffected (they carry no payloads).

## Emission safety

Emission is best-effort by contract: persistence or bus failures are swallowed
(optionally visible at `DEBUG` log level) and must never affect the emitting
pipeline.
