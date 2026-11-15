"""Client -> server WebSocket messages. Mirrored in web/src/lib/types.ts."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

ColorName = Literal["red", "yellow", "green", "blue"]


class Join(BaseModel):
    type: Literal["join"]
    name: Annotated[str, Field(min_length=1, max_length=40)]
    token: str | None = None


class Start(BaseModel):
    type: Literal["start"]


class NextRound(BaseModel):
    type: Literal["next_round"]


class NewGame(BaseModel):
    type: Literal["new_game"]


class Leave(BaseModel):
    type: Literal["leave"]


class Play(BaseModel):
    type: Literal["play"]
    card_id: int
    color: ColorName | None = None
    seq: int


class Draw(BaseModel):
    type: Literal["draw"]
    seq: int


class Keep(BaseModel):
    type: Literal["keep"]
    seq: int


class ChooseColor(BaseModel):
    type: Literal["choose_color"]
    color: ColorName
    seq: int


class Challenge(BaseModel):
    type: Literal["challenge"]
    seq: int


class Accept(BaseModel):
    type: Literal["accept"]
    seq: int


class CallUno(BaseModel):
    type: Literal["call_uno"]


class Catch(BaseModel):
    type: Literal["catch"]
    target: int


ClientMessage = Annotated[
    Join | Start | NextRound | NewGame | Leave | Play | Draw | Keep | ChooseColor | Challenge | Accept | CallUno | Catch,
    Field(discriminator="type"),
]
client_message = TypeAdapter(ClientMessage)

# Engine actions that are only valid against the snapshot the client saw.
SEQUENCED = {"play", "draw", "keep", "choose_color", "challenge", "accept"}
# Engine actions forwarded to Game.apply.
GAME_ACTIONS = SEQUENCED | {"call_uno", "catch"}
