"""The family LLM debugging CLI — `galeed trace` and friends.

The terminal watchtower over the spine: a clean, minimal-noise view of what
context went INTO each LLM call and what text came OUT, for every source that
emits into Galeed (Hoglah automatically; any tool via capture_llm_call).

Design rules (the debugging-interface requirements):
- Default view = step name + full In + full Out, nothing else. Chains render
  as trees via parent_call_id.
- ``--verbose`` reveals the technical layer (model, timing, status, metadata).
- ``--json`` emits machine-readable output (also the export path) and works
  without rich installed; the pretty view needs the ``cli`` extra.
- ``--follow`` tails new calls live (store polling — works across processes,
  unlike the in-process bus).

Commands:
    galeed trace     the In→Out call tree (filters: --session/--trace/--source/
                     --step/--status/--since/--limit)
    galeed sessions  spine sessions summary
    galeed events    raw spine events for a trace/session
    galeed serve     the HTTP API for browser viewers (Mizpah)

Connection: --mongo-uri/--mongo-db, or GALEED_MONGO_URI / GALEED_MONGO_DB
(default mongodb://localhost:27017 / mnemosyne_dev — the family trace db).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

from galeed.llm_calls import call_tree, list_llm_calls
from galeed.recorder import list_trace_events, list_trace_sessions

DEFAULT_MONGO_URI = os.environ.get("GALEED_MONGO_URI", "mongodb://localhost:27017")
DEFAULT_MONGO_DB = os.environ.get("GALEED_MONGO_DB", "mnemosyne_dev")

_STATUS_GLYPH = {"completed": "[green]●[/green]", "failed": "[red]✖[/red]"}


def _database(args: argparse.Namespace) -> Any:
    try:
        from pymongo import MongoClient
    except ImportError:
        _die("pymongo is required — install the cli extra:  pip install galeed[cli]")
    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=3000)
    return client[args.mongo_db]


def _console():
    try:
        from rich.console import Console
    except ImportError:
        _die("rich is required for the pretty view — install the cli extra:  pip install galeed[cli]\n"
             "(--json output works without it)")
    return Console()


def _die(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


# --- trace (the In→Out debug view) ------------------------------------------


def _query_calls(db: Any, args: argparse.Namespace) -> list[dict[str, Any]]:
    return list_llm_calls(
        db,
        trace_id=args.trace,
        session_id=args.session,
        source=args.source,
        step_name=args.step,
        status=args.status,
        call_id=getattr(args, "call", None),
        since=args.since,
        limit=args.limit,
    )


def _call_title(call: dict[str, Any], verbose: bool) -> str:
    glyph = _STATUS_GLYPH.get(call.get("status") or "", "○")
    name = call.get("step_name") or call.get("model") or (call.get("call_id") or "?")[:12]
    title = f"{glyph} [bold]{name}[/bold]"
    if verbose:
        bits = [call.get("model") or "?", call.get("source") or "?"]
        if call.get("duration_ms") is not None:
            bits.append(f"{call['duration_ms']}ms")
        bits.append((call.get("call_id") or "")[:12])
        title += "  [dim]" + " · ".join(str(b) for b in bits) + "[/dim]"
    return title


def _call_body(call: dict[str, Any], verbose: bool):
    """The clean In→Out block for one call (a rich Group)."""
    from rich.console import Group
    from rich.text import Text

    parts: list[Any] = []

    def _label(name: str) -> Text:
        return Text(name, style="bold cyan")

    messages = call.get("messages")
    if messages:
        parts.append(_label("In:"))
        for message in messages:
            role = str(message.get("role", "?"))
            parts.append(Text(f"[{role}] ", style="magenta") + Text(str(message.get("content", ""))))
    elif call.get("prompt") is not None:
        parts.append(_label("In:"))
        parts.append(Text(str(call["prompt"])))

    if call.get("error"):
        parts.append(_label("Out:"))
        parts.append(Text(str(call["error"]), style="red"))
    else:
        parts.append(_label("Out:"))
        parts.append(Text(str(call.get("output") or "(no output)")))

    if verbose and call.get("metadata"):
        parts.append(Text("meta: " + json.dumps(call["metadata"], default=str), style="dim"))
    return Group(*parts)


def _render_trace_tree(console: Any, calls: list[dict[str, Any]], verbose: bool) -> None:
    from rich.console import Group
    from rich.panel import Panel
    from rich.tree import Tree

    by_trace: dict[str, list[dict[str, Any]]] = {}
    for call in calls:
        by_trace.setdefault(call.get("trace_id") or "?", []).append(call)

    for trace_id, group in by_trace.items():
        first = group[0]
        header = f"[bold]{trace_id}[/bold]  [dim]{first.get('session_id')} · {len(group)} call(s)[/dim]"
        tree = Tree(header)

        def _add(node: Any, call: dict[str, Any]) -> None:
            branch = node.add(Group(_call_title(call, verbose), _call_body(call, verbose)))
            for child in call.get("children", []):
                _add(branch, child)

        for root in call_tree(group):
            _add(tree, root)
        console.print(Panel(tree, border_style="dim"))


def cmd_trace(args: argparse.Namespace) -> int:
    db = _database(args)
    calls = _query_calls(db, args)

    if args.json and not args.follow:
        print(json.dumps(calls, indent=2, default=str))
        return 0

    console = _console()
    if not calls:
        console.print("[dim](no captured LLM calls match — is emission enabled? "
                      "Hoglah: galeed_enabled + galeed_capture_io)[/dim]")
    else:
        _render_trace_tree(console, calls, args.verbose)

    if not args.follow:
        return 0

    console.print("[dim]following… Ctrl-C to stop[/dim]")
    last_seen = calls[-1]["completed_at"] if calls else None
    try:
        while True:
            time.sleep(args.interval)
            fresh = list_llm_calls(
                db,
                trace_id=args.trace, session_id=args.session, source=args.source,
                step_name=args.step, status=args.status,
                since=last_seen, limit=args.limit,
            )
            fresh = [c for c in fresh if c.get("completed_at") != last_seen]
            if fresh:
                _render_trace_tree(console, fresh, args.verbose)
                last_seen = fresh[-1]["completed_at"]
    except KeyboardInterrupt:
        return 0


# --- sessions / events (spine views) -----------------------------------------


def cmd_sessions(args: argparse.Namespace) -> int:
    db = _database(args)
    sessions = list_trace_sessions(db, limit=args.limit)
    if args.json:
        print(json.dumps(sessions, indent=2, default=str))
        return 0
    console = _console()
    from rich.table import Table

    table = Table(title="Spine sessions", header_style="bold")
    for column in ("session", "sources", "events", "traces", "updated", "first query"):
        table.add_column(column)
    for s in sessions:
        table.add_row(
            s["session_id"], ", ".join(s.get("sources") or []),
            str(s.get("event_count", 0)), str(s.get("trace_count", 0)),
            str(s.get("updated_at") or ""), (s.get("first_query") or "")[:60],
        )
    console.print(table)
    return 0


def cmd_events(args: argparse.Namespace) -> int:
    db = _database(args)
    events = list_trace_events(db, trace_id=args.trace, session_id=args.session, limit=args.limit)
    if args.json:
        print(json.dumps(events, indent=2, default=str))
        return 0
    console = _console()
    from rich.table import Table

    table = Table(title="Spine events", header_style="bold")
    for column in ("time", "source", "type", "status", "summary"):
        table.add_column(column)
    for event in events:
        table.add_row(
            str(event.get("timestamp") or "")[:19], event.get("source") or "",
            event.get("type") or "", event.get("status") or "",
            (event.get("summary") or "")[:80],
        )
    console.print(table)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn

        from galeed.web import create_app
    except ImportError as exc:
        _die(f"serve needs the web extra ({exc}) — pip install galeed[web]")
    print(f"Galeed trace API on http://{args.host}:{args.port} — db: {args.mongo_db}")
    uvicorn.run(
        create_app(mongo_uri=args.mongo_uri, mongo_db=args.mongo_db),
        host=args.host, port=args.port, log_level="warning",
    )
    return 0


# --- parser -------------------------------------------------------------------


def _add_connection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mongo-uri", default=DEFAULT_MONGO_URI, help="Family trace MongoDB URI.")
    parser.add_argument("--mongo-db", default=DEFAULT_MONGO_DB, help="Family trace database.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="galeed", description="Family LLM debugging: clean In→Out views over the trace spine."
    )
    sub = parser.add_subparsers(dest="command")

    p_trace = sub.add_parser("trace", help="The In→Out LLM call tree (the debug view).")
    p_trace.add_argument("--session", default=None, help="Filter by session id.")
    p_trace.add_argument("--trace", default=None, help="Filter by trace id.")
    p_trace.add_argument("--source", default=None, help="Filter by emitter (hoglah, mahalath, …).")
    p_trace.add_argument("--step", default=None, help="Filter by step name.")
    p_trace.add_argument("--call", default=None, help="Filter by exact call id (== job id for Hoglah calls).")
    p_trace.add_argument("--status", default=None, choices=["completed", "failed"], help="Filter by outcome.")
    p_trace.add_argument("--since", default=None, help="ISO timestamp lower bound.")
    p_trace.add_argument("--limit", type=int, default=50, help="Max calls shown (newest kept).")
    p_trace.add_argument("--verbose", "-v", action="store_true", help="Show the technical layer (model, timing, metadata).")
    p_trace.add_argument("--json", action="store_true", help="Machine-readable output / export (no rich needed).")
    p_trace.add_argument("--follow", "-f", action="store_true", help="Tail new calls live.")
    p_trace.add_argument("--interval", type=float, default=2.0, help="Poll interval for --follow (s).")
    _add_connection_args(p_trace)
    p_trace.set_defaults(func=cmd_trace)

    p_sessions = sub.add_parser("sessions", help="Summarise spine sessions across the family.")
    p_sessions.add_argument("--limit", type=int, default=50)
    p_sessions.add_argument("--json", action="store_true")
    _add_connection_args(p_sessions)
    p_sessions.set_defaults(func=cmd_sessions)

    p_events = sub.add_parser("events", help="Raw spine events for a trace/session.")
    p_events.add_argument("--session", default=None)
    p_events.add_argument("--trace", default=None)
    p_events.add_argument("--limit", type=int, default=200)
    p_events.add_argument("--json", action="store_true")
    _add_connection_args(p_events)
    p_events.set_defaults(func=cmd_events)

    p_serve = sub.add_parser("serve", help="HTTP API for browser viewers (Mizpah).")
    p_serve.add_argument("--host", default="127.0.0.1", help="Bind address (keep local; no auth).")
    p_serve.add_argument("--port", type=int, default=8785, help="Port for the trace API.")
    _add_connection_args(p_serve)
    p_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    if getattr(args, "func", None) is None:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
