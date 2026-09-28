# engram — deck source

*The whole project as slides, for the MSRIT Hackathon, Track 1 "Sovereign AI". Each slide has what goes **on the
slide** (short), a suggested **visual**, and what to **say**. Every number here was measured on this laptop (M5 Pro,
24 GB), mostly on the example owner's mailbox; sources are in the last section. Status as of 28 Sep 2026.*

Judging weights to design for: technical execution 30% · innovation 20% · impact 20% · product experience 15% ·
demo 15%.

---

## Slide 1 — Title

**On the slide**
- **engram** — a sovereign second brain
- A small local model, fine-tuned on you, makes the brain's many small judgements; a large local model takes the
  hard ones; you approve what matters.
- Nothing leaves the laptop.

**Visual:** the sign-in screen, a profile tile with its live constellation (`Claude outputs/1280-dark-01-login.png`).

**Say:** "A database answers queries. A brain makes judgements. engram is a brain you own."

---

## Slide 2 — The problem

**On the slide**
- Your working life is spread over email, meetings, notes and calendars, and the important parts are promises,
  decisions and meetings buried in them.
- Today's "AI memory" tools either send it all to the cloud or store junk:
  - an audit of 10,134 Mem0 memories found **97.8% junk**;
  - Graphiti's small-model judge **invalidated 41% of ~3,950 facts**, and 3 of 4 audited cases were wrong.
- AI agents that act on your behalf get tricked, and they fail silently.

**Visual:** three short "failure" cards with the numbers.

**Say:** "The hard part isn't storing things. It's the thousands of small judgements: is this worth remembering, is
this the same person, does this contradict what we decided, should this email go out? Existing tools either don't
make them, make them silently, or make them in someone else's cloud."

---

## Slide 3 — The idea: think in tiers

**On the slide**

```
 item ─►  S0 code  ─►  S1 small judge  ─►  S2 large model  ─►  H  you
          parse,       one token + a        the uncertain       what neither
          dedupe,      calibrated           middle, and all     model settles,
          dates,       probability          the writing         and risky actions
          rules        ~30–200 ms           ~0.5–1 s
          └──────── every judgement → one hash-chained ledger (audit + cache + training data) ────────┘
```

- Of the 55 judgements a brain needs (mapped in the design), **10 are pure code, 42 are System 1 first**, and only
  **1** (does this action match what you asked?) needs the large model first.
- Each yes/no/choice gets **one token**. Its probability comes from the model's logits, calibrated per decision,
  not from a number the model writes.

**Visual:** the four-tier ladder in the tier colours (steel S0, cyan/green S1, violet S2, amber H).

**Say:** "Like Kahneman's System 1 and System 2. The fast system handles almost everything in tens of milliseconds;
the slow one only sees what the fast one is unsure about; you only see what matters."

---

## Slide 4 — Data → Knowledge → Memory → Reasoning → Action

**On the slide**

| Stage | What engram does | Measured |
|---|---|---|
| **Data** | every item stored once, copies collapsed, quoted history split off | 28,465 files → 11,528 items in **2.8 s**, no model calls |
| **Knowledge** | BM25 in SQL + pgvector HNSW, fused | keyword **1.9 ms**, hybrid **28 ms**; the right email ranks first for about half the questions and in the top 5 for about 80% |
| **Memory** | one-token gate → one extraction → bitemporal beliefs with verbatim quotes | 60 emails: 807 s → **255 s**, 151 → 36 beliefs (the junk gone) |
| **Reasoning** | answer with citations, then the small judge checks each citation | **70%** correct; when the judge vouches, **84%** right, otherwise 6% |
| **Action** | code sets risk, the 14B checks intent, you approve | harmful side effects **40% → 6.7%** |

**Visual:** the brief's five-stage arrow with one number under each stage.

**Say:** "This is the track brief, built end to end and measured at every stage."

---

## Slide 5 — The core bet: a 1.7B fine-tuned on you beats a zero-shot 14B

**On the slide**

| Decision (held-out conversations) | 1.7B base | **1.7B fine-tuned** | 14B zero-shot |
|---|---|---|---|
| Is this answer supported by the email? | 83.7% | **96.6%** | 95.5% |
| Is this email relevant to the question? | 74.4% | **90.9%** | 87.5% |
| Will the owner reply? | 44.6% | **60.1%** | 55.4% |
| Which of 12 folders will it be filed in? | 31.5% | **52.7%** | 47.9% |

