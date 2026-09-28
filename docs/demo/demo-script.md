# engram: the 3-minute demo

A voice script and shot list for the judges' video. The screen part is driven by the page's presenter mode: open
`http://127.0.0.1:8770/?demo`, and every **→** (or Space) runs the next beat against the real brain and the real
models. The lower-left caption names each beat, so the video also reads with the sound off. The smartwatch is only
mentioned here (beat 9); its own demo is recorded separately.

A finished screen recording (no sound) is at `~/Movies/engram-demo/engram-demo.mp4`, with each beat's start time in
`engram-demo.beats.txt`. It was recorded with `docs/demo/record_demo.py`, which drives this presenter mode in a
Chromium window and captures the frames the page paints; `--from 6` reshoots from beat 6.

- **→ / Space:** next beat. A beat that is still waiting on a model ignores extra presses, so press once and talk.
- **H:** hide or show the captions. **Esc:** leave presenter mode.
- **`?demo=6`:** start at beat 6 (already signed in), to reshoot from there.

Timings assume a quiet machine: the 14B warm, and no training or evaluation running. Speak at about 150 words a
minute. The **[wait]** marks are where a model is working; keep talking over them, or trim them in the edit.

---

## Before you record (10 minutes)

1. **Free the Mac.** Quit apps you don't need, and make sure no training or evaluation is running (Activity Monitor:
   no `mlx_lm` or `v2_baseline` process). Memory pressure is what slowed the models in the rehearsal.
2. **Warm the models.** Sign in, then ask the demo question once on the Database view. The 14B and the judge are then
   loaded, and Ask takes about 7 s instead of 25 s. Sign out afterwards.
3. **The browser.** Use Safari or Chrome, full screen, at 1920×1080 or 1280×800, with no other tabs showing and
   bookmarks hidden. Open `http://127.0.0.1:8770/?demo` on the sign-in page, in the dark theme.
4. **Record.** Press ⌘⇧5, choose *Record Selected Portion* around the browser, and under Options pick your microphone
   if you want the voice live. Or record the screen silently and the voice afterwards with QuickTime or Voice Memos.
   Start the recording, wait two seconds, then press **→**.
5. **Retakes.** The demo email and the meeting request are the same every take. The email collapses into the same item
   (Add data then says "already in memory"), and the meeting reply only touches the WorkBench sandbox, which is in
   memory. Beat 9 approves the reply on the page, which writes one human approval to the ledger each take.

---

## The script

### Beat 1 · The problem (0:00–0:15), sign-in page

> **[→]** Your mail, your notes, your meetings: a second brain should know all of it, and it shouldn't have to send
> any of it to someone else's cloud. This is engram. Everything you're about to see runs on this laptop.

### Beat 2 · Sign in (0:15–0:25)

> **[→]** *(the kaminski tile opens; type the passphrase and press Enter)*
> Each brain is its own Postgres database, opened with its own passphrase. This one is a real mailbox: eleven and a
> half thousand emails.

*On screen: the tile's constellation grows into the 3D brain.*

### Beat 3 · Ask, with System 1 checking System 2 (0:25–0:55)

> **[→]** Let's ask it something. *(the question types itself)*
> Search finds candidates in milliseconds. A small model, 1.7 billion parameters that we fine-tuned on this owner's
> own mail, throws out what's irrelevant. **[wait]** Then the 14-billion-parameter model writes the answer, with a
> citation. And then the small model checks the big one: is the answer actually supported by what it cites?
> Supported, at 0.99. When the small judge vouches for an answer, it's right 84 percent of the time.

*On screen: the brain lights up in retrieval order, then the answer with "answered by qwen3:14b" and "supported · p
0.99" chips.*

### Beat 4 · Add data (0:55–1:25)

> **[→]** New information arrives all the time. Here's an email from Shirley. *(it types in)*
> It's searchable in milliseconds: stored, split, embedded. Then the judge makes a one-token decision: is this worth
> remembering? **[wait]** If yes, the big model pulls out the commitment and the meeting, and code rejects any quote
> that isn't really in the email. It all lands in an Obsidian vault the owner can edit.

