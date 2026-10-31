"""Testy logiki rankingu na sztucznych danych. Uruchom: python -m pytest testy  (albo python testy/test_analiza.py)"""
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from narzedzie.analiza import DO_WERYFIKACJI, KOMPLETNY, NIEPELNY, POTWIERDZONY, analizuj  # noqa: E402

TZ = ZoneInfo("Europe/Warsaw")
START = datetime(2026, 10, 1, 18, 0, tzinfo=TZ)
KONIEC = datetime(2026, 10, 15, 23, 59, tzinfo=TZ)
T = int(START.timestamp()) + 3600
CFG = {"film_konkursowy_id": "100", "wlasciciel_profilu": "ja", "tryb_uczestnikow": "slowa_kluczowe",
       "slowa_kluczowe": ["biorę udział", "zgłaszam"], "liczba_zwyciezcow": 2}


def k(cid, vid, user, text, dt=0, parent="0", uid=None):
    return {"cid": str(cid), "video_id": vid, "username": user, "uid": uid or "id_" + user, "text": text,
            "create_time": T + dt, "parent_cid": parent}


def filmy(status2=KOMPLETNY):
    return [{"video_id": "100", "url": "https://www.tiktok.com/@ja/video/100", "status": KOMPLETNY, "pobrane": 5},
            {"video_id": "200", "url": "https://www.tiktok.com/@ja/video/200", "status": status2, "pobrane": 3,
             "zgloszona_liczba": 3}]


def test_podstawowy_ranking():
    kom = [
        k(1, "100", "ania", "Biorę udział!"), k(2, "100", "basia", "zgłaszam się"), k(3, "100", "celina", "śliczne"),
        k(4, "100", "ja", "Powodzenia!"), k(5, "100", "ania", "super", 10),
        k(6, "200", "ania", "super", 20), k(6, "200", "ania", "super", 20),  # duplikat pobrania
        k(7, "200", "basia", "<3", 30), k(8, "200", "obcy", "hej", 40),
        k(9, "200", "ania", "poza", 10**8),  # poza okresem
    ]
    w = analizuj(filmy(), kom, CFG, START, KONIEC)
    u = {x.username: x for x in w.uczestnicy.values()}
    assert set(u) == {"ania", "basia", "celina"}          # właściciel i obcy poza listą
    assert u["ania"].status == POTWIERDZONY and u["celina"].status == DO_WERYFIKACJI
    r = {x["username"]: x for x in w.ranking}
    assert r["ania"]["wszystkie"] == 3                    # 1,5,6 (duplikat i komentarz poza okresem nie liczone)
    assert r["ania"]["filmy"] == 2 and r["ania"]["powtorzone"] == 1
    assert r["ania"]["konkursowy"] == 2 and r["ania"]["inne"] == 1
    assert r["basia"]["wszystkie"] == 2
    assert [z["username"] for z in w.zwyciezcy] == ["ania", "basia"]
    assert w.wiarygodny
    assert any("poza okresem" in c["powod_weryfikacji"] for c in w.do_weryfikacji)


def test_remis_i_niekompletne():
    kom = [k(1, "100", "ania", "biorę udział"), k(2, "100", "basia", "biorę udział"),
           k(3, "100", "celina", "biorę udział"), k(4, "200", "ania", "x")]
    w = analizuj(filmy(NIEPELNY), kom, CFG, START, KONIEC)
    assert not w.wiarygodny and "REMIS" in w.werdykt
    w2 = analizuj(filmy(), kom, dict(CFG, liczba_zwyciezcow=1), START, KONIEC)
    assert w2.wiarygodny and w2.zwyciezcy[0]["username"] == "ania"


def test_reczne_dodanie_i_zmiana_nazwy():
    kom = [k(1, "100", "celina", "piękne"), k(2, "200", "celina_nowa", "a", uid="id_celina")]
    w = analizuj(filmy(), kom, CFG, START, KONIEC, dodaj=["@celina"])
    r = w.ranking[0]
    assert r["status"] == POTWIERDZONY and r["wszystkie"] == 2   # ta sama osoba mimo zmiany nazwy


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("OK", n)