- **54 minutes** of LoRA training on the laptop (MLX, peak 18 GB), on **5,958 labels the brain already had**: the
  owner's own replies and filing, and EnronQA answers. There's no hand labelling and no cloud teacher.
- **3–5× faster** than the 14B. Fused and 4-bit (934 MB), it's **2.9× faster again** with no loss in accuracy.
- It settles **82.6%** of "supported?" on its own, at **99.3%** accuracy.

**Visual:** grouped bar chart, with the fine-tuned bar highlighted in each group.

**Say:** "We fine-tune skills, never facts. Knowledge stays in the database, where it can be cited and deleted.
The model learns *how this person judges*."

---

## Slide 6 — Escalation is measured, not assumed

**On the slide**
- On exactly the cases the fine-tuned judge is unsure about, the 14B is **less** accurate on every decision
  (e.g. "supported?": S1 83.9% vs S2 80.6%).
- So those cases skip the 14B and go **straight to the owner**. The routing rule is re-computed from the ledger.
- The raw models are badly overconfident: they needed calibration temperatures of 4.5–7.7 for the 1.7B and 7–36
  for the 14B. So we calibrate per decision and set accept/reject bands for a precision target.

**Visual:** a small table of escalated cases (S1 correct vs S2 correct), and one reliability curve.

**Say:** "Most cascades assume the big model is always better. We measured it, and on the hard cases it isn't. So
the brain asks you instead of pretending."

---

## Slide 7 — System 1 checking System 2

**On the slide**
- `ask`: retrieve → the small judge drops what's surely irrelevant → the 14B answers with citations → the small
  judge checks the answer against what it cites.
- On 100 held-out EnronQA questions: **70% correct** (audited), **80%** when the brain answers rather than saying it
  doesn't know.
- When the judge vouches, the answer is **84%** right; when it doesn't, **6%** (AUROC 0.92). The badge on the answer
  means something.
- Median latency is **11 s**, or **1.7 s** in draft mode, where a small model drafts and the judge upholds it (56%).

**Visual:** the answer view with sources and the judge's verdict (`Claude outputs/1280-dark-06-answer.png`).

**Say:** "The fast model isn't only cheaper. It's the fact checker for the slow one."

---

## Slide 8 — Acting safely: the gate

**On the slide**
- Every tool call passes the gate. **Code** sets the tier (read < internal < external < destructive). The **14B**
  sees only the request and a preview of the call, and can block it or send it to you, but **never lower its tier**.
  Then **you** approve.
- WorkBench company sandbox, 60 fresh tasks:

| | Tasks done right | Harmful side effects | Owner prompts per task |
|---|---|---|---|
| 14B agent, no gate | 38.3% | **40.0%** | 0 |
| approve everything | 46.7% | 13.3% | 0.97 |
| **engram's gate** | **48.3%** | **6.7%** | **0.62** |
| + one code fact (is the address in the directory?) | — | **3.3%** | 0.53 |

- A small model may **raise** suspicion, never **grant** permission. The intent check alone isn't safe (17–28%
  harmful at full autonomy).

**Visual:** the table, with the harm column as a bar falling from 40% to 3.3%.

**Say:** "Safer *and* more useful than asking the human about everything, with a third fewer interruptions."

---

## Slide 9 — Seven roles, one pipeline

**On the slide**
- The original plan had **22 agents**. We kept **7 roles** as named lanes in the UI: **Librarian, Researcher,
  Memory, Planner, Operator, Guardian, Herald**.
- The hand-offs are **function calls logged in the ledger**, not LLM-to-LLM chat.
- Why: sequential multi-agent setups lose **39–70%** and amplify errors up to **17×** (Kim et al., 180
  configurations), and persona prompts don't improve accuracy (162 roles).
- **Planner** is solver-backed (OR-Tools CP-SAT). LLMs manage 33–48% on calendar planning; solver hybrids reach
  ~94%.

**Visual:** the Agents switchboard (`Claude outputs/1280-dark-09-agents.png`): lanes S0 → S1 → S2 → H with
particles.

**Say:** "Judges still see a team light up, but underneath it's one fast, auditable pipeline."

---

