# Analiza konkursu TikTok – kto był najbardziej aktywny?

Program sam otwiera przeglądarkę, przechodzi przez Twoje filmy z okresu konkursu, przewija wszystkie
komentarze (z odpowiedziami), liczy aktywność uczestników i tworzy ranking oraz plik Excel.
Nie trzeba niczego kopiować ręcznie.

---

## Instrukcja krok po kroku (Windows)

### Krok 0. Pobierz program
Na stronie repozytorium kliknij zielony przycisk **Code → Download ZIP**, a potem rozpakuj plik
(prawy przycisk → *Wyodrębnij wszystkie*), np. na Pulpit.

### Krok 1. Zainstaluj Pythona (tylko raz)
1. Wejdź na https://www.python.org/downloads/ i kliknij żółty przycisk **Download Python**.
2. Uruchom pobrany instalator i **koniecznie zaznacz na dole pole „Add python.exe to PATH”**.
3. Kliknij **Install Now**.

### Krok 2. Zainstaluj program (tylko raz)
Kliknij dwukrotnie plik **`1_INSTALUJ.bat`**. Poczekaj kilka minut, aż pojawi się „Gotowe!”.

> Jeśli Windows pokaże okno „System Windows ochronił komputer”, kliknij **Więcej informacji → Uruchom mimo to**.

### Krok 3. Wklej zasady konkursu (zalecane)
Otwórz plik **`zasady_konkursu.txt`** (np. w Notatniku), wklej treść zasad z opisu filmu i zapisz.
Zostaną dołączone do raportu.

### Krok 4. Uruchom analizę
Kliknij dwukrotnie **`2_URUCHOM_ANALIZE.bat`**. Przy pierwszym uruchomieniu program zapyta o:
1. link do Twojego profilu (np. `https://www.tiktok.com/@twojanazwa`),
2. link do filmu konkursowego – może być skrócony z przycisku *Udostępnij → Kopiuj link* (np. `https://vm.tiktok.com/...`); program sam go rozwinie,
3. datę i godzinę rozpoczęcia konkursu (np. `2026-10-01 18:00`),
4. datę i godzinę zakończenia (np. `2026-10-15 23:59`),
5. sposób rozpoznawania uczestników,
6. czy odpowiedzi w wątkach liczą się jako komentarze.

Potem:
* Otworzy się okno przeglądarki z TikTokiem. **Zaloguj się samodzielnie** (program nie zna Twojego hasła
  i go nie potrzebuje). Logowanie jest zapamiętywane – przy kolejnych uruchomieniach zwykle nie trzeba
  logować się ponownie. Potem wróć do czarnego okna i naciśnij **Enter**.
* Program pokaże listę znalezionych filmów z okresu konkursu i zapyta, czy jest kompletna.
  Jeśli czegoś brakuje – wpisz `N`, dopisz brakujące linki do pliku **`dodatkowe_filmy.txt`**
  (jeden w linii) i uruchom **`4_ODSWIEZ_LISTE_FILMOW.bat`**.
* Program przechodzi film po filmie. **Nie zamykaj okna przeglądarki i nie klikaj w nim** w trakcie pracy.
  Około 130 komentarzy pod filmem konkursowym zajmuje zwykle kilka minut.

### Krok 5. Wyniki
Po zakończeniu w folderze **`wyniki`** znajdziesz:
* **`wyniki_konkursu.xlsx`** – plik Excel z arkuszami:
  *Podsumowanie, Uczestnicy konkursu, Przeanalizowane filmy, Wszystkie komentarze, Ranking,
  TOP zwycięzcy, Do weryfikacji, Komentarze zwycięzców*,
* **`raport.html`** – czytelny raport (otwórz dwuklikiem w przeglądarce): ranking TOP 20, zwycięzcy,
  lista filmów i wszystkie komentarze zwycięzców,
* folder **`csv`** – te same tabele w plikach CSV.

Ranking pojawia się też w czarnym oknie.

---

## Instrukcja krok po kroku (Mac)

1. **Pobierz program:** na GitHubie **Code → Download ZIP**. Plik rozpakuje się sam w folderze
   *Pobrane* (jeśli nie – kliknij go dwukrotnie). Przenieś folder np. na Biurko.
2. **Zainstaluj Pythona (tylko raz):** https://www.python.org/downloads/ → **Download Python** →
   otwórz pobrany plik `.pkg` i przejdź przez instalator (Dalej → Instaluj).
