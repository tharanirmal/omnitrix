# The Omnitrix agent roster against engram: keep, merge, drop, and what to fine-tune next

*28 Sep 2026. This reviews the two roster PDFs: the 21-agent `Omnitrix_Agents.pdf` sent over WhatsApp, and the 22-agent
version in the repository root with technology, features and a build plan. They are compared with what `engram/`
already does, as measured in `brain-design.md` §5, `handoff-round3-agent-queries.md` §6 and LR §10–§11. The
multi-agent evidence is in [`notes/H-agent-roster-evidence.md`](notes/H-agent-roster-evidence.md), and the watch is
in [`notes/G-watch-agent.md`](notes/G-watch-agent.md). The forks that need the owner's call are in §6.*

---

## 1. The finding in one paragraph

**Most of the roster is already built, as pipeline stages rather than chatting agents.** Nine of the fifteen "build"
agents correspond to engram modules that are measured and working: Librarian, Researcher, Fact Checker, Operator,
Guardian, most of Historian and Promise Keeper, and the fine-tuned model the PDF plans for Phase 5.5. The roster's
failure mode is making each role a separate LLM agent that talks to the others. On one laptop GPU that makes every
hand-off a serial 14B call and every agent a new place to lose context, and it runs against engram's central
measured result: most of these "agents" are really a *yes/no/choice question* that the fine-tuned 1.7B judge answers
in ~0.2 s, better than the 14B does (LR §10.5). The recommendation is to keep the roster **as the story and the
UI**, since each name is a role a judge can see light up, and to implement each role as what it really is: code, a
judge decision, a tool, or the one agent loop.

## 2. The roster mapped to engram

Legend: **Built**, meaning working and measured · **Partial** · **Missing**. Verdict: **Keep** (a real role with its
own trigger and output) · **Merge** (becomes part of another role) · **Drop** (for the hackathon).

### Core (13)

| # | Agent | What engram already has | Status | Verdict | What it really is |
|---|---|---|---|---|---|
| 1 | Chief of Staff | `agent.py` (one tool-calling 14B loop, ≤ 8 turns), `research.py` recipes | Partial | **Merge into the agent loop.** It plans *tool calls*, not other agents. | the 14B loop with plan-then-execute (LR §11.2) |
| 2 | Librarian | `sources/`, `store.py`, `text.py`, `index.py`, `memory.py`. Ingest in 2.8 s, searchable 13 ms after adding, recall-first `remember` gate plus one extraction | **Built** | **Keep** (event-driven pipeline) | S0 parse → S1 `remember` → S2 extract |
| 3 | Researcher | `ask.py`, `tools.py`, `mcp.py`, `people.py`. 70% audited on EnronQA; 9 MCP tools | **Built** | **Keep.** Adds "meeting brief" as a recipe | retrieval + S1 `relevant` + S2 answer |
| 4 | Historian | bitemporal beliefs; `same_belief` supersession (D25/D28) | Partial: no contradiction warning (D26) | **Merge with Promise Keeper → "Memory"** | S1 `contradicts` per candidate belief |
| 5 | Promise Keeper | commitments as beliefs with `due_at` (D17 in code) | Partial: no fulfilment check (D27), no reminders | **Merge with Historian → "Memory"**; the reminders go to Herald | S1 `fulfilled` + an S0 timer |
| 6 | Planner | nothing | Missing | **Keep, as code**, not an LLM agent | a scheduler/solver over tasks + calendar; S1 only for duration and attention (D16) |
| 7 | Auditor | `brain_check` (one claim against items) | Partial | **Merge into Researcher** as a batch recipe | D40: S1 `supported` per checklist line |
| 8 | Analyst | nothing | Missing | **Drop for the hackathon** | D39 ripple walk. Needs belief-to-belief relations engram doesn't have yet |
| 9 | Writer | nothing standalone; the 14B writes answers | Partial | **Merge into Operator**: drafting is the step before a send | S2 generation; D48 tone is an S1 option later |
| 10 | Fact Checker | the fine-tuned `supported` judge: 96.6%, settles 82.6% at 99.3% (LR §10.5) | **Built** | **Merge into the judge**. It already *is* the judge | S1 `supported` (D21/D37) |
| 11 | Operator | `agent.py` over WorkBench tools | **Built** | **Keep** | the only caller of write tools |
| 12 | Guardian | `act.py`: code-set tiers, 14B intent check, owner approval, hash-chained ledger; harm 40% → 6.7% on WorkBench | **Built** | **Keep** (code, as the PDF says) | S0 tiers + S2 D45 + H |
| 13 | Herald | nothing | Missing | **Keep**: the watch's brain | S0 channel (D46) + S1 notify-now/batch/digest/drop (D47) |