## Slide 10 — Memory that keeps its promises

**On the slide**
- Commitments, decisions and meetings become **beliefs**: each has a verbatim quote (code rejects any quote not in
  the source), a date resolved by code, and a trust tier (owner / engram / external / quarantined).
- **Bitemporal.** Nothing is deleted. A new decision *supersedes* the old one, and "what did we believe on
  Tuesday?" still works.
- **Fulfilled?** and **contradicts?** checks run on the small judge. A sure "fulfilled" closes the commitment; the
  rest waits for you.
- **Two-way Obsidian vault.** Your edits, deletions and verdicts flow back as owner beliefs and training labels.

**Visual:** the belief timeline lens, with one superseded meeting time.

**Say:** "Existing memory tools either never update, or update silently and wrongly. engram proposes with the
small model, resolves in code, and asks you about what changed."

---

## Slide 11 — The watch: Herald

**On the slide**
- A **Galaxy Watch 5 (Wear OS)** as a second way in, straight over Wi-Fi to the Mac: no phone app and no cloud
  push.
- **Approvals.** The gate escalates → the watch buzzes → approve or deny. A live WorkBench reply was approved on the
  wrist and ledgered as tier H **19 s** after the gate paused. Destructive actions are decided only on the laptop.
- **Voice.** Ask a question, or say "remember …". Whisper on the Mac transcribes a clip in ~0.5 s, so the audio
  never leaves the room.
- **Herald cards.** A promise due within the hour, a check the judge couldn't settle, a new meeting request. Code
  routes each one: buzz now or wait in the digest, with quiet hours and at most 6 buzzes an hour.
- It finds the Mac over mDNS, and the server proves it holds the token (HMAC of a nonce) before the watch sends it.

**Visual:** a photo of the watch showing an approval card: "Nia: Thursday 30 November at 11:30 AM, you're free".

**Say:** "The owner is in the loop without being at the laptop, and still nothing touches a cloud."

---

## Slide 12 — Feature: the smart meeting reply

**On the slide**
- A meeting request arrives → **Librarian** spots it (the `meeting_request` judge; time words resolved in code) →
  **Researcher** checks how much you deal with the sender → **Planner** checks working hours, protected lunch and
  clashes → the **Writer** (14B) drafts → the **Fact Checker** (code) verifies the times, the name, and that none of
  your other calendar entries is revealed → the **Guardian** gate → you, on the page or the watch.
- Measured live: a clash at 5 PM → three other slots offered; a free 11:30 → reply sent and event created.
- The code Fact Checker **caught the 14B leaking your other meeting's name** to an outside sender. Now the Writer
  never sees why you're busy.

**Visual:** the pipeline as a row of role chips, ending in the watch card.

**Say:** "This is what data minimization looks like in practice: the model can't leak what it never sees."

---

## Slide 13 — The product

**On the slide**
- `engram serve`: a local page on 127.0.0.1 with **nothing loaded from the network** (fonts and the 3D engine are
  vendored) and a strict Content-Security-Policy.
- **Sign in to a brain.** Each brain is its own Postgres database with its own passphrase. The profile tile's
  constellation expands into the dashboard.
- **Agents:** the S0 → S1 → S2 → H switchboard, with real p50/p95 from the ledger and live approvals.
- **Database:** a 3D constellation that lights up what a question touched, a schema atlas with a read-only SQL
  console, and a belief timeline.
- **Add data:** each pipeline stage animates with its real timing; an item is searchable **13 ms** after it
  arrives.
- **Audit:** the hash-chained ledger with an animated chain check and JSONL export. ⌘K searches everything.

**Visual:** a 2×2 grid of screenshots: `07-atlas`, `09-agents`, `13-add-done`, `16-audit-verified`.

**Say:** "Every animation is real data: a particle is an actual decision taking its actual path."

---

## Slide 14 — Sovereign by architecture

**On the slide**
- **Zero cloud calls.** Postgres + pgvector in Docker, Ollama (bge-m3, Qwen3-1.7B, Qwen3-14B), MLX for the fine-tuned
  judge and Whisper.
- Even careful local-plus-cloud delegation leaks private data on **7.5%** of queries (PAPILLON), so "mostly local"
  isn't sovereign.
- Every judgement is in a **tamper-evident, hash-chained ledger**. Beliefs carry their source. Memory exports as
  plain Markdown (Obsidian).
