import os

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from pydantic import ValidationError

from .models import Card
from .schemas import (
    Chat,
    Heartbeat,
    MoveCard,
    SyncRequest,
    Typing,
    UpdateCard,
    parse_client_message,
)


def card_to_dict(card):
    return {
        "id": card.id,
        "title": card.title,
        "column": card.column,
        "position": card.position,
        "version": card.version,
    }


class BoardConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        if not self.user.is_authenticated or not self.room_name.isdigit():
            await self.close()
            return
        self.board_id = int(self.room_name)
        self.group_name = f"board_{self.board_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({
            "type": "welcome",
            "user": self.user.username,
            "served_by": os.environ.get("WORKER_NAME", "local"),
            "server_time": timezone.now().isoformat(),
        })
        await self.send_board_state()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # ----- lecture de la base -----

    @database_sync_to_async
    def get_cards(self):
        cards = Card.objects.filter(board_id=self.board_id).order_by("position", "id")
        return [card_to_dict(c) for c in cards]

    async def send_board_state(self):
        await self.send_json({"type": "board_state", "cards": await self.get_cards()})

    # ----- modification versionnee (verrouillage optimiste) -----

    @database_sync_to_async
    def versioned_update(self, card_id, version, **changes):
        """Modifie la carte seulement si sa version est celle envoyee.

        La verification et la modification forment UNE seule operation SQL :
        deux modifications simultanees ne peuvent pas passer toutes les deux.
        """
        with transaction.atomic():
            updated = Card.objects.filter(
                id=card_id, board_id=self.board_id, version=version
            ).update(version=F("version") + 1, **changes)
            card = Card.objects.filter(id=card_id, board_id=self.board_id).first()
        if card is None:
            return "missing", None
        if updated == 0:
            return "conflict", card_to_dict(card)
        return "ok", card_to_dict(card)

    async def finish_update(self, result, card, card_id, event):
        if result == "missing":
            await self.send_json({"type": "error", "reason": "card_not_found"})
        elif result == "conflict":
            # Seul l'emetteur recoit le refus, avec la carte a jour.
            await self.send_json(
                {"type": "conflict", "card_id": card_id, "current": card}
            )
        else:
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "broadcast.message",
                    "data": {**event(card), "by": self.user.username},
                },
            )

    async def handle_move_card(self, msg):
        result, card = await self.versioned_update(
            msg.card_id,
            msg.version,
            column=msg.to_column,
            position=msg.position,
        )
        await self.finish_update(
            result,
            card,
            msg.card_id,
            lambda c: {
                "type": "card_moved",
                "card_id": c["id"],
                "to_column": c["column"],
                "position": c["position"],
                "version": c["version"],
            },
        )

    async def handle_update_card(self, msg):
        result, card = await self.versioned_update(
            msg.card_id, msg.version, title=msg.title
        )
        await self.finish_update(
            result,
            card,
            msg.card_id,
            lambda c: {
                "type": "card_updated",
                "card_id": c["id"],
                "title": c["title"],
                "version": c["version"],
            },
        )

    # ----- reception des messages du navigateur -----

    async def receive_json(self, content):
        try:
            msg = parse_client_message(content)
        except ValidationError:
            await self.send_json({"type": "error", "reason": "invalid"})
            return

        if isinstance(msg, SyncRequest):
            await self.send_board_state()
        elif isinstance(msg, MoveCard):
            await self.handle_move_card(msg)
        elif isinstance(msg, UpdateCard):
            await self.handle_update_card(msg)
        elif isinstance(msg, Typing):
            # Rien n'est enregistre : on previent les autres, pas l'emetteur.
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "broadcast.typing",
                    "sender": self.channel_name,
                    "data": {
                        "type": "typing",
                        "card_id": msg.card_id,
                        "user": self.user.username,
                    },
                },
            )
        elif isinstance(msg, Chat):
            # Chat de test. Le nom vient de la session, jamais du message.
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "broadcast.message",
                    "data": {
                        "type": "chat",
                        "message": msg.message,
                        "user": self.user.username,
                    },
                },
            )
        elif isinstance(msg, Heartbeat):
            pass  # La presence (heartbeat) est branchee plus tard.

    # ----- diffusion vers le navigateur -----

    async def broadcast_message(self, event):
        await self.send_json(event["data"])

    async def broadcast_typing(self, event):
        if event["sender"] != self.channel_name:
            await self.send_json(event["data"])