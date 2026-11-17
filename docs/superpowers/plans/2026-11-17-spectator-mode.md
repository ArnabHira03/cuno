# Spectator Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let anyone who joins a room after its game has started watch it as a spectator. They follow one player over the shoulder and can glance at every hand in a corner panel. Players see a "👁 N watching" chip.

**Architecture:**
- **Room.** `Room` gains a `spectators` list alongside `players`. A spectator stores the `Player` it follows (not a seat index).
- **Snapshots.** The server builds the spectator snapshot from the followed seat's existing view plus every hand (`views.spectator_snapshot_for`).
- **Broadcasting.** It's split from `_commit`, so spectators arriving or leaving never bump `version` or restart the turn timer.
- **Client.** The client centres the table on `you ?? watching` and hides every control for spectators.

**Tech Stack:** Python 3.14 / FastAPI / pydantic / pytest (async tests run without decorators); Svelte 5 runes + TypeScript + Vite.

**Spec:** `docs/superpowers/specs/2026-11-17-spectator-mode-design.md`

## Global Constraints

- A **player** connection must never receive another player's cards. `views.snapshot_for` stays unchanged, and only spectator snapshots carry `hands`.
- Spectators never become host, never clear `room.empty_since`, never keep the turn timer running, and never change game state.
- Spectators arriving or leaving must not change `room.version` or `room.deadline`.
- `watching` follows the **person** across seat renumbering. If they're gone, fall back to the host, then the first connected player, then the first player, then `None`.
- Protocol changes go in `src/cuno/protocol.py` **and** `web/src/lib/types.ts` together.
- New error codes: `spectator` (a spectator tried to act) and `closed` (room swept).
- Panel storage key: `cuno:handsPanel`. Always wrap it in try/catch (use `storageGet`/`storageSet`).
- The hands panel must not use `data-card-id` / `data-hand` attributes.
- Respect `prefers-reduced-motion` for any new transition.
- Copy is fixed by the spec:
  - Join button: "Watch"
  - Join explanation: "This game has started, so you'll join as a spectator."
  - Lobby note: "You're watching. Leave and rejoin to play in the next game."
  - Close message: "This room has closed."
  - Label above the hand: "Watching {name} · {status}"

## Review Focus

1. **Rapid seat switching while an animation is in flight.** Switching must never fly a card into the wrong hand or leave cards hidden. Pin: in Task 6, key the bottom `Hand` (and clear `fx.hiddenHand`) on the followed seat.
2. **The followed player disconnects mid-game.** Their seat stays in the game, so the spectator keeps following it and does not jump. Pin: `test_spectator_keeps_following_disconnected_player` (Task 3).
3. **A spectator refreshes while the room is back in the lobby.** They must come back as a spectator, not take a seat. Pin: `test_spectator_token_in_lobby_stays_spectator` (Task 3).
4. **A spectator sends a sequenced action with a valid `seq`.** It must be rejected with `spectator`, not applied and not answered with `stale`. Pin: `test_spectator_actions_rejected` (Task 2).
5. **The room is swept while a spectator is connected.** The spectator gets `closed`, and the client stops reconnecting. Pin: `test_sweep_notifies_spectators` (Task 3), plus `closed` in `FATAL` (Task 4).

---

### Task 1: Spectator view and `watch` message

**Files:**
- Modify: `src/cuno/views.py`, `src/cuno/protocol.py`
- Test: `tests/test_views.py` (create)

**Interfaces:**
- Produces:
  - `views.spectator_snapshot_for(game: Game, seat: int) -> dict[str, Any]`
  - `protocol.Watch` (`type: Literal["watch"]`, `seat: int`), added to the `ClientMessage` union

- [ ] **Step 1: Write the failing tests**

