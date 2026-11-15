"""Engine tests, organised by section of cuno_rules.md."""

import random
from collections import Counter

import pytest

from cuno.cards import Card, Color, Kind, build_deck
from cuno.engine import Game, IllegalMove, Phase
from cuno.views import events_for, snapshot_for

R, Y, G, B = Color.RED, Color.YELLOW, Color.GREEN, Color.BLUE
_next_id = iter(range(1000, 100000))


def num(color, value):
    return Card(next(_next_id), Kind.NUMBER, color, value)


def act(kind, color=None):
    return Card(next(_next_id), kind, color)


def setup(n=3, hands=None, top=None, turn=0, color=None, pile=None):
    """A started game with hand-picked state."""
    g = Game(n, random.Random(1))
    g.start_round()
    g.pending = None
    g.direction = 1
    g.turn = turn
    g.drawn_card_id = None
    g.uno_called = [False] * n
    g.uno_vulnerable = None
    if hands is not None:
        g.hands = [list(h) for h in hands]
    top = top or num(R, 5)
    g.discard = [top]
    g.current_color = color or top.color
    if pile is not None:
        g.draw_pile = list(pile)
    return g


def types(events):
    return [e["type"] for e in events]


# §1 deck --------------------------------------------------------------------


def test_deck_composition():
    deck = build_deck()
    assert len(deck) == 108
    assert len({c.id for c in deck}) == 108
    kinds = Counter(c.kind for c in deck)
    assert kinds[Kind.NUMBER] == 76
    assert kinds[Kind.SKIP] == kinds[Kind.REVERSE] == kinds[Kind.DRAW2] == 8
    assert kinds[Kind.WILD] == kinds[Kind.WILD4] == 4
    reds = Counter(c.value for c in deck if c.color is R and c.kind is Kind.NUMBER)
    assert reds[0] == 1 and all(reds[v] == 2 for v in range(1, 10))


# §2 setup -------------------------------------------------------------------


@pytest.mark.parametrize("n", [2, 4, 10])
def test_deal(n):
    g = Game(n, random.Random(n))
    g.start_round()
    total = sum(len(h) for h in g.hands) + len(g.draw_pile) + len(g.discard)
    assert total == 108
    assert g.top.kind is not Kind.WILD4
    # Each player has 7 unless a first-card Draw Two hit the first player.
    assert sorted(len(h) for h in g.hands)[0] == 7


def test_rejects_bad_player_counts():
    with pytest.raises(ValueError):
        Game(1)
    with pytest.raises(ValueError):
        Game(11)


def _game_with_first(kind, n=4):
    for seed in range(5000):
        g = Game(n, random.Random(seed))
        g.start_round()
        if g.discard[0].kind is kind:
            return g
    raise AssertionError(f"no seed flips {kind}")


def test_first_card_skip():
    g = _game_with_first(Kind.SKIP)
    assert g.turn == (g.dealer + 2) % 4


def test_first_card_reverse():
    g = _game_with_first(Kind.REVERSE)
    assert g.direction == -1 and g.turn == g.dealer


def test_first_card_draw2():
    g = _game_with_first(Kind.DRAW2)
    first = (g.dealer + 1) % 4
    assert len(g.hands[first]) == 9
    assert g.turn == (g.dealer + 2) % 4


def test_first_card_wild_lets_first_player_choose():
    g = _game_with_first(Kind.WILD)
    first = (g.dealer + 1) % 4
    assert g.pending == {"type": "choose_color", "seat": first}
    assert g.actor == first
    with pytest.raises(IllegalMove):
        g.apply(first, {"type": "draw"})
    g.apply(first, {"type": "choose_color", "color": "blue"})
    assert g.current_color is B and g.turn == first and g.pending is None


# §3 turns -------------------------------------------------------------------


def test_play_matching_colour_number_and_symbol():
    g = setup(hands=[[num(R, 1), num(B, 5), act(Kind.SKIP, G)], [num(Y, 1)] * 1, [num(Y, 2)]])
    assert set(g.playable_ids(0)) == {g.hands[0][0].id, g.hands[0][1].id}
    g.apply(0, {"type": "play", "card_id": g.hands[0][1].id})
    assert g.current_color is B and g.turn == 1


def test_symbol_matches_symbol():
    skip_r = act(Kind.SKIP, R)
    g = setup(hands=[[act(Kind.SKIP, G), num(Y, 1)], [num(Y, 2)], [num(Y, 3)]], top=skip_r)
    assert g.playable_ids(0) == [g.hands[0][0].id]


