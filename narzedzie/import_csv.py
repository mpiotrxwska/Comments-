"""Wczytywanie komentarzy z plików CSV wyeksportowanych rozszerzeniem przeglądarki
(np. "TTCommentExporter") - bez automatycznego przewijania TikToka.

Nazwa pliku musi zawierać identyfikator filmu, np.
TTCommentExporter-7697628228587982112-79-comments.csv
"""
from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .analiza import KOMPLETNY, ROZBIEZNOSC

# Rozpoznawanie kolumn po fragmentach nazw (wersja polska i angielska eksportera)
KOLUMNY = {
    "cid": ["identyfikator komentarza", "comment id", "comment_id", "cid"],
    "uid": ["identyfikator użytkownika", "user id", "user_id", "uid"],
    "username": ["nazwa użytkownika", "username", "unique id", "unique_id"],
    "nickname": ["przezwisko", "nickname", "nick"],
    "text": ["komentarz", "comment text", "comment", "text"],
    "czas": ["czas komentarza", "comment time", "create time", "create_time", "time", "data"],
    "polubienia": ["liczba polubień", "digg count", "likes", "like count"],
    "odpowiedzi": ["liczba odpowiedzi", "reply count", "replies", "reply_comment_total"],
    "parent": ["nadrzędn", "odpowiedź na", "odpowiedz na", "parent", "reply to", "reply_id", "replied"],
}


def _wartosc(v: str) -> str:
    v = (v or "").strip()
    if v.startswith('="') and v.endswith('"'):  # format Excela ="123"
        v = v[2:-1]
    return v.strip()


def _mapuj(naglowki: list[str]) -> dict[str, str]:
    mapa: dict[str, str] = {}
    for pole, wzorce in KOLUMNY.items():
        for w in wzorce:  # wzorce od najbardziej konkretnych
            for n in naglowki:
                nl = n.lower().strip()
                if n in mapa.values():
                    continue
                if (nl == w) or (len(w) > 4 and w in nl):
                    mapa[pole] = n
                    break
            if pole in mapa:
                break
    return mapa


def _czas(t: str, tz: ZoneInfo) -> int:
    t = (t or "").strip()
    if not t:
        return 0
    if t.isdigit():
        return int(t[:10])
    for fmt in ("%d.%m.%Y, %H:%M:%S", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y, %H:%M", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y, %I:%M:%S %p", "%m/%d/%Y %H:%M:%S", "%d/%m/%Y, %H:%M:%S"):
        try:
            return int(datetime.strptime(t, fmt).replace(tzinfo=tz).timestamp())
        except ValueError:
            continue
    return 0


def id_filmu_z_nazwy(nazwa: str) -> str | None:
    m = re.search(r"(\d{17,21})", nazwa)
    return m.group(1) if m else None


def wczytaj_plik(sciezka: Path, tz: ZoneInfo) -> tuple[str, list[dict], dict]:
    vid = id_filmu_z_nazwy(sciezka.name)
    if not vid:
        raise ValueError(f"W nazwie pliku {sciezka.name} nie ma identyfikatora filmu.")
    with open(sciezka, encoding="utf-8-sig", newline="") as f:
        czytnik = csv.DictReader(f)
        mapa = _mapuj(czytnik.fieldnames or [])
        if "cid" not in mapa or "username" not in mapa or "text" not in mapa:
            raise ValueError(f"Nie rozpoznano kolumn w pliku {sciezka.name}: {czytnik.fieldnames}")
        komentarze = []
        for r in czytnik:
            g = lambda pole: _wartosc(r.get(mapa[pole], "")) if pole in mapa else ""  # noqa: E731
            parent = g("parent") or "0"
            komentarze.append({
                "cid": g("cid"), "video_id": vid, "text": r.get(mapa["text"], "") or "",
                "create_time": _czas(g("czas"), tz), "uid": g("uid"), "username": g("username").lstrip("@"),
                "nickname": g("nickname"), "parent_cid": parent if parent not in ("", "0", "-") else "0",
                "liczba_odpowiedzi_tiktok": int(g("odpowiedzi") or 0) if g("odpowiedzi").isdigit() else 0,
                "polubienia": int(g("polubienia") or 0) if g("polubienia").isdigit() else 0,
                "zrodlo": sciezka.name,
            })
    # Kompletność: czy w pliku są wszystkie odpowiedzi, które TikTok zgłasza?
    glowne = [c for c in komentarze if c["parent_cid"] == "0"]
    odp_w_pliku = len(komentarze) - len(glowne)
    odp_tiktok = sum(c["liczba_odpowiedzi_tiktok"] for c in glowne)
    info = {"pobrane": len(komentarze), "zgloszona_liczba": len(glowne) + max(odp_tiktok, odp_w_pliku)}
    if odp_tiktok > odp_w_pliku:
        info["status"] = ROZBIEZNOSC
        info["blad"] = (f"Plik CSV zawiera {len(glowne)} komentarzy głównych i {odp_w_pliku} odpowiedzi, "
                        f"a TikTok podaje {odp_tiktok} odpowiedzi - brakuje {odp_tiktok - odp_w_pliku} odpowiedzi "
                        f"(wyeksportuj z odpowiedziami, jeśli się liczą).")
    else:
        info["status"] = KOMPLETNY
        info["blad"] = ""
    info["blad"] = (info["blad"] + f" Źródło: {sciezka.name}").strip()
    return vid, komentarze, info
