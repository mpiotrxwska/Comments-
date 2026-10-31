"""Obsługa przeglądarki (Playwright): lista filmów z profilu i pobieranie komentarzy.

Zasada działania: program steruje zwykłym oknem przeglądarki - przewija listę
komentarzy i klika "Wyświetl odpowiedzi" tak jak człowiek. Dane odczytuje
z odpowiedzi, które strona TikToka sama pobiera w trakcie przewijania
(identyfikator komentarza, autor, treść, data). Program NIE obchodzi CAPTCHA
ani limitów - gdy się pojawią, zatrzymuje się i prosi o decyzję.
"""
from __future__ import annotations

import json
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from playwright.sync_api import BrowserContext, Page, sync_playwright
from playwright.sync_api import Error as PlaywrightError

from .analiza import BLAD, KOMPLETNY, NIEPELNY, ROZBIEZNOSC

URL_FILMU = re.compile(r"tiktok\.com/@([^/?#]+)/(video|photo)/(\d+)")


class Przerwano(Exception):
    """Użytkownik zdecydował się przerwać (np. przy CAPTCHA). Postęp jest zapisany."""


def id_z_linku(url: str) -> str | None:
    m = URL_FILMU.search(url or "")
    if m:
        return m.group(3)
    m = re.search(r"tiktok\.com/(?:.*/)?(?:video|photo|v)/(\d{15,})", url or "")
    return m.group(1) if m else None


def data_z_id(video_id: str) -> int:
    """Identyfikator filmu TikTok zawiera czas publikacji (górne 32 bity)."""
    try:
        return int(video_id) >> 32
    except (TypeError, ValueError):
        return 0


# --------------------------------------------------------------------------- przeglądarka

def uruchom_przegladarke(folder_profilu: Path):
    """Trwały profil przeglądarki - logowanie zostaje zapamiętane między uruchomieniami."""
    pw = sync_playwright().start()
    folder_profilu.mkdir(parents=True, exist_ok=True)
    opcje = dict(headless=os.environ.get("KONKURS_HEADLESS") == "1", viewport={"width": 1366, "height": 900}, locale="pl-PL")
    ctx = None
    for kanal in ("chrome", "msedge", None):
        try:
            if kanal:
                ctx = pw.chromium.launch_persistent_context(str(folder_profilu), channel=kanal, **opcje)
            else:
                ctx = pw.chromium.launch_persistent_context(str(folder_profilu), **opcje)
            break
        except PlaywrightError:
            continue
    if ctx is None:
        pw.stop()
        raise RuntimeError("Nie udało się uruchomić przeglądarki. Uruchom ponownie plik instalacyjny.")
    return pw, ctx


def pauza(a: float, b: float) -> None:
    time.sleep(random.uniform(a, b))


JS_CAPTCHA = """() => {
  const sel = ['#captcha-verify-container-main-page', '#captcha_container', '.captcha_verify_container',
               '[class*="captcha-verify"]', '[id*="captcha-verify"]', 'iframe[src*="captcha"]'];
  for (const s of sel) { const e = document.querySelector(s); if (e && e.offsetParent !== null) return true; }
  return false;
}"""

JS_LOGIN_MODAL = """() => {
  const e = document.querySelector('[data-e2e="login-modal"], #loginContainer, [class*="LoginModal"]');
  return !!(e && e.offsetParent !== null);
}"""


def czy_blokada(page: Page) -> str | None:
    try:
        if page.evaluate(JS_CAPTCHA):
            return "CAPTCHA"
        if page.evaluate(JS_LOGIN_MODAL):
            return "LOGOWANIE"
    except PlaywrightError:
        return None
    return None


