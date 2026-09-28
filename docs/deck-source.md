# Omnitrix: deck source (8 slides)

*The single source for the MSRIT Hackathon Track 1 "Sovereign AI" pitch. The built deck is
`docs/Omnitrix-deck.pptx`. **Omnitrix** is the whole system: a local AI
secretary made of a brain, seven roles, a web app and a watch. **engram** is its brain. Every number is traced to a file
in **Sources**. "Next" marks what is planned rather than built. Built on the template `engram_template_8.pptx`: its black
background, grey and white shapes, and amber accent are kept exactly. Written 28 Sep 2026.*

Judging weights: technical execution 30% · innovation 20% · impact 20% · product experience 15% · demo 15%.

**Our understanding of the project**

1. **Omnitrix** is a sovereign second brain: local AI roles that work as a personal secretary. It reads, remembers,
   plans, drafts, and asks your watch before anything leaves the laptop.
2. **engram is the brain:** Postgres memory, a small fine-tuned judge (System 1), a 14B model (System 2), and a
   hash-chained ledger of every decision.
3. **Seven roles use the brain:** Librarian, Researcher, Memory, Planner, Operator, Guardian and Herald. The
   meeting reply and the Diplomat are built on them.
4. **You reach it through:** the local web app, the Galaxy Watch app (Herald), an Obsidian vault, and MCP tools for
   other AI agents.
5. **All of it runs on one laptop:** zero cloud calls, measured on public data (the Enron mailbox and WorkBench).

---

## Slide 1: Omnitrix, your second brain on your own laptop

- **Criterion:** Impact (20%). It frames who it's for and why it's local.
- **On the slide:** "Omnitrix". Under it: "A local AI secretary that remembers, plans and acts, only with your
  OK." Three pills: `Brain: engram` · `Track 1 · Sovereign AI` · `MSRIT Hackathon`.
- **Visual:** the template's title slide: a big two-tone title ("Omni" grey, "trix" white), the subtitle in white,
  and three dark pills.
- **Say:** "Omnitrix is a secretary that lives on your laptop. It remembers your work, keeps your promises and
  asks before it acts. Its brain, engram, never sends anything to a cloud."

## Slide 2: Storing is easy. Judging is hard.

- **Criterion:** Impact (20%).
- **On the slide:** "Your promises and decisions hide in email. Memory tools store junk, or judge silently." Three
  numbers: **97.8%** of Mem0 memories were junk · **41%** of Graphiti facts wrongly invalidated · **7.5%** of
  queries leaked by local + cloud.
- **Visual:** the template's "Key Numbers" layout: three dark cards, a big white number, a bold label, and a grey
  source line.
- **Say:** "The hard part isn't storing things. It's thousands of small judgements: is this worth remembering, did
  this plan change, should this email go out? Today's tools skip them, get them wrong silently, or make them in
  someone else's cloud."

## Slide 3: One laptop. One brain. Seven roles.

- **Criterion:** Technical execution (30%).
- **On the slide:** "Local only: zero cloud calls". Boxes: Sources → **engram (the brain)** → You. Seven role
  chips. "22 planned agents → 7 roles on one pipeline."
- **Visual:** a boundary box labelled "Your laptop: local only". On the left, a "Sources" card: Email · Meetings ·
  Notes. In the centre, a large card with an amber outline, "engram: the brain", holding four tier chips (S0 code →
  S1 small judge → S2 14B → You) and a "hash-chained ledger" strip. On the right, a "You" card: Web app · Watch ·
  Obsidian vault · MCP tools. Arrows run left to right. Below, a row of seven role chips: Librarian, Researcher,
  Memory, Planner, Operator, Guardian, Herald.
- **Say:** "Everything inside this box runs on the laptop. The seven roles are lanes of one pipeline, not chatting
  agents. Research shows multi-agent chains lose 39–70% on sequential work, so the hand-offs are logged function
  calls."

## Slide 4: A 1.7B trained on you beats a 14B that isn't

- **Criterion:** Innovation (20%) and technical execution (30%).
- **On the slide:** "S0 code → S1 small judge → S2 14B → you". Chart: accuracy on 4 decisions. "54 min of training
  · 5,958 of the owner's own labels · 3–5× faster."
- **Visual:** a native clustered column chart. Categories: Supported? · Relevant? · Will reply? · Which folder (12)?
  Series: 1.7B base (dark grey 5A5A5A), 14B zero-shot (light grey A0A0A0), 1.7B fine-tuned (white FFFFFF). Data
  labels on top, and a legend at the top. Values are in the appendix.
