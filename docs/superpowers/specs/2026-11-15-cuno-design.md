# Cuno: online Uno-style card game for friends

## Context
Cuno lets a group of 4–10 friends, each at home, play Uno-style card games together in a browser using a room code. Priorities, in order:
1. **Reliable multiplayer**: correct rules, no desyncs, and surviving dropped connections.
2. **A polished frontend**: well-designed cards, responsive layout, animations, and a clear view of who sits where and whose turn it is.
3. **Simple, maintainable architecture.**

The rules are the standard rules as written in `cuno_rules.md` (repo root), which is the source of truth for the engine. The repo is an empty uv project (Python 3.14, `src/cuno/__init__.py` stub). There is no existing code to reuse.

Decisions made so far: room size 2–10 with one deck, no accounts (nickname + room code only), rooms held in memory, Python FastAPI + WebSockets server, Svelte + Vite frontend built to static files served by FastAPI (one deploy). The card art is original, not copied from Mattel: no "UNO" wordmark, no red oval logo.

## Architecture

```
browser (Svelte) ──WebSocket JSON──► FastAPI ─► RoomManager ─► Room ─► Game (pure engine)
                 ◄── per-player snapshot + events ──
```

- **The engine is pure Python**, with no I/O and no asyncio. `Game.apply(seat, action) -> list[Event]` either raises `IllegalMove` or mutates the state. The random number generator is injected so tests are deterministic. Every rule in `cuno_rules.md` maps to a test.
- **The server is authoritative.** After each accepted action, every client gets (a) a **full snapshot filtered for that player** (their own hand plus everyone else's card counts, never other players' cards) and (b) the **events** that just happened, which drive the animations. A full snapshot every time means nothing to keep in sync and no drift. Payloads are tiny at 10 players.
- **Each room has one `asyncio.Lock`**, so actions are applied one at a time in arrival order. This settles the UNO call and Catch race, because whoever reaches the server first wins.
- **Each action carries a `seq`.** Every snapshot has a version number, and an action stamped with an old version is rejected and answered with a fresh snapshot. This stops double-clicks and stale clicks.

### Python layout (`src/cuno/`)
| File | Responsibility |
|------|----------------|
| `cards.py` | `Color`, `Kind` (number/skip/reverse/draw2/wild/wild4), `Card(id, color, kind, value)`, `build_deck()` (108 cards, unique ids) |
| `engine.py` | `Game` state machine: dealing, first-card effects, legal-move check, draw-then-may-play, action effects, Wild Draw Four challenge window, UNO/catch window, reshuffle, round end, scoring to 500 |
| `views.py` | `snapshot_for(game, seat)`: the per-player filtered state |
| `rooms.py` | `Room` (code, seats, host, lobby/playing/round_over/game_over phase, turn timer task, reconnect tokens), `RoomManager` (create/join, removes rooms that have been empty for more than 10 minutes) |
| `protocol.py` | Pydantic models for client→server and server→client messages |
| `server.py` | FastAPI app: `POST /api/rooms`, `GET /ws/{code}`, serves `web/dist` |
| `__init__.py` | `main()` runs uvicorn (keeps the existing `cuno` script entry point) |

### Protocol (JSON over WebSocket)
- **Client → server:** `join{name, token?}`, `start`, `play{card_id, color?, seq}`, `draw{seq}`, `keep{seq}` (pass after drawing), `call_uno`, `catch{target_seat}`, `challenge{seq}`, `accept{seq}`, `next_round`, `leave`.
- **Server → client:** `welcome{seat, token}`, `state{snapshot, events[]}`, `error{code, message}`.
- **Reconnecting:** `token` is a UUID stored in `localStorage` for each room. Rejoining with it gives the player back their seat and hand. While a player is disconnected their seat stays reserved, and their turns are auto-played (draw + pass) when the timer runs out.

### Room behaviour
- The host starts the game once at least 2 players have joined. If the host leaves, the next seat becomes host.
- **Turn timer: 30 s.** On timeout the server draws a card for the player and passes. A ring around their avatar shows the time left.
- The UNO window and the challenge prompt work as described in `cuno_rules.md` §9.
- New joiners can only enter in the lobby. Mid-game joins are a non-goal for now.

## Frontend (`web/`, Svelte 5 + Vite + TypeScript)

### Screens
1. **Home:** nickname, plus *Create room* / *Join with code*. Opening `/r/ABCD` jumps straight to the join step.
2. **Lobby:** a large room code with a copy-link button, seat list, host badge, and a Start button (host only).
3. **Table:** the game itself.
4. **Round summary / game over:** each player's points for the round and running totals up to 500. Host can start the next round.

