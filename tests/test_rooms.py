import asyncio
import random

import pytest
from fastapi.testclient import TestClient

from cuno.engine import Phase
from cuno.rooms import Room, RoomError, RoomManager
from cuno.server import create_app


class FakeConn:
    def __init__(self):
        self.sent = []
        self.closed = False

    async def send_json(self, data):
        self.sent.append(data)

    async def close(self):
        self.closed = True

    def last(self, kind="state"):
        return next(m for m in reversed(self.sent) if m["type"] == kind)

    @property
    def state(self):
        return self.last()["state"]


async def room_with(n, **kw):
    room = Room("ABCD", rng=random.Random(7), **kw)
    conns = [FakeConn() for _ in range(n)]
    for i, c in enumerate(conns):
        await room.join(c, f"P{i}", None)
    return room, conns


async def test_join_and_lobby_state():
    room, conns = await room_with(3)
    s = conns[0].state
    assert s["phase"] == "lobby" and s["host"] == 0 and s["you"] == 0
    assert [p["name"] for p in s["players"]] == ["P0", "P1", "P2"]
    assert conns[2].last("welcome")["seat"] == 2


async def test_only_host_starts_and_needs_two_players():
    room, conns = await room_with(1)
    await room.handle(conns[0], {"type": "start"})
    assert conns[0].last("error")["code"] == "too_few"
    c1 = FakeConn()
    await room.join(c1, "P1", None)
    await room.handle(c1, {"type": "start"})
    assert c1.last("error")["code"] == "not_host"
    await room.handle(conns[0], {"type": "start"})
    assert conns[0].state["phase"] == "playing"
    room.close()


async def test_snapshot_only_contains_own_hand():
    room, conns = await room_with(4)
    await room.handle(conns[0], {"type": "start"})
    for seat, c in enumerate(conns):
        hand_ids = {card["id"] for card in c.state["game"]["hand"]}
        assert hand_ids == {card.id for card in room.game.hands[seat]}
    room.close()


async def test_play_flow_and_stale_seq():
    room, conns = await room_with(2)
    await room.handle(conns[0], {"type": "start"})
    g = room.game
    g.pending = None
    actor = g.turn
    c = conns[actor]
    version = c.state["version"]
    await room.handle(c, {"type": "draw", "seq": version - 1})
    assert c.last("error")["code"] == "stale"
    await room.handle(c, {"type": "draw", "seq": version})
    assert c.state["version"] == version + 1
    assert any(e["type"] == "draw" for e in c.last()["events"])
    room.close()


async def test_draw_event_private_card_ids_only_to_drawer():
    room, conns = await room_with(3)
    await room.handle(conns[0], {"type": "start"})
    room.game.pending = None
    actor = room.game.turn
    await room.handle(conns[actor], {"type": "draw", "seq": room.version})
    for seat, c in enumerate(conns):
        ev = next(e for e in c.last()["events"] if e["type"] == "draw")
        assert ("private" in ev) == (seat == actor)
    room.close()


async def test_rejoin_with_token_after_start():
    room, conns = await room_with(2)
    token = conns[1].last("welcome")["token"]
    await room.handle(conns[0], {"type": "start"})

    await room.disconnect(conns[1])
    assert conns[0].state["players"][1]["connected"] is False
    back = FakeConn()
    await room.join(back, "whatever", token)
    assert back.state["you"] == 1
    assert {c["id"] for c in back.state["game"]["hand"]} == {c.id for c in room.game.hands[1]}
    room.close()


async def test_lobby_leave_removes_seat_and_moves_host():
    room, conns = await room_with(3)
    await room.disconnect(conns[0])
    s = conns[1].state
    assert [p["name"] for p in s["players"]] == ["P1", "P2"]
    assert s["host"] == 0 and s["you"] == 0


async def test_timer_auto_plays():
    room, conns = await room_with(2, turn_seconds=0.05, away_seconds=0.05)
    await room.handle(conns[0], {"type": "start"})
    v = room.version
    await asyncio.sleep(0.2)
    assert room.version > v
    assert any(e["type"] == "timeout" for m in conns[0].sent if m["type"] == "state" for e in m["events"])
    room.close()


async def test_timer_pauses_when_everyone_gone():
    room, conns = await room_with(2, turn_seconds=0.05, away_seconds=0.05)
    await room.handle(conns[0], {"type": "start"})
    await room.disconnect(conns[0])
    await room.disconnect(conns[1])
    v = room.version
    await asyncio.sleep(0.15)
    assert room.version == v and room.timer is None


async def test_uno_catch_race_first_arrival_wins():
    room, conns = await room_with(3)
    await room.handle(conns[0], {"type": "start"})
    g = room.game
    g.hands[0] = g.hands[0][:1]
    g.uno_vulnerable = 0
    g.uno_called[0] = False
    await asyncio.gather(
        room.handle(conns[0], {"type": "call_uno"}),
        room.handle(conns[1], {"type": "catch", "target": 0}),
    )
    # call_uno was queued first, so the catch must have failed.
    assert conns[1].last("error")["code"] == "cant_catch"
    room.close()