def obsluz_blokade(page: Page, rodzaj: str, pytaj: Callable[[str], str]) -> None:
    """Zatrzymuje pracę i oddaje decyzję użytkownikowi. Program niczego nie omija."""
    if rodzaj == "CAPTCHA":
        opis = ("TikTok wyświetlił weryfikację (CAPTCHA). Program NIE rozwiązuje jej automatycznie.\n"
                "Możesz rozwiązać ją samodzielnie w oknie przeglądarki i nacisnąć Enter,\n"
                "albo wpisać 'k' i Enter, aby zakończyć teraz (postęp jest zapisany - uruchom ponownie później,\n"
                "np. za kilka godzin; ograniczenia TikToka zwykle mijają same).")
    else:
        opis = ("TikTok prosi o zalogowanie. Zaloguj się samodzielnie w oknie przeglądarki\n"
                "(program nie zna i nie potrzebuje Twojego hasła), a potem naciśnij Enter.\n"
                "Wpisz 'k' i Enter, aby zakończyć teraz (postęp jest zapisany).")
    odp = pytaj("\n⚠️  " + opis + "\n> ").strip().lower()
    if odp in ("k", "koniec", "q"):
        raise Przerwano(rodzaj)


def logowanie(ctx: BrowserContext, pytaj: Callable[[str], str]) -> Page:
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://www.tiktok.com/", wait_until="domcontentloaded", timeout=60000)
    pytaj("\nW oknie przeglądarki otworzył się TikTok.\n"
          "Jeśli nie jesteś zalogowana/zalogowany - zaloguj się teraz SAMODZIELNIE (zalecane:\n"
          "bez logowania TikTok często ukrywa część komentarzy). Zamknij ewentualne okienka cookies.\n"
          "Gdy będziesz gotowa/gotowy, naciśnij Enter tutaj... ")
    return page


def _dane_ssr(page: Page) -> dict:
    try:
        txt = page.evaluate("""() => { const s = document.querySelector('#__UNIVERSAL_DATA_FOR_REHYDRATION__');
                                       return s ? s.textContent : null; }""")
        return json.loads(txt).get("__DEFAULT_SCOPE__", {}) if txt else {}
    except (PlaywrightError, ValueError):
        return {}


# --------------------------------------------------------------------------- lista filmów

def lista_filmow(page: Page, profil_url: str, start: datetime, koniec: datetime,
                 pytaj: Callable[[str], str], log: Callable[[str], None]) -> tuple[list[dict], bool, str]:
    """Zwraca (filmy z okresu konkursu, czy_lista_pewna, komentarz)."""
    elementy: dict[str, dict] = {}
    odpowiedzi = []
    def on_resp(r):
        if "/api/post/item_list" in r.url:
            odpowiedzi.append(r)

    page.on("response", on_resp)
    try:
        return _lista_filmow(page, profil_url, start, koniec, pytaj, log, elementy, odpowiedzi)
    finally:
        page.remove_listener("response", on_resp)


def _lista_filmow(page, profil_url, start, koniec, pytaj, log, elementy, odpowiedzi):
    page.goto(profil_url, wait_until="domcontentloaded", timeout=60000)
    pauza(3, 5)
    has_more = True
    bez_zmian = 0
    t0 = time.time()

    while time.time() - t0 < 600:
        rodzaj = czy_blokada(page)
        if rodzaj:
            obsluz_blokade(page, rodzaj, pytaj)
        # dane z API
        while odpowiedzi:
            r = odpowiedzi.pop(0)
            try:
                d = r.json()
            except Exception:
                continue
            for it in d.get("itemList") or []:
                vid = str(it.get("id"))
                autor = (it.get("author") or {}).get("uniqueId", "")
                rodz = "photo" if it.get("imagePost") else "video"
                elementy[vid] = {
                    "video_id": vid, "create_time": int(it.get("createTime") or data_z_id(vid)),
                    "opis": it.get("desc", ""), "przypiety": bool(it.get("isPinnedItem")),
                    "zgloszona_liczba": (it.get("stats") or {}).get("commentCount"),
                    "url": f"https://www.tiktok.com/@{autor}/{rodz}/{vid}" if autor else "",
                }
            if "hasMore" in d:
                has_more = bool(d.get("hasMore"))
        # dane z widocznych kafelków (zapasowo - data z identyfikatora)
        try:
            linki = page.evaluate("""() => Array.from(document.querySelectorAll('a[href*="/video/"], a[href*="/photo/"]'))
                                         .map(a => a.href)""")
        except PlaywrightError:
            linki = []
        przed = len(elementy)
        for href in linki:
            vid = id_z_linku(href)
            if vid and vid not in elementy:
                elementy[vid] = {"video_id": vid, "create_time": data_z_id(vid), "opis": "", "przypiety": False,
                                 "zgloszona_liczba": None, "url": href.split("?")[0]}
            elif vid and not elementy[vid]["url"]:
                elementy[vid]["url"] = href.split("?")[0]
        # czy dotarliśmy do filmów starszych niż start konkursu?
        nieprzypiete = sorted((e for e in elementy.values() if not e["przypiety"]),
                              key=lambda e: e["create_time"], reverse=True)
        starsze = [e for e in nieprzypiete if e["create_time"] < start.timestamp()]
        if len(starsze) >= 3 or not has_more:
            break
        bez_zmian = bez_zmian + 1 if len(elementy) == przed else 0
        if bez_zmian >= 8:
            break
        page.mouse.wheel(0, 2500)
        page.evaluate("window.scrollBy(0, 2500)")
        pauza(1.5, 3)

    log(f"Na profilu znaleziono {len(elementy)} publikacji (przeglądanych od najnowszych).")
    nieprzypiete = [e for e in elementy.values() if not e["przypiety"]]
    pewna = (not has_more) or any(e["create_time"] < start.timestamp() for e in nieprzypiete)
    uwaga = "" if pewna else ("Nie udało się przewinąć profilu do filmów sprzed rozpoczęcia konkursu - "
                              "lista może być niepełna.")
    filmy = [e for e in elementy.values() if start.timestamp() <= e["create_time"] <= koniec.timestamp()]
    filmy.sort(key=lambda e: e["create_time"])
    return filmy, pewna, uwaga


