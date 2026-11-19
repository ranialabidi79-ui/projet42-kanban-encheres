# Projet 42 - Kanban et encheres en temps reel

## Installation (Windows, PowerShell)

    python -m venv venv
    .\venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    python manage.py migrate
    python manage.py create_test_users aazzee!!
    python manage.py seed_cards
    python manage.py runserver

Si l'activation est bloquee :
`Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`

Ouvrir http://127.0.0.1:8000/board/1/
Comptes : rania, shahed, maram, nour, ranim.

## Tests

    python -m pytest -v