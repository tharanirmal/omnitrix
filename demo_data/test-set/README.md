# Librarian test set (30 items)

Hand-labelled messages for measuring how well the Librarian extracts tasks, meeting requests and
other people's promises. **dev.jsonl** (20) is for improving prompts; **holdout.jsonl** (10) is only
run for the final score we report - never tune prompts on it.

Each line: `id, split, tags, received_at, from, reader, text, expected{tasks, meeting_request, promises}`.

## Labelling conventions
- The reader is Ravi Kumar; only tasks **Ravi** must do are tasks. Things other people will do are
  `promises`, not tasks.
- Relative dates are resolved from `received_at` in Asia/Kolkata ("tomorrow", "next Tuesday",
  "end of the month" = 31 Oct).
- "Next <weekday>" means that weekday in the following week (said on Mon 5 Oct, "next Wednesday"
  is Wed 14 Oct); a bare weekday ("by Friday") is the coming one.
- A date without a time means 18:00 local; "morning" means 10:00.
- "Next week" with no day is a window, not a date: `due_at: null` plus `window`.
- Times in another timezone are converted to IST in `start`, and the original zone is kept in `timezone`.
- Negations ("no need to...") and things already done produce **no** task. Newsletters and
  notifications produce nothing.

## Scoring (implemented in `evals/` in Phase 1)
A predicted task matches an expected one when the `action_type` agrees, the due date is on the same
day (or both are null), and at least one person overlaps. Titles are free text and are not scored.
Reported: task precision / recall / F1, meeting start accuracy, and "nothing extracted" accuracy on
noise, negation and already-done items.
