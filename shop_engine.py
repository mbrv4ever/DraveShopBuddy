# -*- coding: utf-8 -*-
# shop_engine.py - zoekmotor van DraveShopBuddy.
# Copyright (C) 2026 Dravenlock (Roger & Claudio). Vrije software onder de GNU GPL v3.0.
"""Zoekt producten en prijzen op openbare prijsvergelijkers.

Eerlijk en netjes:
- De app zegt wie hij is (eigen User-Agent) en doet maar een paar verzoeken per zoekopdracht.
- Alleen pagina's die volgens robots.txt mogen. Blokkeert een site, dan slaan we hem over
  (geen omzeilen) en meldt de app "niet bereikbaar".
- Er gaat niets van de gebruiker mee, alleen de zoekterm.

Bronnen:
- Kieskeurig.nl  (hoofdbron: laagste prijs + prijs per winkel)
- Beslist.nl     (extra bron, als hij bereikbaar is)
Prijzen komen uit de schema.org-gegevens (ld+json) die de sites zelf in hun pagina zetten.
"""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

VERSIE = "0.1.0"
UA = "DraveShopBuddy/%s (+https://dravenlock.nl; prijsvergelijker voor thuisgebruik)" % VERSIE
TIMEOUT = 15

BRONNEN = ("Kieskeurig", "Beslist")

# knoppen "ook kijken bij" (opent de browser, de app haalt hier zelf niets op)
OOK_BIJ = [
    ("bol", "https://www.bol.com/nl/nl/s/?searchtext=%s"),
    ("Coolblue", "https://www.coolblue.nl/zoeken?query=%s"),
    ("Tweakers", "https://tweakers.net/pricewatch/zoeken/?keyword=%s"),
    ("Amazon.nl", "https://www.amazon.nl/s?k=%s"),
    ("MediaMarkt", "https://www.mediamarkt.nl/nl/search.html?query=%s"),
    ("Kruidvat", "https://www.kruidvat.nl/search?q=%s"),
]


class Geblokkeerd(Exception):
    """De site weigert automatische verzoeken; we omzeilen dat niet."""


def _get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.5",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as f:
            code = f.getcode()
            data = f.read()
            eind = f.geturl()
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 429, 503):
            raise Geblokkeerd(str(e.code))
        raise
    if code == 202 or not data:
        raise Geblokkeerd(str(code))
    return eind, data.decode("utf-8", "ignore")


def _ld_json(html):
    for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            yield json.loads(m.group(1))
        except Exception:
            continue


def _loop(obj, type_):
    st = [obj]
    while st:
        x = st.pop()
        if isinstance(x, list):
            st.extend(x)
        elif isinstance(x, dict):
            t = x.get("@type")
            if t == type_ or (isinstance(t, list) and type_ in t):
                yield x
            st.extend(v for v in x.values() if isinstance(v, (dict, list)))


