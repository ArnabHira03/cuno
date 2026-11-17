import random

from cuno.engine import Game
from cuno.protocol import Watch, client_message
from cuno.views import snapshot_for, spectator_snapshot_for


def started(n=3):
    g = Game(n, random.Random(1))
    g.start_round()
    return g


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
