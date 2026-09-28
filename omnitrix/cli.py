"""omnitrix - command line for the foundation: health checks, database, demo clock, schemas, events, models."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
import psycopg
import typer
from rich.console import Console
from rich.table import Table

from omnitrix.config import get_settings
from omnitrix.core.clock import ClockStore, parse_when
from omnitrix.core.db import Database
from omnitrix.core.events import CHANNEL, EventBus, make_event, tail
from omnitrix.core.schemas import EVENT_TYPES, EXPORTED, TaskCandidateList
from omnitrix.llm import LLM, OllamaClient, OllamaError

app = typer.Typer(help="Omnitrix - sovereign second brain", no_args_is_help=True)
db_app = typer.Typer(help="Database migrations", no_args_is_help=True)
clock_app = typer.Typer(help="The shared demo clock", no_args_is_help=True)
schemas_app = typer.Typer(help="Shared formats", no_args_is_help=True)
events_app = typer.Typer(help="Event bus", no_args_is_help=True)
llm_app = typer.Typer(help="Local models", no_args_is_help=True)
demo_app = typer.Typer(help="The fictional demo world (demo_data/)", no_args_is_help=True)
brain_app = typer.Typer(help="The brain: ingestion, scoped recall, benchmark, graph", no_args_is_help=True)
for sub, name in [(db_app, "db"), (clock_app, "clock"), (schemas_app, "schemas"), (events_app, "events"),
                  (llm_app, "llm"), (demo_app, "demo"), (brain_app, "brain")]:
    app.add_typer(sub, name=name)

console = Console()
ROOT = Path(__file__).resolve().parents[1]


def run(coro):
    return asyncio.run(coro)


def _db() -> Database:
    return Database(get_settings().database_url, max_size=4)


# ----------------------------------------------------------------------------------------------- doctor

@app.command()
def doctor() -> None:
    """Check every local service Omnitrix needs."""
    rows = run(_doctor())
    table = Table(title="Omnitrix doctor")
    for col in ("check", "status", "detail"):
        table.add_column(col)
    for check, ok, detail in rows:
        table.add_row(check, "[green]ok[/]" if ok else "[red]FAIL[/]", detail)
    console.print(table)
    if not all(ok for _, ok, _ in rows):
        raise typer.Exit(1)


def _tagged(name: str) -> str:
    return name if ":" in name else f"{name}:latest"


async def _doctor() -> list[tuple[str, bool, str]]:
    s = get_settings()
    rows: list[tuple[str, bool, str]] = []
    rows.append(("python", sys.version_info >= (3, 12), sys.version.split()[0]))

    try:
        async with Database(s.database_url, max_size=1) as db:
            ext = await db.fetchrow("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            rows.append(("postgres", True, s.database_url.rsplit("@", 1)[-1]))
            rows.append(("pgvector", ext is not None, f"v{ext['extversion']}" if ext else "run: omnitrix db migrate"))
            try:
                migrations = await db.applied_migrations()
                rows.append(("migrations", bool(migrations), ", ".join(migrations) or "none applied"))
                clock = await ClockStore(db).load(s.tz)
                rows.append(("demo clock", True, clock.describe()))
            except psycopg.errors.UndefinedTable:
                rows.append(("migrations", False, "run: omnitrix db migrate"))
    except Exception as e:  # noqa: BLE001
        rows.append(("postgres", False, f"{type(e).__name__}: {e} - run: docker compose up -d"))

    async with httpx.AsyncClient(timeout=3) as http:
        for name, url, path in [("mailpit", s.mailpit_url, "/api/v1/info"), ("ntfy", s.ntfy_url, "/v1/health")]:
            try:
                r = await http.get(url + path)
                rows.append((name, r.status_code == 200, url))
            except httpx.HTTPError as e:
                rows.append((name, False, f"{url} unreachable ({type(e).__name__}) - run: docker compose up -d"))

    client = OllamaClient(s.ollama_url)
    try:
        installed = {_tagged(m) for m in await client.list_models()}
        rows.append(("ollama", True, s.ollama_url))
        for role in ("main", "fast", "embed"):
            model = s.model_for(role)
            ok = _tagged(model) in installed
            rows.append((f"model: {role}", ok, model if ok else f"{model} missing - run: ollama pull {model}"))
    except OllamaError as e:
        rows.append(("ollama", False, f"{e} - install from ollama.com and start it"))
    finally:
        await client.close()
    return rows


# ----------------------------------------------------------------------------------------------- database

@db_app.command("migrate")
def db_migrate() -> None:
    """Apply pending migrations."""
    async def go():
        async with _db() as db:
            return await db.migrate()
    applied = run(go())
    console.print(f"applied: {', '.join(applied)}" if applied else "database is up to date")


@db_app.command("reset")
def db_reset(yes: bool = typer.Option(False, "--yes", help="Confirm dropping every table"),
             migrate: bool = typer.Option(True, help="Re-apply migrations afterwards")) -> None:
    """Drop every table (local development only) and re-create the schema."""
    if not yes:
        console.print("[red]This deletes all local Omnitrix data.[/] Re-run with --yes to confirm.")
        raise typer.Exit(1)

    async def go():
        async with _db() as db:
            await db.reset()
            return await db.migrate() if migrate else []
    applied = run(go())
    console.print(f"reset done; applied: {', '.join(applied) or 'nothing'}")


# ----------------------------------------------------------------------------------------------- clock

async def _clock_change(action: str, arg: str | None = None) -> str:
    s = get_settings()
    async with _db() as db:
        store = ClockStore(db)
        clock = await store.load(s.tz)
        before = clock.now()
        if action == "jump":
            clock.jump_to(parse_when(arg, clock))
        elif action == "freeze":
            clock.freeze(parse_when(arg, clock) if arg else None)
        elif action == "unfreeze":
            clock.unfreeze()
        elif action == "reset":
            clock.reset()
        await store.save(clock)
        if action != "show":
            event = make_event("clock.jumped", emitted_by="cli", clock=clock, priority="high",
                               payload={"from": before.isoformat(), "to": clock.now().isoformat(),
                                        "mode": clock.state.mode})
            await EventBus(db).publish(event)
        return clock.describe()


@clock_app.command("show")
def clock_show() -> None:
    """Show the demo time."""
    console.print(run(_clock_change("show")))


@clock_app.command("jump")
def clock_jump(to: str = typer.Argument(..., help="'14:00' (today), '+90m', '+2h', '+1d' or an ISO date-time")) -> None:
    """Fast-forward (or rewind) the demo clock; time keeps flowing from there."""
    console.print(run(_clock_change("jump", to)))


@clock_app.command("freeze")
def clock_freeze(at: str = typer.Argument(None, help="Optional time to freeze at, same formats as jump")) -> None:
    """Stop the demo clock (repeatable demo beats and tests)."""
    console.print(run(_clock_change("freeze", at)))


@clock_app.command("unfreeze")
def clock_unfreeze() -> None:
    """Let a frozen demo clock run again from where it stopped."""
    console.print(run(_clock_change("unfreeze")))


@clock_app.command("reset")
def clock_reset() -> None:
    """Back to real time."""
    console.print(run(_clock_change("reset")))


# ----------------------------------------------------------------------------------------------- schemas

@schemas_app.command("export")
def schemas_export(out: Path = typer.Option(ROOT / "schemas", help="Output folder")) -> None:
    """Write every shared format as JSON Schema (for teammates, tests and tools)."""
    out.mkdir(parents=True, exist_ok=True)
    for name, model in EXPORTED.items():
        (out / f"{name}.schema.json").write_text(json.dumps(model.model_json_schema(), indent=2) + "\n")
    (out / "event_types.json").write_text(json.dumps(EVENT_TYPES, indent=2) + "\n")
    console.print(f"wrote {len(EXPORTED) + 1} files to {out}")


# ----------------------------------------------------------------------------------------------- events

@events_app.command("emit")
def events_emit(type: str, payload: str = typer.Option("{}", help="JSON payload"),
                priority: str = typer.Option("normal"), correlation: str = typer.Option(None),
                key: str = typer.Option(None, help="Idempotency key (repeat it to test de-duplication)")) -> None:
    """Publish a test event."""
    if type not in EVENT_TYPES:
        console.print(f"[red]unknown event type {type!r}[/] - known types: {', '.join(EVENT_TYPES)}")
        raise typer.Exit(1)

    async def go():
        s = get_settings()
        async with _db() as db:
            clock = await ClockStore(db).load(s.tz)
            event = make_event(type, emitted_by="cli", clock=clock, idempotency_key=key, priority=priority,
                               correlation_id=correlation, payload=json.loads(payload))
            return event, await EventBus(db).publish(event)
    event, stored = run(go())
    console.print(f"{event.event_id} {event.type} " + ("stored" if stored else "[yellow]duplicate - ignored[/]"))


@events_app.command("tail")
def events_tail(follow: bool = typer.Option(False, "--follow", "-f", help="Keep printing new events")) -> None:
    """Show recent events."""
    async def go():
        async with _db() as db:
            for e in await tail(db):
                _print_event(e)
            if not follow:
                return
            bus = EventBus(db)
            async with await psycopg.AsyncConnection.connect(db.url, autocommit=True) as conn:
                await conn.execute(f"LISTEN {CHANNEL}")
                async for note in conn.notifies():
                    event = await bus.get(note.payload)
                    if event:
                        _print_event(event)
    try:
        run(go())
    except KeyboardInterrupt:
        pass


def _print_event(e) -> None:
    at = e.occurred_at.astimezone(get_settings().tz)
    console.print(f"[dim]{at:%a %H:%M:%S}[/] [bold]{e.type}[/] [dim]{e.priority} by {e.emitted_by}"
                  f"{' story=' + e.correlation_id if e.correlation_id else ''}[/] {json.dumps(e.payload)}")


# ----------------------------------------------------------------------------------------------- demo

@demo_app.command("reset")
def demo_reset(yes: bool = typer.Option(False, "--yes", help="Confirm wiping all local data and Mailpit")) -> None:
    """Wipe local data, load the demo world, fill Mailpit, freeze the clock at Thu 8 Oct 08:55."""
    from omnitrix import demo
    if not yes:
        console.print("[red]This deletes all local Omnitrix data and every message in Mailpit.[/] "
                      "Re-run with --yes to confirm.")
        raise typer.Exit(1)

    async def go():
        async with _db() as db:
            return await demo.reset(db, get_settings())
    counts = run(go())
    table = Table(title="Demo world loaded")
    table.add_column("what")
    table.add_column("count", justify="right")
    for k, v in counts.items():
        table.add_row(k, str(v))
    console.print(table)
    console.print("Demo clock frozen at Thu 08 Oct 2026 08:55. Mailpit inbox: " + get_settings().mailpit_url)


@demo_app.command("status")
def demo_status() -> None:
    """Demo clock and the live emails still to come."""
    from omnitrix import demo

    async def go():
        async with _db() as db:
            clock = await ClockStore(db).load(get_settings().tz)
            live, sent = await demo.live_status(db)
            return clock, live, sent
    clock, live, sent = run(go())
    console.print(f"demo clock: {clock.describe()}")
    table = Table(title="Live emails")
    for col in ("id", "at", "from", "subject", "scenario", "status"):
        table.add_column(col)
    for e in live:
        due = datetime.fromisoformat(e["at"]) <= clock.now()
        status = "[green]sent[/]" if e["id"] in sent else ("[yellow]due - run demo play[/]" if due else "waiting")
        table.add_row(e["id"], e["at"][11:16], e["from"]["name"], e["subject"], e.get("scenario", ""), status)
    console.print(table)


@demo_app.command("play")
def demo_play() -> None:
    """Send every live email that is due by the demo clock (run after each clock jump)."""
    from omnitrix import demo

    async def go():
        async with _db() as db:
            clock = await ClockStore(db).load(get_settings().tz)
            return await demo.play(db, get_settings(), clock)
    sent = run(go())
    console.print(f"sent: {', '.join(sent)}" if sent else "nothing due yet")


@demo_app.command("send")
def demo_send(ids: list[str] = typer.Argument(..., help="Live email ids, e.g. L1 L2")) -> None:
    """Send specific live emails now, regardless of the demo clock."""
    from omnitrix import demo

    async def go():
        async with _db() as db:
            return await demo.send_live(db, get_settings(), [i.upper() for i in ids])
    try:
        console.print(f"sent: {', '.join(run(go()))}")
    except KeyError as e:
        console.print(f"[red]{e.args[0]}[/]")
        raise typer.Exit(1) from e


# ----------------------------------------------------------------------------------------------- brain

VAR = ROOT / "var"


@brain_app.command("ingest")
def brain_ingest() -> None:
    """Read the inbox (Mailpit), the vault copy and the watched folder into the brain. Only new items are processed."""
    from omnitrix.brain.connectors import FolderConnector, MailpitConnector, VaultConnector
    from omnitrix.brain.ingest import Ingestor

    async def go():
        s = get_settings()
        llm = LLM(s)
        try:
            async with _db() as db:
                clock = await ClockStore(db).load(s.tz)
                connectors = [MailpitConnector(s.mailpit_url), VaultConnector(VAR / "vault", s.tz),
                              FolderConnector(VAR / "files", clock.now())]
                return await Ingestor(db, lambda texts: llm.embed(texts, priority="low"), clock).ingest(connectors)
        finally:
            await llm.close()
    st = run(go())
    console.print(f"seen {st.seen} items: {st.new_sources} new, {st.skipped} already in the brain")
    console.print(f"stored {st.documents} documents, {st.chunks} chunks, {st.mentions} entity links, "
                  f"{st.links} reply links; embeddings {st.embed_ms / 1000:.1f}s, total {st.total_ms / 1000:.1f}s")


def _brain_session(fn):
    """Run fn(brain) with an open database and model client."""
    from omnitrix.brain.recall import Brain

    async def go():
        s = get_settings()
        llm = LLM(s)
        try:
            async with _db() as db:
                clock = await ClockStore(db).load(s.tz)
                return await fn(Brain(db, lambda texts: llm.embed(texts, priority="high"), clock))
        finally:
            await llm.close()
    return run(go())


@brain_app.command("ask")
def brain_ask(question: str, strategy: str = typer.Option("brain", help="brain | vector_all | keyword_all"),
              k: int = typer.Option(5), agent: str = typer.Option("cli"),
              show_prompt: bool = typer.Option(False, "--prompt", help="Print the context exactly as an agent gets it")) -> None:
    """Ask the brain: see what it narrowed down to and what it would hand an agent."""
    pack = _brain_session(lambda brain: brain.recall(question, agent=agent, strategy=strategy, k=k))
    st = pack.stats
    ents = ", ".join(f"{e['name']} ({e['type']})" for e in pack.entities) or "none - searched everything"
    console.print(f"[bold]about:[/] {ents}")
    console.print(f"[bold]searched:[/] {st['scope_documents']} of {st['corpus_documents']} documents, "
                  f"{st['scope_chunks']} of {st['corpus_chunks']} chunks ({st['share_searched']:.0%})")
    console.print(f"[bold]returned:[/] {st['returned_chunks']} chunks + {st['facts']} facts = {st['returned_tokens']} tokens "
                  f"({st['share_returned']:.1%} of the brain's {st['corpus_tokens']} tokens) in {st['total_ms']:.0f} ms")
    for f in pack.facts:
        console.print(f"  [cyan]fact[/] {f.text}")
    for i, it in enumerate(pack.items, 1):
        ref = it.ref.get("demo_id") or it.ref.get("path") or it.ref.get("filename") or ""
        console.print(f"  [green][{i}][/] {it.doc_type} '{it.title}' [dim]{ref} · {', '.join(it.why)}[/]")
        console.print("      " + it.text[:160].replace("\n", " ") + ("..." if len(it.text) > 160 else ""))
    if show_prompt:
        console.rule("context for the agent")
        console.print(pack.to_prompt())


def _share(x: float) -> str:
    return f"{x:.1%}" if 0 < x < 0.1 else f"{x:.0%}"


@brain_app.command("bench")
def brain_bench(k: int = typer.Option(5), budget: int = typer.Option(1200)) -> None:
    """Accuracy, speed and data read per question: scoped brain vs search-everything baselines."""
    from omnitrix.brain.bench import run_bench

    results, per_query = _brain_session(lambda brain: run_bench(brain, k=k, token_budget=budget))
    summaries = [r.summary() for r in results]
    corpus_tokens = None

    async def corpus():
        async with _db() as db:
            return (await db.fetchrow("SELECT count(*) AS c, coalesce(sum(length(text)),0) AS chars FROM chunks"))
    row = run(corpus())
    corpus_tokens = -(-row["chars"] // 4)
    table = Table(title=f"Recall benchmark - {len(per_query)} questions, top {k}, budget {budget} tokens")
    for col in ("strategy", "answered", "source in top k", "sources found", "MRR", "facts", "tokens / question",
                "latency p50 / p95", "share searched", "read <1%"):
        table.add_column(col, justify="right" if col != "strategy" else "left")
    for sm in summaries:
        table.add_row(sm["strategy"], f"{sm['answered']:.0%}", f"{sm['hit_at_k']:.0%}", f"{sm['recall']:.0%}",
                      f"{sm['mrr']:.2f}", sm["facts"], f"{sm['tokens']:.0f}",
                      f"{sm['ms_p50']:.0f} / {sm['ms_p95']:.0f} ms", _share(sm["searched"]),
                      f"{sm['under_1pct']}/{len(per_query)}")
    table.add_row("everything", "100%", "-", "100%", "-", "-", f"{corpus_tokens}", "-", "100%", "0/14")
    console.print(table)
    detail = Table(title="Per question (sources found: brain / vector_all / keyword_all)")
    for col in ("id", "question", "brain", "vector_all", "keyword_all", "brain searched"):
        detail.add_column(col)
    for q in per_query:
        detail.add_row(q["id"], q["ask"], *(f"{q[s]['recall']:.0%}" + (" +fact" if q[s]["facts_found"] else "")
                                            for s in ("brain", "vector_all", "keyword_all")),
                       _share(q["brain"]["searched"]))
    console.print(detail)


@brain_app.command("scale")
def brain_scale(docs: int = typer.Option(2000, help="How many look-alike documents to add"),
                remove: bool = typer.Option(False, "--remove", help="Remove all scale-test documents instead")) -> None:
    """Scale test: add fictional look-alike documents about other companies, then run `brain bench` again."""
    from omnitrix.brain.ingest import Ingestor
    from omnitrix.brain.noise import NoiseConnector, remove_noise

    async def go():
        s = get_settings()
        llm = LLM(s)
        try:
            async with _db() as db:
                if remove:
                    return await remove_noise(db)
                clock = await ClockStore(db).load(s.tz)
                return await Ingestor(db, lambda t: llm.embed(t, priority="low"), clock).ingest(
                    [NoiseConnector(docs, clock.now())])
        finally:
            await llm.close()
    result = run(go())
    if remove:
        console.print(f"removed {result} scale-test documents")
    else:
        console.print(f"added {result.documents} look-alike documents ({result.chunks} chunks) in "
                      f"{result.total_ms / 1000:.1f}s (embeddings {result.embed_ms / 1000:.1f}s)")


@brain_app.command("graph")
def brain_graph(out: Path = typer.Option(VAR / "brain_map.html", help="Where to write the page"),
                open_page: bool = typer.Option(False, "--open", help="Open it in the default browser")) -> None:
    """Export the Brain Map: one offline HTML page showing how the data connects, its clusters and what each
    question touched."""
    from omnitrix.brain.graph_view import export_graph_with_clusters, render_html

    async def go():
        async with _db() as db:
            return await export_graph_with_clusters(db, VAR)
    data = run(go())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(data))
    g = data["graphify"]
    clusters = f"{len(g['clusters'])} clusters" if g["available"] else f"no clusters ({g['reason']})"
    console.print(f"wrote {out} - {len(data['nodes'])} nodes, {len(data['edges'])} links, {clusters}, "
                  f"{len(data['traces'])} replayable questions")
    if open_page:
        import webbrowser
        webbrowser.open(out.resolve().as_uri())


@brain_app.command("graphify")
def brain_graphify() -> None:
    """Run graphify on the brain's graph: clusters, hub nodes, cohesion and a report (var/graphify-out/)."""
    from omnitrix.brain.graph_view import export_graph_with_clusters

    async def go():
        async with _db() as db:
            return await export_graph_with_clusters(db, VAR)
    g = run(go())["graphify"]
    if not g["available"]:
        console.print(f"[red]graphify is not available:[/] {g['reason']}")
        raise typer.Exit(1)
    table = Table(title=f"{len(g['clusters'])} clusters (graphify) + {len(g['unlinked'])} unlinked")
    for col in ("cluster", "nodes", "cohesion"):
        table.add_column(col, justify="left" if col == "cluster" else "right")
    for c in g["clusters"]:
        table.add_row(c["label"], str(c["size"]), f"{c['cohesion']:.2f}")
    console.print(table)
    console.print("hubs: " + ", ".join(f"{h['label']} ({h['degree']})" for h in g["hubs"][:8]))
    problems = {k: v for k, v in g["health"].items() if v}
    console.print("graph health: " + (", ".join(f"{v} {k.replace('_', ' ')}" for k, v in problems.items())
                                      if problems else "OK - no missing, dangling or collapsed links"))
    console.print(f"report: {g['report']}")


