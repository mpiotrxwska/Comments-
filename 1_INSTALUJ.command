#!/bin/bash
cd "$(dirname "$0")"
python3 -m venv .venv || { echo "Zainstaluj Pythona ze strony https://www.python.org/downloads/"; read -p "Enter..."; exit 1; }
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
echo; echo "Gotowe! Teraz uruchom 2_URUCHOM_ANALIZE.command"; read -p "Naciśnij Enter..."