# --------------------------------------------------------------------------- komentarze

JS_OTWORZ_KOMENTARZE = """() => {
  if (document.querySelector('[data-e2e="comment-level-1"], [class*="CommentItemContainer"]')) return 'ok';
  const kandydaci = [...document.querySelectorAll('[data-e2e="comment-icon"], [data-e2e="browse-comment-icon"], [data-e2e="comment-tab"]')];
  for (const t of document.querySelectorAll('[role="tab"], button, p, span')) {
    const s = (t.innerText || '').trim().toLowerCase();
    if (/^(komentarze|comments)(\\s*\\(?[\\d.,km]*\\)?)?$/.test(s)) kandydaci.push(t);
  }
  for (const k of kandydaci) { try { k.click(); return 'klik'; } catch (e) {} }
  return 'brak';
}"""

JS_PRZEWIN = """() => {
  const items = document.querySelectorAll('[data-e2e="comment-level-1"], [data-e2e="comment-level-2"], [class*="CommentItemContainer"]');
  let el = items.length ? items[items.length - 1] : null;
  let przewinieto = false;
  let p = el;
  while (p && p !== document.body) {
    const st = getComputedStyle(p);
    if (/(auto|scroll)/.test(st.overflowY) && p.scrollHeight > p.clientHeight + 5) {
      p.scrollTop = p.scrollHeight; przewinieto = true; break;
    }
    p = p.parentElement;
  }
  if (el) el.scrollIntoView({block: 'end'});
  window.scrollTo(0, document.body.scrollHeight);
  return {liczba: items.length, przewinieto};
}"""

# Klikanie "Wyświetl X odpowiedzi" / "Wyświetl więcej" (nie klika "Ukryj")
JS_ROZWIN = """(limit) => {
  const re = /(wyświetl|wyswietl|pokaż|pokaz|zobacz|view|show).{0,25}(odpowied|repl|więcej|wiecej|more|jeszcze)/i;
  const nie = /(ukryj|hide)/i;
  const el = [...document.querySelectorAll('[data-e2e^="view-more"], [class*="ReplyAction"] *, [class*="ViewMore"], [class*="CommentReply"] p, [class*="CommentReply"] span, [class*="DivViewRepliesContainer"] *')];
  const widziane = new Set(); let n = 0;
  for (const e of el) {
    if (n >= limit) break;
    const t = (e.innerText || '').trim();
    if (!t || t.length > 60 || nie.test(t) || !re.test(t) || widziane.has(t + e.offsetTop)) continue;
    if (e.offsetParent === null) continue;
    widziane.add(t + e.offsetTop);
    try { e.click(); n++; } catch (x) {}
  }
  return n;
}"""


