# Cuno: spectator mode

## Intent
Today, opening a room link after the game has started is a dead end: `Room.join` refuses with "This game has already started." Spectator mode turns that into a seat in the audience. Anyone with the room link or code can watch a running game but cannot play. This is for friends who arrive late or just want to watch the group play.

This reverses a non-goal in `2026-11-15-cuno-design.md` ("spectators or mid-game joins"). Mid-game *joining as a player* is still out of scope.

## Goals
- Joining a room whose game has started makes you a **spectator** instead of an error.
- A spectator watches **over one player's shoulder**: the table is laid out exactly as that player sees it, with that player's hand face-up at the bottom (read-only).
- A spectator can **switch** to any other player by tapping their seat. They stay on the chosen player until they switch again manually. The view never jumps on its own.
- A small **hands panel** in the bottom-left corner of the felt shows every other player's current hand as tiny card chips, so spectators can check all hands without switching.
- **Players see they are being watched**: a "👁 N watching" chip in the top bar, which shows the spectators' names when tapped.

## Non-goals
- Spectators taking a seat. Once you're a spectator in a room, you stay one until you **leave and rejoin**. If you rejoin while the room is in the lobby, you join as a player as usual.
- Chat, reactions or any other spectator interaction.
- A spectator limit (it's a friends game).
- Watching after elimination. Cuno has no elimination: games run to the target score.

## Anti-goals (a failure even if it works)
- **A player connection receiving any other player's cards.** Spectators get every hand. Players get exactly what they get today: their own hand plus counts. This must be enforced on the server and tested.
- A spectator keeping a dead game alive (running the turn timer, or stopping the room from being swept).
- A spectator becoming host, or any spectator message changing game state.
- The spectator view jumping between players without the spectator asking.

## Decisions (made with the user)
1. **Who becomes a spectator:** anyone joining (with a nickname, through the existing Join form) while `room.game is not None`. In the lobby, joining works exactly as today.
2. **Server-side selection.** The spectator tells the server which seat it follows (`watch{seat}`), and the server builds the snapshot around that seat.
3. **Spectators see every hand.** The followed player's hand is shown big at the bottom. All other hands are in the corner panel. The user accepted the consequence that a player could open the link in a private window and see all hands, because this is a game between friends. The watching chip is the mitigation.
4. **Table layout:** over the shoulder (the spectator's "me" is the followed seat), defaulting to the host.
5. **Hands panel:** option B from the mockups, a small panel in the bottom-left corner that can be collapsed.
6. **After a game:** spectators stay spectators (including in the lobby before the next game) until they leave and rejoin.
7. **Watching chip** shown to players.

## Approaches considered
**Which hand(s) a spectator receives**
- **Server-side (chosen).** The server knows each spectator's followed seat and sends a snapshot built around it, plus all hands for the panel. This keeps all view logic in `views.py`, as the architecture requires, and lets the existing per-seat event filtering drive the draw animations into the followed hand.
- Client-side: the server sends every hand and the browser picks one. Switching is instant, but this moves view logic into the client and differs from how players are served. It was rejected.

**Where all hands are shown** (mockups A, B and C)
- A, a slide-out drawer: full detail, but hidden by default.
- **B, a corner mini-panel (chosen):** visible at a glance and collapsible.
- C, face-up chips under each seat: changes the seats, and has no room in compact mode.

**Spectator layout:** over the shoulder (chosen). A bird's-eye view of all hands was rejected because it's unreadable at 6–10 players and on phones. Following the current turn was rejected because the table spins every turn.

## Design

### Server: `rooms.py`
- New `Spectator` dataclass: `token`, `name`, `conn: Connection | None`, `watching: Player`. `Room.spectators: list[Spectator]`. `watching` stores **the player, not the seat number**, because seat numbers shift when `new_game` drops disconnected players or people leave the lobby. The spectator must stay behind the same person. The seat number is worked out (`players.index`) only when the snapshot is built. *(Settled by the conversation: spectators are tied to a player until they switch.)*
- `join(conn, name, token)`:
  - If `token` matches a player, behave as today.
  - If `token` matches a spectator, reattach `conn` (with the same "replaced" handling as players) and keep `watching`.
  - Otherwise, if `self.game is not None`, create a spectator with `watching` = the host. If there is no host, use the first connected player, or the first player. Do **not** raise `in_progress`.
  - Otherwise, behave as today (become a player; `full` still applies to players only).
  - Spectators never become `host`, and never clear `empty_since`.
  - Send `welcome{seat: null, token, role: "spectator"}` to spectators, and `welcome{seat, token, role: "player"}` to players.
  - Broadcast a `spectator_joined{name}` event so the players' watching chip updates. This goes through `_broadcast`, **not** `_commit`, so it causes no version bump and no timer reset. *(My call. Otherwise every spectator arriving, refreshing or dropping would restart the turn timer and make players' in-flight moves fail as `stale`.)*
- `disconnect(conn)`: for a spectator, set `conn = None` and keep the record so a refresh reclaims it. Broadcast `spectator_left{name}` (no version bump, no timer reset). The player-only logic (host handover, `empty_since`) is unchanged and ignores spectators.
- Explicit `leave` (the client clears its token too) **removes** the spectator record. *(My call: `server.py` currently breaks out of its loop on `leave` and calls `disconnect`, so add a `Room.leave(conn)` that the loop calls on `leave`. Then a dropped connection keeps the record and an explicit leave removes it. For players, `leave` keeps today's behaviour.)* A later rejoin is a fresh join, so in the lobby it becomes a player. This is how "leave and rejoin" works.
- `handle(conn, raw)`: a spectator may send only `watch{seat}` (and `leave`, which the socket loop handles). Anything else gets `error{code: "spectator", ...}`. For `watch`, validate `0 <= seat < len(players)` and set `watching = players[seat]`. Send that spectator alone a fresh `state` with no events and no version bump. It is *not* a game action, so it takes no `seq`.
- Split `_commit` into version bump + timer + `_broadcast(events)`. `_broadcast` sends to connected players as today, then sends each connected spectator its spectator state with `events_for(events, seat of spectator.watching)`.
- When `new_game` drops disconnected players, any spectator whose `watching` player was dropped falls back to the host. The same applies to a lobby `left`.
- Timer and sweep: these already count players only (`_schedule_timer`, `empty_since`). Keep it that way. When `RoomManager.sweep` removes a room, send each connected spectator `error{code: "closed", message: "This room has closed."}` so they aren't left on a frozen table. Add `closed` to the client's `FATAL` set.

### Server: `views.py`
- `spectator_snapshot_for(game, seat)` returns `snapshot_for(game, seat)` plus `hands: {str(seat): [card dicts]}` for **every** seat. It's the same shape as `last_round.hands`.
- `snapshot_for` itself is unchanged, so player snapshots cannot gain `hands`.

### Room snapshot (`Room.snapshot_for` and the spectator variant)
These fields are added, and must be mirrored in `web/src/lib/types.ts`:
- `role: "player" | "spectator"`
- `you: number | null`: `null` for spectators
- `watching: number | null`: the followed seat for spectators, `null` for players
- `spectators: string[]`: names of **connected** spectators, sent to everyone (drives the chip; a spectator's own name is included)
- For spectators, `game` comes from `spectator_snapshot_for(game, watching)`. In the lobby `game` is `null` as usual.

### Protocol (`protocol.py` and `types.ts`)
- Client → server: new `Watch{type: "watch", seat: int}`.
- Server → client: `welcome` gains `role` and `seat` becomes nullable.
- New error codes: `spectator` (a spectator tried to act), `closed` (room swept).

### Frontend
- `client.svelte.ts`: add `watch(seat)` (sends `watch`). Add `closed` to `FATAL`. The token per room code works unchanged for spectators, so a refresh reclaims the spectator record and the followed seat.
- **The seat the screen is centred on:** components that use `s.you` for layout (`Table.svelte` seat ring, `fx.svelte.ts` hand anchors and toasts) use `view = s.you ?? s.watching`. Wording that says "You" for `s.you` must use the followed player's name for spectators, e.g. "Ana's turn" rather than "Your turn". In fx toasts, "caught you" becomes "caught Ana".
- **Table, spectator mode** (`s.role === "spectator"`):
  - The bottom hand renders the followed player's `g.hand` read-only: no play, draw, keep, CUNO, Catch, challenge or colour-pick controls, and no keyboard shortcuts.
  - A label above the hand: "Watching Ana · Cal's turn".
  - Tapping an opponent seat calls `client.watch(seat)`. A short fade covers the table re-rotating. Seats should look tappable, for example with a hover or focus ring and a tooltip "Watch Cal".
  - The top bar shows a "Watching" chip in place of anything player-specific.
- **Hands panel** (new `HandsPanel.svelte`, spectators only):
  - Bottom-left of the felt, overlaid on the felt, not in the layout flow.
  - One row per player in play order, **excluding the followed player**. Each row is the name, then mini chips sorted by colour then value: number, ⊘ skip, ⇄ reverse, +2, W wild, +4 (the wild ones in a four-colour style).
  - The current turn's row is highlighted. Tapping a row = `client.watch(seat)`.
  - It collapses to a small "Hands" tab, and the collapsed state is saved in `localStorage` (`cuno:handsPanel`, try/catch like the other storage).
  - It starts collapsed when compact or when there are more than 6 players. When open, its height is capped and it scrolls instead of covering the table.
  - It must not use the `data-card-id` / `data-hand` attributes, so fx flights never target it.
- **Watching chip** (players and spectators): "👁 N watching" in the top bar when `spectators.length > 0`. Tapping it shows a small popover listing the names. It's shown in the Lobby too.
- **Lobby, spectator mode:** read-only. No Start button, plus the note "You're watching. Leave and rejoin to play in the next game."
- **RoundSummary, spectator mode:** no Next round or New game buttons. "You" wording is replaced as above.
- **Home (my call):** when the code entered or in the URL belongs to a room whose `phase` isn't `lobby` (`GET /api/rooms/{code}` already returns `phase`), the Join button reads "Watch" and a line explains "This game has started, so you'll join as a spectator." Skip this when a token for that room is already saved, because it's a rejoin.
- **Prompts (my call):** during colour-pick and challenge prompts, spectators see only the status line ("Ana is choosing a colour"), never the pickers.

## Testing
- `tests/test_rooms.py`:
  - joining a started game yields a spectator, not `in_progress`
  - the spectator snapshot has `you is None`, `watching` = the host's seat, and `hands` for every seat
  - **player snapshots never contain `hands` or other players' cards**, with spectators present
  - `watch` changes the followed seat and only that spectator gets a new state
  - `watch` with a bad seat errors
  - spectator game actions are rejected with `spectator`
  - a spectator never becomes host
  - a spectator-only room pauses the timer and is swept, and connected spectators get `closed`
  - a spectator rejoining with its token stays a spectator on the same seat
  - `leave` then rejoining in the lobby makes a player
  - after `new_game`, spectators remain spectators and still follow the same *person* even when seat numbers shift; a spectator following a dropped player falls back to the host
  - spectators arriving or leaving does not change `version` or the turn `deadline`
  - `spectators` lists connected spectator names for everyone
- `views.py`: `spectator_snapshot_for` includes all hands, and `snapshot_for` is unchanged.
- Frontend: `npm run check`, plus a manual pass: two browsers playing and a third spectating. Check desktop and phone width, switching, the panel collapsing, the chip, a refresh while spectating, and the game ending and returning to the lobby.

## Left to the builder
- Exact styling of the panel, chips and watching popover (follow existing tokens and `Seat.svelte` styling).
- The fade on switching, and whether the bottom hand animates on switch. Respect `prefers-reduced-motion`.
- Whether `spectator_joined` / `spectator_left` also show a toast to players.
- Update `CLAUDE.md` (architecture: "Never put another player's cards into a snapshot" becomes "into a *player* snapshot", and mention spectators) and the "spectators" non-goal line in the original design doc.
