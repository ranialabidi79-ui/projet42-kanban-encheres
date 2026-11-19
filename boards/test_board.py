import pytest
from channels.db import database_sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

import boards.routing
from boards.models import Card

application = URLRouter(boards.routing.websocket_urlpatterns)
pytestmark = pytest.mark.django_db(transaction=True)


@database_sync_to_async
def make_user(name):
    return get_user_model().objects.create_user(username=name)


@database_sync_to_async
def make_card(board_id=1, column="todo"):
    return Card.objects.create(
        board_id=board_id, title="Carte test", column=column, position=0
    )


@database_sync_to_async
def reload_card(card_id):
    return Card.objects.get(id=card_id)


async def connect(user, board_id=1):
    communicator = WebsocketCommunicator(application, f"/ws/board/{board_id}/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected
    welcome = await communicator.receive_json_from()
    state = await communicator.receive_json_from()
    assert welcome["type"] == "welcome"
    assert state["type"] == "board_state"
    return communicator


def move(card_id, to_column, version):
    return {
        "type": "move_card",
        "card_id": card_id,
        "to_column": to_column,
        "position": 0,
        "version": version,
    }


async def test_move_with_good_version():
    user = await make_user("rania")
    card = await make_card()
    comm = await connect(user)
    await comm.send_json_to(move(card.id, "doing", 1))
    msg = await comm.receive_json_from()
    assert msg["type"] == "card_moved"
    assert msg["to_column"] == "doing"
    assert msg["version"] == 2
    assert msg["by"] == "rania"
    saved = await reload_card(card.id)
    assert (saved.column, saved.version) == ("doing", 2)
    await comm.disconnect()


async def test_stale_version_is_refused():
    user = await make_user("rania")
    card = await make_card()
    comm = await connect(user)
    await comm.send_json_to(move(card.id, "doing", 1))
    assert (await comm.receive_json_from())["type"] == "card_moved"
    # La carte est maintenant en version 2 : renvoyer la version 1 doit echouer.
    await comm.send_json_to(move(card.id, "done", 1))
    msg = await comm.receive_json_from()
    assert msg["type"] == "conflict"
    assert msg["current"]["version"] == 2
    assert msg["current"]["column"] == "doing"
    saved = await reload_card(card.id)
    assert (saved.column, saved.version) == ("doing", 2)
    await comm.disconnect()


async def test_conflict_is_sent_only_to_sender():
    rania = await make_user("rania")
    shahed = await make_user("shahed")
    card = await make_card()
    a = await connect(rania)
    b = await connect(shahed)
    await a.send_json_to(move(card.id, "doing", 1))
    assert (await a.receive_json_from())["type"] == "card_moved"
    assert (await b.receive_json_from())["type"] == "card_moved"
    await b.send_json_to(move(card.id, "done", 1))
    assert (await b.receive_json_from())["type"] == "conflict"
    assert await a.receive_nothing()
    await a.disconnect()
    await b.disconnect()

async def test_other_board_cannot_move_card():
    user = await make_user("rania")
    card = await make_card(board_id=1)
    comm = await connect(user, board_id=2)
    await comm.send_json_to(move(card.id, "doing", 1))
    msg = await comm.receive_json_from()
    assert msg == {"type": "error", "reason": "card_not_found"}
    saved = await reload_card(card.id)
    assert (saved.column, saved.version) == ("todo", 1)
    await comm.disconnect()


async def test_malformed_message_returns_error():
    user = await make_user("rania")
    comm = await connect(user)
    await comm.send_json_to({"type": "move_card", "card_id": "abc"})
    assert await comm.receive_json_from() == {"type": "error", "reason": "invalid"}
    await comm.send_json_to({"type": "inconnu"})
    assert await comm.receive_json_from() == {"type": "error", "reason": "invalid"}
    await comm.disconnect()


async def test_anonymous_is_refused():
    comm = WebsocketCommunicator(application, "/ws/board/1/")
    comm.scope["user"] = AnonymousUser()
    connected, _ = await comm.connect()
    assert connected is False