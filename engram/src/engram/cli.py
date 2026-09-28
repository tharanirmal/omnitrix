"""engram command line: migrate, ingest, index, search, stats."""
from __future__ import annotations

import os
import time
from contextlib import nullcontext
from datetime import datetime
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from . import index as idx
from .config import settings
from .db import connect
from .db import migrate as run_migrations
from .llm import Ollama
from .sources import enron
from .store import ingest_messages

# Sovereign by default: model files load from the local cache and the Hugging Face Hub is never contacted (it would
# otherwise be asked for the latest revision on every load). Download a model explicitly, once, with the hf CLI.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
app = typer.Typer(no_args_is_help=True, add_completion=False, help="engram: a sovereign second brain.")
console = Console()
Day = Annotated[datetime | None, typer.Option(formats=["%Y-%m-%d"])]


@app.callback()
def main(brain: Annotated[str | None, typer.Option(help="which brain: its database on the engram server "
                                                        "(default: the one in ENGRAM_DATABASE_URL)")] = None) -> None:
    if brain:
        from psycopg.conninfo import make_conninfo

        settings.database_url = make_conninfo(settings.database_url, dbname=brain)


@app.command()
def migrate() -> None:
    """Create or update the database schema."""
    applied = run_migrations(settings.database_url)
    console.print(f"applied: {', '.join(applied)}" if applied else "schema is up to date")


@app.command()
def ingest(owner: Annotated[str, typer.Option(help="Enron mailbox id of the brain's owner")] = settings.owner,
           source: Annotated[str, typer.Option(help="'enron' (a mailbox) or 'qmsum' (AMI product-team "
                                                    "meetings)")] = "enron") -> None:
    """Load the owner's mailbox from the Enron parquet files, or product-team meetings from QMSum, into the brain."""
    t0 = time.monotonic()
    if source == "qmsum":
        from .sources import qmsum

        messages = [s for m in qmsum.read_meetings(settings.qmsum_dir) if m.is_ami for s in qmsum.segments(m)]
        addrs, kind = set(), "meeting"
    elif source == "enron":
        messages = enron.read_mailbox(settings.enron_dir, owner)
        addrs, kind = enron.owner_addresses(messages), "email"
    else:
        raise typer.BadParameter(f"unknown source {source!r}")
    if not messages:
        raise typer.BadParameter(f"nothing to ingest from {source}")
    with connect(settings.database_url) as conn:
        stats = ingest_messages(conn, messages, addrs, source, kind)
        conn.commit()
        idx.refresh_stats(conn)
    if addrs:
        console.print(f"owner addresses: {', '.join(sorted(addrs))}")
    console.print(f"{stats.messages} files -> {stats.new_items} new items, {stats.new_refs} new refs, "
                  f"{stats.chunks} chunks in {time.monotonic() - t0:.1f}s")


@app.command()
def rederive() -> None:
    """Re-split stored items with the current parser (after a parser change); ids are kept, changed items'
    chunks are rebuilt. Run `engram index` afterwards to embed them."""
    from .store import rederive as run

    with connect(settings.database_url) as conn:
        n = run(conn)
        conn.commit()
        idx.refresh_stats(conn)
    console.print(f"{n} items re-derived")


@app.command()
def index(batch: Annotated[int, typer.Option(help="chunks per embedding call")] = 32) -> None:
    """Embed chunks that have no vector yet, then make sure the vector index exists."""
    with Ollama(settings.ollama_url) as llm, connect(settings.database_url) as conn:
        todo = conn.execute("SELECT count(*) AS n FROM chunks WHERE embedding IS NULL").fetchone()["n"]
        t0 = time.monotonic()

        def progress(done: int) -> None:
            rate = done / max(time.monotonic() - t0, 1e-9)
            console.print(f"\r{done}/{todo} chunks  {rate:.1f}/s", end="")

        n = idx.embed_pending(conn, lambda texts: llm.embed(settings.embed_model, texts), batch, progress,
                              settings.embed_model)
        console.print(f"\nembedded {n} chunks in {time.monotonic() - t0:.1f}s")
        idx.ensure_ann_index(conn)
        idx.refresh_stats(conn)


@app.command()
def search(query: str, k: Annotated[int, typer.Option("--k", "-k", help="number of results")] = 8,
           since: Day = None, until: Day = None,
           person: Annotated[list[str] | None, typer.Option("--person", "-p",
                                                            help="address fragment; repeatable")] = None,
           direction: Annotated[str | None, typer.Option(help="'in' (received) or 'out' (sent)")] = None,
           keywords_only: Annotated[bool, typer.Option(help="skip the embedding model")] = False) -> None:
    """Hybrid search over the owner's items."""
    t0 = time.monotonic()
    with (nullcontext() if keywords_only else Ollama(settings.ollama_url)) as llm, \
            connect(settings.database_url) as conn:
        embed = None if llm is None else (lambda texts: llm.embed(settings.embed_model, texts))
        hits = idx.search(conn, embed, query, k, since=since, until=until, people=person or (), direction=direction)
    table = Table(title=f"{len(hits)} results in {(time.monotonic() - t0) * 1000:.0f} ms")
    for col in ("date", "from", "subject", "text", "why"):
        table.add_column(col, overflow="fold")
    for h in hits:
        table.add_row(f"{h.sent_at:%Y-%m-%d}" if h.sent_at else "", h.from_addr, h.subject,
                      h.text[:240].replace("\n", " "), ", ".join(h.why))
    console.print(table)