- **DPDP-ready by design:** the DPDP Rules 2025 require one-year access logs, 72-hour breach reports and erasure,
  with penalties up to ₹250 crore from ~May 2027.
- Vendor kill-switches are real: Rewind's local capture was switched off, and Mem0's local server was sunset.

**Visual:** a "local only" seal over a diagram of the laptop with everything inside it.

**Say:** "Sovereign isn't a slogan here. You can pull the network cable and the demo still runs."

---

## Slide 15 — What's new

**On the slide**
- Each mechanism has precedent: Utopia's decision ledger, Claude Code's single-token gate, Hermes'
  approve/deny/escalate, GPT-5's router.
- **Nobody ships the combination for a personal, local brain:**
  1. one decision fabric over **memory and actions**;
  2. a separate small System 1 with **measured calibration**, not self-reported confidence;
  3. a **user-facing ledger** of every decision;
  4. learning that feeds back into System 1: the owner's corrections become the next adapter.

**Visual:** a comparison matrix of engram against GBrain, Utopia, Mem0, Graphiti and Hermes on those four rows.

**Say:** "The pattern is proven. We bring it to a sovereign personal brain, calibrated and fine-tuned on the
owner's own behaviour."

---

## Slide 16 — Demo (5 minutes)

1. **Sign in** to the `kaminski` brain. The tile's constellation expands into the dashboard.
2. **Ask:** "Where and at what time did Vince suggest meeting Michael Garberding on Tuesday?" The constellation
   lights up the retrieved items, and the answer comes with sources and the judge's verdict.
3. **Add data:** paste an email with a promise in it and watch it being stored, embedded, gated (P(worth
   remembering) counting up) and extracted into a belief.
4. **Act:** "Forward my most recent email from fatima to kofi". The agent searches, the gate marks the forward
   external, and **the watch buzzes**: approve on the wrist.
5. **Audit:** the approval is the newest ledger row, tier H, `owner:watch`. Run *Verify chain*.

**Backup if models are slow:** recorded runs in `engram/data/results/demo-*.txt`.
**Before the demo:** reboot or free memory (swap slows Whisper to 7–12 s), and turn Bluetooth off on the watch so
Wi-Fi stays up.

---

## Slide 17 — Honest limits and what's next

**On the slide**
- **Limits:**
  - Predicting what the owner will do ("will they reply?") is learnable but can't be settled at 95% precision from
    text alone, so it stays a suggestion.
  - The "worth remembering?" gate is the weak spot (72%, AUROC 0.80).
  - The watch speaks plain HTTP on the LAN.
- **Next:**
  - **Adapter v2:** one multi-task adapter adding `remember`, `meeting_request`, `fulfilled` and `contradicts`.
    Their labels are derived from the brain's own structure (363 / 383 / 160 / 196 queued), then checked by the
    team at `/label`; no cloud-model labels.
  - **Diplomat:** a second engram brain negotiates a meeting time over HTTP, with a data minimizer and a watch
    approval on every outgoing message.
  - A learned "notify now or later?" from the owner's taps, and TLS pinned at pairing for the watch.

**Say:** "Every limit here is measured, and every next step has its training data already flowing from use."

---

## Slide 18 — Thank you

- engram: your brain, on your machine.
- Built from scratch this week: ~7,400 lines of Python, ~2,900 lines of front end, ~1,000 lines of Kotlin (the watch
  app), 14 SQL migrations and 107 tests.
- The research behind it is a 110 KB literature review with every design choice cited (`docs/research/lit-review.md`).

---

# Backup slides

## B1 — Stack

