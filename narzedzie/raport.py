"""Eksport wyników: Excel (osobne arkusze), CSV i raport HTML."""
from __future__ import annotations

import csv
import html
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .analiza import KOMPLETNY, OPIS_STATUSU, Wynik


def _data(ts, tz: ZoneInfo) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(int(ts), tz).strftime("%Y-%m-%d %H:%M:%S")


def _tak(b) -> str:
    return "TAK" if b else "NIE"


def tabele(w: Wynik, cfg: dict, tz: ZoneInfo) -> dict[str, tuple[list[str], list[list]]]:
    filmy_url = {str(f["video_id"]): f.get("url", "") for f in w.filmy}
    konkurs_id = str(cfg["film_konkursowy_id"])

    # 1. Uczestnicy
    uczestnicy = []
    for u in sorted(w.uczestnicy.values(), key=lambda x: x.username.lower()):
        zgl = u.komentarze_zgloszeniowe
        uczestnicy.append(["@" + u.username, u.nick, u.status, u.powod,
                           " | ".join(c.get("text", "") for c in zgl[:3]),
                           _data(zgl[0].get("create_time"), tz) if zgl else "",
                           u.klucz])

    # 2. Filmy
    filmy = []
    for f in sorted(w.filmy, key=lambda x: x.get("create_time") or 0):
        filmy.append([f.get("url", ""), str(f["video_id"]), _data(f.get("create_time"), tz),
                      _tak(str(f["video_id"]) == konkurs_id), f.get("status", ""),
                      OPIS_STATUSU.get(f.get("status"), ""), f.get("pobrane", 0),
                      f.get("zgloszona_liczba") if f.get("zgloszona_liczba") is not None else "",
                      f.get("blad", ""), f.get("analizowano", ""), (f.get("opis") or "")[:200]])

    # 3. Komentarze
    komentarze = []
    for c in sorted(w.komentarze, key=lambda x: (str(x.get("video_id")), x.get("create_time") or 0)):
        komentarze.append(["@" + (c.get("username") or ""), c.get("nickname", ""), c.get("text", ""),
                           _data(c.get("create_time"), tz), c.get("film_url") or filmy_url.get(str(c.get("video_id")), ""),
                           str(c.get("video_id")), c.get("cid", ""),
                           "odpowiedź" if c.get("odpowiedz") else "komentarz", c.get("parent_cid", "0"),
                           _tak(c.get("film_konkursowy")), _tak(c.get("uczestnik")), c.get("status_uczestnika", ""),
                           c.get("w_czasie_konkursu", ""), _tak(c.get("liczony")), _tak(c.get("powtorzony")),
                           c.get("powod_nieliczenia", ""), c.get("polubienia", 0)])

    # 4. Ranking
    ranking = []
    for r in w.ranking:
        ranking.append([r["miejsce"], "@" + r["username"], r["nick"], r["status"], r["wszystkie"], r["filmy"],
                        r["konkursowy"], r["inne"], r["powtorzone"], r["bez_powtorzen"], r["odpowiedzi"],
                        _tak(r["remis"]), _data(r["pierwszy"], tz), _data(r["ostatni"], tz)])

    # 5. TOP zwycięzców
    top = []
    for i, r in enumerate(w.zwyciezcy, 1):
        top.append([f"Zwycięzca nr {i}", "@" + r["username"], r["nick"], r["status"], r["wszystkie"], r["filmy"],
                    r["konkursowy"], r["inne"], r["powtorzone"],
                    "\n".join(filmy_url.get(v, v) for v in r["lista_filmow"])])

    # 6. Do weryfikacji
    weryf = []
    for c in w.do_weryfikacji:
        weryf.append([c.get("powod_weryfikacji", ""), "@" + (c.get("username") or ""), c.get("text", ""),
                      _data(c.get("create_time"), tz), c.get("film_url", ""), str(c.get("video_id")),
                      c.get("cid", ""), _tak(c.get("liczony"))])
    # 7. Komentarze zwycięzców
    klucze_zw = {r["klucz"] for r in w.zwyciezcy}
    zw_kom = []
    for c in sorted(w.komentarze, key=lambda x: x.get("create_time") or 0):
        if not c.get("liczony"):
            continue
        k = str(c.get("uid") or "") or "u:" + (c.get("username") or "").lower()
        if k in klucze_zw:
            zw_kom.append(["@" + c.get("username", ""), c.get("text", ""), _data(c.get("create_time"), tz),
                           c.get("film_url", ""), c.get("cid", ""), _tak(c.get("powtorzony")),
                           "odpowiedź" if c.get("odpowiedz") else "komentarz"])

    return {
        "Uczestnicy konkursu": (["Username", "Nick", "Status", "Powód", "Komentarz zgłoszeniowy",
                                 "Data zgłoszenia", "ID konta"], uczestnicy),
        "Przeanalizowane filmy": (["Link", "ID filmu", "Data publikacji", "Film konkursowy", "Status",
                                   "Opis statusu", "Pobrane komentarze", "Liczba wg TikToka", "Błąd / uwagi",
                                   "Data analizy", "Opis filmu"], filmy),
        "Wszystkie komentarze": (["Username", "Nick", "Treść", "Data komentarza", "Link filmu", "ID filmu",
                                  "ID komentarza", "Typ", "ID komentarza nadrzędnego", "Pod filmem konkursowym",
                                  "Uczestnik", "Status uczestnika", "W czasie konkursu", "Liczony do rankingu",
                                  "Powtórzony", "Powód nieliczenia", "Polubienia (nie wpływa na ranking)"], komentarze),
        "Ranking": (["Miejsce", "Username", "Nick", "Status uczestnika", "Wszystkie komentarze",
                     "Skomentowane filmy", "Pod filmem konkursowym", "Pod innymi filmami",
                     "Powtórzone komentarze", "Komentarze bez powtórzeń", "W tym odpowiedzi", "Remis",
                     "Pierwszy komentarz", "Ostatni komentarz"], ranking),
        "TOP zwycięzcy": (["Miejsce", "Username", "Nick", "Status", "Wszystkie komentarze", "Skomentowane filmy",
                           "Pod filmem konkursowym", "Pod innymi filmami", "Powtórzone", "Filmy"], top),
        "Do weryfikacji": (["Powód", "Username", "Treść", "Data", "Link filmu", "ID filmu", "ID komentarza",
                            "Liczony do rankingu"], weryf),
        "Komentarze zwycięzców": (["Username", "Treść", "Data", "Link filmu", "ID komentarza", "Powtórzony", "Typ"],
                                  zw_kom),
    }