@app.command("ask")
def ask_cmd(question: str, k: Annotated[int, typer.Option("--k", "-k", help="items to retrieve")] = 10,
            since: Day = None, until: Day = None,
            person: Annotated[list[str] | None, typer.Option("--person", "-p", help="address fragment")] = None,
            ) -> None:
    """Answer from the brain, citing items; the judge checks the answer against what it cites."""
    from .ask import ask
    from .judge import Judge, OllamaScorer

    t0 = time.monotonic()
    with Ollama(settings.ollama_url) as llm, connect(settings.database_url) as conn, \
            Judge(settings.database_url, _scorer(settings.judge_model or settings.s1_model),
                  OllamaScorer(settings.ollama_url, settings.s2_model)) as judge:
        r = ask(conn, judge, llm, settings.s2_model, lambda texts: llm.embed(settings.embed_model, texts), question,
                k, since=since, until=until, people=person or (), draft=settings.draft_model)
        cited = conn.execute("SELECT id, sent_at, from_addr, subject FROM items WHERE id = ANY(%s)",
                             (list(r.cites),)).fetchall()
    s = r.support
    sure = "no citation" if s is None else (f"supported (p={s.p:.2f}, {s.tier})" if s.settled and s.value == "yes"
                                            else f"NOT supported (p={s.p:.2f}, {s.tier})" if s.settled
                                            else f"unsure (p(yes)={s.probs['yes']:.2f}) - check the sources")
    console.print(f"[bold]{r.answer}[/]\n{sure}; {len(r.kept)}/{len(r.considered)} retrieved items kept; "
                  f"{time.monotonic() - t0:.1f}s")
    for c in cited:
        when = f"{c['sent_at']:%Y-%m-%d}" if c["sent_at"] else "undated"
        console.print(f"  item {c['id']}: {when} {c['from_addr']} - {c['subject']}")


@app.command("eval-qa")
def eval_qa(n: Annotated[int, typer.Option(help="benchmark questions to sample")] = 100,
            draft: Annotated[str | None, typer.Option(help="a small model that answers first (default: "
                                                           "ENGRAM_DRAFT_MODEL)")] = None,
            out: Annotated[str, typer.Option(help="JSONL of every question, answer and grade")]
            = "data/results/qa.jsonl", seed: int = 0) -> None:
    """Answer the owner's held-out EnronQA questions with `ask` and grade them against the references."""
    import json
    import random
    from pathlib import Path

    from .evaluate import qa
    from .judge import Judge, OllamaScorer
    from .sources.enronqa import read_qa

    s2 = OllamaScorer(settings.ollama_url, settings.s2_model)
    t0 = time.monotonic()
    with Ollama(settings.ollama_url) as llm, connect(settings.database_url) as conn, \
            Judge(settings.database_url, None, s2) as grader, \
            Judge(settings.database_url, _scorer(settings.judge_model or settings.s1_model), s2) as judge:
        report, rows = qa(conn, judge, grader, llm, settings.s2_model,
                          lambda texts: llm.embed(settings.embed_model, texts),
                          read_qa(settings.enronqa_dir, settings.owner), n, random.Random(seed),
                          draft or settings.draft_model)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text("".join(json.dumps(r) + "\n" for r in rows))
    console.print_json(json.dumps(report))
    console.print(f"in {time.monotonic() - t0:.0f}s")


judge_app = typer.Typer(no_args_is_help=True, help="System 1 judge: evaluate and calibrate, verify the ledger.")
finetune_app = typer.Typer(no_args_is_help=True, help="Fine-tune the personal System 1 judge (MLX LoRA).")
app.add_typer(judge_app, name="judge")
app.add_typer(finetune_app, name="finetune")
DECISIONS = ("supported", "relevant", "replied", "filed", "remember", "meeting_request", "fulfilled", "contradicts",
             "todo")
DERIVED = ("remember", "meeting_request", "fulfilled", "contradicts", "todo")   # adapter v2: team-checked


def _examples(decision: str, n: int, seed: int, human_only: bool = False):
    """Labelled examples for one decision type: from the benchmark, the owner's behaviour, or (adapter v2's
    decisions) derived labels the team checked on /label."""
    import random

    from . import derive, labels
    from .sources.enronqa import read_qa

    rng = random.Random(seed)
    with connect(settings.database_url) as conn:
        if decision in DERIVED:
            examples = derive.examples(conn, decision, human_only)
            if decision == "remember":                      # plus the owner's Obsidian verdicts on the gate
                from .memory import REMEMBER

                seen = {e.subject for e in examples} | {f"item:{i}" for i in derive.gold_items(
                    settings.data_dir / "results" / "remember-gold.json")}     # the gold set stays evaluation-only
                examples += [e for e in labels.stored(conn, REMEMBER, ("human",)) if e.subject not in seen]
            examples = [e for e in examples if e.label in ("yes", "no")]
            return rng.sample(examples, min(n, len(examples)))
        if decision in ("supported", "relevant"):
            return getattr(labels, decision)(conn, read_qa(settings.enronqa_dir, settings.owner), n, rng)
        if decision in ("replied", "filed"):
            return getattr(labels, decision)(conn, n, rng)
    raise typer.BadParameter(f"unknown decision {decision!r}; one of {', '.join(DECISIONS)}")


def _scorer(spec: str):
    from .judge import make_scorer

    return make_scorer(spec, settings.ollama_url)


