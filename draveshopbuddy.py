# -*- coding: utf-8 -*-
# DraveShopBuddy - zoek de laagste prijs, met prijswachter.
# Copyright (C) 2026 Dravenlock (Roger & Claudio). Vrije software onder de GNU GPL v3.0.
"""DraveShopBuddy

Een zoekmachine voor de laagste prijs:
- Prijsvergelijker: zoekt bij Kieskeurig.nl (honderden webwinkels) en Beslist.nl,
  goedkoopste eerst, met per product de prijs per winkel.
- Heel internet: een ingebouwde browser (Google Shopping, DuckDuckGo, Bing ...).
  Op elke winkelpagina: "Volg deze prijs".
- Prijswachter: je volglijst met doelprijs. Kijkt alleen als de app open staat
  (bij het starten en daarna elke paar uur). Zakt de prijs onder je doel: melding + geluid.

Alle gegevens staan naast de app in de map DraveShopBuddy-data (portable).
"""
import datetime
import hashlib
import json
import locale
import os
import sys
import threading
import traceback
import urllib.parse
import urllib.request
import webbrowser

VERSIE = "0.1.1"
APP = "DraveShopBuddy"


def _base():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _res(*parts):
    base = getattr(sys, "_MEIPASS", None) or _base()
    p = os.path.join(base, *parts)
    if not os.path.exists(p):
        p = os.path.join(_base(), *parts)
    return p


DATA = os.path.join(_base(), "DraveShopBuddy-data")
IMG = os.path.join(DATA, "img")
WEB = os.path.join(DATA, "browser")
for _m in (DATA, IMG, WEB):
    try:
        os.makedirs(_m, exist_ok=True)
    except Exception:
        pass
WACHTER = os.path.join(DATA, "prijswachter.json")
INSTEL = os.path.join(DATA, "instellingen.json")
LOG = os.path.join(DATA, "error.log")


def _log_fout(tekst):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), tekst))
    except Exception:
        pass


def _excepthook(t, v, tb):
    _log_fout("".join(traceback.format_exception(t, v, tb)))
    sys.__excepthook__(t, v, tb)


sys.excepthook = _excepthook

# QtWebEngine: profielmap in de app-map (cookies/toestemming blijven bewaard, niet in AppData)
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-logging")

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl, QRectF, QPointF, QObject
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QPen, QColor, QFont, QAction, QDesktopServices
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QPushButton,
                             QComboBox, QHBoxLayout, QVBoxLayout, QFrame, QTabWidget, QScrollArea,
                             QSystemTrayIcon, QMenu, QDialog, QDoubleSpinBox,
                             QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QAbstractItemView,
                             QCheckBox)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage

import shop_engine as se

# ------------------------------------------------------------------ taal
try:
    _TAAL = (locale.getlocale()[0] or locale.getdefaultlocale()[0] or "nl")
except Exception:
    _TAAL = "nl"
NL = _TAAL.lower().startswith(("nl", "dutch"))

TX = {
    "zoek_hint": ("Wat zoek je? Bijvoorbeeld: dvd speler, zeep, airfryer ...",
                  "What are you looking for? For example: dvd player, soap, air fryer ..."),
    "zoek": ("Zoek", "Search"),
    "tab_vergelijk": ("💰  Prijsvergelijker", "💰  Price comparison"),
    "tab_web": ("🌐  Heel internet", "🌐  Whole internet"),
    "tab_wacht": ("👁  Prijswachter", "👁  Price watcher"),
    "sorteer": ("Sorteer:", "Sort:"),
    "goedkoop": ("Goedkoopste eerst", "Cheapest first"),
    "duur": ("Duurste eerst", "Most expensive first"),
    "winkels_meest": ("Meeste winkels", "Most shops"),
    "max": ("Max. prijs €", "Max. price €"),
    "geen_max": ("geen", "none"),
    "meer": ("Meer resultaten laden", "Load more results"),
    "bezig": ("Bezig met zoeken ...", "Searching ..."),
    "niets": ("Niets gevonden. Probeer een ander woord, of kijk bij 'Heel internet'.",
              "Nothing found. Try another word, or look at 'Whole internet'."),
    "vanaf": ("vanaf", "from"),
    "winkel1": ("winkel", "shop"),
    "winkelsN": ("winkels", "shops"),
    "btn_winkels": ("🏪  Winkels", "🏪  Shops"),
    "btn_volg": ("👁  Volg prijs", "👁  Watch price"),
    "btn_open": ("🌐  Bekijk", "🌐  View"),
    "ook_bij": ("Ook kijken bij:", "Also look at:"),
    "bronnen": ("Bronnen:", "Sources:"),
    "geblokkeerd": ("niet bereikbaar", "not reachable"),
    "web_volg": ("👁  Volg deze prijs", "👁  Watch this price"),
    "web_extern": ("Open in mijn browser", "Open in my browser"),
    "web_motor": ("Zoek op:", "Search with:"),
    "geen_prijs": ("Op deze pagina vond ik geen prijs.\nOpen de pagina van één product (niet een lijst) en probeer opnieuw.",
                   "I found no price on this page.\nOpen the page of a single product (not a list) and try again."),
    "volg_titel": ("Prijs volgen", "Watch price"),
    "volg_nu": ("Prijs nu:", "Price now:"),
    "volg_doel": ("Waarschuw mij als de prijs lager is dan:", "Warn me when the price is below:"),
    "volg_ok": ("Toevoegen aan prijswachter", "Add to price watcher"),
    "annuleer": ("Annuleren", "Cancel"),
    "k_product": ("Product", "Product"),
    "k_nu": ("Nu", "Now"),
    "k_doel": ("Doel", "Target"),
    "k_laagst": ("Laagste ooit", "Lowest ever"),
    "k_gekeken": ("Laatst gekeken", "Last checked"),
    "k_status": ("Status", "Status"),
    "w_nu": ("🔄  Nu controleren", "🔄  Check now"),
    "w_open": ("🌐  Open", "🌐  Open"),
    "w_doel": ("🎯  Doelprijs wijzigen", "🎯  Change target"),
    "w_weg": ("🗑  Verwijderen", "🗑  Remove"),
    "w_elke": ("Controleer elke:", "Check every:"),
    "uur": ("uur", "hours"),
    "w_leeg": ("Je volglijst is nog leeg. Zoek iets en klik op 'Volg prijs'.",
               "Your watch list is empty. Search something and click 'Watch price'."),
    "w_bezig": ("Prijzen controleren ...", "Checking prices ..."),
    "w_klaar": ("Prijzen gecontroleerd om %s.", "Prices checked at %s."),
    "w_volgende": ("Volgende controle om %s (alleen als de app open staat).",
                   "Next check at %s (only while the app is open)."),
    "st_onder": ("🔔 ONDER JE DOEL!", "🔔 BELOW TARGET!"),
    "st_ok": ("wacht nog", "waiting"),
    "st_lager": ("⬇ lager", "⬇ lower"),
    "st_hoger": ("⬆ hoger", "⬆ higher"),
    "st_fout": ("kon niet kijken", "could not check"),
    "alarm_titel": ("Prijsalarm!", "Price alert!"),
    "alarm_tekst": ("%s is nu € %s (jouw doel: € %s)", "%s is now € %s (your target: € %s)"),
    "geschiedenis": ("Prijsverloop", "Price history"),
    "toegevoegd": ("Toegevoegd aan je prijswachter: %s", "Added to your price watcher: %s"),
    "winkels_titel": ("Prijs per winkel", "Price per shop"),
    "op_voorraad": ("op voorraad", "in stock"),
    "niet_voorraad": ("niet op voorraad", "out of stock"),
    "laden": ("Winkels ophalen ...", "Loading shops ..."),
    "snelgids": ("📖  Snelgids", "📖  Quick guide"),
    "toon": ("Venster tonen", "Show window"),
    "stop": ("Afsluiten", "Quit"),
    "geluid": ("Geluid bij alarm", "Sound on alert"),
}


