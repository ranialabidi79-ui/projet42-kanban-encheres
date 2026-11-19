from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

NAMES = ["rania", "shahed", "maram", "nour", "ranim"]


class Command(BaseCommand):
    help = "Cree 5 comptes de test (un par membre du groupe)"

    def add_arguments(self, parser):
        parser.add_argument("password")

    def handle(self, *args, **options):
        User = get_user_model()
        for name in NAMES:
            user, created = User.objects.get_or_create(username=name)
            if created:
                user.set_password(options["password"])
                user.save()
                self.stdout.write(f"cree : {name}")
            else:
                self.stdout.write(f"existe deja : {name}")