3. **Otwórz Terminal:** naciśnij **Cmd+Spacja**, wpisz `Terminal` i naciśnij Enter.
   (Nie klikaj dwukrotnie plików `.command` w Finderze – nowsze wersje macOS pokazują wtedy
   ostrzeżenie „nieznany plik / przenieś do kosza”. Przez Terminal tego problemu nie ma.)
4. **Przejdź do folderu programu:** w Terminalu wpisz `cd` i **spację**, potem **przeciągnij myszką
   folder programu** z Findera do okna Terminala (wklei się jego ścieżka) i naciśnij **Enter**.
5. **Zainstaluj program (tylko raz):** wpisz i zatwierdź Enterem:
   ```
   bash 1_INSTALUJ.command
   ```
   Poczekaj, aż pojawi się „Gotowe!”. Jeśli macOS zaproponuje instalację „narzędzi wiersza poleceń”
   (Command Line Tools) – zgódź się, a po instalacji wpisz powyższą komendę jeszcze raz.
6. **Uruchom analizę:**
   ```
   bash 2_URUCHOM_ANALIZE.command
   ```
   Odpowiadaj na pytania w Terminalu (wklejanie: **Cmd+V**, zatwierdzanie: **Enter**).
7. Pozostałe czynności (zawsze najpierw krok 4, jeśli otwierasz nowe okno Terminala):
   `bash 3_PRZELICZ_RAPORT.command`, `bash 4_ODSWIEZ_LISTE_FILMOW.command`,
   `bash 5_NOWE_DANE_KONKURSU.command`.
8. Wyniki: folder **`wyniki`** – `wyniki_konkursu.xlsx` otworzysz w Excelu albo w Numbers,
   `raport.html` w Safari.

W trakcie pracy program otwiera osobne okno przeglądarki (Chrome, jeśli jest zainstalowany, w przeciwnym
razie wbudowaną przeglądarkę Chromium). Nie zamykaj go i nie klikaj w nim, dopóki program pracuje.
Na MacBooku nie zamykaj klapy w trakcie analizy.

---

## Gdy coś pójdzie nie tak

| Sytuacja | Co zrobić |
|---|---|
| Program przerwał pracę / zamknęłaś okno / brak internetu | Uruchom ponownie `2_URUCHOM_ANALIZE.bat` – postęp zapisuje się po **każdym** filmie, program wznowi od miejsca przerwania. Filmy pobrane w całości są pomijane, a filmy z błędem pobierane ponownie. |
| TikTok pokazał weryfikację „nie jestem robotem” (CAPTCHA) | Program **nie omija** zabezpieczeń – zatrzyma się i zapyta. Możesz rozwiązać weryfikację samodzielnie w oknie przeglądarki i nacisnąć Enter, albo wpisać `k`, aby zakończyć. Wróć za kilka godzin – postęp zostanie zachowany. |
| TikTok prosi o zalogowanie | Zaloguj się w oknie przeglądarki i naciśnij Enter. |
| Film ma status NIEPELNY / BLAD | Uruchom analizę ponownie – program spróbuje jeszcze raz tylko te filmy. |
| Film ma status ROZBIEZNOSC | Lista komentarzy została przewinięta do końca, ale TikTok podaje wyższy licznik (zwykle przez komentarze usunięte, ukryte lub odfiltrowane przez TikToka). Możesz spróbować ponownie: `.venv\Scripts\python.exe konkurs.py --ponow-rozbieznosci` albo porównać liczby ręcznie w aplikacji. Raport sprawdza, czy brakujące komentarze **w ogóle mogą** zmienić wynik. |
| Chcesz zmienić daty lub inne ustawienia | Otwórz `ustawienia.json` w Notatniku albo uruchom `5_NOWE_DANE_KONKURSU.bat`. Potem `3_PRZELICZ_RAPORT.bat` (jeśli zmieniły się daty – `4_ODSWIEZ_LISTE_FILMOW.bat`). |
| Nowy, zupełnie inny konkurs | Usuń folder `dane` (oprócz `dane/przegladarka`, jeśli chcesz zachować logowanie) i uruchom `5_NOWE_DANE_KONKURSU.bat`. |

Jeśli TikTok trwale blokuje automatyczne przeglądanie, zgodny z zasadami sposób dokończenia analizy to:
otworzyć brakujące filmy ręcznie w aplikacji TikTok Studio (sekcja komentarzy), a liczbę komentarzy
konkretnych osób z tych filmów zweryfikować samodzielnie – raport pokazuje dokładnie, których filmów to dotyczy.

---

## Uczestnicy „do weryfikacji”