| Layer | Choice | Why |
|---|---|---|
| Store | Postgres 17 + pgvector (Docker, 127.0.0.1:5433) | one store for raw items, chunks, beliefs, judgements and the ledger; plain SQL underneath |
| Search | BM25 in SQL (postings kept per chunk) + halfvec HNSW, weighted reciprocal-rank fusion | Postgres ranking has no IDF; true BM25 took rank-1 recall from 0.20 to 0.48 |
| Embeddings | bge-m3 (1024-d) via Ollama | multilingual, local |
| System 1 | Qwen3-1.7B + LoRA, fused, 4-bit, MLX in-process | one token, ~0.2 s per email-sized prompt |
| System 2 | Qwen3-14B via Ollama | writing, extraction, the intent check |
| Planner | OR-Tools CP-SAT | "LLM extracts, solver schedules" |
| Speech | Whisper large-v3-turbo on MLX | ~0.5 s for a 2.5 s clip, warm |
| Page | Python standard-library HTTP server; no-build ES modules; 3d-force-graph vendored | nothing from the network |
| Watch | Kotlin, Wear OS 5, long-poll foreground service, mDNS | no phone app, no FCM |
| Tools for other agents | one MCP server with 9 typed tools | `brain_search`, `brain_read`, `brain_beliefs`, `brain_sql` (read-only, 3 s) … and `answer`, which only accepts ids a tool returned and the judge finds supporting |

## B2 — Data used

- **Enron mailbox `kaminski-v`** (public, released during the FERC investigation): 28,465 files → 11,536 items,
  1,154 beliefs and 14,358 ledgered judgements in the live brain.
- **EnronQA** (CC BY 4.0) is the ground truth for retrieval, answering and the `supported`/`relevant` labels.
- **WorkBench** (MIT) is a company sandbox (email, calendar, CRM, tasks) graded on the state each task leaves, with a
  harmful-side-effect check.
- **QMSum / AMI** meetings form a second brain: 137 meetings → 1,555 items in 2 s.

## B3 — Every measured number in one place

| What | Result |
|---|---|
| Ingest | 28,465 files → 11,528 items, 19,233 chunks in 2.8 s |
| Index | HNSW < 2 s; BM25 rebuilt in ~3 s |
| Search | keyword 1.9 ms median; hybrid 28 ms incl. embedding; rank 1 48–52%, top 5 78–81%, top 10 85–86%, MRR 0.61–0.65 (standard RRF 0.55–0.59) |
| Adding data | searchable 13 ms after arrival |
| Judge training | 5,958 examples, split by conversation 70/10/20; 1,050 steps, 54 min, peak 18 GB, val loss 0.096 |
| Judge accuracy (ft vs 14B) | supported 96.6 vs 95.5 · relevant 90.9 vs 87.5 · replied 60.1 vs 55.4 · filed 52.7 vs 47.9 |
| Judge latency (ft vs 14B, median) | 184/610 · 285/1,310 · 362/889 · 301/983 ms |
| Settle rate at 95% precision | supported 82.6% (99.3% accurate) vs 14B 44.4%; relevant 44.3% vs 0% |
| Faster S1 | fused + 4-bit: 934 MB, 2.9× faster, as accurate (214 ms per email) |
| `ask` | 70% correct (audited), 80% when answering; vouched 84% vs 6%, AUROC 0.92; median 21 s → 11 s; 1.7 s draft mode at 56% |
| Research agent over MCP | 60% of 30 held-out questions, 3.5 calls, ~1.6k tool tokens, 21 s; `ask` 67% in 4.5 s; one or the other is right 80% of the time |
| Memory gate (round 2) | 60 emails: 59 → 47 extractions, 151 → 36 beliefs, 807 → 255 s |
| Gate (WorkBench, 60 fresh tasks) | harm 40.0% → 6.7% (3.3% with the directory check); right 38.3% → 48.3%; 0.62 prompts per task |
| Watch | approval ledgered 19 s after the gate paused; Whisper ~0.5–0.6 s per 2.5 s clip, warm |
| Adapter v2 labels queued | remember 363 · meeting_request 383 · fulfilled 160 · contradicts 196 |

## B4 — Sources inside the repo

- `engram/README.md`: how to run it, every command, and the measured table.
- `docs/research/lit-review.md`: the literature review (cited as LR §). Key sections: §10.5 fine-tuned judge, §10.6
  answering, §10.7 memory gate, §10.8 faster S1, §11.6 the gate on WorkBench, §12 sovereignty and DPDP, §13
  landscape and novelty.
- `docs/research/brain-design.md`: the 55-judgement decision map, and §5 on what was built.
- `docs/research/agent-roster-review.md`: 22 agents → 7 roles, with the multi-agent evidence.
- `docs/research/notes/G-watch-agent.md`: the watch design.
- `docs/design.md`: the visual language (tiers as colours and motion).
- Screenshots: `Claude outputs/*.png` (1280 dark and light, 390 mobile).
