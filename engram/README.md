# engram — a sovereign second brain

engram turns one person's data into a brain they own: a Postgres database of what they received, wrote and decided,
searchable by keyword and meaning, with a small local model — fine-tuned on that person's own behaviour — making
the many small judgements a brain needs (*is this worth remembering? relevant? supported? same thing? would they
reply?*) in tens of milliseconds, and a larger local model taking only the cases it is unsure about. It answers
questions with citations it checks, and it acts only through a gate: code sets each action's risk, the large model
checks it against what the owner asked, and the owner approves the rest. Nothing calls a cloud service. Every
judgement is logged in a tamper-evident ledger that is also the training set.

Design and evidence: [`../docs/research/lit-review.md`](../docs/research/lit-review.md) (the literature review, cited
as LR § in the code) and [`../docs/research/brain-design.md`](../docs/research/brain-design.md).

## How it thinks

```
             S0  code            S1  small judge             S2  large model          H  the owner
 item  ──►  parse, dedupe,  ──►  one-token answer with  ──►  the uncertain middle ──►  what neither
            thread, time,        calibrated probability      band, and all writing     model settles
            permissions          (~30–70 ms)                 (~0.5–1 s per judgement)
                     └────────────── every judgement → hash-chained ledger (audit + cache + training data) ─┘
```

- **Data → Knowledge**: raw items are stored once (copies collapse, every original folder is kept); quoted history is
  split off; items are chunked with a who/when/subject header; keyword search is **BM25 in SQL**, meaning search is
  **pgvector HNSW on halfvec**, fused by weighted reciprocal rank.
- **Memory**: one-token gates decide which items hold commitments, decisions or meetings; one extraction call per
  such item; code rejects any quote not found verbatim in the item and resolves dates against the item's date;
  beliefs are bitemporal and superseded, never deleted.
- **Reasoning**: `ask` retrieves, lets the small judge drop what is surely irrelevant, has the large model answer
  with citations, then has the small judge check the answer against what it cites — System 1 checking System 2.
- **Action**: the agent (the large model, native tool calling) proposes one call at a time; each passes the gate
  first. Code sets the tier (read < internal < external < destructive); the large model, seeing only the request
  and a preview of the call, can block it or send it to the owner — never lower its tier.