- **Say:** "Small yes/no judgements go to a 1.7B model we fine-tuned on the owner's own behaviour, on the laptop,
  in 54 minutes. It beats the 14B on all four decisions at a third to a fifth of the latency. We fine-tune skills,
  never facts: facts stay in the database, where they can be cited and deleted."

## Slide 5: Checked answers. Gated actions.

- **Criterion:** Technical execution (30%).
- **On the slide:** Two cards. **Answers:** "84% vs 6%", right when the judge vouches vs when it doesn't (AUROC
  0.92). **Actions:** "40.0% → 6.7%" harmful side effects; 0.62 owner prompts per task. "A small model may raise
  suspicion, never grant permission."
- **Visual:** the template's "Side by Side" layout. The left card is "Answers checked" with a big white number, the
  right card is "Actions gated". A thin footer card holds the rule.
- **Say:** "The small model checks the big one: when it vouches, answers are right 84% of the time, when it
  doesn't, 6%. For actions, code sets the risk, the 14B checks intent, and you approve. On 60 fresh sandbox tasks,
  harmful side effects fell from 40% to 6.7%, with fewer interruptions than approving everything."

## Slide 6: What you see

- **Criterion:** Product experience (15%).
- **On the slide:** Four screenshots with captions: Ask with sources · The brain as a 3D map and SQL · Belief
  timeline · Audit verified. A watch card: "Approve on your wrist · voice · reminders".
- **Visual:** a 2×2 grid of screenshots in dark rounded frames:
  - `Claude outputs/1280-dark-06-answer.png`
  - `Claude outputs/1280-dark-07-atlas.png`
  - `Claude outputs/1280-dark-09-agents.png`: despite its name, it shows the **belief timeline**, so the caption
    says so.
  - `Claude outputs/1280-dark-16-audit-verified.png`

  `1280-dark-13-add-done.png` is left out because it shows a database connection string with its password in the
  vault stage. The code bug behind that is fixed, but the screenshot is old.

  On the right, a drawn round watch card: "Approve? email.reply_email" with Approve and Deny. Under it: "approved
  on the wrist, ledgered 19 s after the gate paused".
- **Say:** "Every animation is real data: a particle is a real decision taking its real path. The watch is a second
  way in, straight over Wi-Fi with no phone app and no cloud push. You approve, ask by voice, and get reminders."

## Slide 7: Sovereign by design. New as a combination.

- **Criterion:** Innovation (20%) and impact (20%).
- **On the slide:** Left, "Zero cloud calls": Postgres + pgvector · Ollama and MLX on the Mac · watch over LAN
  Wi-Fi · a ledger of every decision. A DPDP pill. Right, a four-row comparison.
- **Visual:** On the left, four icon rows. Under them, a pill: "DPDP Rules: 1-year access logs · 72-hour breach
  reports · penalties up to ₹250 crore". On the right, a table with columns "Tool", "How it works", "Where it
  breaks":
  - Mem0: ADD-only memory; local server sunset (Jul 2026). Breaks: 97.8% junk in a 10,134-memory audit.
  - Graphiti: a small-model judge updates facts. Breaks: invalidated 41% of ~3,950 facts, silently.
  - GBrain: Postgres memory; LLM features hosted by default. Breaks: no per-decision confidence.
  - **Omnitrix:** a calibrated local judge plus a ledger. Breaks: limits measured (slide 8).
- **Say:** "Even careful local-plus-cloud delegation leaks on 7.5% of queries, so 'mostly local' isn't sovereign.
  Each mechanism has precedent. What nobody ships is the combination: one calibrated decision layer over memory
  and actions, with every decision visible, on your own machine."

## Slide 8: Demo, limits, next

- **Criterion:** Demo (15%), with honesty for technical execution.
- **On the slide:** Three columns (Demo · Limits · Next), plus a build line.
- **Visual:** three dark cards with amber step numbers.
  - **Demo:**
    1. Sign in to the kaminski brain.
    2. Ask "Where and at what time did Vince suggest meeting Michael Garberding on Tuesday?"
    3. Add an email with a promise: it becomes a belief.
    4. Act: "Forward my most recent email from fatima to kofi": the watch buzzes, approve.
    5. Audit: the newest ledger row is `owner:watch`; Verify chain.
  - **Limits:**
    - "Will they reply?" is only 60.1%, so it stays a suggestion.
    - The "worth remembering?" gate is the weak spot (72%, AUROC 0.80).
    - The watch uses plain HTTP on the LAN.
    - With Bluetooth on, the watch drops Wi-Fi when asleep.
  - **Next:**
    - Adapter v2 (+ remember, meeting_request, fulfilled, contradicts).
    - A learned "buzz now or later?" from the owner's taps.
    - TLS pinned at pairing.
  - **Build line:** "Built this week: 7,414 lines of Python · 3,047 of front end · 985 of Kotlin · 15 SQL migrations
    · 113 tests".