Jeśli ktoś skomentował film konkursowy, ale z treści nie wynika jednoznacznie zgłoszenie
(np. napisał tylko „❤️”), dostaje status **DO WERYFIKACJI** – nie jest automatycznie odrzucany i
**jest liczony w rankingu**, ale oznaczony. Po sprawdzeniu:
* osoby, które uznajesz za uczestników, wpisz do **`uczestnicy_dodaj.txt`** (np. `@anna_kowalska`),
* osoby do wykluczenia wpisz do **`uczestnicy_wyklucz.txt`**,
* kliknij **`3_PRZELICZ_RAPORT.bat`** – ranking przeliczy się bez ponownego pobierania z TikToka.

Słowa rozpoznające zgłoszenie (np. „biorę udział”, „zgłaszam”) są w `ustawienia.json`
(`slowa_kluczowe`) – możesz dopisać własne, zgodnie z regulaminem. Jeśli w regulaminie wystarczyło
skomentować film, wybierz w kreatorze opcję `1` (lub ustaw `"tryb_uczestnikow": "wszyscy"`).

---

## Jak liczona jest aktywność

* **Kryterium główne: łączna liczba komentarzy** uczestnika pod wszystkimi filmami z okresu konkursu
  (film konkursowy + pozostałe). Polubienia komentarzy nie mają znaczenia.
* Liczone są tylko osoby z listy uczestników (z filmu konkursowego). Komentarze innych osób są
  zapisane w arkuszu *Wszystkie komentarze* z adnotacją „nie liczony”. Twoje własne komentarze nie są liczone.
* Liczone są tylko komentarze opublikowane między datą rozpoczęcia a zakończenia
  (`licz_tylko_w_czasie_konkursu`); te spoza okresu trafiają do arkusza *Do weryfikacji*.
* Ten sam komentarz (ten sam identyfikator TikToka) jest liczony **tylko raz**, nawet jeśli pobrał się kilka razy.
* **Powtórzone/identyczne komentarze** tej samej osoby (np. kilka razy „❤️”) **są liczone**, ale
  pokazane osobno (kolumna *Powtórzone komentarze* i *Komentarze bez powtórzeń*), żebyś mogła ocenić je zgodnie z regulaminem.
* Osoba jest rozpoznawana po stałym identyfikatorze konta – jeśli w trakcie konkursu zmieniła @nazwę,
  jej komentarze nadal są liczone razem.
* Remis na granicy miejsc nagradzanych jest wyraźnie oznaczony. Kolejność pomocniczo ustala liczba
  skomentowanych filmów, ale raport prosi o sprawdzenie regulaminu.
* Raport **nie uzna wyniku za pewny**, jeśli któryś film nie został pobrany w całości – chyba że
  brakujących komentarzy jest za mało, by zmienić skład zwycięzców (raport to wylicza i opisuje).

## Jak program pobiera dane (dla ciekawych)

Program steruje zwykłą przeglądarką (Python + Playwright): otwiera Twój profil, przewija listę filmów,
otwiera każdy film, przewija komentarze do końca i klika „Wyświetl odpowiedzi”. Dane (identyfikator komentarza,
autor, treść, dokładna data) odczytuje z tych samych odpowiedzi, które strona TikToka wczytuje w trakcie
przewijania. Datę publikacji filmu odczytuje ze strony lub z identyfikatora filmu. Działa w normalnym tempie
z przerwami, nie omija logowania, CAPTCHA ani limitów.

**Ograniczenia:** TikTok często zmienia wygląd strony. Jeśli po aktualizacji TikToka program przestanie
przewijać lub rozwijać odpowiedzi, filmy zostaną oznaczone jako NIEPELNY (program nigdy nie uzna
niepełnych danych za kompletne).

## Dla zaawansowanych

```
python konkurs.py                       # analiza (wznawia od miejsca przerwania)
python konkurs.py --tylko-raport        # przelicz raport z zapisanych danych
python konkurs.py --odswiez-liste       # ponownie wyszukaj filmy na profilu
python konkurs.py --ponow-rozbieznosci  # pobierz ponownie filmy ze statusem ROZBIEZNOSC
python konkurs.py --ponow-wszystkie     # pobierz od nowa wszystkie filmy
python konkurs.py --nowa-konfiguracja   # podaj od nowa dane konkursu
python testy/test_analiza.py            # testy logiki rankingu
python testy/test_symulacja.py          # test całego programu na symulowanym TikToku (offline)
```

Dane robocze: `dane/filmy.json` (lista filmów i ich status), `dane/komentarze/<id_filmu>.json`
(surowe komentarze), `dane/przegladarka/` (profil przeglądarki z zapamiętanym logowaniem –
nie udostępniaj tego folderu nikomu).
