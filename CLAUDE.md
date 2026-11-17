# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Cuno is a browser-based, room-code multiplayer Uno-style card game for 2–10 friends playing remotely. The design spec is `docs/superpowers/specs/2026-11-15-cuno-design.md`. Game rules live in `cuno_rules.md`, which is the source of truth for the engine: if the code and that file disagree, one of them is a bug. Card art and branding must stay original (no "UNO" wordmark or Mattel-style oval logo).

## Commands

Backend (Python 3.14, managed with uv):

```bash
uv sync                                   # install deps (incl. dev group)
uv run cuno                               # run server on :8000 (serves web/dist if built)
uv run pytest                             # all tests
uv run pytest tests/test_engine.py::test_skip -x   # single test (tests/test_rooms.py covers rooms + WebSocket)
```

Frontend (`web/`, Svelte 5 + Vite + TypeScript):

```bash
cd web && npm install
npm run dev        # Vite on :5173, proxies /api and /ws to :8000 (run `uv run cuno` too)
npm run build      # outputs web/dist, which FastAPI serves in production
npm run check      # svelte-check type checking
```

## Architecture

```
browser (Svelte) ──WebSocket JSON──► server.py ─► rooms.py (Room, RoomManager) ─► engine.py (Game)
                 ◄── per-player snapshot + events ──
```

- **`engine.py` is pure.** It has no I/O and no asyncio. `Game.apply(seat, action)` validates the action (raising `IllegalMove`), mutates the state, and returns a list of event dicts. Randomness comes through an injected `random.Random` so tests are deterministic. All rule logic belongs here, not in the server or the client.
- **The server is authoritative and sends full snapshots.** After every accepted action, `Room` broadcasts to each connection `views.snapshot_for(game, seat)` (that player's own hand plus only the counts of other players' hands) together with the `events` from that action. Clients never compute game state; they render snapshots and use `events` only to drive animations. Never put another player's cards into a *player* snapshot.
- **Spectators.** Anyone who joins after the game has started becomes a `Spectator` (kept in `Room.spectators`, separate from `players`). A spectator follows one player: `Spectator.watching` holds the `Player` object rather than a seat number, because seat numbers change between games. It falls back to the host if that player is gone. A spectator gets `views.spectator_snapshot_for` (the followed seat's view plus `hands` for every seat) and may only send `watch{seat}`; any other message gets the `spectator` error. Spectators arriving or leaving use `Room._broadcast`, which sends a snapshot without bumping `version` or resetting the timer. `_commit` is reserved for game changes. Spectators never become host and don't count toward the timer or room cleanup. `leave` removes a spectator, while a dropped connection keeps the record so a refresh can reclaim it. On the client, the table is drawn around `viewSeat(state)` (`you ?? watching`).
- **Concurrency:** each `Room` serialises actions with its own `asyncio.Lock`. Ordering races (an UNO call against a Catch) are decided by arrival order at the lock.
- **Stale actions:** each snapshot carries a `version`. Turn actions include `seq` (the version the client saw), and a mismatch is rejected with a fresh snapshot.
- **Identity and reconnecting:** there are no accounts. On `join` the server issues a `token`, which the client keeps in `localStorage` per room code. Rejoining with that token reclaims the same seat and hand. Disconnected seats stay in the game, and the turn timer auto-plays (draw + pass) for them.
- **Rooms live only in memory** (`RoomManager`). Empty rooms are removed after a grace period. There is no database.
- **Frontend state:** `web/src/lib/client.svelte.ts` owns the WebSocket (auto-reconnect with backoff, rejoin with token, adds `seq` to sequenced actions) and holds the latest `RoomState`. Components render only from `client.state`. The turn timer is sent as a relative `time_left_ms`, and the client converts it to a local `client.deadline`.
- **Animations (`fx.svelte.ts`):** the client calls `fx.before(events)` before rendering a new snapshot and `fx.after(events)` after it. `before` records where your hand cards are and hides the cards that are about to arrive (`hiddenTop`, `hiddenHand`). `after` flies temporary `Card` instances between `[data-pile=draw|discard]`, `[data-seat-anchor=N]` and `[data-hand] [data-card-id=…]` using the Web Animations API, then un-hides them. Anything new that should be animated needs these data attributes. Seat effects and toasts are also driven by `fx`. Hand reflow uses `animate:flip`. Respect `prefers-reduced-motion`.
- **Layout:** `Table.svelte` puts opponents around an ellipse in play order (the next player sits on your left). It switches to a scrolling strip of chips (`compact`, passed down to `Seat`) based on the measured felt size and the player count, not only the viewport width. Card sizes come from the `--card-lg`/`--card-md` CSS variables set in `App.svelte`. `Card.svelte` sizes its insides with `cqw` units, which resolve against the `.card` container element, so styles go on `.face`, not `.card`.
- **Protocol:** message shapes are defined in `src/cuno/protocol.py` and mirrored by hand in `web/src/lib/types.ts`. Change both together.
- **Deploy:** the `Dockerfile` builds `web/dist`, then runs `uv run cuno`, which serves the SPA (unknown paths fall back to `index.html` for `/r/CODE` links). Rooms live in memory, so run a single instance.