```python
import random
from cuno.engine import Game
from cuno.protocol import Watch, client_message
from cuno.views import snapshot_for, spectator_snapshot_for

def started(n=3):
    g = Game(n, random.Random(1)); g.start_round(); return g

def test_spectator_snapshot_has_every_hand_and_followed_view():
    g = started()
    s = spectator_snapshot_for(g, 1)
    assert set(s["hands"]) == {"0", "1", "2"}
    for seat in range(3):
        assert [c["id"] for c in s["hands"][str(seat)]] == [c.id for c in g.hands[seat]]
    assert s["hand"] == snapshot_for(g, 1)["hand"]

def test_player_snapshot_has_no_hands():
    assert "hands" not in snapshot_for(started(), 0)

def test_watch_message_parses():
    assert isinstance(client_message.validate_python({"type": "watch", "seat": 2}), Watch)
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_views.py -v`
Expected: FAIL with ImportError on `spectator_snapshot_for` / `Watch`.

- [ ] **Step 3: Implement `spectator_snapshot_for`** (it returns `snapshot_for(game, seat)` plus `"hands"`, with keys `str(seat)` and values `card.to_dict()` lists) and `Watch` (it isn't in `SEQUENCED` or `GAME_ACTIONS`).

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `uv run pytest tests/test_views.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cuno/views.py src/cuno/protocol.py tests/test_views.py
git commit -m "Add spectator snapshot view and watch message"
```

---

### Task 2: Spectators in `Room` (join, snapshot, broadcast, watch, reject)

**Files:**
- Modify: `src/cuno/rooms.py`
- Test: `tests/test_rooms.py` (replace `test_cannot_join_started_game_but_can_rejoin_with_token`, add tests)

**Interfaces:**
- Consumes: `spectator_snapshot_for`, `Watch` (Task 1)
- Produces:
  - `@dataclass(eq=False) class Spectator: token: str; name: str; conn: Connection | None = None; watching: Player | None = None`, with a `connected` property
  - `Room.spectators: list[Spectator]`
  - `Room.spectator_for(conn) -> Spectator | None`
  - `Room._default_watch() -> Player | None`: the host if it's in `players`, else the first connected player, else `players[0]`, else `None`
  - `Room._watch_seat(spec) -> int | None`: `players.index(spec.watching)` if present, otherwise reset `spec.watching = _default_watch()` and return its index
  - `Room._base_snapshot() -> dict` holds the shared fields, including `"spectators": [s.name for s in spectators if s.connected]`
  - `Room.snapshot_for(player)` adds `role: "player"`, `you: seat`, `watching: None`
  - `Room.spectator_snapshot(spec)` adds `role: "spectator"`, `you: None`, `watching: seat`, and `game: spectator_snapshot_for(game, seat)` (or `None` in the lobby, or when the seat is `None`)
  - `Room._broadcast(events)` sends to connected players and then to connected spectators, with events filtered by `events_for(events, watching_seat)`, which is `-1` when `None`
  - `_commit(events)` = version bump + `_schedule_timer()` + `_broadcast(events)`
  - `welcome` gains `role` and has `seat: None` for spectators

- [ ] **Step 1: Write the failing tests** (in `tests/test_rooms.py`, reusing `FakeConn` / `room_with`)

```python
async def started_room(n=3):
    room, conns = await room_with(n)
    await room.handle(conns[0], {"type": "start"})
    return room, conns

async def test_late_joiner_becomes_spectator_following_host():
    room, conns = await started_room()
    spec = FakeConn()
    await room.join(spec, "Watcher", None)
    w = spec.last("welcome")
    assert w["seat"] is None and w["role"] == "spectator" and w["token"]
    s = spec.state
    assert s["role"] == "spectator" and s["you"] is None and s["watching"] == 0
    assert set(s["game"]["hands"]) == {"0", "1", "2"}
    assert len(room.players) == 3 and room.host is room.players[0]
    room.close()

async def test_player_snapshots_never_contain_other_hands_with_spectators():
    room, conns = await started_room()
    await room.join(FakeConn(), "Watcher", None)
    for seat, c in enumerate(conns):
        g = c.state["game"]
        assert "hands" not in g
        assert {x["id"] for x in g["hand"]} == {x.id for x in room.game.hands[seat]}
        assert c.state["spectators"] == ["Watcher"] and c.state["role"] == "player"
    room.close()

async def test_spectator_join_and_leave_keep_version_and_deadline():
    room, conns = await started_room()
    v, d = room.version, room.deadline
    spec = FakeConn()
    await room.join(spec, "Watcher", None)
    await room.disconnect(spec)
    assert room.version == v and room.deadline == d
    assert conns[0].state["spectators"] == []
    room.close()

async def test_watch_switches_only_that_spectator():
    room, conns = await started_room()
    a, b = FakeConn(), FakeConn()
    await room.join(a, "A", None); await room.join(b, "B", None)
    before = len(b.sent); v = room.version
    await room.handle(a, {"type": "watch", "seat": 2})
    assert a.state["watching"] == 2 and a.state["game"]["hand"] == spectator_hand(room, 2)
    assert len(b.sent) == before and room.version == v
    await room.handle(a, {"type": "watch", "seat": 9})
    assert a.last("error")["code"] == "bad_seat"
    room.close()

async def test_spectator_actions_rejected():
    room, conns = await started_room()
    spec = FakeConn()
    await room.join(spec, "W", None)
    for msg in ({"type": "draw", "seq": room.version}, {"type": "start"}, {"type": "catch", "target": 0}):
        await room.handle(spec, msg)
        assert spec.last("error")["code"] == "spectator"
    room.close()

async def test_spectator_never_becomes_host():
    room, conns = await started_room(2)
    spec = FakeConn()
    await room.join(spec, "W", None)
    for c in conns:
        await room.disconnect(c)
    assert room.host is None or room.host in room.players
    room.close()

async def test_spectator_only_room_pauses_and_is_sweepable():
    room, conns = await started_room(2)
    await room.join(FakeConn(), "W", None)
    for c in conns:
        await room.disconnect(c)
    assert room.timer is None and room.empty_since is not None
    room.close()
```

Add the helper `spectator_hand(room, seat)`, which returns `[c.to_dict() for c in room.game.hands[seat]]`. Rewrite the old `test_cannot_join_started_game...` as `test_rejoin_with_token_after_start`, which keeps only its rejoin half.

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_rooms.py -v`
Expected: the new tests FAIL. The rest PASS.

- [ ] **Step 3: Implement** the Interfaces above in `rooms.py`.
  - **`join`:**
    - Check the token against players, then against spectators. A matching spectator reattaches with the same "replaced" handling and keeps `watching`.
    - With no matching token, if `game is not None`, create a spectator.
    - The `full` check stays for players only.
    - The host and `empty_since` assignments happen on the player path only.
    - For a spectator, send `welcome` and then `await self._broadcast([{"type": "spectator_joined", "name": name}])`. Don't use `_commit`.
  - **`disconnect`:** a spectator gets `conn = None` and `_broadcast([{"type": "spectator_left", "name": ...}])`.
  - **`handle`:** resolve the player first, then the spectator. For a spectator:
    - `watch` with `0 <= seat < len(players)` sets `watching = players[seat]` and sends that spectator alone `{"type": "state", "state": spectator_snapshot(spec), "events": []}`.
    - A bad seat gets `error("bad_seat", ...)`.
    - Anything else gets `error("spectator", "Spectators can't play.")`.
  - **`handle` for players:** a player sending `watch` gets `bad_action` via `_apply`'s fallthrough.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `uv run pytest -v` → all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cuno/rooms.py tests/test_rooms.py
git commit -m "Let late joiners watch as spectators"
```

---

### Task 3: Leave vs. drop, following people across renumbering, notify on sweep

**Files:**
- Modify: `src/cuno/rooms.py`, `src/cuno/server.py`
- Test: `tests/test_rooms.py`

**Interfaces:**
- Consumes: Task 2's `Spectator`, `_broadcast`, `_watch_seat`, `_default_watch`
- Produces:
  - `Room.leave(conn) -> None`: a spectator's record is **removed** (and `spectator_left` is broadcast). A player gets exactly `disconnect(conn)`.
  - `server.py`'s loop calls `await room.leave(ws)` on `{"type": "leave"}` and returns. The `finally: disconnect` must then be a no-op for that conn, which it already is, because `player_for`/`spectator_for` find nothing once `conn` is cleared.
  - `Room.close()` also schedules `_safe_send(spec.conn, error_message("closed", "This room has closed."))` for each connected spectator. It does this via `asyncio.get_running_loop().create_task(...)` inside a `try/except RuntimeError`, so the sync `sweep()` keeps its `-> int` signature.

- [ ] **Step 1: Write the failing tests**

```python
async def test_spectator_follows_person_across_new_game():
    room, conns = await started_room(3)
    spec = FakeConn(); await room.join(spec, "W", None)
    await room.handle(spec, {"type": "watch", "seat": 2})
    await room.disconnect(conns[1])                  # seat 1 will be dropped
    room.game.phase = Phase.GAME_OVER
    await room.handle(conns[0], {"type": "new_game"})
    assert spec.state["phase"] == "lobby" and spec.state["role"] == "spectator"
    assert spec.state["players"][spec.state["watching"]]["name"] == "P2"

async def test_spectator_falls_back_to_host_when_followed_player_dropped():
    room, conns = await started_room(3)
    spec = FakeConn(); await room.join(spec, "W", None)
    await room.handle(spec, {"type": "watch", "seat": 1})
    await room.disconnect(conns[1])
    room.game.phase = Phase.GAME_OVER
    await room.handle(conns[0], {"type": "new_game"})
    assert spec.state["watching"] == spec.state["host"]

async def test_spectator_keeps_following_disconnected_player():
    room, conns = await started_room(3)
    spec = FakeConn(); await room.join(spec, "W", None)
    await room.handle(spec, {"type": "watch", "seat": 1})
    await room.disconnect(conns[1])
    assert spec.state["watching"] == 1
    room.close()

async def test_spectator_token_in_lobby_stays_spectator():
    room, conns = await started_room(2)
    spec = FakeConn(); await room.join(spec, "W", None)
    token = spec.last("welcome")["token"]
    await room.disconnect(spec)
    room.game.phase = Phase.GAME_OVER
    await room.handle(conns[0], {"type": "new_game"})
    back = FakeConn(); await room.join(back, "W", token)
    assert back.state["role"] == "spectator" and len(room.players) == 2

async def test_spectator_leave_then_rejoin_in_lobby_is_player():
    room, conns = await started_room(2)
    spec = FakeConn(); await room.join(spec, "W", None)
    token = spec.last("welcome")["token"]
    await room.leave(spec)
    assert room.spectators == []
    room.game.phase = Phase.GAME_OVER
    await room.handle(conns[0], {"type": "new_game"})
    back = FakeConn(); await room.join(back, "W", token)
    assert back.state["role"] == "player" and len(room.players) == 3

async def test_sweep_notifies_spectators():
    m = RoomManager(empty_ttl=0)
    room = m.create()
    a, b = FakeConn(), FakeConn()
    await room.join(a, "A", None); await room.join(b, "B", None)
    await room.handle(a, {"type": "start"})
    spec = FakeConn(); await room.join(spec, "W", None)
    await room.disconnect(a); await room.disconnect(b)
    assert m.sweep(now=room.empty_since + 1) == 1
    await asyncio.sleep(0)
    assert spec.last("error")["code"] == "closed"
```

Also extend `test_websocket_end_to_end`. After the start, a third socket joins, gets `welcome` with `role == "spectator"`, and its state has `game.hands`. Ann's socket then receives a state whose `spectators == ["Cat"]`.

- [ ] **Step 2: Run them to make sure they fail**

Run: `uv run pytest tests/test_rooms.py -v`
Expected: the new tests FAIL. `room.leave` doesn't exist yet, and following falls back incorrectly.

- [ ] **Step 3: Implement** `Room.leave`, the `server.py` change, and the `close()` notify. `_watch_seat` (Task 2) already handles the fallback, so `new_game` needs no extra code beyond making sure spectator snapshots go out through `_broadcast`.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `uv run pytest -v` → all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cuno/rooms.py src/cuno/server.py tests/test_rooms.py
git commit -m "Remove spectators on leave, follow people, notify on room close"
```

---

### Task 4: Client types and connection

**Files:**
- Modify: `web/src/lib/types.ts`, `web/src/lib/client.svelte.ts`

**Interfaces:**
- Consumes: the server shapes from Tasks 1–3
- Produces:
  - `RoomState`:
    - `role: 'player' | 'spectator'`
    - `you: number | null`
    - `watching: number | null`
    - `spectators: string[]`
  - `GameView.hands?: Record<string, Card[]>`
  - `ServerMessage` welcome is `{ type: 'welcome'; seat: number | null; token: string; role: 'player' | 'spectator' }`
  - `ClientMessage` gets `| { type: 'watch'; seat: number }`
  - `client.watch(seat: number): void`
  - `'closed'` is in `FATAL`
  - Exported helper `viewSeat(s: RoomState): number`, which returns `s.you ?? s.watching ?? 0`

- [ ] **Step 1:** Make the type and client changes.
- [ ] **Step 2:** Run `cd web && npm run check`. Expected: errors only where components use `s.you` as a `number`. Those are fixed in Task 6; list them.
- [ ] **Step 3:** Commit: `git commit -am "Client types for spectators"`. Run-check errors are acceptable at this commit only if Task 6 lands in the same branch before merging.

---

### Task 5: Hands panel and watching chip components

**Files:**
- Create: `web/src/lib/HandsPanel.svelte`, `web/src/lib/WatchingChip.svelte`

**Interfaces:**
- Consumes: `client.watch`, `storageGet`/`storageSet`, `Card` type
- Produces:
  - `<HandsPanel state={s} startCollapsed={boolean} />`. It's spectator-only and absolutely positioned bottom-left inside `.felt`.
    - Rows are in play order starting after the followed seat (reverse order when `g.direction === -1`), excluding `s.watching`.
    - Each row is the name followed by chips. Chips are sorted with Hand's colour/kind/value order (move `COLOR_ORDER`/`KIND_ORDER`/sort into `web/src/lib/cardSort.ts` and use it from both).
    - Chip labels: the number, `⊘` skip, `⇄` reverse, `+2`, `W` wild, `+4` wild4. Wilds use a four-colour conic background.
    - The `g.turn` row gets `.now`. Clicking or pressing Enter on a row calls `client.watch(seat)`.
    - The header has a "–"/"Hands" toggle. Collapsed state is `storageGet('cuno:handsPanel')` (`'1'` = collapsed), falling back to `startCollapsed`.
    - The open body has `max-height: 40%` of the felt with `overflow-y: auto`.
  - `<WatchingChip names={string[]} />`. It renders nothing when empty. Otherwise it's a `.chip` button "👁 {n} watching", and clicking it toggles a small popover listing the names. Clicking outside or pressing Esc closes it.

- [ ] **Step 1:** Build both components, plus `cardSort.ts`. Make `Hand.svelte` import the sort from it.
- [ ] **Step 2:** Run `cd web && npm run check`. Expected: no new errors from these files.
- [ ] **Step 3:** Commit: `git add web/src/lib && git commit -m "Add hands panel and watching chip"`.

---

### Task 6: Spectator table, lobby and round summary

**Files:**
- Modify: `web/src/lib/Table.svelte`, `web/src/lib/Seat.svelte`, `web/src/lib/fx.svelte.ts`, `web/src/lib/Lobby.svelte`, `web/src/lib/RoundSummary.svelte`

**Interfaces:**
- Consumes: `viewSeat`, `client.watch` (Task 4); `HandsPanel`, `WatchingChip` (Task 5)
- Produces:
  - `Seat` gets an optional `onselect?: () => void`. When it's set, the seat gets `role="button"`, `tabindex="0"`, `title="Watch {name}"`, a focus/hover ring, and a click/Enter handler. The catch button stops propagation.

- [ ] **Step 1: Table.**
  - `const spectator = $derived(s.role === 'spectator')`.
  - `me = $derived(viewSeat(s))`.
  - `name(seat)` returns 'You' only when `!spectator && seat === me`.
  - When `spectator`, force `myTurn`, `canDraw`, `canKeep`, `challengeMe`, `chooseMe` and `unoAvailable` to false. Skip `onKey`, render no `.actions` and no Catch (`canCatch` false), and pass `onselect={() => client.watch(o.seat)}` to each Seat.
  - The status text uses `name()`, so it reads "Ana's turn" etc.
  - Above the hand, show `Watching {s.players[me].name} · {status}` instead of the plain status. The top bar shows a "Watching" chip.
  - Render `<HandsPanel state={s} startCollapsed={compact || n > 6} />` inside `.felt` when spectating.
  - Render `<WatchingChip names={s.spectators} />` in `.chips` for everyone.
  - Wrap the bottom `<section class="me">` contents in `{#key me}`, with a 150ms fade that's skipped under reduced motion. When spectating, pass `myTurn={false}` and `onplay={() => {}}` to Hand.
  - The Leave modal copy for spectators: "You'll stop watching. Rejoining while a game is on makes you a spectator again."
- [ ] **Step 2: fx.**
  - In `run`/`before`/`after`, `me = viewSeat(next)`.
  - `name()` returns 'You' only for `next.role === 'player'`.
  - "caught you — draw 2!" and "Time ran out — you drew a card" use the player's name for spectators.
  - Add a `resetHand()` that clears `hiddenHand` and `captured`. Table calls it when `me` changes.
- [ ] **Step 3: Lobby.** When `s.role === 'spectator'`:
  - no Start button and no "Waiting for…" line
  - show the note "You're watching. Leave and rejoin to play in the next game."
  - add `<WatchingChip names={s.spectators} />` near the player count (for everyone)
- [ ] **Step 4: RoundSummary.** Spectators see no host buttons (already true because `s.you` is `null`). Check that the `npm run check` types are clean.
- [ ] **Step 5: Verify**
  - Run `cd web && npm run check`. Expected: 0 errors.
  - Run `npm run build`.
  - Manual pass: `uv run cuno` with two player browsers and one spectator window. Check:
    - desktop and 390px width
    - switching seats rapidly mid-animation
    - the panel collapsing and persisting across a refresh
    - the chip counts on players
    - a spectator refreshing mid-game and in the lobby
    - the game ending and returning to the lobby
- [ ] **Step 6:** Commit: `git add web/src && git commit -m "Spectator table, lobby and summary views"`.

---

### Task 7: "Watch" on the home screen, plus docs

**Files:**
- Modify: `web/src/lib/Home.svelte`, `web/src/App.svelte` (if the fetch lives there), `CLAUDE.md`, `docs/superpowers/specs/2026-11-15-cuno-design.md`

- [ ] **Step 1: Home.**
  - When the code is 4 valid letters, fetch `GET /api/rooms/{code}`, debounced by about 250ms and ignoring failures.
  - If `phase !== 'lobby'` and `storageGet('cuno:token:' + CODE)` is empty, the Join button reads "Watch" and a line under it reads "This game has started, so you'll join as a spectator."
- [ ] **Step 2: Docs.**
  - In `CLAUDE.md`, change "Never put another player's cards into a snapshot" to say *player* snapshot. Add one bullet on spectators: the `spectators` list, `watching` stores a Player, `_broadcast` vs `_commit`, and `views.spectator_snapshot_for`.
  - In the original design doc, update the non-goal line so it says spectators are now covered by `2026-11-17-spectator-mode-design.md`.
- [ ] **Step 3: Verify.**
  - Run `cd web && npm run check && npm run build`. Expected: 0 errors.
  - Run `uv run pytest`. Expected: all pass.
  - Manually enter a running room's code and see "Watch".
- [ ] **Step 4:** Commit: `git add -A web/src CLAUDE.md docs/superpowers/specs/2026-11-15-cuno-design.md && git commit -m "Home shows Watch for running games; document spectators"`.