@judge_app.command("eval")
def judge_eval(decision: Annotated[str, typer.Argument(help=" | ".join(DECISIONS))],
               n: Annotated[int, typer.Option(help="labelled examples (balanced)")] = 200,
               s1: Annotated[str, typer.Option(help="System 1: an Ollama model or mlx:<path>[@<adapter>]")] = "",
               s2: Annotated[bool, typer.Option(help="also run System 2 and the cascade")] = True,
               test_only: Annotated[bool, typer.Option(help="only items in the fine-tuning test split")] = False,
               human_only: Annotated[bool, typer.Option(help="only examples the team checked (v2 decisions)")] = False,
               target: Annotated[float, typer.Option(help="precision each settled side must keep")] = 0.95,
               seed: int = 0) -> None:
    """Score labelled examples with S1 (and S2), fit calibration, report accuracy and the cascade."""
    import json

    from .evaluate import evaluate
    from .finetune import split_of

    examples = _examples(decision, n, seed, human_only)
    if test_only:
        examples = [e for e in examples if split_of(e.group) == "test"]
    scorers = [("S1", _scorer(s1 or settings.s1_model))]
    if s2:
        scorers.append(("S2", _scorer(settings.s2_model)))
    t0 = time.monotonic()
    report = evaluate(settings.database_url, examples, scorers, target)
    console.print_json(json.dumps(report))
    console.print(f"{len(examples)} examples in {time.monotonic() - t0:.0f}s")


@app.command("plan")
def plan(day: Annotated[datetime, typer.Argument(formats=["%Y-%m-%d"], help="the day to plan")],
         now: Annotated[str | None, typer.Option(help="re-plan at this local time (HH:MM): marks what was missed; "
                                                      "for a demo, fast-forward the clock")] = None) -> None:
    """Plan the owner's day from their open commitments and today's meetings (OR-Tools CP-SAT), or re-plan it."""
    from datetime import time as dtime
    from zoneinfo import ZoneInfo

    from .judge import Judge, OllamaScorer, make_scorer
    from .planner import owner_names, plan_day

    tz = settings.owner_timezone
    at = datetime.combine(day.date(), dtime.fromisoformat(now), ZoneInfo(tz)) if now else None
    s1 = make_scorer(settings.judge_model or settings.s1_model, settings.ollama_url)
    s2 = OllamaScorer(settings.ollama_url, settings.s2_model)
    with connect(settings.database_url) as conn, Judge(settings.database_url, s1, s2) as judge:
        version, entries = plan_day(conn, day.date(), tz, owner_names(conn, settings.owner), at, judge)
    console.print(f"[bold]{day:%A %d %B %Y}[/], plan v{version}" + (f" (re-planned at {now})" if now else ""))
    for e in entries:
        when = f"{e.starts.astimezone(ZoneInfo(tz)):%H:%M}-{e.ends.astimezone(ZoneInfo(tz)):%H:%M}" if e.starts \
            else "  --:--  "
        mark = {"done": "[green]done[/]", "missed": "[red]missed[/]", "bumped": "[yellow]bumped[/]"}.get(e.status, "")
        title = e.task.title if len(e.task.title) <= 64 else e.task.title[:63] + "…"
        console.print(f"  {when}  {title:<64} {mark} [dim]{'; '.join(e.task.why)}[/]", soft_wrap=True)


label_app = typer.Typer(no_args_is_help=True, help="Adapter v2's labels: derive them, then the team checks them.")
app.add_typer(label_app, name="label")


@label_app.command("queue")
def label_queue(n: Annotated[int, typer.Option(help="examples per decision (balanced where the data allows)")] = 300,
                seed: int = 0) -> None:
    """Derive labels for remember, meeting_request, fulfilled and contradicts from the brain's own structure, queue
    the owner's commitments for `todo`, and send them all to the team's check at http://127.0.0.1:8770/label."""
    import random

    from . import derive

    with connect(settings.database_url) as conn:
        added = derive.queue(conn, n, random.Random(seed), derive.gold_items(settings.data_dir / "results" /
                                                                             "remember-gold.json"), settings.owner)
        report = derive.agreement(conn)
    for name, k in added.items():
        console.print(f"{name:>16}: +{k:<4d} queued {report.get(name, {}).get('queued', 0)}")


@label_app.command("report")
def label_report() -> None:
    """How many the team has checked per decision, and how often the derived label was right."""
    import json

    from . import derive

    with connect(settings.database_url) as conn:
        console.print_json(json.dumps(derive.agreement(conn)))


@judge_app.command("teach")
def judge_teach(n: Annotated[int, typer.Option(help="items to label")] = 600, seed: int = 0) -> None:
    """Teacher labels for the memory gate: the large model answers `remember` for a random sample of items."""
    import random

    from .judge import Judge, OllamaScorer
    from .labels import teach
    from .memory import REMEMBER

    t0 = time.monotonic()
    with connect(settings.database_url) as conn, \
            Judge(settings.database_url, None, OllamaScorer(settings.ollama_url, settings.s2_model)) as judge:
        added = teach(conn, judge, REMEMBER, n, random.Random(seed),
                      lambda k: console.print(f"\r{k} labelled  {time.monotonic() - t0:.0f}s", end=""))
        dist = conn.execute("SELECT value, count(*) AS n FROM labels WHERE question = 'remember' GROUP BY value"
                            ).fetchall()
    console.print(f"\n{added} teacher labels; now " + ", ".join(f"{r['value']}: {r['n']}" for r in dist))


@finetune_app.command("data")
def finetune_data(out: Annotated[str, typer.Option(help="output directory")] = "data/finetune/v1",
                  n: Annotated[int, typer.Option(help="examples per decision type")] = 1500,
                  decisions: Annotated[str, typer.Option(help="comma-separated (default: all)")] = "",
                  checked_only: Annotated[bool, typer.Option(help="v2 decisions: only checked labels (team or "
                                                                  "assistant), not the derived ones")] = True,
                  repeat: Annotated[int, typer.Option(help="how often v2 decisions' training rows are shown")] = 1,
                  seed: int = 0) -> None:
    """Build train/valid/test JSONL from the labelled decision types, split by conversation."""
    from pathlib import Path

    from .finetune import write_dataset

    chosen = [d for d in (decisions.split(",") if decisions else DECISIONS) if d]
    unknown = set(chosen) - set(DECISIONS)
    if unknown:
        raise typer.BadParameter(f"unknown decisions: {', '.join(sorted(unknown))}")
    examples = [e for d in chosen for e in _examples(d, n, seed, checked_only and d in DERIVED)]
    counts = write_dataset(examples, Path(out), seed, {d: repeat for d in DERIVED})
    for split, c in counts.items():
        console.print(f"{split:>5}: {sum(c.values()):5d}  " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())))