# -------------------------------------------------------------------------------------------- dashboard

@app.command()
def dashboard(port: int = typer.Option(None, help="Port (default: OMNITRIX_DASHBOARD_PORT, 8000)"),
              open_page: bool = typer.Option(False, "--open", help="Open it in the default browser")) -> None:
    """The local dashboard: the agent log (every brain recall, live) and the Brain Map. Local only (127.0.0.1)."""
    import uvicorn

    from omnitrix.dashboard.app import create_app

    port = port or get_settings().dashboard_port
    url = f"http://127.0.0.1:{port}"
    console.print(f"dashboard at [bold]{url}[/] - Ctrl+C to stop")
    if open_page:
        import webbrowser
        webbrowser.open(url)
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning", timeout_graceful_shutdown=2)


# ----------------------------------------------------------------------------------------------- models

SMOKE_TEXT = ("Hi Ravi, could you send me the revised quote by Thursday evening? "
              "Also, let's fix a call next week about payment terms. - Rajesh")


@llm_app.command("check")
def llm_check() -> None:
    """Smoke-test the local models: forced-JSON extraction on the fast model, and an embedding."""
    async def go():
        s = get_settings()
        llm = LLM(s)
        try:
            t0 = time.monotonic()
            result = await llm.structured(
                "fast",
                "Extract every task the reader (Ravi) must do from the message. Use only what the text says.",
                SMOKE_TEXT, TaskCandidateList, priority="high")
            t1 = time.monotonic()
            vectors = await llm.embed(["Send quote to Mehta"])
            t2 = time.monotonic()
            return result, t1 - t0, len(vectors[0]), t2 - t1, llm.usage
        finally:
            await llm.close()
    try:
        result, t_extract, dim, t_embed, usage = run(go())
    except OllamaError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1) from e
    console.print_json(result.model_dump_json())
    console.print(f"extraction: {len(result.tasks)} task(s) in {t_extract:.1f}s "
                  f"({usage.output_tokens} output tokens, {usage.retries} retries); embedding: {dim} dims in {t_embed:.1f}s")


if __name__ == "__main__":
    app()
