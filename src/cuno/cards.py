"""Card model and deck construction (see cuno_rules.md §1)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Color(StrEnum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"
    BLUE = "blue"


class Kind(StrEnum):
    NUMBER = "number"
    SKIP = "skip"
    REVERSE = "reverse"
    DRAW2 = "draw2"
    WILD = "wild"
    WILD4 = "wild4"


@dataclass(frozen=True, slots=True)
class Card:
    id: int
    kind: Kind
    color: Color | None = None  # None for wild cards
    value: int | None = None  # 0-9 for number cards

    @property
    def is_wild(self) -> bool:
        return self.kind in (Kind.WILD, Kind.WILD4)

    @property
    def points(self) -> int:
        if self.kind is Kind.NUMBER:
            assert self.value is not None
            return self.value
        if self.is_wild:
            return 50
        return 20

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "color": self.color.value if self.color else None,
            "value": self.value,
        }


def build_deck() -> list[Card]:
    """The standard 108-card deck, each card with a unique id."""
    cards: list[Card] = []

    def add(kind: Kind, color: Color | None = None, value: int | None = None) -> None:
        cards.append(Card(len(cards), kind, color, value))

    for color in Color:
        add(Kind.NUMBER, color, 0)
        for value in range(1, 10):
            add(Kind.NUMBER, color, value)
            add(Kind.NUMBER, color, value)
        for kind in (Kind.SKIP, Kind.REVERSE, Kind.DRAW2):
            add(kind, color)
            add(kind, color)
    for _ in range(4):
        add(Kind.WILD)
        add(Kind.WILD4)
    return cards