### Extra (3) and external (6)

| # | Agent | Verdict | Why |
|---|---|---|---|
| 14 | Interviewer | Drop | No data to demonstrate it on. |
| 15 | Toolsmith | **Drop, permanently** | An agent that writes its own tools removes the fixed tool menu the gate depends on (the action-selector pattern, LR §11.2). |
| 16 | Apprentice | Drop (later: D54 rule mining from the ledger) | The ledger already records what repeats; a rule proposer is a small S0 job later. |
| 17 | Diplomat | **Owner's call** (§6 Q2) | A strong demo, but agent-to-agent exchange is the highest-risk channel for leaks, and it needs a second running brain. |
| 18 | Scout | **Merge into Librarian** as a source | Watching news is ingest from another folder plus S1 D11 ("does this matter to what I track?"). Live web fetching breaks the "nothing calls out" claim; the PDF's local "outside world" folder is the honest version. |
| 19 | Client Desk | Drop (later: Researcher with a trust filter) | It is `ask` restricted to public-tier items. |
| 20 | Vendor Agent | Drop | No invoice data. |
| 21 | Filing Agent | Drop | Needs browser automation, and stops for a human anyway. |
| 22 | Guest Agent Manager | **Drop, permanently** | "Hire an outside AI" contradicts sovereignty, which is Track 1's premise. |

### The result: 22 names → 7 roles, 3 of them to build

| Role (the name shown in the UI) | Absorbs | State |
|---|---|---|
| **Librarian** | Scout | built; add a news folder + D11 |
| **Researcher** | Auditor, and Client Desk later | built; add brief and checklist recipes |
| **Memory** (Historian + Promise Keeper) | — | partial; add `contradicts` (D26) and `fulfilled` (D27) |
| **Planner** | — | **to build**, as code |
| **Operator** | Chief of Staff, Writer | built |
| **Guardian** | Fact Checker, through the judge | built |
| **Herald** | — | **to build**, the watch |

The UI keeps a named lane per role, so when one question lights up Librarian → Researcher → Guardian, the judges
still see a team. The difference is that the hand-offs are function calls, logged in the ledger, not LLM-to-LLM
messages.

## 3. What the roster PDF's technology choices become

| PDF choice | engram today | Keep? |
|---|---|---|
| Qwen3 14B + **Qwen3 4B** for fast jobs | 14B + **fine-tuned Qwen3-1.7B, 4-bit** (the 4B tag installed here is thinking-only and ignores `think:false`) | engram's choice. The 1.7B-ft beats the zero-shot 14B on every trained decision |
| **Mem0** for habits and agent memory | own bitemporal `beliefs` with trust tiers and verbatim quotes | engram's. Mem0's audit found 97.8% junk writes (LR §13.3), and a second memory store would duplicate beliefs |
| Graphiti (stretch) | Postgres beliefs + `people` | drop; Graphiti's collateral-invalidation bug is in LR §13.3 |
| FastAPI dashboard | `serve.py`, standard library | engram's; no need to add a framework |
| **ntfy** via the phone app to the watch | undecided (G note: a direct Wear OS app) | **§6 Q3**: ntfy needs no watch code |
| Mailpit | the WorkBench sandbox (email, calendar, CRM, tasks) with graded outcomes | engram's; it is also the benchmark |
| whisper.cpp | proposed mlx-whisper (G §7) | either works; mlx is already installed |
| Tesseract OCR | — | optional; only if the demo shows a scanned document |
| APScheduler / LISTEN/NOTIFY | — | one small timer thread for Herald and Promise Keeper; LISTEN/NOTIFY only if there are several processes |
| OR-Tools | — | **yes for Planner**: the evidence strongly favours "LLM extracts, solver schedules" (§7, H §3) |
| 12 MCP servers | **one** MCP server with 9 typed tools | engram's; one server, and one gate in front of every write |

## 4. Fine-tuning: what is done, and what to train next

**The PDF's Phase 5.5 is already done, and done better.** The PDF plans to LoRA-tune a 4B on extraction, using the
14B as teacher. engram fine-tuned the 1.7B judge on *ground truth the brain already holds*, not on teacher labels:
EnronQA answers and the owner's own reply and filing behaviour. On held-out conversations it beats the zero-shot 14B
on all four decisions at a third to a fifth of the latency (LR §10.5), and after fusing and 4-bit quantization it is
2.9× faster with no loss (§10.8). The teacher-student idea was tested and **rejected on evidence**: on the `remember`
question even the 14B *with reasoning* agrees with the rubric only 72% of the time, so it is not a usable teacher
(LR §10.7).