async def test_full_game_to_lobby():
    room, conns = await room_with(3)
    room.rng = random.Random(3)
    await room.handle(conns[0], {"type": "start"})
    room.game.target_score = 1
    rng = random.Random(1)
    for _ in range(3000):
        g = room.game
        if g.phase is not Phase.PLAYING:
            break
        seat = g.actor
        c = conns[seat]
        seq = room.version
        if g.pending and g.pending["type"] == "challenge":
            await room.handle(c, {"type": "accept", "seq": seq})
        elif g.pending:
            await room.handle(c, {"type": "choose_color", "color": "red", "seq": seq})
        elif ids := g.playable_ids(seat):
            await room.handle(c, {"type": "play", "card_id": ids[0], "color": "red", "seq": seq})
        elif g.drawn_card_id is not None:
            await room.handle(c, {"type": "keep", "seq": seq})
        else:
            await room.handle(c, {"type": "draw", "seq": seq})
    assert conns[0].state["phase"] == "game_over"
    assert conns[2].state["game"]["last_round"]["winner"] is not None
    await room.handle(conns[0], {"type": "new_game"})
    assert conns[1].state["phase"] == "lobby"
    room.close()


async def test_manager_sweeps_empty_rooms():
    m = RoomManager(empty_ttl=10)
    room = m.create()
    assert m.get(room.code.lower()) is room
    assert m.sweep(now=room.empty_since + 5) == 0
    assert m.sweep(now=room.empty_since + 11) == 1
    assert m.get(room.code) is None


def test_websocket_end_to_end():
    app = create_app(static_dir=__import__("pathlib").Path("/nonexistent"))
    client = TestClient(app)
    code = client.post("/api/rooms").json()["code"]
    assert client.get(f"/api/rooms/{code}").json()["players"] == 0
    assert client.get("/api/rooms/ZZZZ").status_code == 404
    with client.websocket_connect(f"/ws/{code}") as a, client.websocket_connect(f"/ws/{code}") as b:
        a.send_json({"type": "join", "name": "Ann"})
        assert a.receive_json()["type"] == "welcome"
        assert a.receive_json()["type"] == "state"
        b.send_json({"type": "join", "name": "Bob"})
        assert b.receive_json()["type"] == "welcome"
        b.receive_json()
        a.receive_json()  # Bob joined
        a.send_json({"type": "start"})
        sa, sb = a.receive_json(), b.receive_json()
        assert sa["state"]["phase"] == sb["state"]["phase"] == "playing"
        assert sa["state"]["game"]["hand"] != sb["state"]["game"]["hand"]
        a.send_json({"type": "nonsense"})
        assert a.receive_json()["code"] == "bad_message"


def test_websocket_unknown_room():
    client = TestClient(create_app())
    with client.websocket_connect("/ws/QQQQ") as ws:
        assert ws.receive_json()["code"] == "not_found"


# ------------------------------------------------------------------ spectators


async def started_room(n=3):
    room, conns = await room_with(n)
    await room.handle(conns[0], {"type": "start"})
    return room, conns


def spectator_hand(room, seat):
    return [c.to_dict() for c in room.game.hands[seat]]


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
    await room.join(a, "A", None)
    await room.join(b, "B", None)
    before = len(b.sent)
    v = room.version
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
    v = room.version
    for msg in ({"type": "draw", "seq": room.version}, {"type": "start"}, {"type": "catch", "target": 0}):
        await room.handle(spec, msg)
        assert spec.last("error")["code"] == "spectator"
    assert room.version == v
    room.close()


async def test_spectator_never_becomes_host():
    room, conns = await started_room(2)
    p1_token = conns[1].last("welcome")["token"]
    spec = FakeConn()
    await room.join(spec, "W", None)
    for c in conns:
        await room.disconnect(c)
    assert room.host is None
    await room.handle(spec, {"type": "watch", "seat": 0})  # spectator activity changes nothing
    assert room.host is None
    back = FakeConn()
    await room.join(back, "P1", p1_token)
    assert room.host is room.players[1]
    room.close()


async def test_spectator_only_room_pauses_and_is_sweepable():
    room, conns = await started_room(2)
    await room.join(FakeConn(), "W", None)
    for c in conns:
        await room.disconnect(c)
    assert room.timer is None and room.empty_since is not None
    room.close()


async def test_spectator_follows_person_across_new_game():
    room, conns = await started_room(3)
    spec = FakeConn()
    await room.join(spec, "W", None)
    await room.handle(spec, {"type": "watch", "seat": 2})
    await room.disconnect(conns[1])  # seat 1 will be dropped
    room.game.phase = Phase.GAME_OVER
    await room.handle(conns[0], {"type": "new_game"})
    assert spec.state["phase"] == "lobby" and spec.state["role"] == "spectator"
    assert spec.state["players"][spec.state["watching"]]["name"] == "P2"


