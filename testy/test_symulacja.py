"""Test całego programu na SYMULOWANYM TikToku (lokalne, sztuczne strony - bez łączenia z TikTokiem).

Sprawdza: listę filmów z profilu, przewijanie komentarzy, rozwijanie odpowiedzi,
zapis postępu, raport Excel/CSV/HTML. Uruchom: python testy/test_symulacja.py
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["KONKURS_HEADLESS"] = "1"

from narzedzie import glowny, tiktok  # noqa: E402

START_TS = 1790870400  # 2026-10-01 18:00 Europe/Warsaw
DZIEN = 86400


def vid_z_czasu(ts, n):
    return str((ts << 32) + n)


FILMY = {  # id -> czas publikacji
    vid_z_czasu(START_TS - 100 * DZIEN, 1): START_TS - 100 * DZIEN,  # stary, przypięty
    vid_z_czasu(START_TS + 60, 2): START_TS + 60,                    # konkursowy
    vid_z_czasu(START_TS + 3 * DZIEN, 3): START_TS + 3 * DZIEN,
    vid_z_czasu(START_TS + 9 * DZIEN, 4): START_TS + 9 * DZIEN,
    vid_z_czasu(START_TS - 5 * DZIEN, 5): START_TS - 5 * DZIEN,      # przed konkursem
    vid_z_czasu(START_TS - 9 * DZIEN, 6): START_TS - 9 * DZIEN,
    vid_z_czasu(START_TS - 12 * DZIEN, 7): START_TS - 12 * DZIEN,
    vid_z_czasu(START_TS + 20 * DZIEN, 8): START_TS + 20 * DZIEN,    # po konkursie
}
KONKURSOWY = vid_z_czasu(START_TS + 60, 2)
PRZYPIETY = vid_z_czasu(START_TS - 100 * DZIEN, 1)


def user(n):
    return {"uid": f"9{n:03d}", "unique_id": f"osoba_{n}", "nickname": f"Osoba {n}"}


def komentarze_filmu(vid):
    """Deterministyczne dane: top-level + odpowiedzi."""
    ts0 = FILMY[vid] + 100
    top, odp = [], {}
    n_top = 45 if vid == KONKURSOWY else 12
    for i in range(n_top):
        u = i % 15
        text = ("Biorę udział! " if vid == KONKURSOWY and u < 12 else "") + ("❤️" if i % 4 == 0 else f"piękne {i}")
        cid = f"{vid[-4:]}{i:04d}"
        n_odp = 5 if i % 10 == 0 else 0
        top.append({"cid": cid, "aweme_id": vid, "text": text, "create_time": ts0 + i * 60, "user": user(u),
                    "reply_id": "0", "reply_comment_total": n_odp, "digg_count": i})
        odp[cid] = [{"cid": f"{cid}{j}", "aweme_id": vid, "text": f"odp {j}", "create_time": ts0 + i * 60 + j,
                     "user": user((u + j + 1) % 15), "reply_id": cid, "reply_comment_total": 0} for j in range(n_odp)]
    return top, odp


DANE = {v: komentarze_filmu(v) for v in FILMY}

STRONA_FILMU = """<html><head><meta charset="utf-8"></head><body><script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">%s</script>
<div style="display:flex"><div style="width:600px;height:800px">wideo</div>
<div id="lista" style="height:700px;overflow-y:auto;width:500px"></div></div>
<script>
const vid = "%s"; let cursor = 0, more = true, busy = false;
async function laduj() {
  if (!more || busy) return; busy = true;
  const d = await (await fetch(`/api/comment/list/?aweme_id=${vid}&cursor=${cursor}&count=20`)).json();
  for (const c of d.comments) {
    const el = document.createElement('div'); el.setAttribute('data-e2e', 'comment-level-1');
    el.style.height = '60px'; el.textContent = c.user.unique_id + ': ' + c.text;
    document.getElementById('lista').appendChild(el);
    if (c.reply_comment_total > 1) {
      const b = document.createElement('p'); b.setAttribute('data-e2e', 'view-more-1');
      b.textContent = `Wyświetl ${c.reply_comment_total - 1} odpowiedzi`; let rc = 0;
      b.onclick = async () => {
        const r = await (await fetch(`/api/comment/list/reply/?item_id=${vid}&comment_id=${c.cid}&cursor=${rc}&count=3`)).json();
        rc = r.cursor; b.textContent = r.has_more ? 'Wyświetl więcej' : 'Ukryj';
      };
      document.getElementById('lista').appendChild(b);
    }
  }
  cursor = d.cursor; more = !!d.has_more; busy = false;
}
document.getElementById('lista').addEventListener('scroll', e => {
  const t = e.target; if (t.scrollTop + t.clientHeight >= t.scrollHeight - 50) laduj(); });
laduj();
</script></body></html>"""

STRONA_PROFILU = """<html><body><div id="siatka"></div><div style="height:3000px"></div><script>
let cursor = 0, more = true, busy = false;
async function laduj() { if (!more || busy) return; busy = true;
  const d = await (await fetch(`/api/post/item_list/?cursor=${cursor}&count=3`)).json();
  for (const it of d.itemList) { const a = document.createElement('a');
    a.href = `https://www.tiktok.com/@ja/video/${it.id}`; a.textContent = it.id;
    document.getElementById('siatka').appendChild(a); }
  cursor = d.cursor; more = d.hasMore; busy = false; }
