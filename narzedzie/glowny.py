"""Program główny: konfiguracja, przebieg analizy, zapisywanie postępu."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import raport
from .analiza import BLAD, KOMPLETNY, NIEPELNY, NIEPRZEANALIZOWANY, ROZBIEZNOSC, analizuj, norm_username

FOLDER = Path(__file__).resolve().parent.parent
USTAWIENIA = FOLDER / "ustawienia.json"
DANE = FOLDER / "dane"
KOMENTARZE = DANE / "komentarze"
PLIK_FILMOW = DANE / "filmy.json"
WYNIKI = FOLDER / "wyniki"

DOMYSLNE_SLOWA = [
    "biorę udział", "biore udzial", "wezmę udział", "wezme udzial", "chcę wziąć udział", "chce wziac udzial",
    "zgłaszam", "zglaszam", "zgłoszenie", "zgloszenie", "uczestniczę", "uczestnicze", "wchodzę", "wchodze",
    "zapisuję się", "zapisuje sie", "dołączam", "dolaczam", "biorę", "konkurs", "udział", "udzial",
    "chętnie", "chetnie", "ja też", "ja tez", "🙋",
]


def log(t: str) -> None:
    print(t, flush=True)


def pytaj(t: str) -> str:
    try:
        return input(t)
    except EOFError:
        return ""


def parsuj_date(tekst: str, tz: ZoneInfo, koniec: bool = False) -> datetime:
    t = tekst.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            d = datetime.strptime(t, fmt)
            if fmt in ("%Y-%m-%d", "%d.%m.%Y") and koniec:
                d = d + timedelta(days=1) - timedelta(seconds=1)
            return d.replace(tzinfo=tz)
        except ValueError:
            continue
    raise ValueError(f'Nie rozpoznano daty "{tekst}". Użyj formatu np. 2026-10-01 18:00 lub 01.10.2026 18:00')


def wlasciciel_z_linku(url: str) -> str:
    m = re.search(r"tiktok\.com/@([^/?#]+)", url or "")
    return m.group(1) if m else ""


def czytaj_liste(plik: Path) -> list[str]:
    if not plik.exists():
        return []
    return [l.strip() for l in plik.read_text(encoding="utf-8").splitlines() if l.strip() and not l.strip().startswith("#")]


SKROCONY = re.compile(r"(vm|vt)\.tiktok\.com/|tiktok\.com/t/")


def normalizuj_link(u: str) -> str:
    u = (u or "").strip()
    if u and not u.startswith("http"):
        u = "https://" + u
    return u


def kreator() -> dict:
    log("\n=== Pierwsze uruchomienie - podaj dane konkursu ===\n")
    profil = ""
    while not wlasciciel_z_linku(profil):
        profil = pytaj("1. Link do Twojego profilu TikTok (np. https://www.tiktok.com/@nazwa): ").strip()
    from .tiktok import id_z_linku
    film = ""
    while not (id_z_linku(film) or SKROCONY.search(film)):
        film = pytaj("2. Link do filmu konkursowego (pełny z /video/ albo skrócony vm.tiktok.com/...): ").strip()
        if not (id_z_linku(film) or SKROCONY.search(film)):
            log("   To nie wygląda na link do filmu TikTok. Skopiuj go przyciskiem 'Udostępnij -> Kopiuj link'.")
    tz = ZoneInfo("Europe/Warsaw")
    while True:
        s = pytaj("3. Data i godzina ROZPOCZĘCIA konkursu (np. 2026-10-01 18:00): ")
        try:
            parsuj_date(s, tz)
            break
        except ValueError as e:
            log("   " + str(e))
    while True:
        k = pytaj("4. Data i godzina ZAKOŃCZENIA konkursu (np. 2026-10-15 23:59): ")
        try:
            if parsuj_date(k, tz, True) > parsuj_date(s, tz):
                break
            log("   Koniec musi być po początku.")
        except ValueError as e:
            log("   " + str(e))
    log("\n5. Jak rozpoznać uczestników pod filmem konkursowym?\n"
        "   [1] Każda osoba, która skomentowała film konkursowy, bierze udział\n"
        "   [2] Tylko osoby, które napisały zgłoszenie (np. 'biorę udział'); pozostali -> 'do weryfikacji'")
    tryb = "wszyscy" if pytaj("   Wybierz 1 lub 2 [2]: ").strip() == "1" else "slowa_kluczowe"
    odp = pytaj("6. Czy odpowiedzi na komentarze (w wątkach) też liczą się jako komentarze? [T/n]: ").strip().lower()
    cfg = {
        "profil": normalizuj_link(profil.split("?")[0]),
        "film_konkursowy": normalizuj_link(film if SKROCONY.search(film) else film.split("?")[0]),
        "start": s.strip(),
        "koniec": k.strip(),
        "strefa_czasowa": "Europe/Warsaw",
        "tryb_uczestnikow": tryb,
        "slowa_kluczowe": DOMYSLNE_SLOWA,
        "licz_odpowiedzi": odp not in ("n", "nie"),
        "licz_tylko_w_czasie_konkursu": True,
        "do_weryfikacji_w_rankingu": True,
        "liczba_zwyciezcow": 2,
        "max_minut_na_film": 20,
    }
    USTAWIENIA.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    zasady = FOLDER / "zasady_konkursu.txt"
    log(f"\nZapisano ustawienia w pliku: {USTAWIENIA.name} (możesz je później zmienić w Notatniku).")
    if not czytaj_liste(zasady):
        log(f"Wklej treść zasad konkursu do pliku {zasady.name} (zostaną dołączone do raportu).")
    return cfg


def wczytaj_ustawienia() -> dict:
    cfg = json.loads(USTAWIENIA.read_text(encoding="utf-8"))
    from .tiktok import id_z_linku
    cfg["profil"] = normalizuj_link(cfg["profil"])
    cfg["film_konkursowy"] = normalizuj_link(cfg["film_konkursowy"])
    cfg["film_konkursowy_id"] = id_z_linku(cfg["film_konkursowy"])
    cfg["wlasciciel_profilu"] = wlasciciel_z_linku(cfg["profil"])
    if not cfg["film_konkursowy_id"] and not SKROCONY.search(cfg["film_konkursowy"]):
        raise SystemExit("W ustawieniach jest nieprawidłowy link do filmu konkursowego.")
    return cfg


def rozwin_link_konkursowy(page, cfg) -> None:
    """Skrócony link (vm.tiktok.com) zamieniamy na pełny, otwierając go w przeglądarce."""
    from .tiktok import id_z_linku, pauza
    if cfg["film_konkursowy_id"]:
        return
    log(f"\nRozwijam skrócony link do filmu konkursowego: {cfg['film_konkursowy']}")
    page.goto(cfg["film_konkursowy"], wait_until="domcontentloaded", timeout=60000)
    pauza(3, 5)
    pelny = page.url
    if not id_z_linku(pelny):
        try:
            pelny = page.evaluate("() => (document.querySelector('link[rel=canonical]') || {}).href || ''")
        except Exception:
            pass
    vid = id_z_linku(pelny)
    if not vid:
        raise SystemExit("Nie udało się odczytać pełnego linku do filmu konkursowego. Otwórz film w przeglądarce "
                         "na komputerze, skopiuj adres z paska (z /video/) i wpisz go w ustawienia.json.")
    if "www.tiktok.com/@" in pelny:
        cfg["film_konkursowy"] = pelny.split("?")[0]
    else:  # np. wersja mobilna - budujemy standardowy adres
        cfg["film_konkursowy"] = f"https://www.tiktok.com/@{cfg['wlasciciel_profilu']}/video/{vid}"
    cfg["film_konkursowy_id"] = vid
    zapis = json.loads(USTAWIENIA.read_text(encoding="utf-8"))
    zapis["film_konkursowy"] = cfg["film_konkursowy"]
    USTAWIENIA.write_text(json.dumps(zapis, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Pełny link: {cfg['film_konkursowy']} (zapisano w ustawieniach)")


def wczytaj_filmy() -> list[dict]:
    return json.loads(PLIK_FILMOW.read_text(encoding="utf-8")) if PLIK_FILMOW.exists() else []


def zapisz_filmy(filmy: list[dict]) -> None:
    DANE.mkdir(parents=True, exist_ok=True)
    tmp = PLIK_FILMOW.with_suffix(".tmp")
    tmp.write_text(json.dumps(filmy, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PLIK_FILMOW)


def wczytaj_komentarze() -> list[dict]:
    wynik = []
    for p in sorted(KOMENTARZE.glob("*.json")):
        wynik += json.loads(p.read_text(encoding="utf-8")).get("komentarze", [])
    return wynik


def ustal_filmy(page, cfg, start, koniec, tz, bez_pytan: bool) -> list[dict]:
    from .tiktok import data_z_id, id_z_linku, lista_filmow
    log("\n=== ETAP 2: Szukam filmów z okresu konkursu na profilu ===")
    znalezione, pewna, uwaga = lista_filmow(page, cfg["profil"], start, koniec, pytaj, log)
    po_id = {f["video_id"]: f for f in znalezione}
    # film konkursowy zawsze na liście
    kid = cfg["film_konkursowy_id"]
    if kid not in po_id:
        po_id[kid] = {"video_id": kid, "url": cfg["film_konkursowy"], "create_time": data_z_id(kid), "opis": ""}
    # filmy dopisane ręcznie
    for link in czytaj_liste(FOLDER / "dodatkowe_filmy.txt"):
        vid = id_z_linku(link)
        if vid and vid not in po_id:
            po_id[vid] = {"video_id": vid, "url": link.split("?")[0], "create_time": data_z_id(vid), "opis": "",
                          "dodany_recznie": True}
    filmy = sorted(po_id.values(), key=lambda f: f["create_time"])
    for f in filmy:
        if not f.get("url"):
            f["url"] = f"https://www.tiktok.com/@{cfg['wlasciciel_profilu']}/video/{f['video_id']}"
        f.setdefault("status", NIEPRZEANALIZOWANY)
        f.setdefault("pobrane", 0)

    log(f"\nFilmy do przeanalizowania ({len(filmy)}):")
    for i, f in enumerate(filmy, 1):
        d = datetime.fromtimestamp(f["create_time"], tz).strftime("%Y-%m-%d %H:%M")
        dop = " [KONKURSOWY]" if f["video_id"] == kid else (" [dodany ręcznie]" if f.get("dodany_recznie") else "")
        log(f"  {i:>2}. {d}  {f['url']}{dop}")
    if not pewna:
        log("\n⚠️  " + uwaga)
    if not bez_pytan:
        o = pytaj("\nCzy to są WSZYSTKIE filmy z okresu konkursu? [T = tak, kontynuuj / N = nie, przerwij]: ").strip().lower()
        if o in ("n", "nie"):
            raise SystemExit("\nDopisz brakujące linki (jeden w linii) do pliku dodatkowe_filmy.txt i uruchom program "
                             "ponownie z opcją odświeżenia listy (plik 'Odswiez liste filmow').")
    elif not pewna:
        log("Kontynuuję mimo możliwej niepełnej listy - zostanie to zaznaczone w raporcie.")
    zapisz_filmy(filmy)
    return filmy


def pobieranie(cfg, start, koniec, tz, args) -> None:
    from .tiktok import Przerwano, logowanie, pobierz_komentarze, uruchom_przegladarke
    filmy = wczytaj_filmy()
    pw, ctx = uruchom_przegladarke(DANE / "przegladarka")
    try:
        page = logowanie(ctx, pytaj)
        rozwin_link_konkursowy(page, cfg)
        if not filmy or args.odswiez_liste:
            stare = {f["video_id"]: f for f in filmy}
            filmy = ustal_filmy(page, cfg, start, koniec, tz, args.bez_pytan)
            for f in filmy:  # zachowaj postęp już pobranych filmów
                if f["video_id"] in stare:
                    f.update({k: v for k, v in stare[f["video_id"]].items() if k in
                              ("status", "pobrane", "zgloszona_liczba", "blad", "analizowano")})
            zapisz_filmy(filmy)
        else:
            log(f"\nWznawiam: lista {len(filmy)} filmów z poprzedniego uruchomienia.")

        kid = cfg["film_konkursowy_id"]
        filmy.sort(key=lambda f: (f["video_id"] != kid, f["create_time"]))  # konkursowy najpierw (Etap 1)
        do_zrobienia = [f for f in filmy if args.ponow_wszystkie or f.get("status") not in
                        ((KOMPLETNY,) if args.ponow_rozbieznosci else (KOMPLETNY, ROZBIEZNOSC))]
        log(f"\n=== ETAP 1 i 3: Pobieranie komentarzy - {len(do_zrobienia)} z {len(filmy)} filmów do zrobienia ===")
        KOMENTARZE.mkdir(parents=True, exist_ok=True)
        for i, f in enumerate(do_zrobienia, 1):
            log(f"\n[{i}/{len(do_zrobienia)}] {f['url']}" + ("  (FILM KONKURSOWY)" if f["video_id"] == kid else ""))
            try:
                w = pobierz_komentarze(page, f, pytaj, log, cfg.get("max_minut_na_film", 20))
            except Przerwano:
                log("\nPrzerwano na Twoje życzenie. Postęp zapisany - uruchom program ponownie, aby kontynuować.")
                break
            stary_plik = KOMENTARZE / f"{f['video_id']}.json"
            # nie nadpisuj lepszych danych gorszymi (np. przy blokadzie przy ponownej próbie)
            if stary_plik.exists() and w["status"] in (BLAD, NIEPELNY):
                stare = json.loads(stary_plik.read_text(encoding="utf-8")).get("komentarze", [])
                if len(stare) > len(w["komentarze"]):
                    scal = {c["cid"]: c for c in stare}
                    scal.update({c["cid"]: c for c in w["komentarze"]})
                    w["komentarze"] = list(scal.values())
                    w["pobrane"] = len(w["komentarze"])
            stary_plik.write_text(json.dumps({"video_id": f["video_id"], "url": f["url"], "status": w["status"],
                                              "komentarze": w["komentarze"]}, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
            f.update(status=w["status"], pobrane=w["pobrane"], zgloszona_liczba=w["zgloszona_liczba"],
                     blad=w["blad"], analizowano=datetime.now(tz).strftime("%Y-%m-%d %H:%M"))
            zapisz_filmy(filmy)  # zapis postępu po każdym filmie
            log(f"   -> {w['status']}: pobrano {w['pobrane']} komentarzy (TikTok podaje: "
                f"{w['zgloszona_liczba'] if w['zgloszona_liczba'] is not None else '?'})" +
                (f"\n   uwagi: {w['blad']}" if w["blad"] else ""))
    finally:
        try:
            ctx.close()
            pw.stop()
        except Exception:
            pass


PLIKI_CSV = FOLDER / "pliki_csv"


def dane_z_plikow_csv(cfg, start, koniec, tz) -> tuple[list[dict], list[dict]]:
    """Filmy i komentarze z plików CSV (eksporter w przeglądarce). Filmy, których nie ma w CSV,
    bierzemy z wcześniejszego automatycznego pobierania (jeśli było pobrane w całości)."""
    from .import_csv import wczytaj_plik
    from .tiktok import data_z_id
    pliki = sorted(PLIKI_CSV.glob("*.csv")) if PLIKI_CSV.exists() else []
    if not pliki:
        raise SystemExit(f"Brak plików CSV w folderze {PLIKI_CSV}. Wrzuć tam pliki wyeksportowane z TikToka.")
    kid = cfg["film_konkursowy_id"]
    wl = cfg["wlasciciel_profilu"]
    filmy: dict[str, dict] = {}
    kom: list[dict] = []
    for p in pliki:
        try:
            vid, k, info = wczytaj_plik(p, tz)
        except ValueError as e:
            log(f"! Pominięto plik {p.name}: {e}")
            continue
        if vid in filmy:  # kilka plików tego samego filmu - łączymy (duplikaty usuwa analiza)
            f = filmy[vid]
            f["pobrane"] += info["pobrane"]
            f["blad"] += " | " + info["blad"]
        else:
            filmy[vid] = {"video_id": vid, "url": f"https://www.tiktok.com/@{wl}/video/{vid}",
                          "create_time": data_z_id(vid), "opis": "", **info,
                          "analizowano": "plik CSV"}
        kom += k
        log(f"Wczytano {p.name}: {info['pobrane']} komentarzy ({info['status']})")
    # Filmy z okresu konkursu znane z automatycznego wyszukiwania, a bez pliku CSV
    zapis = {f["video_id"]: f for f in wczytaj_filmy()}
    poprzednie = {c["cid"]: c for c in wczytaj_komentarze()}
    for vid, f in zapis.items():
        w_oknie = start.timestamp() <= (f.get("create_time") or 0) <= koniec.timestamp()
        if vid in filmy or not (w_oknie or vid == kid):
            continue
        if f.get("status") == KOMPLETNY:
            filmy[vid] = dict(f, analizowano=f"{f.get('analizowano', '')} (przeglądarka)")
            kom += [c for c in poprzednie.values() if str(c.get("video_id")) == vid]
        else:
            filmy[vid] = dict(f, status=NIEPRZEANALIZOWANY, pobrane=0,
                              blad="Brak pliku CSV dla tego filmu - wyeksportuj jego komentarze")
    if kid not in filmy:
        log("! UWAGA: brak pliku CSV z filmu konkursowego - nie da się ustalić listy uczestników.")
        filmy[kid] = {"video_id": kid, "url": cfg["film_konkursowy"], "create_time": data_z_id(kid),
                      "status": NIEPRZEANALIZOWANY, "pobrane": 0, "blad": "Brak pliku CSV"}
    poza = [f for f in filmy.values() if f["video_id"] != kid and
            not start.timestamp() <= f["create_time"] <= koniec.timestamp()]
    for f in poza:
        log(f"! Plik z filmu {f['url']} - film opublikowany poza okresem konkursu "
            f"({datetime.fromtimestamp(f['create_time'], tz):%Y-%m-%d %H:%M}); jego komentarze i tak są analizowane.")
    return sorted(filmy.values(), key=lambda f: f["create_time"]), kom


def generuj_raport(cfg, start, koniec, tz, z_plikow: bool = False) -> None:
    if z_plikow:
        filmy, kom = dane_z_plikow_csv(cfg, start, koniec, tz)
    else:
        filmy = wczytaj_filmy()
        if not filmy:
            raise SystemExit("Brak danych - najpierw uruchom analizę (pobieranie komentarzy).")
        ids = {str(f["video_id"]) for f in filmy}
        kom = [c for c in wczytaj_komentarze() if str(c.get("video_id")) in ids]  # tylko filmy z aktualnej listy
    w = analizuj(filmy, kom, cfg, start, koniec,
                 czytaj_liste(FOLDER / "uczestnicy_dodaj.txt"), czytaj_liste(FOLDER / "uczestnicy_wyklucz.txt"))
    WYNIKI.mkdir(exist_ok=True)
    pods = raport.tekst_podsumowania(w, cfg, tz, start, koniec)
    zasady = FOLDER / "zasady_konkursu.txt"
    if czytaj_liste(zasady):
        pods += ["", "Zasady konkursu (z pliku zasady_konkursu.txt):", "\n".join(czytaj_liste(zasady))]
    xlsx = WYNIKI / "wyniki_konkursu.xlsx"
    try:
        raport.zapisz_excel(xlsx, w, cfg, tz, pods)
    except PermissionError:
        xlsx = WYNIKI / f"wyniki_konkursu_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        raport.zapisz_excel(xlsx, w, cfg, tz, pods)
    raport.zapisz_csv(WYNIKI / "csv", w, cfg, tz)
    raport.zapisz_html(WYNIKI / "raport.html", w, cfg, tz, pods)

    log("\n" + "=" * 78)
    komplet = sum(1 for f in filmy if f.get("status") == KOMPLETNY)
    log(f"Przeanalizowane filmy: {len(filmy)} | w całości: {komplet} | z problemami: {len(filmy) - komplet}")
    for f in filmy:
        if f.get("status") != KOMPLETNY:
            log(f"   ! {f.get('status')}: {f['url']} (pobrano {f.get('pobrane', 0)}"
                f"/{f.get('zgloszona_liczba') or '?'}) {f.get('blad', '')}")
    log(f"Pobrane komentarze: {len(w.komentarze)} | policzone do rankingu: {sum(1 for c in w.komentarze if c.get('liczony'))}"
        f" | uczestnicy: {len(w.uczestnicy)}")
    log("\nRANKING TOP 20")
    log(f"{'Miejsce':<8}{'Username':<32}{'Wszystkie':>10}{'Filmy':>8}{'Powtórz.':>10}  Status")
    for r in w.ranking[:20]:
        log(f"{str(r['miejsce']) + ('=' if r['remis'] else ''):<8}{'@' + r['username']:<32}{r['wszystkie']:>10}"
            f"{r['filmy']:>8}{r['powtorzone']:>10}  {r['status']}")
    log("")
    for i, r in enumerate(w.zwyciezcy, 1):
        log(f"ZWYCIĘZCA NR {i}: @{r['username']} - {r['wszystkie']} komentarzy pod {r['filmy']} filmami")
    log("\n" + w.werdykt)
    log(f"\nPliki wyników:\n  {xlsx}\n  {WYNIKI / 'raport.html'}\n  {WYNIKI / 'csv'}")
    log("=" * 78)


def main(argv=None) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Analiza aktywności w konkursie TikTok")
    ap.add_argument("--z-plikow", action="store_true",
                    help="policz ranking z plików CSV w folderze pliki_csv (bez przeglądarki)")
    ap.add_argument("--tylko-raport", action="store_true", help="tylko przelicz ranking z zapisanych danych")
    ap.add_argument("--odswiez-liste", action="store_true", help="ponownie pobierz listę filmów z profilu")
    ap.add_argument("--ponow-rozbieznosci", action="store_true", help="ponów też filmy ze statusem ROZBIEZNOSC")
    ap.add_argument("--ponow-wszystkie", action="store_true", help="pobierz od nowa komentarze ze wszystkich filmów")
    ap.add_argument("--bez-pytan", action="store_true", help="nie pytaj o potwierdzenie listy filmów")
    ap.add_argument("--nowa-konfiguracja", action="store_true", help="podaj od nowa dane konkursu")
    args = ap.parse_args(argv)

    if not USTAWIENIA.exists() or args.nowa_konfiguracja:
        kreator()
    cfg = wczytaj_ustawienia()
    tz = ZoneInfo(cfg.get("strefa_czasowa", "Europe/Warsaw"))
    start = parsuj_date(cfg["start"], tz)
    koniec = parsuj_date(cfg["koniec"], tz, True)
    log(f"Konkurs: {start:%Y-%m-%d %H:%M} - {koniec:%Y-%m-%d %H:%M} | profil @{cfg['wlasciciel_profilu']}")

    if not args.tylko_raport and not args.z_plikow:
        pobieranie(cfg, start, koniec, tz, args)
    elif not cfg["film_konkursowy_id"]:
        raise SystemExit("W ustawieniach jest skrócony link do filmu konkursowego. Wpisz w ustawienia.json pełny "
                         "link (z /video/ i numerem) albo uruchom raz 2_URUCHOM_ANALIZE.")
    generuj_raport(cfg, start, koniec, tz, z_plikow=args.z_plikow)


if __name__ == "__main__":
    main()