def zapisz_excel(sciezka: Path, w: Wynik, cfg: dict, tz: ZoneInfo, podsumowanie: list[str]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Podsumowanie"
    for linia in podsumowanie:
        ws.append([linia])
    ws.column_dimensions["A"].width = 130
    for row in ws.iter_rows():
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws["A1"].font = Font(bold=True, size=14)

    naglowek = PatternFill("solid", fgColor="FCE4EC")
    for nazwa, (kol, wiersze) in tabele(w, cfg, tz).items():
        ws = wb.create_sheet(nazwa[:31])
        ws.append(kol)
        for c in ws[1]:
            c.font = Font(bold=True)
            c.fill = naglowek
            c.alignment = Alignment(wrap_text=True, vertical="top")
        for wiersz in wiersze:
            ws.append(wiersz)
        ws.freeze_panes = "A2"
        if wiersze:
            ws.auto_filter.ref = ws.dimensions
        for i, k in enumerate(kol, 1):
            dl = max([len(str(k))] + [len(str(r[i - 1]).split("\n")[0]) for r in wiersze[:500]])
            ws.column_dimensions[get_column_letter(i)].width = min(max(10, dl + 2), 70)
        # klikalne linki
        for row in ws.iter_rows(min_row=2):
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("https://www.tiktok.com/") and "\n" not in c.value:
                    c.hyperlink = c.value
                    c.font = Font(color="0563C1", underline="single")
    wb.save(sciezka)


def zapisz_csv(folder: Path, w: Wynik, cfg: dict, tz: ZoneInfo) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    nazwy = {"Uczestnicy konkursu": "1_uczestnicy", "Przeanalizowane filmy": "2_filmy",
             "Wszystkie komentarze": "3_komentarze", "Ranking": "4_ranking", "TOP zwycięzcy": "5_top_zwyciezcy",
             "Do weryfikacji": "6_do_weryfikacji", "Komentarze zwycięzców": "7_komentarze_zwyciezcow"}
    for nazwa, (kol, wiersze) in tabele(w, cfg, tz).items():
        # średnik + BOM: plik otwiera się poprawnie w polskim Excelu
        with open(folder / f"{nazwy[nazwa]}.csv", "w", newline="", encoding="utf-8-sig") as f:
            wr = csv.writer(f, delimiter=";")
            wr.writerow(kol)
            wr.writerows(wiersze)


def tekst_podsumowania(w: Wynik, cfg: dict, tz: ZoneInfo, start: datetime, koniec: datetime) -> list[str]:
    komplet = sum(1 for f in w.filmy if f.get("status") == KOMPLETNY)
    linie = [
        "Raport konkursu TikTok",
        f"Wygenerowano: {datetime.now(tz).strftime('%Y-%m-%d %H:%M')}",
        f"Profil: {cfg.get('profil')}",
        f"Film konkursowy: {cfg.get('film_konkursowy')}",
        f"Okres konkursu: {start.strftime('%Y-%m-%d %H:%M')} - {koniec.strftime('%Y-%m-%d %H:%M')} ({cfg.get('strefa_czasowa')})",
        "",
        f"Filmy: {len(w.filmy)} (pobrane w całości: {komplet}, z problemami: {len(w.filmy) - komplet})",
        f"Pobrane komentarze (unikalne): {len(w.komentarze)}",
        f"Komentarze policzone do rankingu: {sum(1 for c in w.komentarze if c.get('liczony'))}",
        f"Uczestnicy: {len(w.uczestnicy)} (potwierdzeni: {sum(1 for u in w.uczestnicy.values() if u.status != 'DO WERYFIKACJI')}, "
        f"do weryfikacji: {sum(1 for u in w.uczestnicy.values() if u.status == 'DO WERYFIKACJI')})",
        "",
        "WERDYKT:",
        *w.werdykt.split("\n"),
        "",
    ]
    for i, r in enumerate(w.zwyciezcy, 1):
        linie.append(f"Zwycięzca nr {i}: @{r['username']} - {r['wszystkie']} komentarzy pod {r['filmy']} filmami "
                     f"(konkursowy: {r['konkursowy']}, inne: {r['inne']}, powtórzone: {r['powtorzone']}, status: {r['status']})")
    if w.ostrzezenia:
        linie += ["", "FILMY Z PROBLEMAMI:"] + w.ostrzezenia
    linie += ["", "Zasady liczenia: podstawowe kryterium - łączna liczba komentarzy (z odpowiedziami: "
              f"{'tak' if cfg.get('licz_odpowiedzi', True) else 'nie'}; tylko w okresie konkursu: "
              f"{'tak' if cfg.get('licz_tylko_w_czasie_konkursu', True) else 'nie'}). Polubienia nie mają wpływu. "
              "Powtórzone komentarze są liczone, ale oznaczone osobno. Każdy komentarz liczony raz (wg ID)."]
    return linie


def zapisz_html(sciezka: Path, w: Wynik, cfg: dict, tz: ZoneInfo, podsumowanie: list[str]) -> None:
    e = html.escape
    filmy_url = {str(f["video_id"]): f.get("url", "") for f in w.filmy}
    czesci = ["<!doctype html><html lang='pl'><head><meta charset='utf-8'><title>Raport konkursu</title>",
              "<style>body{font-family:system-ui,Arial,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#222}"
              "table{border-collapse:collapse;width:100%;margin:12px 0}td,th{border:1px solid #ddd;padding:6px 8px;text-align:left;vertical-align:top}"
              "th{background:#fce4ec}.ok{background:#e8f5e9;padding:12px;border-radius:8px}.zle{background:#fff3e0;padding:12px;border-radius:8px}"
              "pre{white-space:pre-wrap}</style></head><body>",
              f"<h1>{e(podsumowanie[0])}</h1>",
              f"<div class='{'ok' if w.wiarygodny else 'zle'}'><pre>{e(chr(10).join(podsumowanie[1:]))}</pre></div>",
              "<h2>Ranking TOP 20</h2><table><tr><th>Miejsce</th><th>Username</th><th>Wszystkie komentarze</th>"
              "<th>Skomentowane filmy</th><th>Powtórzone komentarze</th><th>Status</th></tr>"]
    for r in w.ranking[:20]:
        czesci.append(f"<tr><td>{r['miejsce']}{' (remis)' if r['remis'] else ''}</td><td>@{e(r['username'])}</td>"
                      f"<td>{r['wszystkie']}</td><td>{r['filmy']}</td><td>{r['powtorzone']}</td><td>{e(r['status'])}</td></tr>")
    czesci.append("</table>")
    for i, r in enumerate(w.zwyciezcy, 1):
        czesci.append(f"<h2>Zwycięzca nr {i}: @{e(r['username'])} - {r['wszystkie']} komentarzy</h2><p>Filmy:</p><ul>")
        for v in r["lista_filmow"]:
            u = filmy_url.get(v, v)
            n = sum(1 for c in w.komentarze if c.get("liczony") and str(c.get("video_id")) == v and
                    (str(c.get("uid") or "") or "u:" + (c.get("username") or "").lower()) == r["klucz"])
            czesci.append(f"<li><a href='{e(u)}'>{e(u)}</a> - {n} kom.</li>")
        czesci.append("</ul><table><tr><th>Data</th><th>Treść</th><th>Film</th><th>Powtórzony</th></tr>")
        for c in sorted(w.komentarze, key=lambda x: x.get("create_time") or 0):
            k = str(c.get("uid") or "") or "u:" + (c.get("username") or "").lower()
            if c.get("liczony") and k == r["klucz"]:
                czesci.append(f"<tr><td>{_data(c.get('create_time'), tz)}</td><td>{e(c.get('text', ''))}</td>"
                              f"<td><a href='{e(c.get('film_url', ''))}'>{e(str(c.get('video_id')))}</a></td>"
                              f"<td>{_tak(c.get('powtorzony'))}</td></tr>")
        czesci.append("</table>")
    czesci.append("</body></html>")
    sciezka.write_text("\n".join(czesci), encoding="utf-8")