def T(k):
    v = TX.get(k, (k, k))
    return v[0] if NL else v[1]


def euro(x):
    if x is None:
        return "?"
    s = "%.2f" % x
    return s.replace(".", ",")


# ------------------------------------------------------------------ kleuren (Dravenlock)
BG = "#16131f"
PANEEL = "#1f1a2c"
KAART = "#262036"
RAND = "#4a3d66"
ACCENT = "#7F77DD"
LICHT = "#b59cff"
TEKST = "#efeaff"
SUB = "#b8afd6"
GOED = "#5fd38d"
ROOD = "#ff6b81"
GOUD = "#ffc857"

STIJL = """
* { font-family: 'Segoe UI', Arial; font-size: 15px; color: %(t)s; }
QMainWindow, QWidget#wortel { background: %(bg)s; }
QTabWidget::pane { border: 2px solid %(r)s; border-radius: 10px; background: %(p)s; top: -2px; }
QTabBar::tab { background: %(k)s; padding: 12px 26px; margin-right: 6px; border: 2px solid %(r)s;
               border-bottom: none; border-top-left-radius: 10px; border-top-right-radius: 10px;
               font-size: 17px; font-weight: 600; color: %(s)s; }
QTabBar::tab:selected { background: %(a)s; color: white; }
QLineEdit { background: %(k)s; border: 2px solid %(r)s; border-radius: 10px; padding: 8px 12px; }
QLineEdit#zoekbalk { font-size: 22px; padding: 12px 22px; border-radius: 26px; border: 3px solid %(a)s; }
QPushButton { background: %(k)s; border: 2px solid %(r)s; border-radius: 10px; padding: 9px 16px; font-weight: 600; }
QPushButton:hover { background: %(r)s; }
QPushButton#groot { background: %(a)s; color: white; font-size: 20px; padding: 12px 28px; border-radius: 26px; border: none; }
QPushButton#groot:hover { background: %(l)s; color: %(bg)s; }
QPushButton#volg { background: %(goud)s; color: %(bg)s; border: none; font-size: 17px; padding: 10px 20px; }
QPushButton#volg:hover { background: white; }
QComboBox, QDoubleSpinBox { background: %(k)s; border: 2px solid %(r)s; border-radius: 8px; padding: 6px 10px; }
QComboBox QAbstractItemView { background: %(k)s; selection-background-color: %(a)s; }
QFrame#kaart { background: %(k)s; border: 2px solid %(r)s; border-radius: 14px; }
QFrame#kaart:hover { border: 2px solid %(l)s; }
QScrollArea { border: none; background: transparent; }
QWidget#lijst { background: %(p)s; }
QTableWidget { background: %(k)s; gridline-color: %(r)s; border: 2px solid %(r)s; border-radius: 10px;
               font-size: 16px; selection-background-color: %(a)s; }
QHeaderView::section { background: %(p)s; padding: 8px; border: none; border-bottom: 2px solid %(r)s;
                       font-weight: 700; font-size: 15px; }
QLabel#sub { color: %(s)s; }
QLabel#prijs { color: %(goed)s; font-size: 24px; font-weight: 800; }
QLabel#titel { font-size: 17px; font-weight: 700; }
QStatusBar { background: %(p)s; font-size: 14px; }
QToolTip { background: %(k)s; color: %(t)s; border: 1px solid %(r)s; }
""" % {"bg": BG, "p": PANEEL, "k": KAART, "r": RAND, "a": ACCENT, "l": LICHT, "t": TEKST, "s": SUB,
       "goed": GOED, "goud": GOUD}


# ------------------------------------------------------------------ opslag
def _lees(pad, standaard):
    try:
        with open(pad, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return standaard


def _schrijf(pad, data):
    try:
        tmp = pad + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, pad)
    except Exception as e:
        _log_fout("opslaan %s: %s" % (pad, e))


