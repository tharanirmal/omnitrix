# Omnitrix pitch: speaker notes

These notes go with `docs/Omnitrix-pitch.pptx`, which `docs/build_pitch_deck.py` builds. Every number is traced in
`docs/deck-prompt-claude-max.md` §3. The TAM comes from [Research and Markets, Personal AI Assistant Market Report
2026](https://www.researchandmarkets.com/reports/6226037/personal-ai-assistant-market-report); SAM and SOM are our
own assumptions.

## 1 · Omnitrix

> "Omnitrix is a secretary that lives on your laptop. It remembers your work, keeps your promises and acts only with
> your OK. Its brain, engram, never sends anything to a cloud."

## 2 · Storing is easy. Judging is hard.

> "The hard part isn't storing things. It's the thousands of small judgements: is this worth remembering, did this
> plan change, should this email go out? One audit found 97.8% of an AI memory store was junk. Another tool's small
> judge silently invalidated 41% of facts. Even careful local-plus-cloud setups leak on 7.5% of queries."

## 3 · Our answer: a personal AI you own

> "We built a personal AI that learns how *you* judge, runs entirely on your laptop, and uses a 1.7B model we
> fine-tuned on you. It's a small society of models: a fast small one for the many small calls, a slow large one for
> the hard middle, and you for what neither settles. Underneath is a second brain that keeps every memory with its
> source."

## 4 · The brain and its society of agents

> "Everything inside this dashed box runs on one laptop. Sources flow into engram, where code, the small judge and
> the 14B make decisions, and each one lands in a hash-chained ledger. We cut the 22 agents we planned down to 7 roles
> on one pipeline, because research shows chains of chatting agents lose 39–70% on sequential work. Everything is
> plain Postgres: memory, the ledger, plans and the watch's cards."

## 5 · A judge trained on you, a watch that asks you

> "The judge is trained on what the owner already did: 5,958 labels from their own replies and filing, 54 minutes on
> the laptop. It beats the zero-shot 14B on all four decisions, at a fraction of the latency. The watch is a Kotlin
> app on a Galaxy Watch 5. When the gate pauses an action, the watch buzzes over Wi-Fi with no cloud push, and a real
> approval was ledgered 19 seconds after the pause."

## 6 · Impact and benefits

> "Private, because nothing leaves the laptop. Personalised, because the judge learns from you. Harmful actions fell
> from 40% to 6.7%, and the memory gate took a third of the time. The personal AI assistant market is $3.4B in 2025
> and projected at $19.63B by 2030. We target the privacy-first slice. The SAM and SOM figures are our stated
> assumptions, not sourced facts."

## 7 · Feasible today, on one laptop

> "It runs on one 24 GB laptop. Search takes milliseconds, the small judge about 200 ms per email, and an answer a
> median of 11 seconds, or 1.7 seconds in draft mode. And privacy is built into the architecture: the page is served
> on 127.0.0.1, and every decision is logged for the DPDP Rules' audit needs."

## 8 · References

> "Every design choice has a source: the multi-agent evidence, the solver-backed planner, the privacy leak rates, the
> DPDP Rules, the public datasets we measured on, and the market report."

## 9 · Thank you

> "Your brain, on your machine. The code is on GitHub."

Before presenting, replace **TODO: team contact** on this slide with your team's details.
