import pytest
from pydantic import ValidationError

from boards.schemas import (
    Chat,
    MoveCard,
    Typing,
    UpdateCard,
    parse_client_message,
)


def test_valid_move_card():
    msg = parse_client_message(
        {
            "type": "move_card",
            "card_id": 1,
            "to_column": "doing",
            "position": 0,
            "version": 1,
        }
    )
    assert isinstance(msg, MoveCard)
    assert msg.to_column == "doing"


def test_valid_update_card_typing_chat():
    assert isinstance(
        parse_client_message(
            {"type": "update_card", "card_id": 1, "title": "Nouveau", "version": 2}
        ),
        UpdateCard,
    )
    assert isinstance(
        parse_client_message({"type": "typing", "card_id": 3}), Typing
    )
    assert isinstance(
        parse_client_message({"type": "chat", "message": "bonjour"}), Chat
    )


BAD_MESSAGES = [
    "pas un objet",
    [],
    None,
    {},
    {"type": "inconnu"},
    {"type": "move_card"},
    # numeros envoyes sous forme de texte : refuses (mode strict)
    {"type": "move_card", "card_id": "1", "to_column": "doing", "position": 0, "version": 1},
    # un booleen n'est pas un entier valide
    {"type": "move_card", "card_id": True, "to_column": "doing", "position": 0, "version": 1},
    # colonne inconnue
    {"type": "move_card", "card_id": 1, "to_column": "archive", "position": 0, "version": 1},
    # position negative, version zero
    {"type": "move_card", "card_id": 1, "to_column": "doing", "position": -1, "version": 1},
    {"type": "move_card", "card_id": 1, "to_column": "doing", "position": 0, "version": 0},
    # champ inconnu : refuse (par exemple user falsifie)
    {"type": "move_card", "card_id": 1, "to_column": "doing", "position": 0, "version": 1, "user": "nour"},
    # titre vide ou trop long
    {"type": "update_card", "card_id": 1, "title": "", "version": 1},
    {"type": "update_card", "card_id": 1, "title": "x" * 201, "version": 1},
    # chat vide ou trop long
    {"type": "chat", "message": ""},
    {"type": "chat", "message": "x" * 501},
]


@pytest.mark.parametrize("data", BAD_MESSAGES)
def test_invalid_messages_are_refused(data):
    with pytest.raises(ValidationError):
        parse_client_message(data)