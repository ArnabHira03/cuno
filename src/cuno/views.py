"""Per-player views of the game. Never leak another player's cards here."""

from __future__ import annotations

from typing import Any

from .engine import Event, Game, Phase


def snapshot_for(game: Game, seat: int) -> dict[str, Any]:
    pending = None
    if game.pending:
        # Hide "legal": it would reveal whether a Wild Draw Four was a bluff.
        pending = {k: v for k, v in game.pending.items() if k != "legal"}

    last_round = None
    if game.last_round:
        lr = game.last_round
        last_round = {
            "winner": lr["winner"],
            "points": lr["points"],
            "breakdown": {str(k): v for k, v in lr["breakdown"].items()},
            # Hands are revealed to everyone once the round has ended.
            "hands": {str(k): v for k, v in lr["hands"].items()},
        }

    return {
        "phase": game.phase.value,
        "round": game.round_no,
        "dealer": game.dealer,
        "hand": [c.to_dict() for c in game.hands[seat]],
        "hand_counts": [len(h) for h in game.hands],
        "top": game.top.to_dict() if game.discard else None,
        "discard_count": len(game.discard),
        "draw_count": len(game.draw_pile),
        "current_color": game.current_color.value if game.current_color else None,
        "direction": game.direction,
        "turn": game.turn,
        "actor": game.actor,
        "pending": pending,
        "drawn_card_id": game.drawn_card_id if seat == game.turn else None,
        "playable": game.playable_ids(seat),
        "uno_called": list(game.uno_called),
        "uno_vulnerable": game.uno_vulnerable,
        "scores": list(game.scores),
        "target_score": game.target_score,
        "last_round": last_round if game.phase is not Phase.PLAYING else None,
    }


def spectator_snapshot_for(game: Game, seat: int) -> dict[str, Any]:
    """The followed seat's view plus every hand. Only ever sent to spectators."""
    view = snapshot_for(game, seat)
    view["hands"] = {str(i): [c.to_dict() for c in hand] for i, hand in enumerate(game.hands)}
    return view


def events_for(events: list[Event], seat: int) -> list[Event]:
    """Strip private payloads that belong to another seat."""
    out: list[Event] = []
    for ev in events:
        private = ev.get("private")
        if private is None:
            out.append(ev)
            continue
        ev = {k: v for k, v in ev.items() if k != "private"}
        if private.get("seat") == seat:
            ev["private"] = private
        out.append(ev)
    return out
