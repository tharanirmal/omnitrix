# Prior work and third-party components

The hackathon rules ask every team to separate what existed before the event from what was built during it.

## Built before the hackathon

**society-of-agents** (our own project, commits from 22-23 Sep 2026): a five-agent software team on a DAG,
with a typed agent board, verification gates, lineage/resource recording and a dashboard.

- **Code reused so far: none.** Omnitrix's foundation (clock, formats, database schema, event bus, board,
  Ollama client, model queue, priority scoring, CLI) was written from scratch during the hackathon.
- **Ideas carried over:** agents talk only through a typed board; deterministic checks run before any model
  judgement; every model and tool call is recorded.
- If any society-of-agents code is copied in later, it will be listed here file by file, in a commit of its
  own, before it is changed.

## Built during the hackathon

Everything in this repository unless listed above.

## Third-party software (used, not written by us)

| Component | Licence | Use |
|---|---|---|
| Ollama | MIT | Runs the local models |
| Qwen3 14B / 4B (Alibaba) | Apache 2.0 | Open-weight models, run locally |
| bge-m3 (BAAI) | MIT | Embedding model, run locally |
| PostgreSQL + pgvector | PostgreSQL / PostgreSQL | Storage and vector search |
| Mailpit | MIT | Local mail server for the demo |
| ntfy | Apache 2.0 / GPLv2 | Self-hosted notifications to phone and watch |
| FastAPI, Starlette, Uvicorn | MIT / BSD-3 / BSD-3 | Local dashboard server |
| graphify (graphifyy) | Apache 2.0 | Clustering, hub nodes and cohesion for the Brain Map; run as a separate local tool, not copied into this repo |
| Python libraries | see `pyproject.toml` | pydantic, psycopg, httpx, typer, rich |

## Data

All demo data (people, companies, emails, notes) is fictional and written by the team. Email addresses use the
reserved `.example` domain. No real personal data is included.
