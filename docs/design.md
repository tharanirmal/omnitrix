# engram — design

How engram's front end looks, feels and moves. The feature prompt says *what* the UI does; this file says how it should
look. When the two disagree about something visual, this file wins.

## 1. Concept: the brain as an instrument

engram is a precise, local machine that thinks in tiers: code (S0), the small judge (S1), the large model (S2) and the owner (H).
The UI should feel like a purpose-built lab instrument or observatory console. It should not look like a SaaS dashboard or a
chat app.

- **Data is the decoration.** Real counts, probabilities, latencies and hashes carry the visual interest. Nothing is
  there only to look impressive.
- **The architecture is the visual language.** The four tiers each own one colour and one motion character, used the
  same way everywhere. After a minute of use, a viewer should be able to tell "S2 decided that" at a glance.
- **Calm by default, alive where it matters.** The screen is mostly still. Movement means something happened.
- **Quietly sovereign.** A small "local only" seal is always visible, and nothing is loaded from the network (fonts and
  icons are vendored).

## 2. Colour

Dark-first. Ink and graphite surfaces, one warm off-white for text, and the four tier colours as the **only** accents.

| Token | Value | Use |
|---|---|---|
| `--ink` | `#07080B` | page background |
| `--graphite-1` | `#0E1015` | panels, drawers |
| `--graphite-2` | `#151821` | raised elements, inputs |
| `--hairline` | `#232733` | 1px rules, table lines, graph edges at rest |
| `--text` | `#ECE8DF` | primary text (warm off-white, never pure white) |
| `--text-dim` | `#9A9689` | labels, secondary text |
| `--text-faint` | `#5F5C55` | disabled, timestamps at rest |
| `--s0` | `#8C96A8` | S0 · code: steel |
| `--s1` | `#46D2E0` | S1 · small judge: cyan |
| `--s2` | `#A393FF` | S2 · large model: soft violet |
| `--h`  | `#F3B64A` | H · the owner: amber; also "waiting on you" |
| `--ok` | `#6FCF97` | verified, done (sparingly) |
| `--bad` | `#FF7A6B` | broken chain, errors |

Rules:
- A tier colour appears only where that tier is involved: its chip, its lane, its particle, its node glow.
- Keep large filled areas neutral. Accents appear as strokes, glows, dots, chips and small numerals.
- Belief kinds in the graph (commitment, decision, meeting, person, item) use desaturated variants that don't compete
  with the tier colours: tints of the text colour at different lightness, told apart by shape as well as colour.
- A light theme is optional. If you build one, keep the same tier hues darkened to reach AA on a warm paper
  (`#F4F1EA`).
- Contrast: body text ≥ 4.5:1 and UI glyphs ≥ 3:1 against their surface. Check tier colours on `--graphite-2`.

## 3. Typography

- **A grotesk with character for UI text.** Proposed: *Instrument Sans* (OFL).
- **A monospace for every measurement:** ms, p, counts, ids and hashes. Proposed: *JetBrains Mono* (OFL), with tabular
  numerals.
- Both are vendored as woff2 in `web/vendor/fonts/`, ≤ 300 KB total, with licences in `vendor/NOTICE.md`. Ask before
  downloading. The fallback stack is `-apple-system, system-ui` / `ui-monospace, "SF Mono", Menlo`.
- Scale: 11 / 12 / 14 / 16 / 20 / 28 / 44 px. Body text is 14 px. Big numbers such as counts on profile tiles are 44 px mono
  with weight 300.
- Labels are small caps or uppercase at 11 px with +0.08em tracking and `--text-dim`, as on an instrument panel.
- Numbers never jump in width while they change: use `font-variant-numeric: tabular-nums`.

## 4. Layout and components

- **Shell:** a thin top bar (brain name, live counts, S1/S2 model names, local-only seal, pending-approvals indicator),
  a left rail of four views (Agents, Database, Add, Audit) with icons and labels, and the content area. The 3D
  constellation sits behind everything at very low intensity and comes forward only in the Database view.
- **Grid:** 8 px base. Panels have 1px `--hairline` borders and 10 px radius, and are flat. Use depth from layering and
  hairlines, not heavy shadows. At most one soft shadow, only on drawers and the command palette.
- **Drawers**, not modals, for details (agent, node, ledger row). They slide in from the right, stack, and close with Esc.
- **Chips:** tier chips are a small dot plus a mono label (`● S1`). Status chips (idle, running, waiting, offline,
  error) are outlined, except "waiting on you", which is filled amber.
- **Tables** (audit log): dense 32 px rows, hairline separators, mono numerals right-aligned, hover highlights the
  row and its chain connector.
- **Icons:** custom inline SVG, 1.5 px stroke, round caps, drawn on a 20 px grid. No emoji and no icon fonts.
- **Empty states** explain what will appear and how to cause it ("Drop a .eml file to watch it being sorted"). No
  illustrations.
