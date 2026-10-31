@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Instalacja narzedzia do analizy konkursu...
where py >nul 2>nul && (py -3 -m venv .venv) || (python -m venv .venv)
if not exist .venv\Scripts\python.exe (
  echo.
  echo BLAD: nie znaleziono Pythona. Zainstaluj go ze strony https://www.python.org/downloads/
  echo i podczas instalacji zaznacz "Add python.exe to PATH". Potem uruchom ten plik ponownie.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
echo.
echo Gotowe! Teraz uruchom plik 2_URUCHOM_ANALIZE.bat
pause