def test_cannot_play_non_matching_or_out_of_turn():
    g = setup(hands=[[num(B, 1), num(R, 2)], [num(R, 3), num(R, 4)], [num(Y, 2)]])
    with pytest.raises(IllegalMove) as e:
        g.apply(0, {"type": "play", "card_id": g.hands[0][0].id})
    assert e.value.code == "not_playable"
    with pytest.raises(IllegalMove) as e:
        g.apply(1, {"type": "play", "card_id": g.hands[1][0].id})
    assert e.value.code == "not_your_turn"


def test_draw_unplayable_passes_turn():
    g = setup(hands=[[num(B, 1), num(B, 2)], [num(R, 3), num(R, 4)], [num(Y, 2)]], pile=[num(G, 9)])
    events = g.apply(0, {"type": "draw"})
    assert types(events) == ["draw"]
    assert len(g.hands[0]) == 3 and g.turn == 1 and g.drawn_card_id is None


def test_draw_playable_may_play_it_or_keep():
    drawn = num(R, 9)
    g = setup(hands=[[num(B, 1), num(B, 2)], [num(R, 3), num(R, 4)], [num(Y, 2)]], pile=[drawn])
    g.apply(0, {"type": "draw"})
    assert g.turn == 0 and g.drawn_card_id == drawn.id
    assert g.playable_ids(0) == [drawn.id]
    with pytest.raises(IllegalMove):
        g.apply(0, {"type": "draw"})
    g.apply(0, {"type": "play", "card_id": drawn.id})
    assert g.turn == 1

    g2 = setup(hands=[[num(B, 1), num(B, 2)], [num(R, 3), num(R, 4)], [num(Y, 2)]], pile=[num(R, 8)])
    g2.apply(0, {"type": "draw"})
    g2.apply(0, {"type": "keep"})
    assert g2.turn == 1 and len(g2.hands[0]) == 3


def test_after_drawing_only_drawn_card_can_be_played():
    playable_in_hand = num(R, 1)
    g = setup(hands=[[playable_in_hand, num(B, 2)], [num(R, 3)], [num(Y, 2)]], pile=[num(R, 9)])
    g.apply(0, {"type": "draw"})  # allowed even with a playable card
    with pytest.raises(IllegalMove) as e:
        g.apply(0, {"type": "play", "card_id": playable_in_hand.id})
    assert e.value.code == "must_play_drawn"


def test_reshuffle_when_draw_pile_empty():
    g = setup(hands=[[num(B, 1), num(B, 2)], [num(R, 3)], [num(Y, 2)]], pile=[])
    old = [num(G, 1), num(G, 2), num(G, 3)]
    top = g.top
    g.discard = old + [top]
    events = g.apply(0, {"type": "draw"})
    assert "reshuffle" in types(events)
    assert g.discard == [top]
    assert len(g.draw_pile) == 2 and len(g.hands[0]) == 3


# §4 action cards ------------------------------------------------------------


def test_skip():
    g = setup(n=4, hands=[[act(Kind.SKIP, R), num(B, 1)], [num(B, 2)], [num(B, 3)], [num(B, 4)]])
    events = g.apply(0, {"type": "play", "card_id": g.hands[0][0].id})
    assert {"type": "skip", "seat": 1} in events
    assert g.turn == 2


def test_reverse():
    g = setup(n=4, hands=[[act(Kind.REVERSE, R), num(B, 1)], [num(B, 2)], [num(B, 3)], [num(B, 4)]])
    g.apply(0, {"type": "play", "card_id": g.hands[0][0].id})
    assert g.direction == -1 and g.turn == 3


def test_reverse_with_two_players_acts_as_skip():
    g = setup(n=2, hands=[[act(Kind.REVERSE, R), num(B, 1)], [num(B, 2)]])
    g.apply(0, {"type": "play", "card_id": g.hands[0][0].id})
    assert g.turn == 0


def test_skip_with_two_players_plays_again():
    g = setup(n=2, hands=[[act(Kind.SKIP, R), num(B, 1)], [num(B, 2)]])
    g.apply(0, {"type": "play", "card_id": g.hands[0][0].id})
    assert g.turn == 0


def test_draw_two():
    g = setup(n=3, hands=[[act(Kind.DRAW2, R), num(B, 1)], [num(B, 2)], [num(B, 3)]])
    g.apply(0, {"type": "play", "card_id": g.hands[0][0].id})
    assert len(g.hands[1]) == 3 and g.turn == 2


def test_no_stacking_draw_two():
    g = setup(n=3, hands=[[act(Kind.DRAW2, R), num(B, 1)], [act(Kind.DRAW2, B), num(B, 2)], [num(B, 3)]])
    g.apply(0, {"type": "play", "card_id": g.hands[0][0].id})
    with pytest.raises(IllegalMove):
        g.apply(1, {"type": "play", "card_id": g.hands[1][0].id})