### Table layout
- **You always sit at the bottom.** Opponents are placed around an ellipse in turn order, so the seating matches play direction.
- **Each seat shows:** avatar initial with a colour, name, a small fan of face-down cards with the count, an **active-turn glow + countdown ring**, an UNO badge, and a disconnected indicator.
- **Centre:** draw pile, discard pile, a **current-colour halo** (important after a Wild), and a **direction ring** with arrows that spins on Reverse.
- **Your hand:** a fanned row of cards. Playable cards lift and glow, and unplayable ones are dimmed. Tap or click to play. A Wild opens a colour picker.
- **Action bar:** Draw / Keep, a **UNO!** button (pulses when you have 2 cards and it's your turn), and Catch buttons that appear on opponents who forgot to call UNO.
- **Responsive:** on desktop, a full ellipse. On phones (portrait), opponents become a compact row of chips at the top (scrollable for up to 9), the piles sit in the middle, and the hand overlaps more tightly with horizontal scroll. Target down to 360 px wide with no horizontal page scroll.

### Card design (original, rendered with SVG/CSS, no image files)
- A rounded rectangle with a solid colour body (a tuned red/yellow/green/blue that keeps contrast in light and dark), a large centre emblem shape (rounded diamond) carrying the number or icon, and small corner indices.
- Custom SVG icons for Skip (⊘), Reverse (two arcs), +2, Wild (four-colour pinwheel) and +4.
- Card back: dark gradient with a "cuno" wordmark.
- One `Card.svelte` component with sizes `sm` (opponent fan), `md` (piles), `lg` (hand).

### Animations (Svelte `crossfade` + `animate:flip`, all short at 200–450 ms)
- **Playing a card:** the card flies from your hand, or from an opponent's seat, to the discard pile with a slight rotation. The rest of the hand closes the gap.
- **Drawing:** cards fly from the draw pile to your hand, or to the opponent's seat fan. A +2/+4 shows a short "+N" burst on the victim.
- Skip shows a ⊘ stamp on the skipped seat, Reverse spins the direction ring, and the turn glow slides to the next seat.
- An UNO call shows a speech-bubble burst, and a Catch shakes the caught seat.
- Animations are driven by the server's `events[]`. If someone reconnects or there's no event, the snapshot is applied without animation.
- `prefers-reduced-motion` replaces flight animations with fades.

### Frontend structure
`web/src/lib/`: `socket.ts` (connection, auto-reconnect with backoff, `seq`), `store.svelte.ts` (snapshot + event queue), `Card.svelte`, `Hand.svelte`, `Seat.svelte`, `Table.svelte`, `Piles.svelte`, `ColorPicker.svelte`, `ActionBar.svelte`, `Lobby.svelte`, `Home.svelte`, `RoundSummary.svelte`, `theme.css` (colour tokens, light/dark).
Dev: Vite dev server proxies `/ws` and `/api` to uvicorn on :8000.

## Build order
1. **Engine + tests:** `cards.py`, `engine.py`, `views.py`, with pytest covering every section of `cuno_rules.md`.
2. **Server:** `protocol.py`, `rooms.py`, `server.py`, timer, reconnect. Integration tests drive several WebSocket clients through `TestClient`.
3. **Frontend shell:** Vite/Svelte scaffold, socket and store, Home, Lobby.
4. **Table + cards:** static layout, `Card` designs, responsive breakpoints, playing through a full round.
5. **Animations and polish:** event-driven flights, turn and direction indicators, UNO/Catch/challenge interactions, round summary.
6. **Ship:** multi-stage `Dockerfile` (Node builds `web/dist`, then a Python image runs uvicorn), README with run and deploy steps (Fly.io/Render).

Dependencies: `fastapi`, `uvicorn[standard]`, `pydantic`. Dev dependencies: `pytest`, `pytest-asyncio`, `httpx`. Frontend: `svelte`, `vite`, `@sveltejs/vite-plugin-svelte`, `typescript`.

After approval, the next step is to save this design as `docs/superpowers/specs/2026-11-15-cuno-design.md` and turn it into a step-by-step implementation plan (writing-plans) before writing code.

## Verification
- `uv run pytest`: engine rule tests (deterministic seeds), and room/protocol tests that run full games with 2, 4 and 10 simulated clients, including disconnect + rejoin, timer auto-play, the UNO/Catch race, and Wild Draw Four challenge outcomes.
- **Manual multiplayer:** `npm run build` then `uv run cuno`. Open 4+ browser windows (normal + private) and play a round to the end. Kill one tab mid-turn and reopen it to check the player gets their seat back.
- **Responsive:** check widths of 360, 768 and 1440 px in devtools, light and dark themes, and reduced motion.
- **Real network:** expose the dev server through a tunnel and play one game with friends on phones.

## Non-goals (for now)
House rules, accounts and persistence, mid-game joins as a player (spectators are now covered by `2026-11-17-spectator-mode-design.md`), voice and text chat, sound effects, using Mattel branding or art.
