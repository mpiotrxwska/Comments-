@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Najpierw uruchom 1_INSTALUJ.bat & pause & exit /b 1)
.venv\Scripts\python.exe konkurs.py --tylko-raport
pause