- **Judgement**: typed questions (`noul` yes/no, `choice`, `score` — the same shapes as TypeSafe's Jev) answered in
  one token; probabilities from logits, temperature-calibrated per decision; accept/reject/escalate bands chosen
  for a precision target with a confidence bound.
- **Learning**: the owner's replies and filing, benchmark ground truth and corrections become LoRA training data for
  the judge (split by conversation, loss on the answer only); knowledge itself never goes into weights.

## Quickstart (macOS, Apple Silicon)

```bash
docker compose up -d                      # Postgres 17 + pgvector on 127.0.0.1:5433
uv sync                                   # add `--extra finetune` for MLX training and in-process scoring
ollama pull bge-m3 && ollama pull qwen3:1.7b && ollama pull qwen3:14b
uv run engram migrate
uv run engram ingest                      # the owner's mailbox from data/raw/enron-emails (see Data)
uv run engram index                       # embeddings + HNSW + BM25 statistics
uv run engram search "valuation memo for LJM" -p rakesh --since 2001-10-01
uv run engram ask "Where and at what time did Vince suggest meeting Michael Garberding on Tuesday?"
uv run engram profile add kaminski --database engram   # let the page open this brain, with a passphrase
uv run engram serve                       # the brain in a local web page: http://127.0.0.1:8770
uv run engram serve --lan auto            # …and the owner's paired watch on the LAN (:8771); prints a pairing code
uv run engram vault sync                  # the brain's memory as an Obsidian vault in data/vault/<brain>
uv run engram people                      # who the owner deals with, every address and name merged into one person
uv run engram agent brain "Who was Bernard Murphy's PhD supervisor?"   # a small agent using the brain's tools

# the brain's tools for any AI agent, over MCP (stdio): e.g. in Claude Code
claude mcp add engram -- uv --directory "$PWD" run engram mcp

# the owner's own judge: build its training set from the brain, LoRA-train it (~1 h), measure it, then use it
uv sync --extra finetune && uv run engram finetune data && uv run engram finetune train --iters 1050
uv run python -m mlx_lm fuse --model mlx-community/Qwen3-1.7B-bf16 --adapter-path data/adapters/v1 \
  --save-path data/models/judge-v1 && uv run python -m mlx_lm convert --hf-path data/models/judge-v1 \
  --mlx-path data/models/judge-v1-q4 -q --q-bits 4          # 934 MB, as accurate, 2.9x faster (LR §10.8)
J=mlx:data/models/judge-v1-q4
for d in supported relevant replied filed; do uv run engram judge eval $d --n 1500 --s1 $J --test-only; done
echo "ENGRAM_JUDGE_MODEL=$J" >> .env

# a second brain: a product team's meetings (QMSum / AMI), in its own database
uv run engram --brain meetings migrate && uv run engram --brain meetings ingest --source qmsum
uv run engram --brain meetings index && uv run engram --brain meetings memory build --limit 40

# act in the WorkBench company sandbox (git clone https://github.com/olly-styles/WorkBench data/raw/workbench)
uv run engram agent run "Forward my most recent email from fatima to kofi" --domain email
```

| Command | What it does |
|---|---|
| `engram --brain NAME …` | use another brain (its own database on the same server; `migrate` creates it) |
| `engram ingest` / `rederive` / `index` | load a mailbox (`--source enron`) or meetings (`--source qmsum`); re-split after a parser change; embed and refresh search statistics |
| `engram search` | hybrid search with time, people and direction filters |
| `engram ask` / `eval-qa` | answer with checked citations; grade answers on held-out EnronQA questions |
| `engram mcp` | the brain as tools for AI agents over MCP (stdio): `brain_search` (one hit per conversation, filters, paging), `brain_read` (within a token budget, optionally the whole thread), `brain_beliefs` (commitments, decisions, meetings by person, status and due date; possible prompt injections withheld), `brain_people`, `brain_sql` (read-only role, 3 s), `brain_scan` (the small judge reads what search misses), `brain_check` (the judge checks a claim against items), `brain_ask`, and `answer`, which only accepts ids a tool returned and that the judge finds support the answer |
| `engram agent brain` / `eval-agent` | a small research agent over those tools (the large model, at most 8 turns, forced to answer); compare it with `ask` on held-out EnronQA questions |
| `engram people` | rebuild people from addresses and belief names (`vkaminski@aol.com` and "Vince" join Vince Kaminski) |
| `engram agent run` / `eval` | carry out a request in the WorkBench sandbox through the gate (you approve); benchmark gate policies |
| `engram serve` | a local page (standard library only, 127.0.0.1, nothing loaded from the network, a strict Content-Security-Policy): sign in to a brain, then four views around the **live 3D brain** — **Agents** (the S0 → S1 → S2 → H switchboard: every agent's real status, p50/p95 from the ledger, a particle along each decision's actual path, approvals, a task box for the WorkBench agent), **Database** (the constellation that lights up what a question touched; a schema atlas with the read-only **SQL** console; a bitemporal belief timeline), **Add data** (paste or drop .txt/.md/.eml; every pipeline stage animated with its real timing) and **Audit** (the hash-chained ledger: filters, keyset paging, an animated chain check, JSONL export). ⌘K searches everything |
| `engram profile add / list / remove` | the brains the page can open: each a profile with its own database and passphrase (scrypt, per-profile salt, in `data/profiles.json`). The page can create new brains; adopting an existing database (e.g. `engram`) is done here. Sessions are an HttpOnly, SameSite=Strict cookie that ends after 30 idle minutes; five wrong passphrases lock a profile for 30 s, doubling |
| `engram serve --lan` / `engram watch` | the owner's watch (Galaxy Watch 5, Wear OS) as a second way in, on a separate LAN listener: it long-polls for what the gate escalates and approves or denies it (never destructive actions), and asks or adds by voice, transcribed on this Mac with Whisper on MLX (`uv sync --extra voice`), so the audio never leaves it. It is announced over mDNS (`_engram._tcp`), so the watch finds this Mac again when the hotspot hands out a new address; before sending its token, the watch checks that the server holds the token's hash. It needs a paired device's token (`watch pair` / `devices` / `forget`) and refuses browsers. The Wear OS app is in [`watch/`](watch/README.md). The SQL console, graph, ledger and page stay on 127.0.0.1. The owner's approvals, from the page or the watch, go into the ledger as tier H (docs/research/notes/G-watch-agent.md) |
| `engram herald sweep` / `cards` | **Herald**, the one way engram reaches the owner. Memory posts a card when one of the owner's commitments or meetings is due within the hour, and one for every fulfils/contradicts check the judge could not settle. The Librarian posts one for a fresh incoming item that holds a meeting or commitment. Code rules route each card: buzz now, or wait in the digest. Quiet hours (22:00–07:00) use the wearer's time zone, and at most 6 buzzes an hour. The watch shows the cards, and each tap goes back to the role that asked: done or snooze, confirm or reject (a human label for adapter v2), OK or later. Every tap goes into the ledger, as data for a learned notify decision (D47). The server sweeps every minute, and a LISTEN on `herald_cards` wakes the watch when any process posts a card |
| `engram vault sync` | Obsidian as two-way memory: beliefs, people and sources as linked notes (with Bases views); your edits, deletions, new notes and review verdicts flow back as owner beliefs and labels |
| `engram judge teach` | teacher labels for a decision from the large model (use with care: LR §10.7) |
| `engram eval-retrieval` | recall@k and MRR of keyword, meaning and hybrid search on the owner's EnronQA questions |
| `engram judge eval <decision>` | score labelled examples with S1 (and S2), fit calibration, report the cascade |
| `engram judge verify` | check the ledger's hash chain |
| `engram memory build` / `show` | distil commitments, decisions and meetings into beliefs; list current beliefs |
| `engram plan DAY [--now HH:MM]` | Planner: the owner's open commitments and today's meetings become a day plan, placed by OR-Tools CP-SAT around meetings and protected time (the models only extracted; H §3). The judge keeps only real to-dos. `--now` re-plans: what was missed is marked, raised a step and placed again |
| `engram meeting [EMAIL_ID]` (or `--from/--subject/--body`), `POST /api/meeting` | Feature 2, the smart meeting reply, in the WorkBench sandbox. The roles as one pipeline: Librarian (`meeting_request`, then the time words resolved in code), Researcher (how much you deal with the sender), Planner (working hours, protected lunch, clashes; else one free slot per working day), Writer (the 14B drafts), Fact Checker (code: exactly the offered times, the right name, and none of your calendar entries named), then the gate. The reply, and the event when accepting, wait for you on the page or the watch, whose card reads "Nia: Thursday 30 November at 11:30 AM, you're free" |
| `engram diplomat peer` / `meet PEER`, `POST /api/diplomat` | Diplomat: your secretary agrees a meeting time with another company's secretary over HTTP (a shared token per peer in `data/diplomat/peers.json`). No prose crosses: a message is a kind, the topic, a length and at most three times, built only by the minimizer (D44, which refuses a topic with contact details or amounts); the other side is believed only as far as that schema goes. Negotiating is code. Every message out, and the booking, waits for your approval on the page or the watch. `diplomat peer` runs a demo counterpart |
| `engram label queue` / `report` | adapter v2's labels, derived from the brain's own structure (a verified meeting belief, a superseded time, the actor's "attached" in the thread), then checked by the owner's team at `http://127.0.0.1:8770/label`. The hand-labelled `remember` gold set never reaches training |
| `engram finetune data` / `train` | build the judge's training set (with adapter v2: `remember`, `meeting_request`, `fulfilled`, `contradicts` beside the four round-1 decisions); LoRA-train it with MLX |

Everything is plain SQL underneath (`docker compose exec db psql -U engram`): `items`, `item_refs`, `chunks`,
`judgements`, `labels`, `calibration`, `beliefs` / `current_beliefs` (each with a trust tier: owner, engram,
external, quarantined), `contacts`, `people`.

## Measured on the example owner (Enron, `kaminski-v`, M5 Pro 24 GB)

| | |
|---|---|
| Ingest | 28,465 files → 11,528 items (duplicates collapsed), 19,233 chunks, **2.8 s**, no model calls |
| Index | HNSW < 2 s (49 MB); BM25 postings 112 MB, rebuilt in ~3 s |
| Search | keyword **1.9 ms** median; hybrid **28 ms** per question including the embedding. On 500 EnronQA questions the gold email is **rank 1 for 48–52%**, top 5 for 78–81%, top 10 for 85–86% (MRR 0.61–0.65; standard RRF 0.55–0.59) |
| Fine-tuned judge | Qwen3-1.7B + LoRA, 54 min of training on the owner's own ground truth. On held-out conversations it beats the zero-shot 14B on every decision: `supported` **96.6%** (base 83.7%, 14B 95.5%), `relevant` **90.9%** (74.4%, 87.5%), `replied` **60.1%** (44.6%, 55.4%), `filed` 12-way **52.7%** (31.5%, 47.9%), at a third to a fifth of the latency. It settles **82.6%** of `supported` on its own at 99.3% accuracy |
| Escalation | on the cases the fine-tuned judge is unsure about, the 14B is *less* accurate for every decision, so those cases go to the owner instead |
| Answering (`ask`, 100 held-out EnronQA questions) | **70% correct** (audited; 80% when the brain answers rather than saying it doesn't know). When the fine-tuned judge vouches for an answer it is right **84%** of the time, otherwise **6%** (AUROC 0.92) |
| Gate (WorkBench, 60 fresh tasks) | the 14B agent alone does right by 38.3% of tasks and leaves **harmful side effects in 40.0%**; through the gate at default autonomy, **48.3% right and 6.7% harmful**, asking the owner 0.62 times per task (approval-only: 46.7%, 13.3%, 0.97 prompts); with the directory check added to previews, 3.3% harmful at 0.53 prompts. The intent check alone is *not* safe (17–28% harmful at full autonomy) |
| Memory gate (round 2) | S0 bulk rules + one recall-first S1 question + extraction that may find nothing: 60 real emails went from 59 extractions / 151 beliefs / 807 s to 47 / 36 / **255 s**; the most borderline items wait for your verdict in Obsidian (LR §10.7) |
| Adding data | an item is searchable **13 ms** after it arrives (postings kept per chunk), keyword search stays at 2 ms |
| Faster System 1 (round 2) | the judge fused and quantized to 4-bit: as accurate, **2.9× faster** (214 ms per email). `ask` median 21 s → **11 s** with accuracy up (55% → 62%, same grader), or **1.7 s** if a small model drafts and the judge upholds it (56%; `ENGRAM_DRAFT_MODEL=qwen3:1.7b`). LR §10.8 |
| Adapter v2 (round 4) | Three more decisions trained on the owner's mail: `remember` (the memory gate), `meeting_request` and `todo`. Their labels were derived from the brain's own structure, then **checked by the assistant (Claude) at the owner's request instead of the team**: 533 checks on the public Enron data, kept as their own label source, with a human check always winning. The 90 hand-labelled `remember` items were never trained on. On held-out examples v2 wins where it was trained: `remember` gold 90 **67% → 80%** (AUROC 0.70 → 0.86), `meeting_request` 66% → 75% (0.62 → 0.85). But it lost ground on round 1's decisions (`supported` 95.7% → 90.8%, `replied` 64% → 52%). So the brain routes per decision: v2 for `remember` and `meeting_request`, v1 for the rest (`ENGRAM_JUDGE_MODEL='<v1>;remember,meeting_request=<v2>'`). The memory gate now keeps 94–95% of memorable emails while sending ~60% of them to the 14B, instead of 99%. `fulfilled` and `contradicts` were left out: 10 and 0 real positives in 100 checked pairs. `data/results/v2-eval.json` |
| Agent tools (round 3) | a small research agent over the MCP tools (14B, ≤ 8 turns) answers **60%** of 30 held-out questions, citing only records it was shown, at 3.5 calls, ~1.6k tool tokens and 21 s; `ask` gets 67% in 4.5 s, and one or the other is right 80% of the time (handoff round 3 §6) |

Details and caveats: [`../docs/research/lit-review.md`](../docs/research/lit-review.md) §4.4 (search), §10.5 (the judge), §10.6 (answering) and §11.6 (the gate), and [`../docs/research/brain-design.md`](../docs/research/brain-design.md) §5.

## Layout

```
src/engram/
  config.py db.py sql/        settings, migrations (001 core, 002 judge/ledger, 003 memory, 004–005 BM25 postings)
  text.py sources/ store.py   parsing and ingest (Enron mailbox, EnronQA, QMSum meetings, the WorkBench sandbox)
  llm.py index.py             Ollama client; embeddings, BM25 + vector hybrid search
  ask.py                      answering with citations the judge checks
  act.py agent.py             the gate (tiers, intent check, approval) and the tool-calling agent
  serve.py profiles.py web/   the local page and its sign-in: web/app.js, web/views/*.js, web/lib/*.js, web/styles/*.css
                              (no build step); 3d-force-graph 1.80.0, Instrument Sans and JetBrains Mono vendored
                              in web/vendor (MIT, OFL)
  vault.py                    the Obsidian vault, two-way
  tools.py mcp.py research.py the brain as agent tools; the MCP server; the small research agent
  people.py                   people as entities: addresses and names merged
  judge.py calibrate.py       System 1: typed questions, scorers (Ollama, MLX), calibration, cascade, ledger
  labels.py evaluate.py       labelled examples from ground truth; evaluation of judges and retrieval
  memory.py                   commitments, decisions, meetings as bitemporal beliefs
  finetune.py cli.py          training data and LoRA; the command line
tests/                        unit tests + database tests against throwaway databases (no model servers needed)
```

## Data

`data/` is git-ignored. The example uses the Enron corpus (`corbt/enron-emails` on Hugging Face; public, released
during the FERC investigation — handle with respect for the people in it), EnronQA (`MichaelR207/enron_qa_0922`,
CC BY 4.0) as ground truth, and, for agent workflows, WorkBench (MIT; clone it into `data/raw/workbench`) and QMSum
(`pszemraj/qmsum-cleaned`; its AMI product-team meetings).
