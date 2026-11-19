"""Schemas Pydantic v2 : le contrat des messages envoyes par le navigateur.

Tout message entrant est valide ici AVANT d'etre traite. Un message qui ne
respecte pas le schema est refuse avec {"type": "error", "reason": "invalid"}.
"""
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class ClientMessage(BaseModel):
    # strict : "12" n'est pas accepte pour un entier, True non plus.
    # forbid : un champ inconnu est refuse.
    model_config = ConfigDict(strict=True, extra="forbid")


class SyncRequest(ClientMessage):
    type: Literal["sync_request"]


class Heartbeat(ClientMessage):
    type: Literal["heartbeat"]


class MoveCard(ClientMessage):
    type: Literal["move_card"]
    card_id: int
    to_column: Literal["todo", "doing", "done"]
    position: int = Field(ge=0)
    version: int = Field(ge=1)


class UpdateCard(ClientMessage):
    type: Literal["update_card"]
    card_id: int
    title: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1)


class Typing(ClientMessage):
    type: Literal["typing"]
    card_id: int


class Chat(ClientMessage):
    type: Literal["chat"]
    message: str = Field(min_length=1, max_length=500)


AnyClientMessage = Annotated[
    Union[SyncRequest, Heartbeat, MoveCard, UpdateCard, Typing, Chat],
    Field(discriminator="type"),
]

_adapter = TypeAdapter(AnyClientMessage)


def parse_client_message(data):
    """Renvoie le message valide, ou leve pydantic.ValidationError."""
    return _adapter.validate_python(data)