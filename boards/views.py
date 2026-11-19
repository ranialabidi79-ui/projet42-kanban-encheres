from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def board(request, room_name):
    return render(request, "boards/board.html", {"room_name": room_name})