@finetune_app.command("train")
def finetune_train(data: Annotated[str, typer.Option(help="dataset directory")] = "data/finetune/v1",
                   adapter: Annotated[str, typer.Option(help="where to write the adapter")] = "data/adapters/v1",
                   base: Annotated[str, typer.Option(help="MLX checkpoint")] = "mlx-community/Qwen3-1.7B-bf16",
                   iters: int = 1000, batch_size: int = 4, learning_rate: float = 1e-4,
                   accumulate: Annotated[int, typer.Option(help="gradient accumulation steps (less peak memory)")]
                   = 1,
                   resume: Annotated[str, typer.Option(help="continue from this adapter checkpoint")] = "") -> None:
    """LoRA-train the judge on the dataset (loss on the answer only)."""
    from pathlib import Path

    from .finetune import train

    t0 = time.monotonic()
    train(base, Path(data), Path(adapter), iters, batch_size, learning_rate, accumulate=accumulate,
          resume=Path(resume) if resume else None)
    console.print(f"adapter written to {adapter} in {time.monotonic() - t0:.0f}s")


@app.command("eval-retrieval")
def eval_retrieval(n: Annotated[int, typer.Option(help="benchmark questions to sample")] = 500,
                   seed: int = 0) -> None:
    """Recall@k and MRR of keyword, meaning and hybrid search on the owner's EnronQA questions."""
    import json
    import random

    from .evaluate import retrieval
    from .sources.enronqa import read_qa

    t0 = time.monotonic()
    with Ollama(settings.ollama_url) as llm, connect(settings.database_url) as conn:
        report = retrieval(conn, lambda texts: llm.embed(settings.embed_model, texts),
                           read_qa(settings.enronqa_dir, settings.owner), n, random.Random(seed))
    console.print_json(json.dumps(report))
    console.print(f"in {time.monotonic() - t0:.0f}s")


@judge_app.command("verify")
def judge_verify() -> None:
    """Check the ledger's hash chain."""
    from .judge import verify_ledger

    with connect(settings.database_url) as conn:
        bad = verify_ledger(conn)
        n = conn.execute("SELECT count(*) AS n FROM judgements").fetchone()["n"]
    console.print(f"ledger intact ({n} judgements)" if bad is None else f"ledger broken at judgement {bad}")
    if bad is not None:
        raise typer.Exit(1)


memory_app = typer.Typer(no_args_is_help=True, help="Memory: commitments, decisions and meetings.")
app.add_typer(memory_app, name="memory")


@memory_app.command("build")
def memory_build(since: Day = None, until: Day = None,
                 limit: Annotated[int | None, typer.Option(help="at most this many items")] = None) -> None:
    """Read items not yet scanned and record the beliefs they hold (gate with S1, extract with S2)."""
    from .judge import Judge, OllamaScorer
    from .memory import build

    s1, s2 = _scorer(settings.judge_model or settings.s1_model), OllamaScorer(settings.ollama_url, settings.s2_model)
    t0 = time.monotonic()

    def progress(s) -> None:
        console.print(f"\r{s.scanned} items  bulk {s.bulk}  passed {s.passed}  beliefs {s.beliefs}  "
                      f"superseded {s.superseded}  fulfilled {s.fulfilled}  contradicts {s.contradictions}  "
                      f"unquoted {s.unquoted}  {s.scanned / max(time.monotonic() - t0, 1e-9):.2f} items/s", end="")

    with Ollama(settings.ollama_url) as llm, connect(settings.database_url) as conn, \
            Judge(settings.database_url, s1, s2) as judge:
        me = conn.execute("SELECT name FROM people WHERE 'owner' = ANY(aliases)").fetchone()   # a name, not an id
        stats = build(conn, judge, llm, settings.s2_model, me["name"] if me else settings.owner,
                      settings.owner_timezone, since, until, limit, progress)
        from .vault import queue_review, sync

        closest = sorted(stats.unsure, key=lambda r: abs(r["p"] - 0.35))[:10]   # the most borderline, at most 10
        queued = queue_review(conn, settings.vault_dir, closest)                  # the owner's verdicts train the gate
        sync(conn, settings.vault_dir)
    console.print(f"\n{stats.scanned} items: {stats.bulk} bulk, {stats.passed} to extraction, {stats.beliefs} beliefs "
                  f"in {time.monotonic() - t0:.0f}s; {queued} unsure items queued for review in {settings.vault_dir}")


