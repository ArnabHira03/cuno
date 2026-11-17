"""Pure game engine. No I/O, no asyncio. Rules: cuno_rules.md.

`Game.apply(seat, action)` validates an action, mutates state and returns a
list of events. Events are broadcast to every player; any data meant for one
player only goes under the event's "private" key ({"seat": s, ...}) and is
stripped for everyone else by `views.events_for`.
"""

from __future__ import annotations

import random
from enum import StrEnum
from typing import Any

from .cards import Card, Color, Kind, build_deck

Event = dict[str, Any]

HAND_SIZE = 7
MIN_PLAYERS = 2
MAX_PLAYERS = 10


class IllegalMove(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class Phase(StrEnum):
    PLAYING = "playing"
    ROUND_OVER = "round_over"
    GAME_OVER = "game_over"


class Game:
    def __init__(
        self,
        n_players: int,
        rng: random.Random | None = None,
        target_score: int = 500,
    ) -> None:
        if not MIN_PLAYERS <= n_players <= MAX_PLAYERS:
            raise ValueError(f"need {MIN_PLAYERS}-{MAX_PLAYERS} players")
        self.n = n_players
        self.rng = rng or random.Random()
        self.target_score = target_score
        self.scores = [0] * n_players
        self.dealer = self.rng.randrange(n_players)
        self.round_no = 0
        self.last_round: dict[str, Any] | None = None
        # Per-round state, initialised by start_round().
        self.phase = Phase.PLAYING
        self.hands: list[list[Card]] = [[] for _ in range(n_players)]
        self.draw_pile: list[Card] = []  # top of pile is the end of the list
        self.discard: list[Card] = []
        self.current_color: Color | None = None
        self.direction = 1
        self.turn = 0
        self.pending: dict[str, Any] | None = None
        self.drawn_card_id: int | None = None
        self.uno_called = [False] * n_players
        self.uno_vulnerable: int | None = None
        self._last_drawn: list[Card] = []

    # ------------------------------------------------------------------ setup

    def start_round(self) -> list[Event]:
        self.round_no += 1
        self.phase = Phase.PLAYING
        self.last_round = None
        self.pending = None
        self.drawn_card_id = None
        self.uno_called = [False] * self.n
        self.uno_vulnerable = None
        self.direction = 1

        self.draw_pile = build_deck()
        self.rng.shuffle(self.draw_pile)
        self.hands = [[] for _ in range(self.n)]
        for _ in range(HAND_SIZE):
            for seat in range(self.n):
                self.hands[seat].append(self.draw_pile.pop())

        # A Wild Draw Four can't start the discard pile (§2).
        while True:
            first = self.draw_pile.pop()
            if first.kind is not Kind.WILD4:
                break
            self.draw_pile.append(first)
            self.rng.shuffle(self.draw_pile)
        self.discard = [first]
        self.current_color = first.color

        events: list[Event] = [
            {"type": "deal", "round": self.round_no, "dealer": self.dealer},
            {"type": "flip", "card": first.to_dict()},
        ]
        first_player = self.next_seat(self.dealer)
        match first.kind:
            case Kind.NUMBER:
                self.turn = first_player
            case Kind.SKIP:
                events.append({"type": "skip", "seat": first_player})
                self.turn = self.next_seat(first_player)
            case Kind.REVERSE:
                self.direction = -1
                events.append({"type": "reverse", "direction": self.direction})
                self.turn = self.dealer
            case Kind.DRAW2:
                events += self._draw(first_player, 2, "draw2")
                self.turn = self.next_seat(first_player)
            case Kind.WILD:
                self.turn = first_player
                self.pending = {"type": "choose_color", "seat": first_player}
        return events

    def next_round(self) -> list[Event]:
        if self.phase is not Phase.ROUND_OVER:
            raise IllegalMove("not_round_over", "The round is not over.")
        self.dealer = self.next_seat(self.dealer)
        return self.start_round()

    # ---------------------------------------------------------------- queries

    def next_seat(self, seat: int, steps: int = 1) -> int:
        return (seat + self.direction * steps) % self.n

    @property
    def top(self) -> Card:
        return self.discard[-1]

    @property
    def actor(self) -> int | None:
        """The seat that must act next (turn player, challenge victim, colour chooser)."""
        if self.phase is not Phase.PLAYING:
            return None
        if self.pending:
            return self.pending.get("victim", self.pending.get("seat"))
        return self.turn

    def matches(self, card: Card) -> bool:
        if card.is_wild:
            return True
        if card.color is self.current_color:
            return True
        top = self.top
        if card.kind is top.kind:
            return card.kind is not Kind.NUMBER or card.value == top.value
        return False

    def playable_ids(self, seat: int) -> list[int]:
        if self.phase is not Phase.PLAYING or self.pending or seat != self.turn:
            return []
        if self.drawn_card_id is not None:
            return [self.drawn_card_id]
        return [c.id for c in self.hands[seat] if self.matches(c)]

    # ---------------------------------------------------------------- actions

    def apply(self, seat: int, action: dict[str, Any]) -> list[Event]:
        if self.phase is not Phase.PLAYING:
            raise IllegalMove("not_playing", "The round is over.")
        if not 0 <= seat < self.n:
            raise IllegalMove("bad_seat", "Unknown seat.")
        match action.get("type"):
            case "play":
                return self._play(seat, action.get("card_id"), action.get("color"))
            case "draw":
                return self._draw_action(seat)
            case "keep":
                return self._keep(seat)
            case "choose_color":
                return self._choose_color(seat, action.get("color"))
            case "challenge":
                return self._resolve_wild4(seat, challenge=True)
            case "accept":
                return self._resolve_wild4(seat, challenge=False)
            case "call_uno":
                return self._call_uno(seat)
            case "catch":
                return self._catch(seat, action.get("target"))
            case other:
                raise IllegalMove("bad_action", f"Unknown action {other!r}.")

    def auto_play(self) -> list[Event]:
        """What happens when the acting player runs out of time."""
        seat = self.actor
        if seat is None:
            return []
        events: list[Event] = [{"type": "timeout", "seat": seat}]
        if self.pending and self.pending["type"] == "challenge":
            events += self._resolve_wild4(seat, challenge=False)
        elif self.pending and self.pending["type"] == "choose_color":
            events += self._choose_color(seat, self.rng.choice(list(Color)).value)
        elif self.drawn_card_id is not None:
            events += self._keep(seat)
        else:
            events += self._draw_action(seat)
            if self.drawn_card_id is not None:
                events += self._keep(seat)
        return events

    def _require_turn(self, seat: int) -> None:
        if self.pending:
            raise IllegalMove("pending", "Waiting for another decision first.")
        if seat != self.turn:
            raise IllegalMove("not_your_turn", "It's not your turn.")

    def _play(self, seat: int, card_id: Any, color: Any) -> list[Event]:
        self._require_turn(seat)
        hand = self.hands[seat]
        card = next((c for c in hand if c.id == card_id), None)
        if card is None:
            raise IllegalMove("no_such_card", "You don't have that card.")
        if self.drawn_card_id is not None and card.id != self.drawn_card_id:
            raise IllegalMove("must_play_drawn", "You can only play the card you just drew.")
        if not self.matches(card):
            raise IllegalMove("not_playable", "That card doesn't match.")
        chosen: Color | None = card.color
        if card.is_wild:
            try:
                chosen = Color(color)
            except ValueError:
                raise IllegalMove("need_color", "Choose a colour for the wild card.") from None

        # Legal only if the player had no card of the current colour (§4).
        wild4_legal = not any(c.color is self.current_color for c in hand if c.id != card.id)

        self.uno_vulnerable = None
        self.drawn_card_id = None
        hand.remove(card)
        self.discard.append(card)
        self.current_color = chosen
        events: list[Event] = [
            {"type": "play", "seat": seat, "card": card.to_dict(), "color": chosen.value}
        ]
        if len(hand) == 1 and not self.uno_called[seat]:
            self.uno_vulnerable = seat
        if not hand:
            return events + self._end_round(seat, card)

        nxt = self.next_seat(seat)
        match card.kind:
            case Kind.NUMBER | Kind.WILD:
                self.turn = nxt
            case Kind.SKIP:
                events.append({"type": "skip", "seat": nxt})
                self.turn = self.next_seat(seat, 2)
            case Kind.REVERSE:
                self.direction *= -1
                events.append({"type": "reverse", "direction": self.direction})
                # With two players Reverse acts like Skip.
                self.turn = seat if self.n == 2 else self.next_seat(seat)
            case Kind.DRAW2:
                events += self._draw(nxt, 2, "draw2")
                self.turn = self.next_seat(seat, 2)
            case Kind.WILD4:
                self.pending = {
                    "type": "challenge",
                    "player": seat,
                    "victim": nxt,
                    "legal": wild4_legal,
                }
                self.turn = nxt
        return events

    def _draw_action(self, seat: int) -> list[Event]:
        self._require_turn(seat)
        if self.drawn_card_id is not None:
            raise IllegalMove("already_drew", "You already drew this turn.")
        self.uno_vulnerable = None
        events = self._draw(seat, 1, "draw")
        drawn = self._last_drawn[0] if self._last_drawn else None
        if drawn is not None and self.matches(drawn):
            self.drawn_card_id = drawn.id  # may play it now, or keep it
        else:
            self.turn = self.next_seat(seat)
        return events

    def _keep(self, seat: int) -> list[Event]:
        self._require_turn(seat)
        if self.drawn_card_id is None:
            raise IllegalMove("nothing_drawn", "You haven't drawn a card.")
        self.drawn_card_id = None
        self.uno_vulnerable = None
        self.turn = self.next_seat(seat)
        return [{"type": "keep", "seat": seat}]

    def _choose_color(self, seat: int, color: Any) -> list[Event]:
        if not self.pending or self.pending["type"] != "choose_color" or self.pending["seat"] != seat:
            raise IllegalMove("not_choosing", "You're not choosing a colour.")
        try:
            self.current_color = Color(color)
        except ValueError:
            raise IllegalMove("need_color", "Unknown colour.") from None
        self.pending = None
        return [{"type": "color_chosen", "seat": seat, "color": self.current_color.value}]

    def _resolve_wild4(self, seat: int, *, challenge: bool) -> list[Event]:
        p = self.pending
        if not p or p["type"] != "challenge" or p["victim"] != seat:
            raise IllegalMove("no_challenge", "There's nothing to challenge.")
        self.pending = None
        self.uno_vulnerable = None
        offender, victim = p["player"], p["victim"]
        if not challenge:
            events: list[Event] = [{"type": "accept", "seat": victim}]
            events += self._draw(victim, 4, "wild4")
            self.turn = self.next_seat(victim)
            return events

        guilty = not p["legal"]
        events = [
            {
                "type": "challenge",
                "seat": victim,
                "target": offender,
                "result": "guilty" if guilty else "innocent",
                "private": {
                    "seat": victim,
                    "hand": [c.to_dict() for c in self.hands[offender]],
                },
            }
        ]
        if guilty:
            events += self._draw(offender, 4, "challenge_guilty")
            self.turn = victim  # challenger keeps their turn
        else:
            events += self._draw(victim, 6, "challenge_failed")
            self.turn = self.next_seat(victim)
        return events

    def _call_uno(self, seat: int) -> list[Event]:
        if len(self.hands[seat]) not in (1, 2):
            raise IllegalMove("cant_call_uno", "You can only call CUNO with one or two cards.")
        if self.uno_called[seat]:
            raise IllegalMove("already_called", "You already called CUNO.")
        self.uno_called[seat] = True
        if self.uno_vulnerable == seat:
            self.uno_vulnerable = None
        return [{"type": "uno", "seat": seat}]

    def _catch(self, seat: int, target: Any) -> list[Event]:
        if target is None or target != self.uno_vulnerable or target == seat:
            raise IllegalMove("cant_catch", "Too late, or nobody to catch.")
        self.uno_vulnerable = None
        events: list[Event] = [{"type": "catch", "seat": seat, "target": target}]
        return events + self._draw(target, 2, "uno_penalty")

    # ---------------------------------------------------------------- helpers

    def _draw(self, seat: int, count: int, reason: str) -> list[Event]:
        events: list[Event] = []
        drawn: list[Card] = []
        for _ in range(count):
            if not self.draw_pile:
                if len(self.discard) <= 1:
                    break  # every card is in someone's hand
                top = self.discard.pop()
                self.draw_pile = self.discard
                self.rng.shuffle(self.draw_pile)
                self.discard = [top]
                events.append({"type": "reshuffle", "count": len(self.draw_pile)})
            drawn.append(self.draw_pile.pop())
        self.hands[seat].extend(drawn)
        self._last_drawn = drawn
        if drawn:
            self.uno_called[seat] = False
            if self.uno_vulnerable == seat:
                self.uno_vulnerable = None
        events.append(
            {
                "type": "draw",
                "seat": seat,
                "count": len(drawn),
                "reason": reason,
                "private": {"seat": seat, "card_ids": [c.id for c in drawn]},
            }
        )
        return events

    def _end_round(self, winner: int, last: Card) -> list[Event]:
        events: list[Event] = []
        victim = self.next_seat(winner)
        if last.kind is Kind.DRAW2:
            events += self._draw(victim, 2, "draw2")
        elif last.kind is Kind.WILD4:
            events += self._draw(victim, 4, "wild4")
        self.pending = None
        self.uno_vulnerable = None
        breakdown = {
            seat: sum(c.points for c in hand) for seat, hand in enumerate(self.hands) if seat != winner
        }
        points = sum(breakdown.values())
        self.scores[winner] += points
        game_over = self.scores[winner] >= self.target_score
        self.phase = Phase.GAME_OVER if game_over else Phase.ROUND_OVER
        self.last_round = {
            "winner": winner,
            "points": points,
            "breakdown": breakdown,
            "hands": {seat: [c.to_dict() for c in hand] for seat, hand in enumerate(self.hands)},
        }
        events.append(
            {"type": "round_over", "winner": winner, "points": points, "game_over": game_over}
        )
        return events
