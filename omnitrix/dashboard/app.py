"""The local dashboard (FastAPI): the agent log - every brain recall, live - and the Brain Map.

Local-only: `omnitrix dashboard` binds to 127.0.0.1, and every script and style is served from this package.
FastAPI's /docs and /redoc pages are switched off because they load Swagger/ReDoc from a CDN.
"""
from __future__ import annotations

import asyncio
import html
import json
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from omnitrix.config import get_settings
from omnitrix.core.clock import ClockStore
from omnitrix.core.db import Database

from . import recalls

STATIC = Path(__file__).with_name("static")
KEEPALIVE_S = 15


def create_app(db: Database | None = None, tz: ZoneInfo | None = None, workdir: Path | None = None) -> FastAPI:
    """Pass an open `db` in tests; otherwise the app opens (and closes) its own pool from the settings.
    `workdir` is where graphify writes graphify-out/ for the Brain Map (default: var/)."""
    settings = get_settings()
    tz = tz or settings.tz
    own_db = db is None
    db = db or Database(settings.database_url, max_size=4)
    feed = recalls.RecallFeed(db.url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if own_db:
            await db.open()
        try:
            yield
        finally:
            await feed.stop()
            if own_db:
                await db.close()

    app = FastAPI(title="Omnitrix dashboard", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    def when(value: str | None) -> datetime | None:
        """A filter time; without an offset it is read in the demo timezone."""
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            raise HTTPException(422, f"not a date-time: {value!r}") from None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=tz)

    # ------------------------------------------------------------------------------------------ pages

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    @app.get("/documents/{document_id}", response_class=HTMLResponse, include_in_schema=False)
    async def document_page(document_id: str, chunk: list[str] = Query(default=[])) -> HTMLResponse:
        doc = await recalls.get_document(db, tz, document_id)
        if doc is None:
            raise HTTPException(404, "document not found")
        return HTMLResponse(render_document(doc, set(chunk)))

    @app.get("/brain-map", response_class=HTMLResponse, include_in_schema=False)
    async def brain_map() -> HTMLResponse:
        from omnitrix.brain.graph_view import WORKDIR, export_graph_with_clusters, render_html
        return HTMLResponse(render_html(await export_graph_with_clusters(db, workdir or WORKDIR)))

    # -------------------------------------------------------------------------------------------- api

    @app.get("/api/meta")
    async def meta() -> dict:
        clock = await ClockStore(db).load(tz)
        now = clock.now()
        return {"timezone": str(tz), "demo_now": now.isoformat(), "demo_now_label": f"{now:%a %d %b %H:%M}",
                "clock_mode": clock.state.mode, **await recalls.agents_and_strategies(db)}

    @app.get("/api/recalls")
    async def list_recalls(agent: str | None = None, strategy: str | None = None, since: str | None = None,
                           until: str | None = None, before: str | None = None,
                           limit: int = Query(100, ge=1, le=500)) -> dict:
        items = await recalls.list_recalls(db, tz, agent=agent or None, strategy=strategy or None,
                                           since=when(since), until=when(until), before=before, limit=limit)
        return {"items": items, "has_more": len(items) == limit}

    @app.get("/api/recalls/stream")
    async def stream(request: Request) -> StreamingResponse:
        """Server-sent events: one `recall` event (the list-row summary) per new log entry."""
        async def events():
            queue = await feed.subscribe()
            try:
                yield "retry: 2000\n\n"
                while not await request.is_disconnected():
                    try:
                        recall_id = await asyncio.wait_for(queue.get(), KEEPALIVE_S)
                    except TimeoutError:
                        yield ": keep-alive\n\n"
                        continue
                    entry = await recalls.get_summary(db, tz, recall_id)
                    if entry:
                        yield f"id: {recall_id}\nevent: recall\ndata: {json.dumps(entry)}\n\n"
            finally:
                feed.unsubscribe(queue)
        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/recalls/{recall_id}")
    async def get_recall(recall_id: str) -> dict:
        entry = await recalls.get_recall(db, tz, recall_id)
        if entry is None:
            raise HTTPException(404, "log entry not found")
        return entry

    @app.get("/api/documents/{document_id}")
    async def get_document(document_id: str) -> dict:
        doc = await recalls.get_document(db, tz, document_id)
        if doc is None:
            raise HTTPException(404, "document not found")
        return doc

    app.state.db = db
    app.state.feed = feed
    return app


SOURCE_LABELS = {"demo_id": "demo id", "path": "vault", "filename": "file"}


def render_document(doc: dict, highlight: set[str]) -> str:
    """The full source document as the brain stores it, chunk by chunk, with the returned chunks marked."""
    e = html.escape
    facts = [f'<span class="tag">{e(doc["doc_type"])}</span>']
    if doc["source"]:
        facts.append(f'{SOURCE_LABELS.get(doc["source"]["kind"], doc["source"]["kind"])} '
                     f'<code>{e(doc["source"]["value"])}</code>')
    if doc["occurred_at"]:
        facts.append(e(doc["occurred_at"]))
    if doc["from"]:
        facts.append(f'from {e(doc["from"])}' + (f' &lt;{e(doc["from_addr"])}&gt;' if doc["from_addr"] else ""))
    if doc["parent"]:
        facts.append(f'attached to <a href="/documents/{e(doc["parent"]["id"])}">{e(doc["parent"]["title"])}</a>')
    if doc["chunks"]:
        body = "\n".join(
            f'<section class="doc-chunk{" hit" if c["id"] in highlight else ""}" id="{e(c["id"])}">'
            f'<div class="doc-chunk-label">chunk {c["position"] + 1}{" · returned" if c["id"] in highlight else ""}'
            f'</div><div class="doc-chunk-text">{e(c["text"])}</div></section>' for c in doc["chunks"])
    else:
        body = f'<section class="doc-chunk"><div class="doc-chunk-text">{e(doc["full_text"])}</div></section>'
    first = next((c["id"] for c in doc["chunks"] if c["id"] in highlight), None)
    scroll = (f'<script>document.getElementById({json.dumps(first)}).scrollIntoView({{block: "center"}})</script>'
              if first else "")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(doc["title"])} · Omnitrix</title><link rel="stylesheet" href="/static/dashboard.css"></head>
<body class="doc-page">
<header class="top"><a class="brand" href="/">Omnitrix <span>dashboard</span></a>
<nav><a href="/">Agent log</a></nav></header>
<main class="doc">
<h1>{e(doc["title"])}</h1>
<p class="doc-meta">{" · ".join(facts)}</p>
{body}
<details class="doc-raw"><summary>Original text as ingested</summary><pre>{e(doc["full_text"])}</pre></details>
</main>{scroll}
</body></html>"""