@memory_app.command("show")
def memory_show(kind: Annotated[str | None, typer.Option(help="commitment | decision | meeting")] = None,
                person: Annotated[str | None, typer.Option("--person", "-p", help="actor or other contains")] = None,
                since: Day = None, until: Day = None, k: Annotated[int, typer.Option("--k", "-k")] = 20) -> None:
    """What the brain currently believes, newest first."""
    with connect(settings.database_url) as conn:
        rows = conn.execute(
            "SELECT kind, actor, other, statement, when_text, due_at, confidence, sent_at, supersedes "
            "FROM current_beliefs WHERE (%(kind)s::text IS NULL OR kind = %(kind)s) "
            "AND (%(p)s::text IS NULL OR actor LIKE %(p)s OR other LIKE %(p)s) "
            "AND (%(since)s::timestamptz IS NULL OR sent_at >= %(since)s) "
            "AND (%(until)s::timestamptz IS NULL OR sent_at < %(until)s) ORDER BY sent_at DESC LIMIT %(k)s",
            {"kind": kind, "p": f"%{person.lower()}%" if person else None, "since": since, "until": until,
             "k": k}).fetchall()
    table = Table(title=f"{len(rows)} beliefs")
    for col in ("from", "kind", "actor", "other", "statement", "when", "due (UTC)", "p"):
        table.add_column(col, overflow="fold")
    for r in rows:
        table.add_row(f"{r['sent_at']:%Y-%m-%d}" if r["sent_at"] else "undated",
                      r["kind"] + (" ↺" if r["supersedes"] else ""), r["actor"],
                      r["other"], r["statement"], r["when_text"], f"{r['due_at']:%Y-%m-%d %H:%M}" if r["due_at"]
                      else "", f"{r['confidence']:.2f}")
    console.print(table)


agent_app = typer.Typer(no_args_is_help=True, help="Act: a local agent whose every state change passes the gate.")
app.add_typer(agent_app, name="agent")


@agent_app.command("run")
def agent_run(request: str,
              domain: Annotated[list[str] | None, typer.Option("--domain", "-d", help="WorkBench toolkit; "
                                                               "repeatable (default: all)")] = None,
              autonomy: Annotated[int, typer.Option(help="highest tier run without asking: 0 read, 1 internal, "
                                                         "2 external, 3 destructive")] = 1,
              think: Annotated[bool, typer.Option(help="let the model reason before each call")] = False) -> None:
    """Carry out one request in the WorkBench sandbox; you approve what the gate escalates."""
    from .act import TIER, Gate, describe
    from .agent import run
    from .judge import Judge, OllamaScorer
    from .sources import workbench as wb

    def approve(request: str, tool, args: dict, verdict) -> bool:
        judged = "" if verdict is None else (f"  [dim](intent check: {verdict.value or 'invalid'}, p={verdict.p:.2f}"
                                             f"{'' if verdict.settled else ', unsure'})[/]")
        console.print(f"[bold]{tool.effect}[/] {describe(tool, args)}{judged}")
        try:
            return typer.confirm("approve?", default=False)
        except typer.Abort:                             # no answer (input closed): no
            return False

    with Ollama(settings.ollama_url) as llm, wb.sandbox(settings.workbench_dir), \
            Judge(settings.database_url, None, OllamaScorer(settings.ollama_url, settings.s2_model)) as judge:
        r = run(llm, settings.s2_model, wb.SYSTEM, request, wb.tools(tuple(domain) if domain else None),
                Gate(judge, approve, autonomy), f"act:{datetime.now():%Y%m%dT%H%M%S}", think)
    table = Table(title=f"{len(r.steps)} calls in {r.turns} turns")
    for col in ("call", "tier", "gate", "p(intent)", "result"):
        table.add_column(col, overflow="fold")
    tiers = {v: k for k, v in TIER.items()}
    for s in r.steps:
        c = s.check
        table.add_row(f"{s.tool}({', '.join(f'{k}={v!r}' for k, v in s.args.items())})",
                      tiers.get(c.tier, "blocked") if c else "", c.reason if c else "",
                      f"{c.verdict.probs['yes']:.2f}" if c and c.verdict else "", s.observation[:200])
    console.print(table)
    console.print(r.answer if r.answer is not None else "[red]stopped at the turn limit[/]")


diplomat_app = typer.Typer(no_args_is_help=True, help="Diplomat: agree a meeting time with another secretary.")
app.add_typer(diplomat_app, name="diplomat")


def _console_approver(yes: bool):
    from .act import describe

    def approve(request: str, tool, args: dict, verdict) -> bool:
        console.print(f"[bold]{tool.effect}[/] {describe(tool, args)}")
        if yes:
            return True
        try:
            return typer.confirm("approve?", default=False)
        except typer.Abort:
            return False
    return approve


@diplomat_app.command("peer")
def diplomat_peer(name: Annotated[str, typer.Option(help="this secretary's owner")] = "bob",
                  port: Annotated[int, typer.Option(help="port on 127.0.0.1")] = 8790,
                  token: Annotated[str, typer.Option(help="the shared token (default: the one for this name "
                                                          "in data/diplomat/peers.json)")] = "",
                  yes: Annotated[bool, typer.Option(help="the owner approves everything (a demo)")] = False) -> None:
    """Run the other company's secretary: a demo owner whose calendar is busy most of Thursday and Friday
    morning. It answers each proposal through its own owner's approval."""
    import threading
    from datetime import timedelta

    from .act import Gate
    from .diplomat import Side, peers, serve_peer
    from .meeting import WB_NOW, Event

    token = token or peers(settings.diplomat_peers).get(name, {}).get("token", "")
    if len(token) < 16:
        raise typer.BadParameter("give a shared --token of at least 16 characters")
    day = WB_NOW.replace(hour=0, minute=0)
    busy = [Event(day + timedelta(hours=10), 120, "busy"), Event(day + timedelta(hours=14), 240, "busy"),
            Event(day + timedelta(days=1, hours=9), 180, "busy")]
    side = Side(name, busy, Gate(None, _console_approver(yes)), WB_NOW)
    server = serve_peer(side, token, port)
    console.print(f"{name}'s secretary on http://127.0.0.1:{port}/diplomat  (Ctrl-C stops)")
    try:
        seen = 0
        threading.Thread(target=server.serve_forever, daemon=True).start()
        while True:
            time.sleep(0.5)
            for line in side.log[seen:]:
                console.print(f"  {line}", markup=False)
            seen = len(side.log)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()