def _parsuj_komentarz(c: dict, video_id: str, parent: str | None = None) -> dict:
    u = c.get("user") or {}
    tekst = c.get("text") or ""
    if not tekst and (c.get("image_list") or c.get("sticker")):
        tekst = "[obraz/naklejka]"
    p = parent or str(c.get("reply_id") or "0")
    return {
        "cid": str(c.get("cid") or ""),
        "video_id": str(c.get("aweme_id") or video_id),
        "text": tekst,
        "create_time": int(c.get("create_time") or 0),
        "uid": str(u.get("uid") or ""),
        "username": u.get("unique_id") or "",
        "nickname": u.get("nickname") or "",
        "parent_cid": p if p not in ("", "None") else "0",
        "liczba_odpowiedzi_tiktok": int(c.get("reply_comment_total") or 0),
        "polubienia": int(c.get("digg_count") or 0),
    }


class Zbieracz:
    def __init__(self, video_id: str):
        self.video_id = video_id
        self.komentarze: dict[str, dict] = {}
        self.lista_ma_wiecej: bool | None = None
        self.total_api: int | None = None
        self.odp_koniec: set[str] = set()   # wątki, których odpowiedzi skończyły się (has_more=0)
        self.bledy_api: list[str] = []

    def dodaj(self, c: dict) -> bool:
        k = c["cid"]
        if not k or c["video_id"] != self.video_id:
            return False
        nowy = k not in self.komentarze
        self.komentarze[k] = {**self.komentarze.get(k, {}), **c}
        return nowy

    def przetworz(self, url: str, d: dict) -> int:
        nowe = 0
        if d.get("status_code") not in (0, None):
            self.bledy_api.append(f'{d.get("status_code")}: {d.get("status_msg", "")}')
            return 0
        if "/api/comment/list/reply" in url:
            m = re.search(r"[?&]comment_id=(\d+)", url)
            parent = m.group(1) if m else None
            for c in d.get("comments") or []:
                nowe += self.dodaj(_parsuj_komentarz(c, self.video_id, parent))
            if parent and not d.get("has_more"):
                self.odp_koniec.add(parent)
        else:
            m = re.search(r"[?&]aweme_id=(\d+)", url)
            if m and m.group(1) != self.video_id:
                return 0
            for c in d.get("comments") or []:
                nowe += self.dodaj(_parsuj_komentarz(c, self.video_id))
                for r in c.get("reply_comment") or []:  # podgląd pierwszych odpowiedzi
                    nowe += self.dodaj(_parsuj_komentarz(r, self.video_id, str(c.get("cid"))))
            self.lista_ma_wiecej = bool(d.get("has_more"))
            if d.get("total") is not None:
                self.total_api = int(d["total"])
        return nowe

    def watki_niedokonczone(self) -> list[str]:
        odp_licznik: dict[str, int] = {}
        for c in self.komentarze.values():
            if c["parent_cid"] != "0":
                odp_licznik[c["parent_cid"]] = odp_licznik.get(c["parent_cid"], 0) + 1
        wynik = []
        for c in self.komentarze.values():
            if c["parent_cid"] == "0" and c["liczba_odpowiedzi_tiktok"] > 0:
                if odp_licznik.get(c["cid"], 0) < c["liczba_odpowiedzi_tiktok"] and c["cid"] not in self.odp_koniec:
                    wynik.append(c["cid"])
        return wynik