- **Responsive:** designed first for a 1280×800 projector, and it must work at 390 px. At narrow widths the left rail becomes
  a bottom bar, drawers become full-screen sheets, and the switchboard lanes stack vertically.

## 5. Motion

Motion has meaning. Each animation says one of: *something arrived, something was decided, something was
verified, something is waiting on you.*

**Tier motion characters**, used for glows, particles and status:
- **S0:** instant and mechanical. Snaps with no easing, 80–120 ms steps.
- **S1:** quick flickers. 120–180 ms, a sharp ease-out.
- **S2:** slow and deliberate. 400–700 ms, soft ease-in-out, like it is thinking.
- **H:** a heartbeat. A double pulse every ~1.6 s while something waits on the owner.

**Tokens:** `--dur-1: 150ms`, `--dur-2: 250ms`, `--dur-3: 400ms`. Standard easing
`cubic-bezier(.2,.8,.2,1)`, spring-like overshoot for arrivals `cubic-bezier(.34,1.4,.64,1)`. Only data
"physics" (the graph, flying fragments) may run longer than 700 ms.

**Tools:** the View Transitions API between views and lenses, WAAPI or CSS for micro-interactions, and canvas/WebGL only
for the graph and particles. Animate only `transform` and `opacity`, never layout properties.

### Choreography per feature

- **Login.** Each profile tile holds a tiny live constellation of its own brain, with a handful of nodes drifting slowly.
  Selecting a tile focuses it, the other tiles dim, and the passphrase field slides out from inside the tile. On
  success, the tile's constellation expands into the full dashboard graph as a shared-element transition. This is the
  signature moment of the demo. A wrong passphrase makes the tile shake quickly three times (±6 px, 300 ms) and shows a
  written message. "Log out" plays the expansion in reverse.
- **Agents switchboard.** Four lanes run left to right: S0 → S1 → S2 → H. Running agents breathe in their tier's character,
  idle agents are perfectly still, and "waiting on you" does the amber heartbeat. Each new ledger row fires one particle
  along the path the decision actually took (for example it enters S1, flickers, hands off to S2, and settles). Particles
  fade out; they never pile up.
  The watch is a device node that flashes amber when an approval comes from it.
- **Database lenses.** Switching lenses (Constellation ↔ Schema atlas ↔ Belief timeline) morphs shared elements,
  so a table node in the atlas grows into its rows. Ask highlights: the touched nodes brighten in sequence along
  retrieval order, then the edges between them draw in.
- **Add data.** The animation tells the true story, one stage at a time, paced by the real stage timings:
  - *Stored:* the text block splits into chunk slivers.
  - *Embedded:* the slivers get a brief vector shimmer.
  - *Gate:* a visible gate element lights in the deciding tier's colour and shows P(worth remembering) counting up.
    If S0 decides there is nothing to remember, the item settles gently into a "not kept" tray.
  - *Extracted:* belief fragments fly into labelled bins (commitments, decisions, meetings, people) with the arrival
    spring.
  - *Vault:* a note glyph lands.
  - *Done:* the new item is born into the constellation and its edges draw in.
  - *Error:* the animation stops at the failing stage, and that stage turns `--bad`.
- **Audit chain.** Each ledger row connects to the row before it with a thin vertical line. "Verify chain" sends a
  scan down the connectors, turning each one `--ok` in turn and accelerating as it goes. On a break, the scan stops at
  that point, the break glows `--bad`, and the row expands to explain what failed.
- **Live numbers.** When a count changes, it rolls digit by digit. It never re-renders the whole number with a flash.
- **Approvals.** The pending card rises from the top bar indicator. Approving or denying collapses it into a small chip that
  flies into the audit log's newest row.

### Reduced motion

With `prefers-reduced-motion: reduce`, every animation above becomes a 150 ms opacity fade or an instant change. The
graph stops drifting, particles are replaced by a brief highlight of the lane that decided, and the chain verification
reports its result immediately. All information shown through motion must also be available as text.

## 6. Banned

- Purple-to-blue gradients, neon glows on everything, glassmorphism as a default surface.
- Generic KPI card grids ("Total items: 11,529" in four identical cards).
- Emoji, icon fonts, "AI sparkle" icons, robot mascots, stock illustrations.
- Skeleton shimmer everywhere. Show real progress (stages, timings) instead.
- Centred hero text, marketing copy, lorem ipsum, fake data.
- Animation with no meaning: ambient floating blobs, parallax, perpetual gradient shifts.

## 7. Accessibility checklist

- Everything is keyboard-reachable with a visible 2px focus ring in `--text` offset by 2px, and a ⌘K command palette.
- Colour is never the only signal: tier chips carry text labels (S0/S1/S2/H), and statuses carry words.
- Live regions announce approvals waiting, add-data completion and chain verification results.
- Hit targets are ≥ 32 px on desktop and ≥ 44 px on touch.