window.addEventListener('scroll', () => laduj()); laduj();
</script></body></html>"""


def obsluga(route):
    url = urlparse(route.request.url)
    q = {k: v[0] for k, v in parse_qs(url.query).items()}
    if url.path.startswith("/api/comment/list/reply"):
        lista = DANE[q["item_id"]][1][q["comment_id"]]
        c = int(q.get("cursor", 0))
        body = {"status_code": 0, "comments": lista[c:c + 3], "cursor": c + 3, "has_more": int(c + 3 < len(lista))}
    elif url.path.startswith("/api/comment/list"):
        top, odp = DANE[q["aweme_id"]]
        c = int(q.get("cursor", 0))
        part = [dict(t, reply_comment=odp[t["cid"]][:1]) for t in top[c:c + 20]]
        body = {"status_code": 0, "comments": part, "cursor": c + 20, "has_more": int(c + 20 < len(top)),
                "total": len(top) + sum(len(v) for v in odp.values())}
    elif url.path.startswith("/api/post/item_list"):
        ids = [PRZYPIETY] + sorted((v for v in FILMY if v != PRZYPIETY), key=lambda v: -FILMY[v])
        c = int(q.get("cursor", 0))
        items = [{"id": v, "createTime": FILMY[v], "author": {"uniqueId": "ja"}, "isPinnedItem": v == PRZYPIETY,
                  "stats": {"commentCount": len(DANE[v][0]) + sum(len(x) for x in DANE[v][1].values())}}
                 for v in ids[c:c + 3]]
        body = {"itemList": items, "cursor": c + 3, "hasMore": c + 3 < len(ids)}
    elif "/video/" in url.path:
        vid = url.path.rsplit("/", 1)[-1]
        top, odp = DANE[vid]
        ssr = {"__DEFAULT_SCOPE__": {"webapp.video-detail": {"itemInfo": {"itemStruct": {
            "createTime": FILMY[vid], "desc": "film", "stats": {"commentCount": len(top) + sum(len(v) for v in odp.values())}}}}}}
        return route.fulfill(status=200, content_type="text/html", body=STRONA_FILMU % (json.dumps(ssr), vid))
    elif url.path.startswith("/@ja"):
        return route.fulfill(status=200, content_type="text/html", body=STRONA_PROFILU)
    else:
        return route.fulfill(status=200, content_type="text/html", body="<html><body>TikTok (symulacja)</body></html>")
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body))


def test_calosc():
    tmp = Path(tempfile.mkdtemp())
    try:
        glowny.FOLDER, glowny.USTAWIENIA = tmp, tmp / "ustawienia.json"
        glowny.DANE, glowny.KOMENTARZE = tmp / "dane", tmp / "dane" / "komentarze"
        glowny.PLIK_FILMOW, glowny.WYNIKI = tmp / "dane" / "filmy.json", tmp / "wyniki"
        cfg = {"profil": "https://www.tiktok.com/@ja", "film_konkursowy": f"https://www.tiktok.com/@ja/video/{KONKURSOWY}",
               "start": "2026-10-01 18:00", "koniec": "2026-10-15 23:59", "strefa_czasowa": "Europe/Warsaw",
               "tryb_uczestnikow": "slowa_kluczowe", "slowa_kluczowe": glowny.DOMYSLNE_SLOWA,
               "licz_odpowiedzi": True, "liczba_zwyciezcow": 2, "max_minut_na_film": 3}
        glowny.USTAWIENIA.write_text(json.dumps(cfg), encoding="utf-8")
        glowny.pytaj = lambda t: ""
        tiktok.pauza = lambda a, b: __import__("time").sleep(0.3)
        oryg = tiktok.uruchom_przegladarke

        def z_symulacja(folder):
            pw, ctx = oryg(folder)
            ctx.route("https://www.tiktok.com/**", obsluga)
            return pw, ctx

        tiktok.uruchom_przegladarke = z_symulacja
        glowny.main(["--bez-pytan"])

        filmy = json.loads(glowny.PLIK_FILMOW.read_text(encoding="utf-8"))
        ids = {f["video_id"] for f in filmy}
        oczekiwane = {v for v, t in FILMY.items() if START_TS <= t <= START_TS + 15 * DZIEN}
        assert ids == oczekiwane, (ids, oczekiwane)
        for f in filmy:
            assert f["status"] == "KOMPLETNY", f
            assert f["pobrane"] == f["zgloszona_liczba"], f
        assert (glowny.WYNIKI / "wyniki_konkursu.xlsx").exists()
        assert (glowny.WYNIKI / "csv" / "4_ranking.csv").exists()
        from openpyxl import load_workbook
        wb = load_workbook(glowny.WYNIKI / "wyniki_konkursu.xlsx")
        print("Arkusze:", wb.sheetnames)
        print("OK - symulacja zakończona poprawnie")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_calosc()