- **Say:** "Five minutes, all live, and nothing leaves the laptop. Every limit here is measured, and every next step
  already has its training data flowing from use."

---

## Chart data appendix

**Slide 4: accuracy on held-out conversations (%)**

| Decision | 1.7B base | 14B zero-shot | 1.7B fine-tuned |
|---|---|---|---|
| Supported? | 83.7 | 95.5 | 96.6 |
| Relevant? | 74.4 | 87.5 | 90.9 |
| Will reply? | 44.6 | 55.4 | 60.1 |
| Which folder (12)? | 31.5 | 47.9 | 52.7 |

**Slide 5: before / after (the gate, 60 fresh WorkBench tasks)**

| Setup | Tasks done right % | Harmful side effects % | Owner prompts per task |
|---|---|---|---|
| 14B agent, no gate | 38.3 | 40.0 | 0 |
| Approve everything | 46.7 | 13.3 | 0.97 |
| engram's gate | 48.3 | 6.7 | 0.62 |
| + directory check | — | 3.3 | 0.53 |

**Slide 5: answer checking (100 held-out EnronQA questions)**

| | Right |
|---|---|
| The judge vouches | 84% |
| The judge doesn't vouch | 6% |
| Overall (audited) | 70% |

## Sources

| Number or claim | File |
|---|---|
| 97.8% of 10,134 Mem0 memories junk; Graphiti 41% of ~3,950 invalidated | `docs/research/lit-review.md` §13.3 (lines 720–721); `docs/deck.md` slide 2 |
| 7.5% leak (PAPILLON); DPDP 1-year logs, 72-hour reports, ₹250 crore | `docs/research/lit-review.md` §12 (lines 68, 694) |
| Mem0 ADD-only, local server sunset (Jul 2026) | `docs/research/lit-review.md` line 711 |
| GBrain: hosted LLM features by default, no per-decision confidence | `docs/research/notes/F-landscape-prior-art.md` line 324 |
| 22 agents → 7 roles; 39–70% loss on sequential work | `docs/research/agent-roster-review.md` §2 and §7 |
| Judge accuracies (83.7/95.5/96.6 … 31.5/47.9/52.7); 54 min; 5,958 labels | `engram/README.md` measured table (line 116); `docs/deck.md` slide 5 |
| 3–5× faster | `docs/deck.md` slide 5; `engram/README.md` ("a third to a fifth of the latency") |
| 84% vs 6%, AUROC 0.92, 70% correct | `engram/README.md` line 118 |
| Gate 40.0% → 6.7%, 0.62 vs 0.97 prompts, 38.3/46.7/48.3 right, 3.3% at 0.53 | `engram/README.md` line 119 |
| Watch approval ledgered 19 s after the gate paused | `docs/deck.md` slide 11 and B3 |
| "Will reply?" 60.1%; remember gate 72%, AUROC 0.80 | `engram/README.md` line 116; `docs/deck.md` slide 17; `docs/research/agent-roster-review.md` §4 |
| Watch drops Wi-Fi with Bluetooth on; plain HTTP on the LAN | `engram/watch/README.md` |
| 7,414 / 3,047 / 985 lines, 15 migrations, 113 tests | counted from the repo on 28 Sep 2026 at 16:25 (`wc -l` over `engram/src/engram/**/*.py`, `engram/src/engram/web` without `vendor/`, and `engram/watch/app/src/**/*.kt`; `ls sql/*.sql`; `pytest --collect-only`) |
| Screenshots | `Claude outputs/1280-dark-06-answer.png`, `-07-atlas.png`, `-09-agents.png`, `-16-audit-verified.png` |

## Open questions

- **An Agents-view screenshot** doesn't exist (the file named `09-agents` is the belief timeline). Take one from the
  Agents tab if you want it on slide 6.
- **Team name, member names and contact** for the title slide: not in the repo. Left off the slides.
- **Adapter v2** is being trained now (28 Sep, by another session). If it finishes and is measured before the
  pitch, move it from "Next" to slide 4 with its numbers.
- **A photo of the real watch** showing an approval card doesn't exist yet. Slide 6 draws the card instead.
- **"Zero cloud calls"** comes from the architecture (every model and store is local). No network capture was
  recorded as proof. If there's time, run the demo with Wi-Fi internet off and say so.
