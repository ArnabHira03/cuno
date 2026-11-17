"""Rooms: seats, connections, turn timer, and broadcasting snapshots.

A "connection" is anything with an async `send_json(data)` method (a
Starlette WebSocket in production, a fake in tests).
"""

from __future__ import annotations

import asyncio
import random
import secrets
import time
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import ValidationError

from .engine import MAX_PLAYERS, MIN_PLAYERS, Event, Game, IllegalMove, Phase
from .protocol import GAME_ACTIONS, SEQUENCED, client_message
from .views import events_for, snapshot_for, spectator_snapshot_for

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # no I or O
CODE_LENGTH = 4


class Connection(Protocol):
    async def send_json(self, data: Any) -> None: ...


class RoomError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(eq=False)
class Player:
    token: str
    name: str
    conn: Connection | None = None

    @property
    def connected(self) -> bool:
        return self.conn is not None


@dataclass(eq=False)
class Spectator:
    token: str
    name: str
    conn: Connection | None = None
    # The person being followed, not a seat number: seats renumber between games.
    watching: Player | None = None

    @property
    def connected(self) -> bool:
        return self.conn is not None


def error_message(code: str, message: str) -> dict[str, Any]:
    return {"type": "error", "code": code, "message": message}


class Room:
    def __init__(
        self,
        code: str,
        *,
        turn_seconds: float = 30,
        away_seconds: float = 8,
        rng: random.Random | None = None,
    ) -> None:
        self.code = code
        self.turn_seconds = turn_seconds
        self.away_seconds = away_seconds
        self.rng = rng or random.Random()
        self.players: list[Player] = []
        self.spectators: list[Spectator] = []
        self.host: Player | None = None
        self.game: Game | None = None
        self.version = 0
        self.lock = asyncio.Lock()
        self.timer: asyncio.Task | None = None
        self.deadline: float | None = None
        self.empty_since: float | None = time.monotonic()

    # ---------------------------------------------------------------- queries

    @property
    def phase(self) -> str:
        return "lobby" if self.game is None else self.game.phase.value

    def player_for(self, conn: Connection) -> Player | None:
        return next((p for p in self.players if p.conn is conn), None)

    def spectator_for(self, conn: Connection) -> Spectator | None:
        return next((s for s in self.spectators if s.conn is conn), None)

    def _default_watch(self) -> Player | None:
        if self.host in self.players:
            return self.host
        return next((p for p in self.players if p.connected), self.players[0] if self.players else None)

    def _watch_seat(self, spec: Spectator) -> int | None:
        if spec.watching not in self.players:
            spec.watching = self._default_watch()
        return None if spec.watching is None else self.players.index(spec.watching)

    def snapshot_for(self, player: Player) -> dict[str, Any]:
        seat = self.players.index(player)
        return {
            **self._base_snapshot(),
            "role": "player",
            "you": seat,
            "watching": None,
            "game": snapshot_for(self.game, seat) if self.game else None,
        }

    def spectator_snapshot(self, spec: Spectator) -> dict[str, Any]:
        seat = self._watch_seat(spec)
        return {
            **self._base_snapshot(),
            "role": "spectator",
            "you": None,
            "watching": seat,
            "game": spectator_snapshot_for(self.game, seat) if self.game and seat is not None else None,
        }

    def _base_snapshot(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "version": self.version,
            "phase": self.phase,
            "host": self.players.index(self.host) if self.host in self.players else None,
            "players": [
                {"seat": i, "name": p.name, "connected": p.connected}
                for i, p in enumerate(self.players)
            ],
            "turn_seconds": self.turn_seconds,
            # Relative, so client/server clock skew doesn't matter.
            "time_left_ms": max(0, int((self.deadline - time.time()) * 1000)) if self.deadline else None,
            "spectators": [s.name for s in self.spectators if s.connected],
        }

    # ------------------------------------------------------------ membership

    async def join(self, conn: Connection, name: str, token: str | None) -> Player | None:
        """Join as a player, or as a spectator (returns None) once the game has started."""
        name = " ".join(name.split())[:16]
        if not name:
            raise RoomError("bad_name", "Pick a nickname.")
        async with self.lock:
            player = next((p for p in self.players if token and p.token == token), None)
            spec = next((s for s in self.spectators if token and s.token == token), None)
            if player is None and (spec is not None or self.game is not None):
                await self._join_spectator(conn, name, spec)
                return None
            if player is not None:
                old = player.conn
                player.conn = conn
                if old is not None and old is not conn:
                    await _safe_send(old, error_message("replaced", "Opened in another tab."))
                event = {"type": "rejoined", "seat": self.players.index(player)}
            else:
                if self.game is not None:
                    raise RoomError("in_progress", "This game has already started.")
                if len(self.players) >= MAX_PLAYERS:
                    raise RoomError("full", f"This room is full ({MAX_PLAYERS} players).")
                player = Player(token=secrets.token_urlsafe(16), name=name, conn=conn)
                self.players.append(player)
                event = {"type": "joined", "seat": len(self.players) - 1}
            if self.host is None or not self.host.connected:
                self.host = player
            self.empty_since = None
            await _safe_send(
                conn,
                {"type": "welcome", "seat": self.players.index(player), "token": player.token, "role": "player"},
            )
            await self._commit([event])
            return player

    async def _join_spectator(self, conn: Connection, name: str, spec: Spectator | None) -> None:
        """Caller holds the lock. Spectators never touch the version, timer, host or empty_since."""
        if spec is None:
            spec = Spectator(token=secrets.token_urlsafe(16), name=name, conn=conn, watching=self._default_watch())
            self.spectators.append(spec)
        else:
            old = spec.conn
            spec.conn = conn
            if old is not None and old is not conn:
                await _safe_send(old, error_message("replaced", "Opened in another tab."))
        await _safe_send(conn, {"type": "welcome", "seat": None, "token": spec.token, "role": "spectator"})
        await self._broadcast([{"type": "spectator_joined", "name": spec.name}])

    async def disconnect(self, conn: Connection) -> None:
        async with self.lock:
            spec = self.spectator_for(conn)
            if spec is not None:
                spec.conn = None
                await self._broadcast([{"type": "spectator_left", "name": spec.name}])
                return
            player = self.player_for(conn)
            if player is None:
                return
            seat = self.players.index(player)
            player.conn = None
            if self.game is None:
                # In the lobby a seat is just removed.
                self.players.remove(player)
                event = {"type": "left", "seat": seat}
            else:
                event = {"type": "disconnected", "seat": seat}
            if self.host is player or self.host not in self.players:
                self.host = next((p for p in self.players if p.connected), None)
            if not any(p.connected for p in self.players):
                self.empty_since = time.monotonic()
            await self._commit([event])

    # ---------------------------------------------------------------- actions

    async def handle(self, conn: Connection, raw: Any) -> None:
        try:
            msg = client_message.validate_python(raw)
        except ValidationError:
            await _safe_send(conn, error_message("bad_message", "Malformed message."))
            return
        async with self.lock:
            player = self.player_for(conn)
            if player is None:
                spec = self.spectator_for(conn)
                if spec is not None:
                    await self._spectator_message(spec, msg.model_dump())
                else:
                    await _safe_send(conn, error_message("not_joined", "Join the room first."))
                return
            try:
                events = self._apply(player, msg.model_dump())
            except (IllegalMove, RoomError) as e:
                await _safe_send(conn, error_message(e.code, e.message))
                if e.code == "stale":
                    await _safe_send(conn, self._state_message(player, []))
                return
            await self._commit(events)

    async def _spectator_message(self, spec: Spectator, msg: dict[str, Any]) -> None:
        if msg["type"] != "watch":
            await _safe_send(spec.conn, error_message("spectator", "Spectators can't play."))
            return
        seat = msg["seat"]
        if not 0 <= seat < len(self.players):
            await _safe_send(spec.conn, error_message("bad_seat", "There's nobody in that seat."))
            return
        spec.watching = self.players[seat]
        await _safe_send(spec.conn, {"type": "state", "state": self.spectator_snapshot(spec), "events": []})

    def _apply(self, player: Player, msg: dict[str, Any]) -> list[Event]:
        kind = msg["type"]
        seat = self.players.index(player)
        is_host = player is self.host

        if kind == "start":
            if not is_host:
                raise RoomError("not_host", "Only the host can start.")
            if self.game is not None:
                raise RoomError("already_started", "The game has already started.")
            if len(self.players) < MIN_PLAYERS:
                raise RoomError("too_few", f"Need at least {MIN_PLAYERS} players.")
            self.game = Game(len(self.players), random.Random(self.rng.random()))
            return self.game.start_round()

        if kind == "next_round":
            if not is_host:
                raise RoomError("not_host", "Only the host can deal the next round.")
            if self.game is None:
                raise RoomError("not_started", "The game hasn't started.")
            return self.game.next_round()

        if kind == "new_game":
            if not is_host:
                raise RoomError("not_host", "Only the host can start a new game.")
            if self.game is None or self.game.phase is not Phase.GAME_OVER:
                raise RoomError("not_over", "The game isn't over yet.")
            # Back to the lobby; anyone who left gives up their seat.
            self.game = None
            self.players = [p for p in self.players if p.connected]
            return [{"type": "lobby"}]

        if kind in GAME_ACTIONS:
            if self.game is None:
                raise RoomError("not_started", "The game hasn't started.")
            if kind in SEQUENCED and msg.get("seq") != self.version:
                raise RoomError("stale", "The game moved on; try again.")
            action = {k: v for k, v in msg.items() if k != "seq" and v is not None}
            return self.game.apply(seat, action)

        raise RoomError("bad_action", f"Unknown action {kind!r}.")

    # -------------------------------------------------------------- broadcast

    def _state_message(self, player: Player, events: list[Event]) -> dict[str, Any]:
        seat = self.players.index(player)
        return {"type": "state", "state": self.snapshot_for(player), "events": events_for(events, seat)}

    async def _commit(self, events: list[Event]) -> None:
        """Bump the version, reset the timer and send everyone their view. Caller holds the lock."""
        self.version += 1
        self._schedule_timer()
        await self._broadcast(events)

    async def _broadcast(self, events: list[Event]) -> None:
        """Send everyone their view without touching the version or timer. Caller holds the lock."""
        sends = [
            _safe_send(p.conn, self._state_message(p, events)) for p in self.players if p.conn is not None
        ]
        for spec in self.spectators:
            if spec.conn is not None:
                state = self.spectator_snapshot(spec)
                seat = state["watching"]
                sends.append(
                    _safe_send(
                        spec.conn,
                        {"type": "state", "state": state, "events": events_for(events, -1 if seat is None else seat)},
                    )
                )
        await asyncio.gather(*sends)

    # ------------------------------------------------------------------ timer

    def _schedule_timer(self) -> None:
        current = asyncio.current_task()
        if self.timer is not None and self.timer is not current:
            self.timer.cancel()
        self.timer = None
        self.deadline = None
        game = self.game
        if game is None or game.phase is not Phase.PLAYING or game.actor is None:
            return
        if not any(p.connected for p in self.players):
            return  # nobody watching; pause until someone comes back
        actor = self.players[game.actor]
        seconds = self.turn_seconds if actor.connected else self.away_seconds
        self.deadline = time.time() + seconds
        self.timer = asyncio.create_task(self._expire(self.version, seconds))

    async def _expire(self, version: int, seconds: float) -> None:
        await asyncio.sleep(seconds)
        async with self.lock:
            if self.version != version or self.game is None or self.game.phase is not Phase.PLAYING:
                return
            events = self.game.auto_play()
            await self._commit(events)

    def close(self) -> None:
        if self.timer is not None:
            self.timer.cancel()


async def _safe_send(conn: Connection | None, data: Any) -> None:
    if conn is None:
        return
    try:
        await conn.send_json(data)
    except Exception:
        pass  # the connection's own receive loop will notice and disconnect


class RoomManager:
    def __init__(self, *, empty_ttl: float = 600, room_kwargs: dict[str, Any] | None = None) -> None:
        self.rooms: dict[str, Room] = {}
        self.empty_ttl = empty_ttl
        self.room_kwargs = room_kwargs or {}

    def create(self) -> Room:
        while True:
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
            if code not in self.rooms:
                break
        room = Room(code, **self.room_kwargs)
        self.rooms[code] = room
        return room

    def get(self, code: str) -> Room | None:
        return self.rooms.get(code.upper())

    def sweep(self, now: float | None = None) -> int:
        now = time.monotonic() if now is None else now
        dead = [
            code
            for code, room in self.rooms.items()
            if room.empty_since is not None and now - room.empty_since > self.empty_ttl
        ]
        for code in dead:
            self.rooms.pop(code).close()
        return len(dead)
