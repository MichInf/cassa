"""Modulo di stampa scontrini ESC/POS.

Gestisce sia la stampante USB termica reale (in produzione su Linux) sia il
fallback ``Dummy`` di python-escpos (in sviluppo / Windows), così l'app resta
testabile ovunque senza hardware collegato.

Tutti gli importi sono in centesimi interi: vengono convertiti in EUR con due
decimali e il punto come separatore (es. 800 -> "8.00 EUR").
"""
from __future__ import annotations

import os
import unicodedata
from datetime import datetime

from escpos.printer import Dummy, Usb

# Parametri della stampante USB reale (vedi docs: VID/PID e endpoint).
_USB_VID = 0x0416
_USB_PID = 0x5011
_USB_IN_EP = 0x82
_USB_OUT_EP = 0x01

# Larghezza in caratteri della carta termica (tipica 80mm = 42, 58mm = 32).
_LINE_WIDTH = 42

# Larghezza utile della carta in punti (dot). 80mm = 576 dot. Usata per
# centrare il logo manualmente, senza dipendere dal profilo della stampante
# (il flag center di python-escpos richiede media.width.pixel nel profilo).
_PAPER_WIDTH_DOTS = 576

# Logo dell'associazione stampato in cima allo scontrino (PNG monocromatico,
# bundlato accanto a questo modulo).
_LOGO_PATH = os.path.join(os.path.dirname(__file__), "logo_eca.png")

# Handle Instagram mostrato in fondo allo scontrino.
_INSTAGRAM_HANDLE = "@eca_associazione"


def _ascii(text: str) -> str:
    """Normalizza una stringa rimuovendo i diacritici (la stampante e' ASCII).

    Esempio: "Caffè" -> "Caffe", "perché" -> "perche". I caratteri non
    rappresentabili in ASCII vengono scartati in modo sicuro.
    """
    if text is None:
        return ""
    # Decomposizione Unicode: separa lettera base e segno diacritico, poi
    # tiene solo i caratteri ASCII risultanti.
    decomposed = unicodedata.normalize("NFKD", str(text))
    return decomposed.encode("ascii", "ignore").decode("ascii")


def _eur(cents: int) -> str:
    """Converte centesimi interi in stringa EUR con due decimali e punto."""
    return f"{cents / 100:.2f} EUR"


def _format_created_at(created_at: str) -> str:
    """Formatta una data ISO in 'gg/mm/aaaa hh:mm' in modo robusto.

    Se il parsing fallisce, ritorna la stringa originale per non bloccare la
    stampa.
    """
    if not created_at:
        return ""
    try:
        dt = datetime.fromisoformat(created_at)
        return dt.strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return str(created_at)


def get_printer(settings: dict):
    """Ritorna l'istanza di stampante secondo ``settings['printer_mode']``.

    - "usb"  -> stampante USB ESC/POS reale.
    - altro  -> Dummy() (sviluppo/test): accumula l'output in memoria.

    L'env var FESTA_PRINTER_MODE ha la precedenza sul valore nel DB, in modo
    che il servizio systemd (Environment=FESTA_PRINTER_MODE=usb) funzioni
    correttamente anche su DB inizializzati in modalita' dummy.
    """
    mode = os.environ.get("FESTA_PRINTER_MODE") or settings.get("printer_mode")
    if mode == "usb":
        return Usb(_USB_VID, _USB_PID, in_ep=_USB_IN_EP, out_ep=_USB_OUT_EP)
    return Dummy()


