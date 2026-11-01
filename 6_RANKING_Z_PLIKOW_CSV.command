#!/bin/bash
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { echo "Najpierw uruchom 1_INSTALUJ.command"; read -p "Enter..."; exit 1; }
mkdir -p pliki_csv
.venv/bin/python konkurs.py --z-plikow
read -p "Naciśnij Enter, aby zamknąć..."