# ------------------------------------------------------------------ JavaScript: prijs van een webpagina lezen
JS_PRIJS = r"""
(function(){
 function num(v){ if(v===null||v===undefined) return null; if(typeof v==='number') return v;
   v=String(v).replace(/[^\d,.\-]/g,'');
   if(v.indexOf(',')>-1 && v.lastIndexOf(',')>v.lastIndexOf('.')) v=v.replace(/\./g,'').replace(',','.'); else v=v.replace(/,/g,'');
   var n=parseFloat(v); return isNaN(n)?null:n; }
 var out={naam:document.title||'', prijs:null, img:null, url:location.href};
 function zet(x){ var o=x.offers; if(Array.isArray(o)) o=o[0]; if(!o) return;
   var p=num(o.lowPrice!==undefined?o.lowPrice:o.price);
   if(p===null && o.priceSpecification){ var ps=o.priceSpecification; if(Array.isArray(ps)) ps=ps[0]; p=num(ps.price); }
   if(p!==null){ out.prijs=p; if(x.name) out.naam=x.name; var im=x.image; if(Array.isArray(im)) im=im[0]; if(im && typeof im==='object') im=im.url; out.img=im||null; } }
 function walk(x){ if(!x||out.prijs!==null) return; if(Array.isArray(x)){ for(var i=0;i<x.length;i++) walk(x[i]); return; }
   if(typeof x!=='object') return; var t=x['@type'];
   if((t==='Product'||(Array.isArray(t)&&t.indexOf('Product')>-1)) && x.offers){ zet(x); }
   for(var k in x){ if(x[k] && typeof x[k]==='object') walk(x[k]); } }
 var s=document.querySelectorAll('script[type="application/ld+json"]');
 for(var i=0;i<s.length;i++){ try{ walk(JSON.parse(s[i].textContent)); }catch(e){} }
 if(out.prijs===null){
   var m=document.querySelector('meta[property="product:price:amount"],meta[property="og:price:amount"],meta[itemprop="price"],[itemprop="price"]');
   if(m){ out.prijs=num(m.getAttribute('content')||m.textContent); }
 }
 if(!out.img){ var og=document.querySelector('meta[property="og:image"]'); if(og) out.img=og.getAttribute('content'); }
 return JSON.stringify(out);
})()
"""

ZOEKMOTOREN = [
    ("Google Shopping", "https://www.google.com/search?tbm=shop&hl=nl&gl=nl&q=%s"),
    ("Google", "https://www.google.com/search?hl=nl&gl=nl&q=%s"),
    ("DuckDuckGo", "https://duckduckgo.com/?kl=nl-nl&ia=shopping&q=%s"),
    ("Bing Shopping", "https://www.bing.com/shop?cc=nl&q=%s"),
    ("Kieskeurig", "https://www.kieskeurig.nl/search?q=%s"),
    ("Beslist", "https://www.beslist.nl/products/r/%s/"),
    ("Tweakers", "https://tweakers.net/pricewatch/zoeken/?keyword=%s"),
]


def img_pad(url):
    return os.path.join(IMG, hashlib.md5(url.encode("utf-8", "ignore")).hexdigest()[:16] + ".img")


# ------------------------------------------------------------------ achtergrond-werkers
class ZoekWerker(QThread):
    klaar = pyqtSignal(list, dict, int)

    def __init__(self, q, pagina):
        super().__init__()
        self.q, self.pagina = q, pagina

    def run(self):
        try:
            r, m = se.zoek(self.q, pagina=self.pagina)
        except Exception as e:
            r, m = [], {"?": str(e)}
        self.klaar.emit(r, m, self.pagina)


class ProductWerker(QThread):
    klaar = pyqtSignal(object)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            p = se.product(self.url)
        except Exception as e:
            p = {"fout": str(e)}
        self.klaar.emit(p)


class PlaatjesLader(QObject):
    """Haalt productfoto's op de achtergrond op (met cache in de datamap)."""
    klaar = pyqtSignal(str, str)   # url, bestandspad

    def haal(self, url):
        if not url:
            return
        pad = img_pad(url)
        if os.path.exists(pad) and os.path.getsize(pad) > 0:
            self.klaar.emit(url, pad)
            return

        def werk():
            try:
                req = urllib.request.Request(url, headers={"User-Agent": se.UA})
                with urllib.request.urlopen(req, timeout=12) as f:
                    data = f.read(3_000_000)
                with open(pad, "wb") as f:
                    f.write(data)
                self.klaar.emit(url, pad)
            except Exception:
                pass
        threading.Thread(target=werk, daemon=True).start()


class Pagina(QWebEnginePage):
    """Links die een nieuw venster/tabblad willen (target=_blank, zoals bij Google)
    openen we gewoon in hetzelfde browservenster van de app."""

    def __init__(self, profiel, view):
        super().__init__(profiel, view)
        self._view = view
        self._tijdelijk = []

    def createWindow(self, soort):
        tijdelijk = QWebEnginePage(self.profile(), self)
        self._tijdelijk.append(tijdelijk)

        def ga(url, t=tijdelijk):
            if url.isValid() and url.toString() not in ("", "about:blank"):
                self._view.setUrl(url)
                try:
                    t.urlChanged.disconnect()
                except Exception:
                    pass
                if t in self._tijdelijk:
                    self._tijdelijk.remove(t)
                t.deleteLater()
        tijdelijk.urlChanged.connect(ga)
        return tijdelijk


# ------------------------------------------------------------------ resultaatkaart
class Kaart(QFrame):
    def __init__(self, app, r):
        super().__init__()
        self.setObjectName("kaart")
        self.app, self.r = app, r
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 12, 14, 12)
        h.setSpacing(16)
        self.foto = QLabel()
        self.foto.setFixedSize(110, 110)
        self.foto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.foto.setStyleSheet("background: white; border-radius: 10px;")
        h.addWidget(self.foto)
        mid = QVBoxLayout()
        t = QLabel(r["naam"])
        t.setObjectName("titel")
        t.setWordWrap(True)
        mid.addWidget(t)
        n = r.get("winkels") or 0
        info = "%s  ·  %d %s  ·  %s" % (r.get("merk") or "", n, T("winkel1") if n == 1 else T("winkelsN"), r["bron"])
        s = QLabel(info.strip(" ·"))
        s.setObjectName("sub")
        mid.addWidget(s)
        mid.addStretch()
        h.addLayout(mid, 1)
        rechts = QVBoxLayout()
        rechts.setSpacing(6)
        vanaf = QLabel(T("vanaf"))
        vanaf.setObjectName("sub")
        vanaf.setAlignment(Qt.AlignmentFlag.AlignRight)
        p = QLabel("€ " + euro(r.get("prijs")))
        p.setObjectName("prijs")
        p.setAlignment(Qt.AlignmentFlag.AlignRight)
        rechts.addWidget(vanaf)
        rechts.addWidget(p)
        knoppen = QHBoxLayout()
        b1 = QPushButton(T("btn_winkels"))
        b1.clicked.connect(lambda: app.toon_winkels(r))
        b2 = QPushButton(T("btn_volg"))
        b2.clicked.connect(lambda: app.volg_dialoog(r["naam"], r.get("prijs"), r["url"], r.get("img")))
        b3 = QPushButton(T("btn_open"))
        b3.clicked.connect(lambda: app.open_web(r["url"]))
        for b in (b1, b2, b3):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            knoppen.addWidget(b)
        rechts.addLayout(knoppen)
        h.addLayout(rechts)
        if r.get("img"):
            app.plaatjes.haal(r["img"])

    def zet_foto(self, pad):
        pm = QPixmap(pad)
        if not pm.isNull():
            self.foto.setPixmap(pm.scaled(104, 104, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation))