async def test_spectator_falls_back_to_host_when_followed_player_dropped():
    room, conns = await started_room(3)
    spec = FakeConn()
    await room.join(spec, "W", None)
    await room.handle(spec, {"type": "watch", "seat": 1})
    await room.disconnect(conns[1])
    room.game.phase = Phase.GAME_OVER
    await room.handle(conns[0], {"type": "new_game"})
    assert spec.state["watching"] == spec.state["host"]


async def test_spectator_keeps_following_disconnected_player():
    room, conns = await started_room(3)
    spec = FakeConn()
    await room.join(spec, "W", None)
    await room.handle(spec, {"type": "watch", "seat": 1})
    await room.disconnect(conns[1])
    assert spec.state["watching"] == 1
    room.close()


async def test_spectator_token_in_lobby_stays_spectator():
    room, conns = await started_room(2)
    spec = FakeConn()
    await room.join(spec, "W", None)
    token = spec.last("welcome")["token"]
    await room.disconnect(spec)
    room.game.phase = Phase.GAME_OVER
    await room.handle(conns[0], {"type": "new_game"})
    back = FakeConn()
    await room.join(back, "W", token)
    assert back.state["role"] == "spectator" and len(room.players) == 2


async def test_spectator_leave_then_rejoin_in_lobby_is_player():
    room, conns = await started_room(2)
    spec = FakeConn()
    await room.join(spec, "W", None)
    token = spec.last("welcome")["token"]
    await room.leave(spec)
    assert room.spectators == []
    assert conns[0].state["spectators"] == []
    room.game.phase = Phase.GAME_OVER
    await room.handle(conns[0], {"type": "new_game"})
    back = FakeConn()
    await room.join(back, "W", token)
    assert back.state["role"] == "player" and len(room.players) == 3


async def test_sweep_notifies_spectators():
    m = RoomManager(empty_ttl=0)
    room = m.create()
    a, b = FakeConn(), FakeConn()
    await room.join(a, "A", None)
    await room.join(b, "B", None)
    await room.handle(a, {"type": "start"})
    spec = FakeConn()
    await room.join(spec, "W", None)
    await room.disconnect(a)
    await room.disconnect(b)
    assert m.sweep(now=room.empty_since + 1) == 1
    await asyncio.sleep(0)
    assert spec.last("error")["code"] == "closed"
    assert spec.closed


def test_websocket_spectator_end_to_end():
    app = create_app(static_dir=__import__("pathlib").Path("/nonexistent"))
    client = TestClient(app)
    code = client.post("/api/rooms").json()["code"]
    with (
        client.websocket_connect(f"/ws/{code}") as a,
        client.websocket_connect(f"/ws/{code}") as b,
        client.websocket_connect(f"/ws/{code}") as c,
    ):
        a.send_json({"type": "join", "name": "Ann"})
        a.receive_json(), a.receive_json()
        b.send_json({"type": "join", "name": "Bob"})
        b.receive_json(), b.receive_json(), a.receive_json()
        a.send_json({"type": "start"})
        a.receive_json(), b.receive_json()
        c.send_json({"type": "join", "name": "Cat"})
        assert c.receive_json()["role"] == "spectator"
        assert set(c.receive_json()["state"]["game"]["hands"]) == {"0", "1"}
        assert a.receive_json()["state"]["spectators"] == ["Cat"]
        c.send_json({"type": "leave"})
        left = a.receive_json()
        assert left["state"]["spectators"] == [] and left["events"][0]["type"] == "spectator_left"


async def test_actions_with_spectators_never_leak_hands_to_players():
    room, conns = await started_room(3)
    spec = FakeConn()
    await room.join(spec, "W", None)
    g = room.game
    g.pending = None

    async def draw():
        seat = g.turn
        await room.handle(conns[seat], {"type": "draw", "seq": room.version})
        return seat

    drawer = await draw()
    for seat, c in enumerate(conns):
        msg = c.last()
        assert "hands" not in msg["state"]["game"]
        assert {x["id"] for x in msg["state"]["game"]["hand"]} == {x.id for x in g.hands[seat]}
        for ev in msg["events"]:
            if "private" in ev:
                assert ev["private"]["seat"] == seat == drawer
    spec_events = spec.last()["events"]
    draw_ev = next(e for e in spec_events if e["type"] == "draw")
    # The spectator follows seat 0 (host): it gets the drawn ids only if seat 0 drew.
    assert ("private" in draw_ev) == (drawer == 0)
    assert set(spec.state["game"]["hands"]) == {"0", "1", "2"}

    # After switching to the next drawer, the spectator gets that seat's private draw.
    if g.drawn_card_id is not None:
        await room.handle(conns[g.turn], {"type": "keep", "seq": room.version})
    g.pending = None
    await room.handle(spec, {"type": "watch", "seat": g.turn})
    drawer = await draw()
    draw_ev = next(e for e in spec.last()["events"] if e["type"] == "draw")
    assert draw_ev["private"]["seat"] == drawer
    for seat, c in enumerate(conns):
        assert "hands" not in c.last()["state"]["game"]
    room.close()