@diplomat_app.command("meet")
def diplomat_meet(peer: Annotated[str, typer.Argument(help="a secretary in data/diplomat/peers.json")],
                  topic: Annotated[str, typer.Option(help="what it is about (no contact details)")] = "meeting",
                  minutes: int = 30,
                  yes: Annotated[bool, typer.Option(help="approve without asking (a demo run)")] = False) -> None:
    """Agree a meeting time with another secretary. You approve every message before it leaves, and the booking."""
    from . import diplomat as dp
    from . import meeting as mt
    from .act import Gate
    from .judge import Judge, OllamaScorer
    from .sources import workbench as wb

    known = dp.peers(settings.diplomat_peers)
    if peer not in known:
        raise typer.BadParameter(f"unknown secretary {peer!r}; add it to {settings.diplomat_peers}")
    with wb.sandbox(settings.workbench_dir), \
            Judge(settings.database_url, None, OllamaScorer(settings.ollama_url, settings.s2_model)) as intent:
        me = dp.Side("me", mt.wb_calendar(), Gate(intent, _console_approver(yes)), mt.WB_NOW)
        create = {t.name: t for t in wb.tools(("calendar",))}["calendar.create_event"].run
        got = dp.negotiate(me, peer, dp.poster(known[peer]["url"], known[peer]["token"], settings.owner), topic,
                           minutes, create)
    for line in me.log:
        console.print(f"  {line}", markup=False)
    console.print(f"[bold]Agreed: {mt.when(got)}[/]" if got else "[yellow]No time agreed[/]")


@app.command("meeting")
def meeting_reply(email_id: Annotated[str | None, typer.Argument(help="a WorkBench inbox email id")] = None,
                  sender: Annotated[str | None, typer.Option("--from", help="or: a new email's sender")] = None,
                  subject: Annotated[str, typer.Option(help="the new email's subject")] = "Meeting",
                  body: Annotated[str | None, typer.Option(help="the new email's text")] = None,
                  yes: Annotated[bool, typer.Option(help="approve without asking (a demo run)")] = False) -> None:
    """Feature 2: answer a meeting request in the WorkBench sandbox. The roles decide, find the time, draft and
    check the reply; you approve the reply and the calendar event."""
    from . import meeting as mt
    from .act import Gate, describe
    from .judge import Judge, OllamaScorer, make_scorer
    from .sources import workbench as wb

    if not email_id and not (sender and body):
        raise typer.BadParameter("give an email id, or --from and --body")

    def approve(request: str, tool, args: dict, verdict) -> bool:
        console.print(f"[bold]{tool.effect}[/] {describe(tool, args)}")
        if yes:
            return True
        try:
            return typer.confirm("approve?", default=False)
        except typer.Abort:
            return False

    s1 = make_scorer(settings.judge_model or settings.s1_model, settings.ollama_url)
    s2 = OllamaScorer(settings.ollama_url, settings.s2_model)
    with Ollama(settings.ollama_url) as llm, wb.sandbox(settings.workbench_dir), \
            Judge(settings.database_url, s1, s2) as judge, Judge(settings.database_url, None, s2) as intent:
        email = mt.wb_email(email_id) if email_id else mt.wb_add_email(sender, subject, body, mt.WB_NOW)
        console.print(f"[dim]{email.sender} · {email.subject} · {email.sent:%a %d %b %H:%M}[/]\n{email.body}\n")
        pr = mt.propose(email, judge, llm, settings.s2_model, mt.wb_calendar(), mt.WB_NOW,
                        mt.wb_contacts(email.sender))
        for st in pr.steps:
            console.print(f"  [bold]{st.role:<12}[/] {st.what} [dim]{st.ms:.0f} ms[/]")
        if pr.reply:
            console.print(f"\n[bold]{pr.headline}[/]\n{pr.reply}\n")
        tools = {t.name: t for t in wb.tools(("email", "calendar"))}
        for name, check, result in mt.carry_out(pr, tools, Gate(intent, approve), f"meeting:{email.email_id}"):
            console.print(f"  {name}: {check.reason}" + (f" → {result}" if check.allowed else ""))


@agent_app.command("eval")
def agent_eval(per_domain: Annotated[int, typer.Option(help="tasks from each WorkBench task file")] = 10,
               think: Annotated[bool, typer.Option(help="let the model reason before each call")] = False,
               out: Annotated[str, typer.Option(help="JSONL of every task's calls and grades")]
               = "data/results/workbench.jsonl",
               skip: Annotated[str | None, typer.Option(help="an earlier run's JSONL: leave its tasks out, for a "
                                                             "fresh test set")] = None,
               seed: int = 0) -> None:
    """Run the agent on WorkBench tasks and grade each gate policy: correct, harmful side effects, owner prompts."""
    import json
    import random
    from pathlib import Path

    from .evaluate import agent_benchmark
    from .judge import Judge, OllamaScorer
    from .sources import workbench as wb

    seen = {json.loads(line)["task"] for line in Path(skip).read_text().splitlines()} if skip else set()
    tasks = wb.sample([t for t in wb.tasks(settings.workbench_dir) if t.id not in seen], per_domain,
                      random.Random(seed))
    path = Path(out).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    with Ollama(settings.ollama_url) as llm, path.open("w") as f, wb.sandbox(settings.workbench_dir), \
            Judge(settings.database_url, None, OllamaScorer(settings.ollama_url, settings.s2_model)) as judge:

        def progress(row: dict) -> None:
            f.write(json.dumps(row, default=str) + "\n")
            f.flush()
            ok = row["policies"]["no gate"]
            console.print(f"{row['task']:<40} correct={ok['correct']!s:<5} harmful={ok['harmful']!s:<5} "
                          f"calls={len(row['calls'])} ({time.monotonic() - t0:.0f}s)")

        report, _ = agent_benchmark(llm, settings.s2_model, judge, tasks, think, progress)
    console.print_json(json.dumps(report))
    console.print(f"{len(tasks)} tasks in {time.monotonic() - t0:.0f}s; calls and grades in {out}")