def test_wild_requires_colour_and_sets_it():
    wild = act(Kind.WILD)
    g = setup(hands=[[wild, num(R, 1)], [num(B, 2)], [num(B, 3)]])
    with pytest.raises(IllegalMove) as e:
        g.apply(0, {"type": "play", "card_id": wild.id})
    assert e.value.code == "need_color"
    g.apply(0, {"type": "play", "card_id": wild.id, "color": "green"})
    assert g.current_color is G and g.turn == 1


def _wild4_game(offender_hand_extra):
    w4 = act(Kind.WILD4)
    g = setup(
        n=3,
        hands=[[w4, *offender_hand_extra], [num(B, 2), num(B, 3)], [num(B, 4)]],
        pile=[num(Y, i) for i in range(1, 10)],
    )
    g.apply(0, {"type": "play", "card_id": w4.id, "color": "blue"})
    return g


def test_wild4_accept():
    g = _wild4_game([num(B, 1), num(Y, 1)])
    assert g.pending["type"] == "challenge" and g.actor == 1
    with pytest.raises(IllegalMove):
        g.apply(1, {"type": "draw"})
    g.apply(1, {"type": "accept"})
    assert len(g.hands[1]) == 6 and g.turn == 2 and g.current_color is B


def test_wild4_challenge_guilty():
    g = _wild4_game([num(R, 1), num(Y, 1)])  # held a red: illegal play
    events = g.apply(1, {"type": "challenge"})
    ch = next(e for e in events if e["type"] == "challenge")
    assert ch["result"] == "guilty"
    assert len(g.hands[0]) == 6 and len(g.hands[1]) == 2
    assert g.turn == 1  # challenger keeps their turn
    # Revealed hand is private to the challenger.
    assert "private" in events_for(events, 1)[0]
    assert "private" not in events_for(events, 2)[0]


def test_wild4_challenge_innocent():
    g = _wild4_game([num(B, 1), act(Kind.SKIP, Y)])  # number/symbol matches are fine
    events = g.apply(1, {"type": "challenge"})
    assert next(e for e in events if e["type"] == "challenge")["result"] == "innocent"
    assert len(g.hands[1]) == 8 and g.turn == 2


def test_snapshot_hides_wild4_legality_and_other_hands():
    g = _wild4_game([num(R, 1)])
    snap = snapshot_for(g, 2)
    assert "legal" not in snap["pending"]
    assert [c["id"] for c in snap["hand"]] == [c.id for c in g.hands[2]]
    assert snap["hand_counts"] == [1, 2, 1]


# §5 UNO ---------------------------------------------------------------------


def test_missed_uno_can_be_caught_until_next_player_acts():
    g = setup(hands=[[num(R, 1), num(R, 2)], [num(B, 2), num(B, 3)], [num(B, 4)]], pile=[num(Y, i) for i in range(1, 9)])
    g.apply(0, {"type": "play", "card_id": g.hands[0][0].id})
    assert g.uno_vulnerable == 0
    events = g.apply(2, {"type": "catch", "target": 0})
    assert types(events) == ["catch", "draw"]
    assert len(g.hands[0]) == 3 and g.uno_vulnerable is None


def test_catch_window_closes_when_next_player_acts():
    g = setup(hands=[[num(R, 1), num(R, 2)], [num(R, 3), num(B, 3)], [num(B, 4)]])
    g.apply(0, {"type": "play", "card_id": g.hands[0][0].id})
    g.apply(1, {"type": "play", "card_id": g.hands[1][0].id})
    with pytest.raises(IllegalMove):
        g.apply(2, {"type": "catch", "target": 0})


def test_calling_uno_protects():
    g = setup(hands=[[num(R, 1), num(R, 2)], [num(B, 2), num(B, 3)], [num(B, 4)]])
    g.apply(0, {"type": "call_uno"})
    g.apply(0, {"type": "play", "card_id": g.hands[0][0].id})
    assert g.uno_vulnerable is None
    with pytest.raises(IllegalMove):
        g.apply(1, {"type": "catch", "target": 0})


def test_calling_uno_after_playing_but_before_caught():
    g = setup(hands=[[num(R, 1), num(R, 2)], [num(B, 2), num(B, 3)], [num(B, 4)]])
    g.apply(0, {"type": "play", "card_id": g.hands[0][0].id})
    g.apply(0, {"type": "call_uno"})
    with pytest.raises(IllegalMove):
        g.apply(1, {"type": "catch", "target": 0})