def pobierz_komentarze(page: Page, film: dict, pytaj: Callable[[str], str], log: Callable[[str], None],
                       max_minut: float = 20) -> dict:
    """Pobiera wszystkie dostępne komentarze (z odpowiedziami) pod jednym filmem."""
    vid = film["video_id"]
    z = Zbieracz(vid)
    odpowiedzi = []

    def on_resp(r):
        if "/api/comment/list" in r.url:
            odpowiedzi.append(r)

    page.on("response", on_resp)
    wynik = {"status": NIEPELNY, "blad": "", "zgloszona_liczba": film.get("zgloszona_liczba")}
    try:
        page.goto(film["url"], wait_until="domcontentloaded", timeout=60000)
        pauza(3, 5)
        ssr = _dane_ssr(page)
        try:
            item = ssr["webapp.video-detail"]["itemInfo"]["itemStruct"]
            wynik["zgloszona_liczba"] = int(item["stats"]["commentCount"])
            film["create_time"] = int(item.get("createTime") or film.get("create_time") or data_z_id(vid))
            film["opis"] = film.get("opis") or item.get("desc", "")
        except (KeyError, TypeError, ValueError):
            pass

        t0 = time.time()
        bez_postepu = 0
        proby_otwarcia = 0
        while True:
            rodzaj = czy_blokada(page)
            if rodzaj:
                obsluz_blokade(page, rodzaj, pytaj)
                bez_postepu = 0
            nowe = 0
            while odpowiedzi:
                r = odpowiedzi.pop(0)
                try:
                    nowe += z.przetworz(r.url, r.json())
                except Exception:
                    continue
            if not z.komentarze and proby_otwarcia < 5:
                page.evaluate(JS_OTWORZ_KOMENTARZE)
                proby_otwarcia += 1
            klikniete = page.evaluate(JS_ROZWIN, 8)
            page.evaluate(JS_PRZEWIN)
            try:
                page.mouse.wheel(0, 1500)
            except PlaywrightError:
                pass
            pauza(1.2, 2.5)
            lista_koniec = z.lista_ma_wiecej is False or (wynik["zgloszona_liczba"] == 0)
            niedokonczone = z.watki_niedokonczone()
            if lista_koniec and not niedokonczone and not klikniete and not odpowiedzi:
                bez_postepu += 1
                if bez_postepu >= 3:
                    break
            elif nowe == 0 and klikniete == 0:
                bez_postepu += 1
                if bez_postepu >= 10:
                    break
            else:
                bez_postepu = 0
            if time.time() - t0 > max_minut * 60:
                wynik["blad"] = f"Przekroczono limit czasu ({max_minut} min) dla filmu."
                break
            if len(z.komentarze) and len(z.komentarze) % 50 == 0 and nowe:
                log(f"   ... {len(z.komentarze)} komentarzy")

        # ostatnie zebranie odpowiedzi
        pauza(1, 2)
        while odpowiedzi:
            r = odpowiedzi.pop(0)
            try:
                z.przetworz(r.url, r.json())
            except Exception:
                pass

        zgl = wynik["zgloszona_liczba"]
        if zgl is None and z.total_api is not None:
            zgl = wynik["zgloszona_liczba"] = z.total_api
        lista_koniec = z.lista_ma_wiecej is False or zgl == 0
        niedokonczone = z.watki_niedokonczone()
        if z.bledy_api and not z.komentarze:
            wynik["status"] = BLAD
            wynik["blad"] = "TikTok odrzucił zapytania o komentarze: " + "; ".join(z.bledy_api[:3])
        elif lista_koniec and not niedokonczone:
            wynik["status"] = KOMPLETNY if (zgl is None or len(z.komentarze) >= zgl) else ROZBIEZNOSC
        else:
            wynik["status"] = NIEPELNY
            pow = []
            if not lista_koniec:
                pow.append("lista komentarzy nie została przewinięta do końca")
            if niedokonczone:
                pow.append(f"nie rozwinięto odpowiedzi w {len(niedokonczone)} wątkach")
            if z.lista_ma_wiecej is None:
                pow.append("strona nie wczytała listy komentarzy (sprawdź logowanie)")
            wynik["blad"] = (wynik["blad"] + " " if wynik["blad"] else "") + "; ".join(pow)
    except Przerwano:
        raise
    except Exception as e:  # noqa: BLE001 - każdy błąd zapisujemy i przechodzimy dalej
        wynik["status"] = BLAD
        wynik["blad"] = f"{type(e).__name__}: {e}"[:500]
    finally:
        page.remove_listener("response", on_resp)

    wynik["komentarze"] = list(z.komentarze.values())
    wynik["pobrane"] = len(z.komentarze)
    return wynik