vault_app = typer.Typer(no_args_is_help=True, help="Obsidian: the brain's memory as an editable vault.")
app.add_typer(vault_app, name="vault")


@vault_app.command("sync")
def vault_sync(path: Annotated[str | None, typer.Option(help="vault folder (default: data/vault/<brain>)")] = None
               ) -> None:
    """Read the owner's edits from the vault into the brain, then write the brain's current beliefs to it."""
    from pathlib import Path

    from .vault import sync

    target = Path(path) if path else settings.vault_dir
    with connect(settings.database_url) as conn:
        s = sync(conn, target)
    console.print(f"{target}\n  from Obsidian: {s.edited} edited, {s.status_changed} status changes, {s.deleted} "
                  f"deleted, {s.created} new beliefs, {s.reviewed} review verdicts, {s.notes} notes ingested\n"
                  f"  to Obsidian: {s.written} beliefs written, {s.removed} removed")


def _brain(llm: Ollama):
    """The brain as agent tools, with the owner's judge (made on first use) and the full `ask` pipeline."""
    from .ask import ask
    from .judge import Judge, OllamaScorer, make_scorer
    from .tools import Brain

    embed = lambda texts: llm.embed(settings.embed_model, texts)  # noqa: E731
    brain = Brain(settings.database_url, embed, lambda: Judge(
        settings.database_url, make_scorer(settings.judge_model or settings.s1_model, settings.ollama_url),
        OllamaScorer(settings.ollama_url, settings.s2_model)))

    def ask_fn(question: str) -> dict:
        with connect(settings.database_url) as conn:
            r = ask(conn, brain.judge, llm, settings.s2_model, embed, question, draft=settings.draft_model)
        s = r.support
        return {"answer": r.answer, "cited_ids": list(r.cites), "supported": None if s is None else s.value == "yes",
                "p": None if s is None else round(s.p, 3), "settled": bool(s and s.settled)}

    brain.ask_fn = ask_fn
    return brain


@app.command()
def mcp() -> None:
    """Serve the brain's tools over MCP (stdio), for Claude Code, Claude Desktop or any MCP client."""
    from .mcp import serve as run
    from .tools import tools

    with Ollama(settings.ollama_url) as llm:
        run(tools(_brain(llm)))


@agent_app.command("brain")
def agent_brain(question: str) -> None:
    """The small test agent: answer a question about the owner by using the brain's tools."""
    from .research import run

    t0 = time.monotonic()
    with Ollama(settings.ollama_url) as llm:
        r = run(llm, settings.s2_model, _brain(llm), question)
    console.print(f"[bold]{r.answer}[/]\ncites {list(r.cited_ids)} (judge-verified: {list(r.supported_ids)}); "
                  f"calls: {' -> '.join(r.calls)}; "
                  f"read ~{r.tool_tokens} tokens; {time.monotonic() - t0:.1f}s")


@app.command("eval-agent")
def eval_agent(n: Annotated[int, typer.Option(help="held-out EnronQA questions")] = 30,
               out: Annotated[str, typer.Option(help="JSONL of every run")] = "data/results/agent-qa.jsonl",
               seed: int = 0) -> None:
    """The test agent against `ask` on held-out EnronQA questions: accuracy, calls, tokens read, time."""
    import json
    import random
    from pathlib import Path

    from .evaluate import agent_qa
    from .judge import Judge, OllamaScorer
    from .sources.enronqa import read_qa

    t0 = time.monotonic()
    with Ollama(settings.ollama_url) as llm, connect(settings.database_url) as conn, \
            Judge(settings.database_url, None, OllamaScorer(settings.ollama_url, settings.s2_model)) as grader:
        report, rows = agent_qa(conn, _brain(llm), llm, settings.s2_model, grader,
                                read_qa(settings.enronqa_dir, settings.owner), n, random.Random(seed))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text("".join(json.dumps(r) + "\n" for r in rows))
    console.print_json(json.dumps(report))
    console.print(f"in {time.monotonic() - t0:.0f}s")


@app.command()
def people() -> None:
    """Rebuild people as entities (every address and name each person appears under)."""
    from .people import build

    with connect(settings.database_url) as conn:
        console.print(f"{build(conn, settings.owner)} people")


@app.command()
def serve(port: Annotated[int, typer.Option(help="port on 127.0.0.1")] = 8770,
          lan: Annotated[str | None, typer.Option(help="also serve the paired watch on the LAN: 'auto' (every "
                                                       "interface, so a new hotspot address keeps working) or one "
                                                       "address")] = None,
          lan_port: Annotated[int, typer.Option(help="the watch's port on the LAN address")] = 8771) -> None:
    """Open the brain in a local web page: ask, search, memory, the gated agent (approve in the page), the ledger."""
    from http.server import ThreadingHTTPServer

    from .serve import serve as run
    from .watch import Devices, lan_address

    address = None
    if lan:
        try:
            shown = lan_address(lan)
        except ValueError as e:
            raise typer.BadParameter(str(e), param_hint="--lan") from None
        address = ("0.0.0.0" if lan == "auto" else shown, lan_port)
    for host, p in [("127.0.0.1", port), *([address] if address else [])]:
        try:
            ThreadingHTTPServer((host, p), None).server_close()                 # is the port free?
        except OSError:
            console.print(f"[red]Port {p} on {host} is in use[/] — engram may already be running. Stop it, or "
                          f"pick another port.")
            raise typer.Exit(1) from None
    console.print(f"engram [{settings.database_url.rsplit('/', 1)[-1]}] on http://127.0.0.1:{port}  (Ctrl-C stops)")
    if address:
        _watch_code(Devices(settings.watch_file), f"http://{shown}:{lan_port} (announced over mDNS)")
    run(settings, port, address)