*On screen: the five stages, each with its real timing; the belief pills appear at the end.*

*Optional line (+5 s):* "That gate runs our second fine-tune. Trained on labels the brain derived from its own
structure, it lifted 'worth remembering' from 67 to 80 percent on a hand-checked set, so each decision gets the adapter
that's best at it."

### Beat 5 · The agents (1:25–1:45)

> **[→]** These are the agents, and they aren't a chat room of LLMs. Each role is a lane of real work: code on the
> left, the small judge, the big model, and you on the right. Guardian decides what's safe. Planner schedules around
> meetings with a constraint solver. Operator acts.

*On screen: the role filter lights Guardian, then Planner, then Operator, across the four lanes.*

### Beat 6 · A meeting request, handled end to end (1:45–2:15)

> **[→]** A meeting request from Nia. One pipeline: the Librarian reads it, the Researcher sees how much you deal
> with her, the Planner finds free slots, the Writer drafts, and a Fact Checker in plain code makes sure the reply
> offers exactly those times and leaks nothing from your calendar. **[wait]** Then the gate stops. Sending an
> email is external, so it waits for me.

*On screen: the role steps with their timings, then the "Waiting on you" card with the exact call it will make.*

### Beat 7 · Audit (2:15–2:30)

> **[→]** Every judgement is written to a hash-chained ledger: what was asked, which tier answered, how sure it was,
> how long it took. Verify: fourteen thousand judgements, intact. The same ledger is the fine-tuning data.

### Beat 8 · The numbers (2:30–2:45)

> **[→]** Measured on this Mac: the fine-tuned 1.7B judge beats the 14B on every decision we trained, at a third of the
> latency. The gate cut harmful agent actions from 40 percent to under 7.

*On screen: the results card (96.6%, 84%, 40% → 6.7%, 13 ms).*

### Beat 9 · Your approval (2:45–3:05)

> **[→]** That meeting reply is still waiting on me. The same card is on my paired smartwatch, so I can approve it from
> my wrist; here I'll do it on the page. Approved: the reply goes out, and my decision goes into the ledger as a human
> one, next to every model's.

*On screen: the waiting card, then Approve; it flips to "Approved · 3.9 s · recorded as H in the ledger", and the top
bar drops to "0 waiting".*

### Beat 10 · Close (3:05–3:10)

> **[→]** Local models, your data, and the last word is yours. That's engram.

---

## Putting it together

- **Tracks:** the screen recording (beats 1–10) and your voice. The smartwatch demo is a separate recording.
- **Editor:** iMovie is enough. Put the screen recording on the main track and the voice underneath. Trim the
  **[wait]** gaps if you run long.
- **Target:** about 3:00. If you need to cut, beat 5 (agents) is the easiest to shorten; beat 7 (audit) can merge into
  beat 8.

## Where the numbers come from

All numbers are measured on this Mac and recorded in `engram/README.md` (*Measured on the example owner*):

- **96.6% vs 95.5%:** `supported`, fine-tuned 1.7B vs zero-shot 14B, on held-out conversations.
- **84% / 6%:** `ask` answers right when the judge vouches / when it doesn't (100 held-out EnronQA questions).
- **40.0% → 6.7%:** WorkBench, 60 fresh tasks, harmful side effects, agent alone vs through the gate.
- **13 ms:** time from arriving to searchable. **11,528 items in 2.8 s:** ingest with no model calls.

- **67% → 80%:** adapter v2 on `remember`, on the hand-labelled gold set of 90 (AUROC 0.70 → 0.86,
  `engram/data/results/v2-eval.log`), and 66% → 75% on `meeting_request` (AUROC 0.62 → 0.85,
  `engram/data/results/v2-eval.json`). v2 lost ground on round 1's decisions, so the judge is routed: v2 for
  those two decisions, v1 for everything else, including the 96.6% on `supported`.
