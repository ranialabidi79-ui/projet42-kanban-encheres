from django.core.management.base import BaseCommand

from boards.models import Card

CARDS = [
    ("Écrire le rapport", "todo", 0),
    ("Préparer la démo", "todo", 1),
    ("Relire le code", "doing", 0),
]


class Command(BaseCommand):
    help = "Cree 3 cartes d'exemple sur le tableau 1"

    def handle(self, *args, **options):
        if Card.objects.filter(board_id=1).exists():
            self.stdout.write("Des cartes existent deja : rien a faire")
            return
        for title, column, position in CARDS:
            Card.objects.create(
                board_id=1, title=title, column=column, position=position
            )
        self.stdout.write("3 cartes creees")