profile_app = typer.Typer(no_args_is_help=True, help="Profiles: the brains the local page can open, each with a "
                                                     "passphrase.")
app.add_typer(profile_app, name="profile")


@profile_app.command("add")
def profile_add(name: str,
                database: Annotated[str | None, typer.Option(help="the brain's database (default: NAME); an "
                                                                  "existing one is adopted")] = None,
                color: Annotated[str, typer.Option(help="avatar colour: s0, s1, s2 or h")] = "s1") -> None:
    """Let the page open a brain: a new database (created and migrated), or an existing one such as `engram`."""
    from psycopg.conninfo import make_conninfo

    from .profiles import Profiles

    passphrase = typer.prompt("Passphrase", hide_input=True, confirmation_prompt=True)
    profiles = Profiles(settings.profiles_file)
    try:
        profiles.check(name, passphrase, color)
        applied = run_migrations(make_conninfo(settings.database_url, dbname=database or name))
        profiles.add(name, passphrase, database, color)
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1) from None
    console.print(f"profile [bold]{name}[/] opens database {database or name}"
                  + (f" (applied: {', '.join(applied)})" if applied else ""))


@profile_app.command("list")
def profile_list() -> None:
    """The profiles and the databases they open."""
    from .profiles import Profiles

    for p in Profiles(settings.profiles_file).list() or [{"name": "(none)", "database": "", "color": ""}]:
        console.print(f"{p['name']:<24} {p['database']:<24} {p['color']}")


@profile_app.command("remove")
def profile_remove(name: str) -> None:
    """Forget a profile (its database is kept)."""
    from .profiles import Profiles

    if not Profiles(settings.profiles_file).remove(name):
        console.print(f"[red]no profile named {name!r}[/]")
        raise typer.Exit(1)
    console.print(f"removed {name}; its database is untouched")


herald_app = typer.Typer(no_args_is_help=True, help="Herald: what the roles send the owner's watch.")
app.add_typer(herald_app, name="herald")


@herald_app.command("sweep")
def herald_sweep(now: Annotated[datetime | None, typer.Option(formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"],
                                                              help="pretend it is this local time (demos)")] = None
                 ) -> None:
    """Post a card for everything the roles have for the owner (the server does this every minute)."""
    from datetime import UTC
    from zoneinfo import ZoneInfo

    from . import herald
    from .planner import owner_names

    tz = settings.herald_timezone or herald.local_timezone()
    at = now.replace(tzinfo=ZoneInfo(tz)) if now else datetime.now(UTC)
    with connect(settings.database_url) as conn:
        posted = herald.sweep(conn, at, tz, owner_names(conn, settings.owner))
    for c in posted:
        console.print(f"[bold]{c['route']:>6}[/]  {c['role']:<9} {c['title']}: {c['body'][:70]}  [dim]({c['why']})[/]")
    console.print(f"{len(posted)} new card(s)")


@herald_app.command("cards")
def herald_cards() -> None:
    """The open cards, as the watch sees them."""
    from datetime import UTC

    from . import herald

    with connect(settings.database_url) as conn:
        for c in herald.cards(conn, datetime.now(UTC)):
            actions = "/".join(a["id"] for a in c["actions"])
            console.print(f"{c['id']:>5} {c['route']:>6}  {c['role']:<9} {c['title']}: {c['body'][:60]}  [{actions}]")


watch_app = typer.Typer(no_args_is_help=True, help="The owner's watch: pair it, list it, forget it.")
app.add_typer(watch_app, name="watch")


def _watch_code(devices, url: str | None = None) -> None:
    from .watch import CODE_TTL

    where = f"watch: {url}  " if url else ""
    console.print(f"{where}pairing code [bold]{devices.new_code()}[/] (one use, {CODE_TTL / 60:.0f} min)")


@watch_app.command("pair")
def watch_pair() -> None:
    """A new one-time pairing code; enter it on the watch (while `engram serve --lan` runs)."""
    from .watch import Devices

    _watch_code(Devices(settings.watch_file))


@watch_app.command("devices")
def watch_devices() -> None:
    """The paired watches."""
    from .watch import Devices

    for d in Devices(settings.watch_file).list() or [{"name": "(none)", "paired_at": ""}]:
        console.print(f"{d['name']:<24} {d['paired_at']}")


@watch_app.command("forget")
def watch_forget(name: str) -> None:
    """Unpair a watch: its token stops working at once."""
    from .watch import Devices

    if not Devices(settings.watch_file).forget(name):
        console.print(f"[red]no paired watch named {name!r}[/]")
        raise typer.Exit(1)
    console.print(f"forgot {name}")


@app.command()
def stats() -> None:
    """What the brain holds."""
    with connect(settings.database_url) as conn:
        row = conn.execute(
            "SELECT (SELECT count(*) FROM items) AS items, (SELECT count(*) FROM item_refs) AS refs, "
            "(SELECT count(*) FROM items WHERE direction = 'out') AS sent, (SELECT count(*) FROM chunks) AS chunks, "
            "(SELECT count(*) FROM chunks WHERE embedding IS NOT NULL) AS embedded, "
            "(SELECT min(sent_at) FROM items) AS first, (SELECT max(sent_at) FROM items) AS last, "
            "pg_size_pretty(pg_database_size(current_database())) AS size").fetchone()
    for key, value in row.items():
        console.print(f"{key:>9}: {value}")
