# Demo data - Ravi Kumar's week

**Everything here is fictional.** People, companies, emails, numbers and the news items are made up
for the demo; all email addresses use the reserved `.example` domain.

**Ravi Kumar**, founder and MD of **Suryodaya Foods Pvt Ltd** (packaged snacks, 120 people, factory
in Hosur), during the week of **Mon 5 - Fri 9 Oct 2026**. The demo day is **Thursday 8 Oct**, starting
at **08:55**.

## Files
| Path | What |
|---|---|
| `persona.yaml` | Ravi, his habits and preferences (loaded into Mem0 later) |
| `entities.yaml` | 14 people, 9 organizations, 7 projects and 41 relations (the knowledge graph seed) |
| `decisions.yaml` | 4 earlier decisions, incl. "no new vendors this quarter" and "max 6% discount" |
| `promise_history.yaml` | Closed promises - Rohit was late 3 of 4 times |
| `calendar.yaml` / `calendar.ics` | The demo week and the week after (40 events) |
| `emails.yaml` | 36 emails: 28 already in the inbox, 8 arriving live during the demo |
| `obsidian-vault/` | Meeting notes, people and project pages (copied to `var/vault` on reset) |
| `documents/` | 7 PDFs incl. the invoice with a hidden instruction and the 8% price letter |
| `voice-notes/` | 4 voice notes (16 kHz WAV) + transcripts |
| `outside-world/` | 4 fictional news pages for the Scout |
| `mehta-instance/` | Rajesh Mehta's AI secretary: calendar, policy, trip (for the Diplomat) |
| `test-set/` | 30 hand-labelled items for measuring extraction accuracy |
| `scenarios.md` | The 16 planted scenarios and the demo beat sheet |
| `build.py` | Regenerates the PDFs, WAVs and .ics files from their sources |

## Commands
```bash
uv run omnitrix demo reset --yes   # wipe local data, load the world, fill Mailpit, freeze clock at Thu 08:55
uv run omnitrix demo status        # demo clock, what's loaded, which live emails are still to come
uv run omnitrix demo play          # send every live email that is due by the demo clock
uv run omnitrix demo send L1       # send one live email now
uv run --group demo python demo_data/build.py   # rebuild PDFs / WAVs / .ics after editing sources
```
