#!/bin/bash
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { echo "Najpierw uruchom 1_INSTALUJ.command"; read -p "Enter..."; exit 1; }
.venv/bin/python konkurs.py 
read -p "Naciśnij Enter, aby zamknąć..."
