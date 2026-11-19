from django.db import models


class Card(models.Model):
    COLUMNS = [
        ("todo", "À faire"),
        ("doing", "En cours"),
        ("done", "Terminé"),
    ]

    board_id = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=200)
    column = models.CharField(max_length=10, choices=COLUMNS, default="todo")
    position = models.PositiveIntegerField(default=0)
    version = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.title} ({self.column}, v{self.version})"