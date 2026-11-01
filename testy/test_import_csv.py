"""Test wczytywania plików CSV z eksportera komentarzy. Uruchom: python testy/test_import_csv.py"""
import sys
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from narzedzie.import_csv import wczytaj_plik  # noqa: E402

CSV = '''"Identyfikator komentarza","Identyfikator użytkownika","Nazwa użytkownika","Przezwisko","Komentarz","Czas komentarza","Liczba polubień","Polubione przez autora","Liczba odpowiedzi","Przypięte do góry","Strona główna użytkownika"
"=""7698044133059904278""","=""7112077324892259333""","gabichoinska","Choina","ale super, ""cytat""","18.10.2026, 18:23:22","0","NIE","1","NIE","https://www.tiktok.com/@gabichoinska"
"=""7698108645100094230""","=""7528835582060626966""","maja.chyczewska","Maja","biorę udział
druga linia","18.10.2026, 22:33:38","0","NIE","0","NIE","https://www.tiktok.com/@maja.chyczewska"
'''


def test_wczytanie():
    d = Path(tempfile.mkdtemp())
    p = d / "TTCommentExporter-7697628228587982112-2-comments.csv"
    p.write_text("﻿" + CSV, encoding="utf-8")
    vid, kom, info = wczytaj_plik(p, ZoneInfo("Europe/Warsaw"))
    assert vid == "7697628228587982112"
    assert [c["cid"] for c in kom] == ["7698044133059904278", "7698108645100094230"]
    assert kom[0]["username"] == "gabichoinska" and kom[0]["uid"] == "7112077324892259333"
    assert kom[0]["text"] == 'ale super, "cytat"' and "druga linia" in kom[1]["text"]
    assert kom[0]["create_time"] == 1792340602  # 18.10.2026 18:23:22 czasu polskiego
    assert info["status"] == "ROZBIEZNOSC" and info["zgloszona_liczba"] == 3  # brak 1 odpowiedzi


if __name__ == "__main__":
    test_wczytanie()
    print("OK test_wczytanie")