def _getal(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    s = re.sub(r"[^\d,.\-]", "", str(v))
    if "," in s and s.rfind(",") > s.rfind("."):
        s = s.replace(".", "").replace(",", ".")      # 1.299,00 -> 1299.00
    else:
        s = s.replace(",", "")                        # 1,299.00 -> 1299.00
    try:
        return round(float(s), 2)
    except Exception:
        return None


def _afbeelding(p):
    img = p.get("image")
    if isinstance(img, list):
        img = img[0] if img else None
    if isinstance(img, dict):
        img = img.get("url")
    return img if isinstance(img, str) else None


def _product_uit(p, bron, url_fallback=""):
    """Zet een schema.org Product om naar ons eigen dict."""
    o = p.get("offers") or {}
    if isinstance(o, list):
        prijzen = [_getal(x.get("price")) for x in o if isinstance(x, dict)]
        prijzen = [x for x in prijzen if x is not None]
        laag, hoog, n = (min(prijzen), max(prijzen), len(prijzen)) if prijzen else (None, None, 0)
    else:
        laag = _getal(o.get("lowPrice")) or _getal(o.get("price"))
        hoog = _getal(o.get("highPrice")) or laag
        n = o.get("offerCount") or (1 if laag is not None else 0)
    merk = p.get("brand")
    if isinstance(merk, dict):
        merk = merk.get("name")
    return {
        "naam": (p.get("name") or "").strip(),
        "merk": merk or "",
        "prijs": laag,
        "hoog": hoog,
        "winkels": int(n or 0),
        "bron": bron,
        "url": p.get("url") or url_fallback,
        "img": _afbeelding(p),
        "ean": p.get("gtin13") or p.get("gtin") or "",
    }


# ------------------------------------------------------------------ zoeken
def _zoek_kieskeurig(q, pagina=1):
    url = "https://www.kieskeurig.nl/search?q=%s" % urllib.parse.quote_plus(q)
    eind, html = _get(url)
    if pagina > 1:
        basis = eind.split("#")[0]
        basis = re.sub(r"([?&])page=\d+&?", r"\1", basis).rstrip("?&")
        teken = "&" if "?" in basis else "?"
        eind, html = _get("%s%spage=%d" % (basis, teken, pagina))
    uit = []
    for d in _ld_json(html):
        for lijst in _loop(d, "ItemList"):
            for e in lijst.get("itemListElement", []):
                p = e.get("item") if isinstance(e, dict) else None
                if isinstance(p, dict) and p.get("name"):
                    uit.append(_product_uit(p, "Kieskeurig", e.get("url", "")))
    return uit


def _zoek_beslist(q, pagina=1):
    url = "https://www.beslist.nl/products/r/%s/" % urllib.parse.quote(q)
    if pagina > 1:
        url += "page_%d/" % pagina
    eind, html = _get(url)
    uit = []
    for d in _ld_json(html):
        for lijst in _loop(d, "ItemList"):
            for e in lijst.get("itemListElement", []):
                p = e.get("item") if isinstance(e, dict) else None
                if isinstance(p, dict) and p.get("name") and p.get("offers"):
                    uit.append(_product_uit(p, "Beslist", p.get("url", "")))
    return uit


_ZOEKERS = {"Kieskeurig": _zoek_kieskeurig, "Beslist": _zoek_beslist}


def zoek(q, bronnen=BRONNEN, pagina=1):
    """Geeft (resultaten, meldingen). meldingen = {bron: 'ok'|'geblokkeerd'|'fout: ...'}"""
    q = (q or "").strip()
    res, meld = [], {}
    if not q:
        return res, meld
    for b in bronnen:
        f = _ZOEKERS.get(b)
        if not f:
            continue
        try:
            r = f(q, pagina)
            res.extend(r)
            meld[b] = "ok (%d)" % len(r)
        except Geblokkeerd:
            meld[b] = "geblokkeerd"
        except Exception as e:
            meld[b] = "fout: %s" % e.__class__.__name__
    # dubbelen (zelfde EAN of zelfde naam) samenvoegen, laagste prijs houden
    gezien = {}
    for r in res:
        sleutel = r["ean"] or re.sub(r"\W+", "", r["naam"].lower())[:60]
        oud = gezien.get(sleutel)
        if oud is None or (r["prijs"] is not None and (oud["prijs"] is None or r["prijs"] < oud["prijs"])):
            if oud is not None:
                r["winkels"] = max(r["winkels"], oud["winkels"])
            gezien[sleutel] = r
    return list(gezien.values()), meld


# ------------------------------------------------------------------ productpagina
def product(url):
    """Haalt een productpagina op: naam, laagste prijs en (als de site het geeft) prijs per winkel."""
    eind, html = _get(url)
    bron = "Kieskeurig" if "kieskeurig." in eind else ("Beslist" if "beslist." in eind else urllib.parse.urlparse(eind).netloc)
    beste = None
    for d in _ld_json(html):
        for p in _loop(d, "Product"):
            if p.get("offers"):
                beste = p
                break
        if beste:
            break
    if not beste:
        return _meta_prijs(html, eind, bron)
    info = _product_uit(beste, bron, eind)
    winkels = []
    o = beste.get("offers") or {}
    lijst = o.get("offers") if isinstance(o, dict) else o
    for x in (lijst or []):
        if not isinstance(x, dict):
            continue
        s = x.get("seller") or {}
        naam = s.get("name") if isinstance(s, dict) else str(s)
        pr = _getal(x.get("price"))
        if pr is None:
            continue
        winkels.append({
            "winkel": (naam or "?").replace("\\u0026", "&"),
            "prijs": pr,
            "voorraad": "InStock" in str(x.get("availability", "")),
            "url": x.get("url") or eind,
        })
    winkels.sort(key=lambda w: w["prijs"])
    info["aanbod"] = winkels
    if winkels:
        info["prijs"] = winkels[0]["prijs"]
        info["winkels"] = max(info["winkels"], len(winkels))
    return info


def _meta_prijs(html, url, bron):
    """Reserve: prijs uit meta-tags (product:price:amount, og:price:amount, itemprop=price)."""
    pr = None
    for pat in (r'<meta[^>]+(?:property|name)=["\'](?:product|og):price:amount["\'][^>]*content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\'](?:product|og):price:amount',
                r'itemprop=["\']price["\'][^>]*content=["\']([^"\']+)',
                r'content=["\']([^"\']+)["\'][^>]*itemprop=["\']price["\']'):
        m = re.search(pat, html, re.I)
        if m:
            pr = _getal(re.sub(r"[^\d,.]", "", m.group(1)))
            if pr is not None:
                break
    if pr is None:
        return None
    t = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    naam = re.sub(r"\s+", " ", t.group(1)).strip() if t else url
    return {"naam": naam, "merk": "", "prijs": pr, "hoog": pr, "winkels": 1, "bron": bron,
            "url": url, "img": None, "ean": "", "aanbod": []}


def prijs_nu(url):
    """Alleen de laagste prijs (voor de prijswachter). None als het niet lukt."""
    p = product(url)
    return (p or {}).get("prijs"), p


def wacht_netjes(sec=3.0):
    """Kleine pauze tussen verzoeken van de prijswachter (vriendelijk voor de sites)."""
    time.sleep(sec)


if __name__ == "__main__":
    import sys
    r, m = zoek(" ".join(sys.argv[1:]) or "zeep")
    print(m)
    for x in sorted(r, key=lambda x: x["prijs"] or 1e9)[:10]:
        print("%8s  %-50s %s (%d winkels)" % (x["prijs"], x["naam"][:50], x["bron"], x["winkels"]))