def _load_centered_logo():
    """Carga il logo monocromatico centrato su una tela larga quanto la carta.

    Ritorna un'immagine PIL gia' centrata, oppure ``None`` se il file manca o
    PIL non e' disponibile. Centrare a monte rende il risultato indipendente
    dal profilo della stampante (il flag ``center`` di python-escpos no).
    """
    try:
        from PIL import Image
    except ImportError:
        return None
    if not os.path.exists(_LOGO_PATH):
        return None
    logo = Image.open(_LOGO_PATH).convert("L")
    # Se il logo e' piu' largo della carta, riduci mantenendo le proporzioni.
    if logo.width > _PAPER_WIDTH_DOTS:
        ratio = _PAPER_WIDTH_DOTS / logo.width
        logo = logo.resize((_PAPER_WIDTH_DOTS, round(logo.height * ratio)))
    # Tela bianca larga quanto la carta, logo incollato al centro.
    canvas = Image.new("L", (_PAPER_WIDTH_DOTS, logo.height), color=255)
    canvas.paste(logo, ((_PAPER_WIDTH_DOTS - logo.width) // 2, 0))
    return canvas


def _print_logo(p) -> None:
    """Stampa il logo in cima allo scontrino, centrato.

    Se il file manca o la stampa immagine fallisce non solleva: lo scontrino
    deve comunque uscire (il logo e' decorativo, non essenziale).
    """
    try:
        logo = _load_centered_logo()
        if logo is not None:
            p.image(logo)
    except Exception:  # noqa: BLE001  (il logo non deve mai bloccare la stampa)
        pass


def render_receipt(p, order: dict, settings: dict) -> None:
    """Scrive lo scontrino cliente sulla stampante ``p`` (API python-escpos).

    Ordine delle sezioni: logo associazione, nome evento (bold), data/ora,
    separatore, righe articoli con sola quantita' (niente prezzi), separatore,
    invito a seguire su Instagram, taglio carta. Niente totale.
    """
    separator = "-" * _LINE_WIDTH

    # --- Logo associazione, centrato in alto ---
    p.set(align="center", bold=False, width=1, height=1)
    _print_logo(p)

    # --- Nome evento, centrato e in bold ---
    p.set(align="center", bold=True, width=1, height=1)
    p.text(_ascii(settings.get("event_name", "")) + "\n")

    # --- Data e ora leggibili ---
    p.set(align="center", bold=False, width=1, height=1)
    p.text(_format_created_at(order.get("created_at", "")) + "\n")

    # --- Separatore ---
    p.set(align="left", bold=False, width=1, height=1)
    p.text(separator + "\n")

    # --- Righe articoli: solo quantita' e nome, senza prezzi ---
    for item in order.get("items", []):
        qty = item.get("quantity", 0)
        name = _ascii(item.get("product_name", ""))
        p.text(f"  {qty} x {name}\n")

    # --- Separatore ---
    p.text(separator + "\n")

    # --- Invito a seguire su Instagram, centrato ---
    p.set(align="center", bold=False, width=1, height=1)
    p.text("\n")
    p.text("Seguici su instagram!\n")
    p.text(_INSTAGRAM_HANDLE + "\n")

    # --- Taglio carta ---
    p.cut()


def _dummy_text(p) -> str | None:
    """Estrae il testo dello scontrino da un Dummy (None per stampanti reali)."""
    output = getattr(p, "output", None)
    if output is None:
        return None
    return output.decode(errors="ignore")


def print_order(order: dict, settings: dict) -> dict:
    """Stampa un ordine completo e ritorna l'esito.

    Ritorna ``{"ok": True, "mode": <modo>, "detail": <testo|None>}``: in
    modalita' dummy ``detail`` contiene il testo dello scontrino, con la
    stampante reale e' None. Le eccezioni sono catturate e riportate in
    ``detail`` con ``ok=False`` (mai sollevate).
    """
    mode = os.environ.get("FESTA_PRINTER_MODE") or settings.get("printer_mode")
    p = None
    try:
        p = get_printer(settings)
        render_receipt(p, order, settings)
        return {"ok": True, "mode": mode, "detail": _dummy_text(p)}
    except Exception as exc:  # noqa: BLE001  (vogliamo non sollevare mai)
        return {"ok": False, "mode": mode, "detail": str(exc)}
    finally:
        if p is not None:
            try:
                p.close()
            except Exception:  # noqa: BLE001
                pass


def test_print(settings: dict) -> dict:
    """Stampa una breve riga di prova e ritorna lo stesso formato di print_order."""
    mode = os.environ.get("FESTA_PRINTER_MODE") or settings.get("printer_mode")
    p = None
    try:
        p = get_printer(settings)
        p.set(align="center", bold=True, width=1, height=1)
        p.text("Test stampa OK\n")
        p.cut()
        return {"ok": True, "mode": mode, "detail": _dummy_text(p)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "mode": mode, "detail": str(exc)}
    finally:
        if p is not None:
            try:
                p.close()
            except Exception:  # noqa: BLE001
                pass