**The next adapter (v2): one multi-task adapter, the four existing decisions plus new ones.** Each new decision has
to earn its place by holding a label source that isn't the 14B.

| Decision | Role it serves | Label source (no 14B teacher) | Size | Priority |
|---|---|---|---|---|
| `remember` (D12/D24) | Librarian | the owner's Obsidian review verdicts (already wired) + the 90 hand labels; target ~400 | small | **High**: the known weak spot (72%, AUROC 0.80) |
| `meeting_request` + time specificity (D17) | Operator, Feature 2 | WorkBench/Enron emails with `calendar.create_event` in the gold calls; Enron items whose extraction produced a meeting belief with a resolved time, audited | ~400 | **High** if Feature 2 is the demo |
| `reply_intent` (approve / reject / approve-with-edit / snooze, D49) | Herald, watch voice | synthetic: templated phrasings × actions, easy to generate and check exactly | ~600 | Medium: tiny, and makes watch voice replies safe |
| `contradicts` (D26) | Memory / Historian | pairs of superseding beliefs (`supersedes` is set) as positives, same-party unrelated beliefs as negatives | ~400 | Medium |
| `fulfilled` (D27) | Memory / Promise Keeper | owner commitments followed by a later message in the same thread by the same actor; audit a sample | ~300 | Medium |
| `notify` (D47) | Herald | bootstrap from `replied` (already trained), refine from the owner's watch reactions (the ledger) | grows with use | Later: the data comes from use |

Rules carried over from round 1:
- split by conversation;
- a template check before training;
- loss on the answer only;
- re-measure the four existing decisions so v2 doesn't regress them;
- re-fit calibration and the escalation rule (D41) per decision.

Training cost at round-1 rates: ~1 h per 1,000 steps at batch 4. The 14B can't be loaded alongside training, so GPU
jobs are queued.

**Don't fine-tune** Planner (code), Guardian (code; small models may only *raise* a tier, LR §11.1), or anything
that holds facts. Writer style is the one generative fine-tune worth considering later, trained on the owner's 8,623
sent emails. It is a different kind of adapter (generation, not a one-token judge) and not needed for the demo.

## 5. Suggested build order

1. **Herald + the watch** (approvals first): the wrist moment is the demo. It needs Q3 answered.
2. **Memory**: `contradicts` + `fulfilled` as zero-shot judge questions first, measured; then add them to v2.
3. **Planner**: tasks from commitment beliefs + WorkBench calendar → a day plan, re-planned when a task is missed.
4. **Feature 2, smart meeting reply**: Librarian `meeting_request` → Planner free slot → Operator draft → Guardian → Herald
   watch card → send. It runs entirely inside WorkBench, so it can be graded.
5. **Adapter v2** once the labels exist (they build up during steps 2–4).
6. Diplomat only if Q2 says so.

## 6. Decisions (owner, 28 Sep 2026)

- **Q1 Roster → 7 roles over one pipeline.** Librarian, Researcher, Memory, Planner, Operator, Guardian, Herald as
  named lanes in the UI and pitch; underneath, code, judge questions and tool calls.
- **Q2 Diplomat → a small scripted demo.** A second engram brain negotiates one meeting time with the first over HTTP.
  Every outgoing message passes a data minimizer (D44) and a watch approval.
- **Q3 Herald → a direct Wear OS app** (G note): approval cards and voice ask/capture over Wi-Fi, with speech
  recognition on the Mac. No ntfy.
- **Q4 Adapter v2 adds `remember`, `meeting_request`, `contradicts` and `fulfilled`** to the four existing
  decisions. `reply_intent` is not in v2.

Revised build order:
1. Memory: `contradicts` + `fulfilled`, zero-shot first and measured.
2. Label builders for all four new decisions.
3. Planner: extraction, then an OR-Tools CP-SAT schedule and re-planning.
4. Herald: a LAN listener with a pairing token, then the Wear OS app.
5. Adapter v2: train, then re-measure all eight decisions.
6. Feature 2: the smart meeting reply, end to end in WorkBench.
7. The Diplomat demo.

## 6a. Built so far (28 Sep 2026)

- **Memory**: `fulfilled` (D27) and `contradicts` (D26) run inside `memory build` on the small judge alone. A sure
  "fulfils" closes the commitment. Every other finding is a `belief_links` row the owner confirms (migration 011).
