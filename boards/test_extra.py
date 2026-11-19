import pytest

from boards.test_board import (
    connect,
    make_card,
    make_user,
    move,
    reload_card,
)

pytestmark = pytest.mark.django_db(transaction=True)


def update(card_id, title, version):
    return {
        "type": "update_card",
        "card_id": card_id,
        "title": title,
        "version": version,
    }


async def test_update_card_with_good_version():
    user = await make_user("rania")
    card = await make_card()
    comm = await connect(user)
    await comm.send_json_to(update(card.id, "Nouveau titre", 1))
    msg = await comm.receive_json_from()
    assert msg["type"] == "card_updated"
    assert msg["title"] == "Nouveau titre"
    assert msg["version"] == 2
    assert msg["by"] == "rania"
    saved = await reload_card(card.id)
    assert (saved.title, saved.version) == ("Nouveau titre", 2)
    await comm.disconnect()


async def test_update_card_with_stale_version_is_refused():
    user = await make_user("rania")
    card = await make_card()
    comm = await connect(user)
    await comm.send_json_to(update(card.id, "Premier", 1))
    assert (await comm.receive_json_from())["type"] == "card_updated"
    # Version 1 est maintenant perimee : le second titre doit etre refuse.
    await comm.send_json_to(update(card.id, "Second", 1))
    msg = await comm.receive_json_from()
    assert msg["type"] == "conflict"
    assert msg["current"]["title"] == "Premier"
    saved = await reload_card(card.id)
    assert (saved.title, saved.version) == ("Premier", 2)
    await comm.disconnect()


async def test_move_then_update_share_the_same_version_counter():
    user = await make_user("rania")
    card = await make_card()
    comm = await connect(user)
    await comm.send_json_to(move(card.id, "doing", 1))
    assert (await comm.receive_json_from())["version"] == 2
    await comm.send_json_to(update(card.id, "Titre", 2))
    assert (await comm.receive_json_from())["version"] == 3
    await comm.disconnect()


async def test_typing_reaches_others_but_not_sender():
    rania = await make_user("rania")
    shahed = await make_user("shahed")
    card = await make_card()
    a = await connect(rania)
    b = await connect(shahed)
    await a.send_json_to({"type": "typing", "card_id": card.id})
    msg = await b.receive_json_from()
    assert msg == {"type": "typing", "card_id": card.id, "user": "rania"}
    assert await a.receive_nothing()
    await a.disconnect()
    await b.disconnect()


async def test_typing_is_not_saved_in_database():
    user = await make_user("rania")
    card = await make_card()
    comm = await connect(user)
    await comm.send_json_to({"type": "typing", "card_id": card.id})
    saved = await reload_card(card.id)
    assert saved.version == 1
    await comm.disconnect()


async def test_chat_uses_session_name_not_message_name():
    rania = await make_user("rania")
    shahed = await make_user("shahed")
    a = await connect(rania)
    b = await connect(shahed)
    await a.send_json_to({"type": "chat", "message": "bonjour"})
    assert await a.receive_json_from() == {
        "type": "chat",
        "message": "bonjour",
        "user": "rania",
    }
    assert (await b.receive_json_from())["user"] == "rania"
    await a.disconnect()
    await b.disconnect()


async def test_fake_user_field_is_refused():
    user = await make_user("rania")
    comm = await connect(user)
    await comm.send_json_to({"type": "chat", "message": "faux", "user": "nour"})
    assert await comm.receive_json_from() == {"type": "error", "reason": "invalid"}
    await comm.disconnect()


async def test_heartbeat_is_accepted_silently():
    user = await make_user("rania")
    comm = await connect(user)
    await comm.send_json_to({"type": "heartbeat"})
    assert await comm.receive_nothing()
    await comm.disconnect()


async def test_sync_request_returns_board_state():
    user = await make_user("rania")
    await make_card()
    comm = await connect(user)
    await comm.send_json_to({"type": "sync_request"})
    msg = await comm.receive_json_from()
    assert msg["type"] == "board_state"
    assert len(msg["cards"]) == 1
    await comm.disconnect()