# ------------------------------------------------------------------ prijsgrafiek
class Grafiek(QWidget):
    def __init__(self):
        super().__init__()
        self.punten, self.doel = [], None
        self.setMinimumHeight(170)

    def zet(self, punten, doel):
        self.punten, self.doel = punten, doel
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(70, 18, -20, -34)
        p.fillRect(self.rect(), QColor(KAART))
        p.setPen(QColor(SUB))
        p.setFont(QFont("Segoe UI", 11))
        if len(self.punten) < 1:
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, T("geschiedenis") + ": -")
            return
        ws = [w for _, w in self.punten] + ([self.doel] if self.doel else [])
        lo, hi = min(ws), max(ws)
        if hi - lo < 0.01:
            lo, hi = lo * 0.95, hi * 1.05 + 0.01
        def xy(i, w):
            x = r.left() + (r.width() * i / max(1, len(self.punten) - 1))
            y = r.bottom() - (w - lo) / (hi - lo) * r.height()
            return QPointF(x, y)
        p.setPen(QPen(QColor(RAND), 1))
        for k in range(3):
            w = lo + (hi - lo) * k / 2
            y = r.bottom() - r.height() * k / 2
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
            p.setPen(QColor(SUB))
            p.drawText(QRectF(0, y - 10, 64, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "€ " + euro(w))
            p.setPen(QPen(QColor(RAND), 1))
        if self.doel:
            y = r.bottom() - (self.doel - lo) / (hi - lo) * r.height()
            p.setPen(QPen(QColor(GOUD), 2, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
        p.setPen(QPen(QColor(LICHT), 3))
        pts = [xy(i, w) for i, (_, w) in enumerate(self.punten)]
        for a, b in zip(pts, pts[1:]):
            p.drawLine(a, b)
        p.setBrush(QColor(LICHT))
        for q in pts:
            p.drawEllipse(q, 4, 4)
        p.setPen(QColor(SUB))
        p.drawText(QRectF(r.left(), r.bottom() + 8, 200, 20), Qt.AlignmentFlag.AlignLeft, self.punten[0][0][:10])
        p.drawText(QRectF(r.right() - 200, r.bottom() + 8, 200, 20), Qt.AlignmentFlag.AlignRight, self.punten[-1][0][:16].replace("T", " "))


# ------------------------------------------------------------------ hoofdvenster
class ShopBuddy(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("%s %s" % (APP, VERSIE))
        ico = _res("assets", "icon.ico")
        if os.path.exists(ico):
            self.setWindowIcon(QIcon(ico))
        self.resize(1280, 900)
        self.instel = _lees(INSTEL, {"uren": 2, "motor": "Google Shopping", "geluid": True})
        self.wacht = _lees(WACHTER, [])
        self.resultaten, self.kaarten, self.werkers = [], {}, []
        self.q, self.pagina = "", 1
        self.plaatjes = PlaatjesLader()
        self.plaatjes.klaar.connect(self._foto_klaar)
        self._bouw()
        self._maak_tray()
        self._vul_wachtlijst()
        # prijswachter: kort na het starten, daarna elke X uur (alleen zolang de app open is)
        self.wtimer = QTimer(self)
        self.wtimer.timeout.connect(self.controleer_alles)
        self._zet_timer()
        QTimer.singleShot(6000, self.controleer_alles)

    # ---------------------------------------------------------- opbouw
    def _bouw(self):
        wortel = QWidget()
        wortel.setObjectName("wortel")
        self.setCentralWidget(wortel)
        v = QVBoxLayout(wortel)
        v.setContentsMargins(18, 14, 18, 8)
        v.setSpacing(12)

        kop = QHBoxLayout()
        logo = QLabel()
        pm = QPixmap(_res("assets", "icon.png"))
        if not pm.isNull():
            logo.setPixmap(pm.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        kop.addWidget(logo)
        naam = QLabel("<span style='font-size:26px;font-weight:800;color:%s'>Drave</span>"
                      "<span style='font-size:26px;font-weight:800;color:%s'>ShopBuddy</span>" % (LICHT, GOUD))
        kop.addWidget(naam)
        kop.addSpacing(18)
        self.zoekbalk = QLineEdit()
        self.zoekbalk.setObjectName("zoekbalk")
        self.zoekbalk.setPlaceholderText(T("zoek_hint"))
        self.zoekbalk.returnPressed.connect(self.zoek)
        self.zoekbalk.setClearButtonEnabled(True)
        kop.addWidget(self.zoekbalk, 1)
        zb = QPushButton("🔍  " + T("zoek"))
        zb.setObjectName("groot")
        zb.setCursor(Qt.CursorShape.PointingHandCursor)
        zb.clicked.connect(self.zoek)
        kop.addWidget(zb)
        gids = QPushButton(T("snelgids"))
        gids.clicked.connect(self._snelgids)
        kop.addWidget(gids)
        v.addLayout(kop)

        self.tabs = QTabWidget()
        v.addWidget(self.tabs, 1)
        self.tabs.addTab(self._bouw_vergelijk(), T("tab_vergelijk"))
        self.tabs.addTab(self._bouw_web(), T("tab_web"))
        self.tabs.addTab(self._bouw_wachter(), T("tab_wacht"))
        self.statusBar().showMessage("Dravenlock · service@dravenlock.nl")

    def _bouw_vergelijk(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        balk = QHBoxLayout()
        balk.addWidget(QLabel(T("sorteer")))
        self.sorteer = QComboBox()
        self.sorteer.addItems([T("goedkoop"), T("duur"), T("winkels_meest")])
        self.sorteer.currentIndexChanged.connect(self._toon_resultaten)
        balk.addWidget(self.sorteer)
        balk.addSpacing(16)
        balk.addWidget(QLabel(T("max")))
        self.maxprijs = QDoubleSpinBox()
        self.maxprijs.setRange(0, 100000)
        self.maxprijs.setDecimals(0)
        self.maxprijs.setSpecialValueText(T("geen_max"))
        self.maxprijs.setSingleStep(10)
        self.maxprijs.valueChanged.connect(self._toon_resultaten)
        balk.addWidget(self.maxprijs)
        balk.addStretch()
        self.bronlabel = QLabel("")
        self.bronlabel.setObjectName("sub")
        balk.addWidget(self.bronlabel)
        v.addLayout(balk)

        ook = QHBoxLayout()
        lab = QLabel(T("ook_bij"))
        lab.setObjectName("sub")
        ook.addWidget(lab)
        for naam, sjabloon in se.OOK_BIJ:
            b = QPushButton(naam)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, s=sjabloon: self._ook_bij(s))
            ook.addWidget(b)
        ook.addStretch()
        v.addLayout(ook)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.lijst = QWidget()
        self.lijst.setObjectName("lijst")
        self.lijstv = QVBoxLayout(self.lijst)
        self.lijstv.setSpacing(10)
        self.lijstv.addStretch()
        self.scroll.setWidget(self.lijst)
        v.addWidget(self.scroll, 1)
        self.meerknop = QPushButton(T("meer"))
        self.meerknop.clicked.connect(self._meer)
        self.meerknop.hide()
        v.addWidget(self.meerknop)
        self.melding = QLabel("")
        self.melding.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.melding.setStyleSheet("font-size: 19px; color: %s; padding: 30px;" % SUB)
        self.lijstv.insertWidget(0, self.melding)
        return w

    def _bouw_web(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(10, 10, 10, 10)
        balk = QHBoxLayout()
        terug = QPushButton("◀")
        verder = QPushButton("▶")
        herlaad = QPushButton("⟳")
        for b in (terug, verder, herlaad):
            b.setFixedWidth(54)
            b.setStyleSheet("font-size: 20px;")
            balk.addWidget(b)
        balk.addWidget(QLabel(T("web_motor")))
        self.motor = QComboBox()
        self.motor.addItems([n for n, _ in ZOEKMOTOREN])
        i = self.motor.findText(self.instel.get("motor", "Google Shopping"))
        self.motor.setCurrentIndex(max(0, i))
        self.motor.currentTextChanged.connect(self._motor_wissel)
        balk.addWidget(self.motor)
        self.adres = QLineEdit()
        self.adres.returnPressed.connect(self._ga_adres)
        balk.addWidget(self.adres, 1)
        volg = QPushButton(T("web_volg"))
        volg.setObjectName("volg")
        volg.setCursor(Qt.CursorShape.PointingHandCursor)
        volg.clicked.connect(self._volg_webpagina)
        balk.addWidget(volg)
        ext = QPushButton(T("web_extern"))
        ext.clicked.connect(lambda: webbrowser.open(self.web.url().toString()))
        balk.addWidget(ext)
        v.addLayout(balk)

        self.profiel = QWebEngineProfile("DraveShopBuddy", self)
        self.profiel.setPersistentStoragePath(WEB)
        self.profiel.setCachePath(os.path.join(WEB, "cache"))
        self.web = QWebEngineView()
        self.web.setPage(Pagina(self.profiel, self.web))
        self.web.urlChanged.connect(lambda u: self.adres.setText(u.toString()))
        terug.clicked.connect(self.web.back)
        verder.clicked.connect(self.web.forward)
        herlaad.clicked.connect(self.web.reload)
        v.addWidget(self.web, 1)
        self.web.setHtml("<body style='background:%s;color:%s;font-family:Segoe UI;font-size:22px;"
                         "display:flex;align-items:center;justify-content:center;height:90vh'>"
                         "<div style='text-align:center'>🔍<br><br>%s</div></body>" % (BG, SUB, T("zoek_hint")))
        # verborgen pagina voor de prijswachter (bij sites die gewone verzoeken weigeren)
        self.stil = QWebEnginePage(self.profiel, self)
        return w

    def _bouw_wachter(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 14, 14, 14)
        balk = QHBoxLayout()
        nu = QPushButton(T("w_nu"))
        nu.setObjectName("groot")
        nu.clicked.connect(self.controleer_alles)
        balk.addWidget(nu)
        balk.addSpacing(16)
        balk.addWidget(QLabel(T("w_elke")))
        self.uren = QComboBox()
        for u in (1, 2, 4, 6, 12):
            self.uren.addItem("%d %s" % (u, T("uur")), u)
        i = self.uren.findData(self.instel.get("uren", 2))
        self.uren.setCurrentIndex(max(0, i))
        self.uren.currentIndexChanged.connect(self._uren_wissel)
        balk.addWidget(self.uren)
        self.geluid = QCheckBox(T("geluid"))
        self.geluid.setChecked(self.instel.get("geluid", True))
        self.geluid.toggled.connect(lambda a: self._instel("geluid", a))
        balk.addWidget(self.geluid)
        balk.addStretch()
        self.wstatus = QLabel("")
        self.wstatus.setObjectName("sub")
        balk.addWidget(self.wstatus)
        v.addLayout(balk)

        self.tabel = QTableWidget(0, 6)
        self.tabel.setHorizontalHeaderLabels([T("k_product"), T("k_nu"), T("k_doel"), T("k_laagst"),
                                              T("k_gekeken"), T("k_status")])
        hh = self.tabel.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for k in range(1, 6):
            hh.setSectionResizeMode(k, QHeaderView.ResizeMode.ResizeToContents)
        self.tabel.verticalHeader().setDefaultSectionSize(44)
        self.tabel.verticalHeader().hide()
        self.tabel.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabel.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabel.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabel.itemSelectionChanged.connect(self._toon_grafiek)
        self.tabel.cellDoubleClicked.connect(lambda r, c: self._w_open())
        v.addWidget(self.tabel, 1)

        knoppen = QHBoxLayout()
        for tekst, f in ((T("w_open"), self._w_open), (T("w_doel"), self._w_doel), (T("w_weg"), self._w_weg)):
            b = QPushButton(tekst)
            b.clicked.connect(f)
            knoppen.addWidget(b)
        knoppen.addStretch()
        v.addLayout(knoppen)
        gl = QLabel(T("geschiedenis"))
        gl.setObjectName("titel")
        v.addWidget(gl)
        self.grafiek = Grafiek()
        v.addWidget(self.grafiek)
        self.leeg = QLabel(T("w_leeg"))
        self.leeg.setObjectName("sub")
        self.leeg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.leeg)
        return w

    # ---------------------------------------------------------- instellingen
    def _instel(self, k, w):
        self.instel[k] = w
        _schrijf(INSTEL, self.instel)

    def _uren_wissel(self):
        self._instel("uren", self.uren.currentData())
        self._zet_timer()

    def _zet_timer(self):
        uren = self.instel.get("uren", 2) or 2
        self.wtimer.start(int(uren * 3600 * 1000))
        self._volgende = datetime.datetime.now() + datetime.timedelta(hours=uren)

    def _motor_wissel(self, naam):
        self._instel("motor", naam)
        if self.q:
            self._laad_web(self.q)

    # ---------------------------------------------------------- zoeken
    def zoek(self):
        q = self.zoekbalk.text().strip()
        if not q:
            return
        self.q, self.pagina = q, 1
        self.resultaten = []
        self._wis_kaarten()
        self.melding.setText("⏳  " + T("bezig"))
        self.melding.show()
        self.meerknop.hide()
        self.bronlabel.setText("")
        self._start_zoek()
        self._laad_web(q)
        if self.tabs.currentIndex() == 2:
            self.tabs.setCurrentIndex(0)

    def _start_zoek(self):
        wk = ZoekWerker(self.q, self.pagina)
        wk.klaar.connect(self._zoek_klaar)
        wk.finished.connect(lambda: self.werkers.remove(wk) if wk in self.werkers else None)
        self.werkers.append(wk)
        wk.start()

    def _meer(self):
        self.pagina += 1
        self.meerknop.setEnabled(False)
        self.meerknop.setText("⏳  " + T("bezig"))
        self._start_zoek()

    def _zoek_klaar(self, res, meld, pagina):
        if pagina != self.pagina:
            return
        bekend = {(r["naam"], r["bron"]) for r in self.resultaten}
        self.resultaten += [r for r in res if (r["naam"], r["bron"]) not in bekend and r.get("prijs") is not None]
        delen = []
        for b, m in meld.items():
            delen.append("%s %s" % (b, "✔" if m.startswith("ok") else "✖ " + T("geblokkeerd")))
        self.bronlabel.setText(T("bronnen") + "  " + "   ".join(delen))
        self.meerknop.setEnabled(True)
        self.meerknop.setText(T("meer"))
        self.meerknop.setVisible(bool(res))
        self._toon_resultaten()

    def _wis_kaarten(self):
        for k in list(self.kaarten.values()):
            for kaart in k:
                kaart.setParent(None)
                kaart.deleteLater()
        self.kaarten = {}

    def _toon_resultaten(self):
        self._wis_kaarten()
        rs = list(self.resultaten)
        mx = self.maxprijs.value()
        if mx > 0:
            rs = [r for r in rs if r["prijs"] is not None and r["prijs"] <= mx]
        i = self.sorteer.currentIndex()
        if i == 0:
            rs.sort(key=lambda r: r["prijs"] if r["prijs"] is not None else 1e12)
        elif i == 1:
            rs.sort(key=lambda r: -(r["prijs"] or 0))
        else:
            rs.sort(key=lambda r: (-(r.get("winkels") or 0), r["prijs"] or 1e12))
        if not rs:
            if self.q:
                self.melding.setText(T("niets"))
            self.melding.show()
            return
        self.melding.hide()
        for n, r in enumerate(rs):
            k = Kaart(self, r)
            self.lijstv.insertWidget(self.lijstv.count() - 1, k)
            self.kaarten.setdefault(r.get("img") or "", []).append(k)
            if r.get("img") and os.path.exists(self._img_pad(r["img"])):
                k.zet_foto(self._img_pad(r["img"]))
        self.scroll.verticalScrollBar().setValue(0) if self.pagina == 1 else None

    def _img_pad(self, url):
        return img_pad(url)

    def _foto_klaar(self, url, pad):
        for k in self.kaarten.get(url, []):
            try:
                k.zet_foto(pad)
            except RuntimeError:
                pass

    def _ook_bij(self, sjabloon):
        q = self.zoekbalk.text().strip() or self.q
        if not q:
            return
        self.open_web(sjabloon % urllib.parse.quote_plus(q))

    # ---------------------------------------------------------- winkels van één product
    def toon_winkels(self, r):
        d = QDialog(self)
        d.setWindowTitle(T("winkels_titel"))
        d.resize(760, 560)
        v = QVBoxLayout(d)
        t = QLabel(r["naam"])
        t.setObjectName("titel")
        t.setWordWrap(True)
        v.addWidget(t)
        info = QLabel("⏳  " + T("laden"))
        info.setObjectName("sub")
        v.addWidget(info)
        tab = QTableWidget(0, 3)
        tab.setHorizontalHeaderLabels([T("winkel1").capitalize(), T("k_nu"), ""])
        tab.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tab.verticalHeader().hide()
        tab.verticalHeader().setDefaultSectionSize(42)
        tab.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        v.addWidget(tab, 1)
        onder = QHBoxLayout()
        bv = QPushButton(T("btn_volg"))
        bv.setObjectName("volg")
        bv.clicked.connect(lambda: (d.accept(), self.volg_dialoog(r["naam"], r.get("prijs"), r["url"], r.get("img"))))
        onder.addWidget(bv)
        onder.addStretch()
        sluit = QPushButton("OK")
        sluit.clicked.connect(d.accept)
        onder.addWidget(sluit)
        v.addLayout(onder)

        def klaar(p):
            if not p or p.get("fout"):
                info.setText("✖  " + T("st_fout"))
                return
            aanbod = p.get("aanbod") or []
            info.setText("%s € %s  ·  %d %s" % (T("vanaf"), euro(p.get("prijs")), len(aanbod) or p.get("winkels", 0), T("winkelsN")))
            r["prijs"] = p.get("prijs") or r.get("prijs")
            for w in aanbod:
                i = tab.rowCount()
                tab.insertRow(i)
                tab.setItem(i, 0, QTableWidgetItem("%s   (%s)" % (w["winkel"], T("op_voorraad") if w["voorraad"] else T("niet_voorraad"))))
                pi = QTableWidgetItem("€ " + euro(w["prijs"]))
                pi.setForeground(QColor(GOED if i == 0 else TEKST))
                tab.setItem(i, 1, pi)
                b = QPushButton(T("btn_open"))
                b.clicked.connect(lambda _=False, u=w["url"]: (d.accept(), self.open_web(u)))
                tab.setCellWidget(i, 2, b)
            tab.resizeColumnsToContents()
            tab.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        wk = ProductWerker(r["url"])
        wk.klaar.connect(klaar)
        self.werkers.append(wk)
        wk.finished.connect(lambda: self.werkers.remove(wk) if wk in self.werkers else None)
        wk.start()
        d.exec()

    # ---------------------------------------------------------- ingebouwde browser
    def _laad_web(self, q):
        sjabloon = dict(ZOEKMOTOREN).get(self.motor.currentText(), ZOEKMOTOREN[0][1])
        if "beslist" in sjabloon:
            q_enc = urllib.parse.quote(q)
        else:
            q_enc = urllib.parse.quote_plus(q)
        self.web.setUrl(QUrl(sjabloon % q_enc))

    def open_web(self, url):
        self.web.setUrl(QUrl(url))
        self.tabs.setCurrentIndex(1)

    def _ga_adres(self):
        t = self.adres.text().strip()
        if not t:
            return
        if "://" not in t:
            if " " in t or "." not in t:
                self.zoekbalk.setText(t)
                self._laad_web(t)
                return
            t = "https://" + t
        self.web.setUrl(QUrl(t))

    def _volg_webpagina(self):
        def klaar(res):
            try:
                d = json.loads(res or "{}")
            except Exception:
                d = {}
            if d.get("prijs") is None:
                QMessageBox.information(self, T("volg_titel"), T("geen_prijs"))
                return
            self.volg_dialoog(d.get("naam") or self.web.title(), d["prijs"], d.get("url") or self.web.url().toString(), d.get("img"))
        self.web.page().runJavaScript(JS_PRIJS, klaar)

    # ---------------------------------------------------------- volgen
    def volg_dialoog(self, naam, prijs, url, img=None):
        d = QDialog(self)
        d.setWindowTitle(T("volg_titel"))
        d.setMinimumWidth(620)
        v = QVBoxLayout(d)
        t = QLabel(naam)
        t.setObjectName("titel")
        t.setWordWrap(True)
        v.addWidget(t)
        p = QLabel("%s  € %s" % (T("volg_nu"), euro(prijs)))
        p.setObjectName("prijs")
        v.addWidget(p)
        v.addSpacing(8)
        v.addWidget(QLabel(T("volg_doel")))
        doel = QDoubleSpinBox()
        doel.setRange(0.01, 1000000)
        doel.setDecimals(2)
        doel.setPrefix("€ ")
        doel.setStyleSheet("font-size: 22px; padding: 8px;")
        doel.setValue(round((prijs or 10) * 0.9, 2))
        v.addWidget(doel)
        k = QHBoxLayout()
        ok = QPushButton(T("volg_ok"))
        ok.setObjectName("volg")
        ok.clicked.connect(d.accept)
        nee = QPushButton(T("annuleer"))
        nee.clicked.connect(d.reject)
        k.addWidget(ok)
        k.addStretch()
        k.addWidget(nee)
        v.addLayout(k)
        if d.exec() != QDialog.DialogCode.Accepted:
            return
        nu = datetime.datetime.now().isoformat(timespec="minutes")
        for item in self.wacht:
            if item["url"] == url:
                item["doel"] = doel.value()
                break
        else:
            self.wacht.append({"naam": naam, "url": url, "img": img, "doel": doel.value(),
                               "prijs": prijs, "laagst": prijs, "gekeken": nu, "status": "ok",
                               "historie": [[nu, prijs]] if prijs is not None else [], "gemeld": False})
        _schrijf(WACHTER, self.wacht)
        self._vul_wachtlijst()
        self.statusBar().showMessage(T("toegevoegd") % naam, 8000)

    # ---------------------------------------------------------- prijswachter
    def _vul_wachtlijst(self):
        self.tabel.setRowCount(0)
        for item in self.wacht:
            i = self.tabel.rowCount()
            self.tabel.insertRow(i)
            prijs, doel = item.get("prijs"), item.get("doel")
            onder = prijs is not None and doel is not None and prijs <= doel
            cel = [item["naam"], "€ " + euro(prijs), "€ " + euro(doel), "€ " + euro(item.get("laagst")),
                   (item.get("gekeken") or "").replace("T", " "), self._status_tekst(item, onder)]
            for k, tekst in enumerate(cel):
                it = QTableWidgetItem(tekst)
                if k == 1:
                    it.setForeground(QColor(GOED if onder else TEKST))
                if k == 5:
                    it.setForeground(QColor(GOUD if onder else (ROOD if item.get("status") == "fout" else SUB)))
                self.tabel.setItem(i, k, it)
        self.tabs.setTabText(2, "%s (%d)" % (T("tab_wacht"), len(self.wacht)))
        self.leeg.setVisible(not self.wacht)
        self._toon_grafiek()

    def _status_tekst(self, item, onder):
        if item.get("status") == "fout":
            return T("st_fout")
        if onder:
            return T("st_onder")
        h = item.get("historie") or []
        if len(h) >= 2 and h[-1][1] is not None and h[-2][1] is not None:
            if h[-1][1] < h[-2][1]:
                return T("st_lager")
            if h[-1][1] > h[-2][1]:
                return T("st_hoger")
        return T("st_ok")

    def _geselecteerd(self):
        r = self.tabel.currentRow()
        return self.wacht[r] if 0 <= r < len(self.wacht) else None

    def _toon_grafiek(self):
        item = self._geselecteerd()
        if not item:
            self.grafiek.zet([], None)
            return
        self.grafiek.zet([h for h in item.get("historie", []) if h[1] is not None], item.get("doel"))

    def _w_open(self):
        item = self._geselecteerd()
        if item:
            self.open_web(item["url"])

    def _w_doel(self):
        item = self._geselecteerd()
        if item:
            self.volg_dialoog(item["naam"], item.get("prijs"), item["url"], item.get("img"))

    def _w_weg(self):
        item = self._geselecteerd()
        if not item:
            return
        if QMessageBox.question(self, T("w_weg"), item["naam"] + "\n\n" + T("w_weg") + "?") == QMessageBox.StandardButton.Yes:
            self.wacht.remove(item)
            _schrijf(WACHTER, self.wacht)
            self._vul_wachtlijst()

    def controleer_alles(self):
        if getattr(self, "_bezig", False) or not self.wacht:
            self._zet_status()
            return
        self._bezig = True
        self.wstatus.setText("⏳  " + T("w_bezig"))
        self._rij = list(self.wacht)
        self._volgende_item()

    def _volgende_item(self):
        if not self._rij:
            self._bezig = False
            _schrijf(WACHTER, self.wacht)
            self._vul_wachtlijst()
            self._zet_timer()
            self._zet_status(klaar=True)
            return
        item = self._rij.pop(0)

        class W(QThread):
            klaar = pyqtSignal(object)

            def run(s):
                try:
                    s.klaar.emit(se.prijs_nu(item["url"])[0])
                except se.Geblokkeerd:
                    s.klaar.emit("blok")
                except Exception:
                    s.klaar.emit(None)

        wk = W()

        def na(prijs):
            if prijs == "blok":
                self._via_browser(item)
                return
            self._verwerk(item, prijs)
            QTimer.singleShot(2500, self._volgende_item)   # netjes: pauze tussen sites
        wk.klaar.connect(na)
        self.werkers.append(wk)
        wk.finished.connect(lambda: self.werkers.remove(wk) if wk in self.werkers else None)
        wk.start()

    def _via_browser(self, item):
        """Site weigert gewone verzoeken: kijk zoals jij zelf zou kijken, in de ingebouwde browser."""
        klaar = {"af": False}

        def lees():
            def res(r):
                if klaar["af"]:
                    return
                klaar["af"] = True
                try:
                    pr = json.loads(r or "{}").get("prijs")
                except Exception:
                    pr = None
                self._verwerk(item, pr)
                QTimer.singleShot(2500, self._volgende_item)
            self.stil.runJavaScript(JS_PRIJS, res)

        def geladen(ok):
            try:
                self.stil.loadFinished.disconnect(geladen)
            except Exception:
                pass
            QTimer.singleShot(2500, lees)

        def te_laat():
            if not klaar["af"]:
                klaar["af"] = True
                self._verwerk(item, None)
                self._volgende_item()
        self.stil.loadFinished.connect(geladen)
        self.stil.setUrl(QUrl(item["url"]))
        QTimer.singleShot(30000, te_laat)

    def _verwerk(self, item, prijs):
        nu = datetime.datetime.now().isoformat(timespec="minutes")
        item["gekeken"] = nu
        if prijs is None:
            item["status"] = "fout"
            return
        item["status"] = "ok"
        oud = item.get("prijs")
        item["prijs"] = prijs
        h = item.setdefault("historie", [])
        if not h or h[-1][1] != prijs or h[-1][0][:10] != nu[:10]:
            h.append([nu, prijs])
        del h[:-200]
        if item.get("laagst") is None or prijs < item["laagst"]:
            item["laagst"] = prijs
        doel = item.get("doel")
        if doel is not None and prijs <= doel:
            if not item.get("gemeld") or (oud is not None and prijs < oud):
                self._alarm(item)
            item["gemeld"] = True
        else:
            item["gemeld"] = False

    def _alarm(self, item):
        tekst = T("alarm_tekst") % (item["naam"][:60], euro(item["prijs"]), euro(item["doel"]))
        if self.tray:
            self.tray.showMessage(T("alarm_titel"), tekst, QSystemTrayIcon.MessageIcon.Information, 15000)
        if self.instel.get("geluid", True):
            try:
                import winsound
                for f, ms in ((880, 160), (1175, 160), (1568, 260)):
                    winsound.Beep(f, ms)
            except Exception:
                QApplication.beep()
        self.statusBar().showMessage("🔔  " + tekst, 30000)

    def _zet_status(self, klaar=False):
        delen = []
        if klaar:
            delen.append(T("w_klaar") % datetime.datetime.now().strftime("%H:%M"))
        if getattr(self, "_volgende", None):
            delen.append(T("w_volgende") % self._volgende.strftime("%H:%M"))
        self.wstatus.setText("   ".join(delen))

    # ---------------------------------------------------------- tray + overige
    def _maak_tray(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip(APP)
        m = QMenu()
        a1 = QAction(T("toon"), self)
        a1.triggered.connect(self._toon)
        a2 = QAction(T("stop"), self)
        a2.triggered.connect(QApplication.quit)
        m.addAction(a1)
        m.addAction(a2)
        self.tray.setContextMenu(m)
        self.tray.messageClicked.connect(lambda: (self._toon(), self.tabs.setCurrentIndex(2)))
        self.tray.activated.connect(lambda r: self._toon() if r == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()

    def _toon(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _snelgids(self):
        pdf = _res("DraveShopBuddy-Snelgids.pdf")
        if os.path.exists(pdf):
            QDesktopServices.openUrl(QUrl.fromLocalFile(pdf))

    def closeEvent(self, e):
        _schrijf(WACHTER, self.wacht)
        if self.tray:
            self.tray.hide()
        e.accept()


def main():
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    app.setStyleSheet(STIJL)
    w = ShopBuddy()
    w.show()
    try:
        import drave_doneer
        drave_doneer.voeg_toe(w)
    except Exception:
        pass
    try:
        import drave_update
        drave_update.start(w, APP, VERSIE)
    except Exception:
        pass
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        w.zoekbalk.setText(" ".join(sys.argv[1:]))
        QTimer.singleShot(300, w.zoek)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