- **Labels for v2** (`derive.py`, `/label`): 363 `remember`, 383 `meeting_request`, 160 `fulfilled` (few real
  fulfilments exist, so near misses are queued for the team to find more) and 196 `contradicts`. All wait for the
  team's check.
- **Planner** (`planner.py`, `engram plan`): CP-SAT around meetings and protected time, re-planning with missed
  tasks raised a step. A `todo` question keeps only real to-dos. Zero-shot the small judge cannot tell a to-do
  from a status (P(yes) 0.16–0.32 on everything), so it escalates to the 14B, which separates the clear cases.
  `todo` is the next candidate for the adapter.
- **Feature 2, the smart meeting reply** (`meeting.py`, `engram meeting`, `POST /api/meeting`): measured live on three cases. A clash with 'project progress update' at 5 PM → three other slots; a free 11:30 → reply sent and event created; no time given → three slots. The code Fact Checker caught the 14B naming the owner's other meeting to an outside sender, so the Writer no longer sees why the owner is busy, and a draft naming a calendar entry fails (D44). Pending approvals carry a `card` (headline, reply, slots) for the watch.
- **Diplomat** (`diplomat.py`, `engram diplomat`, `POST /api/diplomat`): a schema-only protocol instead of agent chat (H §4: agents leak with no attacker present; A2ABreak). The minimizer is the only way a message is built; the peer's replies are parsed strictly (extra fields dropped, off-hours or far-future slots refused); negotiating is code, at most four rounds; each message and the booking go through the gate. Live, over HTTP, against the demo peer: agreed Friday 1 December at 2:00 PM in one round, both owners approving.
- **Herald / the watch**: built in the other session (`engram/watch`, with mDNS discovery). This fork's duplicate
  (`/omnitrix/watch`) is stopped.

## 7. The evidence behind the merges (details and links in [H](notes/H-agent-roster-evidence.md))

- **Sequential work is where multi-agent designs lose.** Kim et al. (Google/DeepMind, 180 configurations,
  arXiv:2512.08296) found that decentralized multi-agent setups amplify errors 17.2× against a single agent
  (centralized: 4.4×). On sequential tasks they lose 39–70%; only parallelizable tasks gain (+80.8%). engram's
  ingest → remember → act chain is sequential, and on one laptop GPU the models run serially anyway.
- **Most multi-agent failures come from the multi-agent part.** MAST (Cemri et al., 1,600+ traces, 7 frameworks,
  arXiv:2503.13657) attributes 44.2% of failures to system design, 32.3% to inter-agent misalignment and 23.5% to
  missing verification.
- **The payoff is expensive.** Anthropic's multi-agent research system was 90.2% better but used ~15× the tokens,
  and was worth it only with parallel workers. MAFBench (2026) measured orchestration scaffolding alone at over 60×
  the latency.
- **Personas don't make a model more accurate.** Across 162 roles and 4 model families, persona prompts did not
  improve factual accuracy (Zheng et al., arXiv:2311.10054). So "the Historian" should be a *typed question*, not
  a system prompt.
- **Planner must be solver-backed.** On NATURAL PLAN calendar scheduling, frontier LLMs score 33–48% at best
  (arXiv:2406.04520); on TravelPlanner, GPT-4-Turbo passes 0.6%. With a SAT/SMT solver checking the plan, o1-preview
  goes from 10% to 93.9% (arXiv:2404.11891). Design: S1/S2 extract tasks and constraints, then OR-Tools CP-SAT
  schedules and code re-plans.
- **Diplomat is the riskiest channel.** A2A reached v1.0 and is under the Linux Foundation, but A2ABreak finds 11
  vulnerabilities that stay open even under full spec compliance (arXiv:2609.10871). ConfAIde, PrivacyLens and
  AirGapAgent show agents leaking context-inappropriate information with no attacker present. If it is built, it
  needs a data minimizer (D44) and a Guardian gate on every outgoing message.
- **The part of the roster with the best evidence is the fast/slow split** that engram already has: NVIDIA's
  "SLMs are the future of agentic AI" (arXiv:2506.02153), CODA's two-brain split (arXiv:2508.20096) and a fine-tuned
  0.8B router (arXiv:2606.22902).

Caveats (H, open questions):
- No study isolates multi-agent overhead for small local models on one GPU; that argument comes from first principles.
- The persona null result is from factual QA, not structured extraction.
- A2ABreak is a formal analysis, not measured exploit rates.
