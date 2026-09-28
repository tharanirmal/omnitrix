# Omnitrix - a sovereign second brain

A team of local AI agents that works as a personal secretary: it reads your work, remembers it, builds your
to-do list and plans your day, re-plans when you miss something, keeps promises, drafts replies, and asks for
your approval on your smartwatch before anything leaves the machine. Every model runs on your own laptop.

MSRIT Hackathon, Track 1 (Sovereign AI). See [PRIOR_WORK.md](PRIOR_WORK.md) for what existed before the event.

> Status: **Phase 0 - foundation.** Agents arrive in the following phases.

## What Phase 0 contains

| Part | Where | What it does |
|---|---|---|
| Shared formats | `omnitrix/core/schemas.py`, `schemas/` | Event, Task Candidate, Task, Meeting Request, Approval Request, Board Message |
| Database | `migrations/001_init.sql` | Postgres + pgvector: knowledge, work, memory, agents, control |
| Event bus | `omnitrix/core/events.py` | Events stored in Postgres, LISTEN/NOTIFY wake-ups, no duplicates, retries, catch-up after restart |
| Agent board | `omnitrix/core/board.py` | Messages between agents (the agent chat room) |
| Demo clock | `omnitrix/core/clock.py` | One shared clock: real time, fast-forward, frozen |
| Local models | `omnitrix/llm/` | Ollama client, priority queue, forced-JSON output with a retry |
| Priority scoring | `omnitrix/planner/scoring.py` | Transparent 0-100 task score with reasons |
| CLI | `omnitrix/cli.py` | `doctor`, `db`, `clock`, `schemas`, `events`, `llm check`, `dashboard` |
| Dashboard | `omnitrix/dashboard/` | Local FastAPI page: live agent log of every brain recall, Brain Map |

## Setup (macOS, Apple Silicon)

1. **Docker Desktop** running, then start the local services (Postgres + pgvector, Mailpit, ntfy):

   ```bash
   docker compose up -d
   ```

2. **Ollama** installed from [ollama.com](https://ollama.com) and running, then pull the models (~14 GB):

   ```bash
   ./scripts/pull_models.sh
   ```

3. **Python** environment (uv installs Python 3.12 if needed) and the database:

   ```bash
   cp .env.example .env
   uv sync
   uv run omnitrix db migrate
   ```

4. Check everything:

   ```bash
   uv run omnitrix doctor
   uv run omnitrix llm check
   ```

## Demo data

A fictional businessman's week lives in [demo_data/](demo_data/) - see its README and
[scenarios.md](demo_data/scenarios.md) for the 16 planted scenarios.

```bash
uv run omnitrix demo reset --yes   # load the demo world, fill Mailpit, freeze the clock at Thu 8 Oct 08:55
uv run omnitrix clock jump 11:05   # move through the demo day
uv run omnitrix demo play          # deliver the live emails that are due by the demo clock
```

## The brain

Agents never read the whole dataset. `Brain.recall()` finds who and what a question is about, narrows the
search to the documents linked to them, runs meaning + keyword search inside that scope, adds structured
facts (relations, decisions, track records, upcoming meetings) and returns a small context pack.

```bash
uv run omnitrix brain ingest                 # inbox + vault + watched folder -> chunks, vectors, entity links
uv run omnitrix brain ask "What is blocking the revised quote for Rajesh Mehta?"
uv run omnitrix brain bench                  # 14 questions: scoped brain vs classic RAG vs keyword vs everything
uv run omnitrix brain scale --docs 2000      # add fictional look-alike documents, then bench again
uv run omnitrix brain scale --remove         # take them out again
uv run omnitrix brain graph --open           # Brain Map: offline page showing connections + what each question touched
uv run omnitrix brain graphify               # clusters, hub nodes and cohesion from graphify (var/graphify-out/)
```

The Brain Map groups the graph into **clusters** found by [graphify](https://github.com/Graphify-Labs/graphify)
(community detection on the brain's own people / project / document links): each cluster is coloured, outlined
and named after its best-connected project, organization or person; nodes are sized by how connected they are,
and the top hubs are always labelled. graphify runs as a separate tool (`uv tool install graphifyy`) on this
machine only - no model is called, and the map still works (coloured by type) without it. It re-runs only when
the graph has changed.

Benchmark on this laptop (M5 Pro), 2,044 documents (44 real + 2,000 look-alikes), top 5, 1,200-token budget:

| strategy | answered | source in top 5 | MRR | tokens / question | data searched |
|---|---|---|---|---|---|
| **scoped brain** | **100%** | **93%** | **0.79** | ~440 | **15% avg; under 1% for 11 of 14** |
| classic RAG (meaning search, everything) | 64% | 64% | 0.52 | ~290 | 100% |
| keyword search (everything) | 93% | 93% | 0.76 | ~360 | 100% |
| no retrieval (send everything) | - | - | - | 74,296 | 100% |

"Answered" counts a correct source in the top 5 or the correct decision / track-record fact.

## Dashboard

```bash
uv run omnitrix dashboard --open             # http://127.0.0.1:8000 - local only, nothing loaded from the internet
```

**Agent log** lists every question put to the brain (from `recall_log`), newest first by demo-clock time, with
filters for agent, strategy and time. Selecting one shows the entities recognised, how much of the brain was
searched, each returned chunk with its document, source id and the reasons it was picked, the facts added, and
the tokens and time it cost. Every returned chunk links to its full source document. A trigger on `recall_log`
sends a Postgres NOTIFY, so questions from `omnitrix brain ask`, the benchmark or any agent appear without
reloading. **Brain map** serves the graph page live instead of as a file, with graphify's clusters.

## Everyday commands

```bash
uv run omnitrix clock freeze 2026-10-08T08:55   # demo "today": Thu 8 Oct, 8:55 AM
uv run omnitrix clock jump 11:05                # fast-forward; publishes clock.jumped
uv run omnitrix clock reset                     # back to real time
uv run omnitrix events tail -f                  # watch the event bus live
uv run omnitrix events emit task.detected --payload '{"task_id": "task_1"}'
uv run omnitrix schemas export                  # write schemas/*.schema.json for the team
uv run pytest                                   # unit tests; event-bus tests need Postgres running
```

Local services: Mailpit inbox at http://localhost:8025, ntfy at http://localhost:8080.

## Architecture (target)

```
Inputs (Mailpit, folders, Obsidian, voice notes, calendar)
  -> ingestion -> agents (15) <-> event bus + board
  -> Guardian gateway (permissions, policies, approvals, audit) -> MCP tool servers
  -> Postgres + pgvector (+ Mem0)   |   Ollama: Qwen3 14B, Qwen3 4B, bge-m3
Outputs: Mailpit, Obsidian vault, calendar, dashboard, ntfy -> phone -> Galaxy Watch
```

## Rules the code follows

- Read the time only from the demo clock, never `datetime.now()`.
- Agents talk through events and the board; events are small, past-tense and never modified.
- AI is used for understanding and writing; ranking, scheduling and security checks are plain code.
- Nothing calls a cloud AI service.

## Licence

MIT - see [LICENSE](LICENSE).