def test_uno_call_resets_after_drawing():
    g = setup(hands=[[num(B, 1), num(B, 2)], [num(B, 3)], [num(B, 4)]], pile=[num(G, 9)])
    g.apply(0, {"type": "call_uno"})
    g.apply(0, {"type": "draw"})
    assert g.uno_called[0] is False


def test_cannot_call_uno_with_many_cards():
    g = setup(hands=[[num(B, 1), num(B, 2), num(B, 3)], [num(B, 3)], [num(B, 4)]])
    with pytest.raises(IllegalMove):
        g.apply(0, {"type": "call_uno"})


# §6-7 round end & scoring ---------------------------------------------------


def test_going_out_scores_other_hands():
    g = setup(
        hands=[[num(R, 1)], [num(B, 7), act(Kind.SKIP, B)], [act(Kind.WILD), num(Y, 0)]],
    )
    events = g.apply(0, {"type": "play", "card_id": g.hands[0][0].id})
    assert events[-1] == {"type": "round_over", "winner": 0, "points": 77, "game_over": False}
    assert g.scores == [77, 0, 0] and g.phase is Phase.ROUND_OVER
    with pytest.raises(IllegalMove):
        g.apply(1, {"type": "draw"})


def test_last_card_draw_two_still_hits_next_player():
    g = setup(hands=[[act(Kind.DRAW2, R)], [num(B, 1)], [num(B, 2)]], pile=[num(Y, 3), num(Y, 4)])
    g.apply(0, {"type": "play", "card_id": g.hands[0][0].id})
    assert len(g.hands[1]) == 3
    assert g.scores[0] == 1 + 3 + 4 + 2


def test_reaching_target_ends_game_and_next_round_rotates_dealer():
    g = setup(hands=[[num(R, 1)], [act(Kind.WILD)], [num(B, 2)]])
    g.scores = [480, 0, 0]
    g.apply(0, {"type": "play", "card_id": g.hands[0][0].id})
    assert g.phase is Phase.GAME_OVER

    g2 = setup(hands=[[num(R, 1)], [num(B, 1)], [num(B, 2)]])
    g2.apply(0, {"type": "play", "card_id": g2.hands[0][0].id})
    dealer = g2.dealer
    g2.next_round()
    assert g2.dealer == (dealer + 1) % 3 and g2.phase is Phase.PLAYING
    assert g2.scores[0] == 3


# timeouts -------------------------------------------------------------------


def test_auto_play_draws_and_passes():
    g = setup(hands=[[num(B, 1)], [num(B, 2)], [num(B, 3)]], pile=[num(R, 9)])
    events = g.auto_play()
    assert types(events)[0] == "timeout"
    assert g.turn == 1 and len(g.hands[0]) == 2


def test_auto_play_accepts_wild4():
    g = _wild4_game([num(B, 1)])
    g.auto_play()
    assert g.pending is None and len(g.hands[1]) == 6


def test_random_full_games_never_break_invariants():
    """Play many games with random legal moves; card count must stay 108."""
    for seed in range(30):
        rng = random.Random(seed)
        n = rng.randint(2, 10)
        g = Game(n, random.Random(seed), target_score=200)
        g.start_round()
        for _ in range(5000):
            if g.phase is Phase.GAME_OVER:
                break
            if g.phase is Phase.ROUND_OVER:
                g.next_round()
                continue
            assert sum(map(len, g.hands)) + len(g.draw_pile) + len(g.discard) == 108
            seat = g.actor
            if rng.random() < 0.05:
                for s in range(n):
                    if len(g.hands[s]) in (1, 2) and not g.uno_called[s]:
                        g.apply(s, {"type": "call_uno"})
            if g.uno_vulnerable is not None and rng.random() < 0.5:
                catcher = (g.uno_vulnerable + 1) % n
                g.apply(catcher, {"type": "catch", "target": g.uno_vulnerable})
                continue
            if g.pending and g.pending["type"] == "challenge":
                g.apply(seat, {"type": rng.choice(["challenge", "accept"])})
            elif g.pending:
                g.apply(seat, {"type": "choose_color", "color": "red"})
            elif (ids := g.playable_ids(seat)) and rng.random() < 0.9:
                g.apply(seat, {"type": "play", "card_id": rng.choice(ids), "color": rng.choice(list(Color)).value})
            elif g.drawn_card_id is not None:
                g.apply(seat, {"type": "keep"})
            else:
                g.apply(seat, {"type": "draw"})
        assert g.phase is Phase.GAME_OVER, f"seed {seed} did not finish"
