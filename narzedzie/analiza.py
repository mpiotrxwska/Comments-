"""Analiza danych konkursu: uczestnicy, zliczanie aktywności, ranking, zwycięzcy.

Moduł nie korzysta z przeglądarki - pracuje wyłącznie na danych zapisanych
przez scraper w folderze ``dane/``. Dzięki temu raport można odtworzyć
w dowolnym momencie (``--tylko-raport``) bez ponownego pobierania.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

# Statusy filmów (ustawiane przez scraper)
KOMPLETNY = "KOMPLETNY"
ROZBIEZNOSC = "ROZBIEZNOSC"  # lista zakończona, ale TikTok podaje więcej komentarzy niż udało się pobrać
NIEPELNY = "NIEPELNY"
BLAD = "BLAD"
NIEPRZEANALIZOWANY = "NIEPRZEANALIZOWANY"

OPIS_STATUSU = {
    KOMPLETNY: "Pobrano w całości",
    ROZBIEZNOSC: "Lista komentarzy zakończona, ale TikTok pokazuje większą liczbę komentarzy "
                 "(mogą to być komentarze usunięte/ukryte/filtrowane) - do sprawdzenia",
    NIEPELNY: "Nie udało się załadować wszystkich komentarzy",
    BLAD: "Błąd lub blokada - film nie został przeanalizowany w całości",
    NIEPRZEANALIZOWANY: "Film jeszcze nie był analizowany",
}

# Statusy uczestników
POTWIERDZONY = "POTWIERDZONY"
DO_WERYFIKACJI = "DO WERYFIKACJI"
DODANY_RECZNIE = "DODANY RĘCZNIE"


def norm_username(u: str) -> str:
    return (u or "").strip().lstrip("@").lower()


def norm_text(t: str) -> str:
    """Normalizacja do wykrywania identycznych komentarzy
    (wielkość liter, odstępy, interpunkcja na końcu)."""
    t = unicodedata.normalize("NFC", t or "").lower().strip()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[\s.,!?;:…]+$", "", t)
    return t


def bez_polskich(t: str) -> str:
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return t.replace("ł", "l").replace("Ł", "L")


def ma_slowo_kluczowe(text: str, slowa: Iterable[str]) -> str | None:
    """Zwraca pierwsze dopasowane słowo kluczowe (bez względu na wielkość liter
    i polskie znaki) albo None."""
    t = bez_polskich((text or "").lower())
    for s in slowa:
        s2 = bez_polskich(s.lower()).strip()
        if s2 and s2 in t:
            return s
    return None


@dataclass
class Uczestnik:
    klucz: str  # stabilny identyfikator konta (uid TikToka albo username)
    username: str
    nick: str = ""
    status: str = DO_WERYFIKACJI
    powod: str = ""
    komentarze_zgloszeniowe: list = field(default_factory=list)


def klucz_autora(c: dict) -> str:
    return str(c.get("uid") or "") or "u:" + norm_username(c.get("username", ""))


def deduplikuj(komentarze: Iterable[dict]) -> list[dict]:
    """Ten sam komentarz (ten sam identyfikator) liczony jest tylko raz."""
    wynik, widziane = [], set()
    for c in komentarze:
        cid = str(c.get("cid") or "")
        klucz = cid or (c.get("video_id"), klucz_autora(c), c.get("create_time"), c.get("text"))
        if klucz in widziane:
            continue
        widziane.add(klucz)
        wynik.append(c)
    return wynik


def identyfikuj_uczestnikow(komentarze_konkursowe: list[dict], cfg: dict,
                            dodaj: list[str], wyklucz: list[str]) -> dict[str, Uczestnik]:
    """Etap 1: lista unikalnych uczestników na podstawie komentarzy pod filmem konkursowym."""
    wlasciciel = norm_username(cfg.get("wlasciciel_profilu", ""))
    tryb = cfg.get("tryb_uczestnikow", "slowa_kluczowe")
    slowa = cfg.get("slowa_kluczowe", [])
    wyklucz_n = {norm_username(u) for u in wyklucz}
    uczestnicy: dict[str, Uczestnik] = {}

    for c in sorted(komentarze_konkursowe, key=lambda x: x.get("create_time") or 0):
        u = norm_username(c.get("username", ""))
        if not u or u == wlasciciel or u in wyklucz_n:
            continue
        k = klucz_autora(c)
        ucz = uczestnicy.get(k)
        if ucz is None:
            ucz = Uczestnik(klucz=k, username=c.get("username", ""), nick=c.get("nickname", ""))
            uczestnicy[k] = ucz
        else:
            ucz.username = c.get("username", "") or ucz.username  # najnowsza nazwa
        if tryb == "wszyscy":
            ucz.status = POTWIERDZONY
            ucz.powod = "Skomentował(a) film konkursowy (zasada: każdy komentarz = zgłoszenie)"
            ucz.komentarze_zgloszeniowe.append(c)
            continue
        slowo = ma_slowo_kluczowe(c.get("text", ""), slowa)
        if slowo:
            if ucz.status != POTWIERDZONY:
                ucz.status = POTWIERDZONY
                ucz.powod = f'Zgłoszenie rozpoznane po słowie/zwrocie: "{slowo}"'
            ucz.komentarze_zgloszeniowe.append(c)
        elif ucz.status != POTWIERDZONY:
            ucz.status = DO_WERYFIKACJI
            ucz.powod = ("Skomentował(a) film konkursowy, ale w treści nie rozpoznano "
                         "jednoznacznego zgłoszenia - sprawdź ręcznie")

    # Osoby dodane ręcznie (plik uczestnicy_dodaj.txt)
    po_nazwie = {norm_username(u.username): u for u in uczestnicy.values()}
    for u in dodaj:
        n = norm_username(u)
        if not n or n in wyklucz_n:
            continue
        if n in po_nazwie:
            po_nazwie[n].status = POTWIERDZONY
            po_nazwie[n].powod = "Potwierdzony ręcznie (plik uczestnicy_dodaj.txt)"
        else:
            k = "u:" + n
            uczestnicy[k] = Uczestnik(klucz=k, username=u.strip().lstrip("@"), status=DODANY_RECZNIE,
                                      powod="Dodany ręcznie (plik uczestnicy_dodaj.txt)")
    return uczestnicy


@dataclass
class Wynik:
    uczestnicy: dict
    filmy: list
    komentarze: list  # wszystkie komentarze (zdeduplikowane) z adnotacjami
    ranking: list
    zwyciezcy: list
    do_weryfikacji: list
    ostrzezenia: list
    wiarygodny: bool
    werdykt: str


def _w_oknie(c: dict, start: datetime, koniec: datetime) -> bool | None:
    ts = c.get("create_time") or 0
    if not ts:
        return None
    return start.timestamp() <= ts <= koniec.timestamp()


def analizuj(filmy: list[dict], komentarze: list[dict], cfg: dict, start: datetime, koniec: datetime,
             dodaj: list[str] | None = None, wyklucz: list[str] | None = None) -> Wynik:
    dodaj, wyklucz = dodaj or [], wyklucz or []
    ostrzezenia: list[str] = []
    konkurs_id = str(cfg["film_konkursowy_id"])
    licz_odp = cfg.get("licz_odpowiedzi", True)
    tylko_okno = cfg.get("licz_tylko_w_czasie_konkursu", True)
    weryf_w_rankingu = cfg.get("do_weryfikacji_w_rankingu", True)
    n_zw = int(cfg.get("liczba_zwyciezcow", 2))
    wlasciciel = norm_username(cfg.get("wlasciciel_profilu", ""))

    komentarze = deduplikuj(komentarze)
    filmy_po_id = {str(f["video_id"]): f for f in filmy}

    # --- Etap 1: uczestnicy
    konkursowe = [c for c in komentarze if str(c.get("video_id")) == konkurs_id]
    if not licz_odp:
        konkursowe_do_zgl = [c for c in konkursowe if str(c.get("parent_cid") or "0") == "0"]
    else:
        konkursowe_do_zgl = konkursowe
    uczestnicy = identyfikuj_uczestnikow(konkursowe_do_zgl, cfg, dodaj, wyklucz)
    po_nazwie = {norm_username(u.username): u for u in uczestnicy.values()}

    def znajdz_uczestnika(c):
        u = uczestnicy.get(klucz_autora(c))
        if u is None:
            u = po_nazwie.get(norm_username(c.get("username", "")))
        return u

    # --- Etap 3/4: przypisanie komentarzy i liczenie
    do_weryfikacji: list[dict] = []
    staty: dict[str, dict] = {}
    widziane_teksty: dict[tuple, int] = {}

    for c in sorted(komentarze, key=lambda x: (x.get("create_time") or 0, str(x.get("cid")))):
        vid = str(c.get("video_id"))
        film = filmy_po_id.get(vid, {})
        c["film_url"] = film.get("url", "")
        c["film_konkursowy"] = vid == konkurs_id
        c["odpowiedz"] = str(c.get("parent_cid") or "0") != "0"
        u = znajdz_uczestnika(c)
        c["uczestnik"] = bool(u)
        c["status_uczestnika"] = u.status if u else ""
        okno = _w_oknie(c, start, koniec)
        c["w_czasie_konkursu"] = {True: "TAK", False: "NIE", None: "BRAK DATY"}[okno]
        powody = []
        liczony = bool(u)
        if not u:
            c["liczony"] = False
            c["powod_nieliczenia"] = ("Autor jest właścicielem profilu" if norm_username(c.get("username", "")) == wlasciciel
                                      else "Autor nie jest na liście uczestników")
            c["powtorzony"] = False
            continue
        if c["odpowiedz"] and not licz_odp:
            liczony = False
            c["powod_nieliczenia"] = "Odpowiedzi nie są liczone (ustawienie)"
        if tylko_okno and okno is False:
            liczony = False
            c["powod_nieliczenia"] = "Komentarz poza okresem konkursu"
            powody.append("Komentarz uczestnika poza okresem konkursu - nie liczony")
        if okno is None:
            powody.append("Brak daty komentarza - nie można sprawdzić, czy był w okresie konkursu")
        if u.status == DO_WERYFIKACJI and not weryf_w_rankingu:
            liczony = False
            c["powod_nieliczenia"] = "Uczestnik do weryfikacji (wyłączony z rankingu w ustawieniach)"
        if u.status == DO_WERYFIKACJI and c["film_konkursowy"]:
            powody.append("Niejednoznaczne zgłoszenie do konkursu")
        c["liczony"] = liczony
        if liczony:
            c.setdefault("powod_nieliczenia", "")
        klucz_t = (u.klucz, norm_text(c.get("text", "")))
        c["powtorzony"] = False
        if liczony:
            if widziane_teksty.get(klucz_t):
                c["powtorzony"] = True
                powody.append("Powtórzony/identyczny komentarz tego samego uczestnika")
            widziane_teksty[klucz_t] = widziane_teksty.get(klucz_t, 0) + 1
            s = staty.setdefault(u.klucz, {"wszystkie": 0, "filmy": set(), "konkursowy": 0, "inne": 0,
                                           "powtorzone": 0, "odpowiedzi": 0, "pierwszy": None, "ostatni": None})
            s["wszystkie"] += 1
            s["filmy"].add(vid)
            s["konkursowy" if c["film_konkursowy"] else "inne"] += 1
            s["powtorzone"] += int(c["powtorzony"])
            s["odpowiedzi"] += int(c["odpowiedz"])
            ts = c.get("create_time") or 0
            if ts:
                s["pierwszy"] = ts if s["pierwszy"] is None else min(s["pierwszy"], ts)
                s["ostatni"] = ts if s["ostatni"] is None else max(s["ostatni"], ts)
        if powody:
            d = dict(c)
            d["powod_weryfikacji"] = "; ".join(powody)
            do_weryfikacji.append(d)

    # Uczestnicy bez żadnych liczonych komentarzy też trafiają do rankingu (z zerem)
    ranking = []
    for u in uczestnicy.values():
        if u.status == DO_WERYFIKACJI and not weryf_w_rankingu:
            continue
        s = staty.get(u.klucz, {"wszystkie": 0, "filmy": set(), "konkursowy": 0, "inne": 0,
                                "powtorzone": 0, "odpowiedzi": 0, "pierwszy": None, "ostatni": None})
        ranking.append({
            "klucz": u.klucz, "username": u.username, "nick": u.nick, "status": u.status,
            "wszystkie": s["wszystkie"], "filmy": len(s["filmy"]), "lista_filmow": sorted(s["filmy"]),
            "konkursowy": s["konkursowy"], "inne": s["inne"], "powtorzone": s["powtorzone"],
            "bez_powtorzen": s["wszystkie"] - s["powtorzone"], "odpowiedzi": s["odpowiedzi"],
            "pierwszy": s["pierwszy"], "ostatni": s["ostatni"],
        })
    # Kryterium główne: łączna liczba komentarzy; pomocnicze: liczba filmów, potem nazwa (tylko dla stabilnej kolejności)
    ranking.sort(key=lambda r: (-r["wszystkie"], -r["filmy"], norm_username(r["username"])))
    for r in ranking:
        r["miejsce"] = 1 + sum(1 for x in ranking if x["wszystkie"] > r["wszystkie"])
        r["remis"] = sum(1 for x in ranking if x["wszystkie"] == r["wszystkie"]) > 1

    # --- Kompletność danych
    niekompletne = [f for f in filmy if f.get("status") != KOMPLETNY]
    for f in niekompletne:
        ostrzezenia.append(f'Film {f.get("url")} - status {f.get("status")}: '
                           f'{OPIS_STATUSU.get(f.get("status"), "")} '
                           f'(pobrano {f.get("pobrane", 0)}, TikTok podaje {f.get("zgloszona_liczba") or "?"}).')

    zwyciezcy = ranking[:n_zw]
    wiarygodny = True
    werdykt_czesci = []
    if len(ranking) < n_zw or any(r["wszystkie"] == 0 for r in zwyciezcy):
        wiarygodny = False
        werdykt_czesci.append("Za mało uczestników z policzonymi komentarzami, aby wyłonić zwycięzców.")

    # Remis na granicy miejsc nagradzanych
    if len(ranking) > n_zw and ranking[n_zw - 1]["wszystkie"] == ranking[n_zw]["wszystkie"]:
        wiarygodny = False
        remisowi = [r["username"] for r in ranking if r["wszystkie"] == ranking[n_zw - 1]["wszystkie"]]
        werdykt_czesci.append(
            f"REMIS na granicy miejsc nagradzanych ({ranking[n_zw - 1]['wszystkie']} komentarzy): "
            + ", ".join("@" + x for x in remisowi)
            + ". Kolejność ustalono kryterium pomocniczym (liczba skomentowanych filmów) - "
              "sprawdź, czy regulamin przewiduje inne rozstrzygnięcie.")

    # Czy brakujące komentarze mogłyby zmienić wynik?
    if niekompletne:
        brak = 0
        nieznany = False
        for f in niekompletne:
            zgl, pob = f.get("zgloszona_liczba"), f.get("pobrane", 0)
            if f.get("status") in (BLAD, NIEPRZEANALIZOWANY) and not zgl:
                nieznany = True
            elif zgl:
                brak += max(0, int(zgl) - int(pob or 0))
            else:
                nieznany = True
        if nieznany:
            wiarygodny = False
            werdykt_czesci.append("Niektóre filmy nie zostały przeanalizowane, a liczba ich komentarzy jest nieznana - "
                                  "wynik może się zmienić. Dokończ analizę tych filmów.")
        elif len(ranking) > n_zw and zwyciezcy:
            przewaga = ranking[n_zw - 1]["wszystkie"] - ranking[n_zw]["wszystkie"]
            if brak >= przewaga:
                wiarygodny = False
                werdykt_czesci.append(
                    f"Brakuje maksymalnie {brak} komentarzy z niekompletnych filmów, a przewaga miejsca {n_zw} "
                    f"nad miejscem {n_zw + 1} wynosi tylko {przewaga}. Brakujące komentarze MOGĄ zmienić wynik.")
            else:
                werdykt_czesci.append(
                    f"Uwaga: części komentarzy nie pobrano (maks. {brak}), ale przewaga miejsca {n_zw} nad "
                    f"miejscem {n_zw + 1} wynosi {przewaga}, więc nawet w najgorszym przypadku skład "
                    f"zwycięzców się nie zmieni.")
    for z in zwyciezcy:
        if z["status"] == DO_WERYFIKACJI:
            wiarygodny = False
            werdykt_czesci.append(f"Zwycięzca @{z['username']} ma status DO WERYFIKACJI - sprawdź jego zgłoszenie.")
        if z["powtorzone"]:
            werdykt_czesci.append(f"@{z['username']} ma {z['powtorzone']} powtórzonych komentarzy "
                                  f"(bez powtórzeń: {z['bez_powtorzen']}) - oceń zgodnie z regulaminem.")

    if wiarygodny:
        werdykt = "Wynik można uznać za wiarygodny na podstawie pobranych danych."
    else:
        werdykt = "NIE MOŻNA jeszcze rzetelnie wyłonić zwycięzców - zobacz uwagi poniżej."
    if werdykt_czesci:
        werdykt += "\n- " + "\n- ".join(werdykt_czesci)

    return Wynik(uczestnicy=uczestnicy, filmy=filmy, komentarze=komentarze, ranking=ranking,
                 zwyciezcy=zwyciezcy, do_weryfikacji=do_weryfikacji, ostrzezenia=ostrzezenia,
                 wiarygodny=wiarygodny, werdykt=werdykt)
