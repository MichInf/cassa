"""Modulo di stampa scontrini ESC/POS.

Gestisce sia la stampante USB termica reale (in produzione su Linux) sia il
fallback ``Dummy`` di python-escpos (in sviluppo / Windows), così l'app resta
testabile ovunque senza hardware collegato.

Tutti gli importi sono in centesimi interi: vengono convertiti in EUR con due
decimali e il punto come separatore (es. 800 -> "8.00 EUR").
"""
from __future__ import annotations

import unicodedata
from datetime import datetime

from escpos.printer import Dummy, Usb

# Parametri della stampante USB reale (vedi docs: VID/PID e endpoint).
_USB_VID = 0x0416
_USB_PID = 0x5011
_USB_IN_EP = 0x82
_USB_OUT_EP = 0x01

# Larghezza in caratteri della carta termica (tipica 80mm = 42, 58mm = 32).
# Usata per allineare a destra i totali di riga.
_LINE_WIDTH = 42


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
    """
    if settings.get("printer_mode") == "usb":
        return Usb(_USB_VID, _USB_PID, in_ep=_USB_IN_EP, out_ep=_USB_OUT_EP)
    return Dummy()


def render_receipt(p, order: dict, settings: dict) -> None:
    """Scrive lo scontrino cliente sulla stampante ``p`` (API python-escpos).

    Ordine delle sezioni: intestazione associazione (grande/bold), evento,
    data/ora, numero ordine, separatore, righe articoli con totale a destra,
    separatore, totale in bold, riga vuota, messaggio finale, taglio carta.
    """
    separator = "-" * _LINE_WIDTH

    # --- Intestazione: nome associazione, centrato e grande/bold ---
    p.set(align="center", bold=True, width=2, height=2)
    p.text(_ascii(settings.get("association_name", "")) + "\n")

    # --- Nome evento, centrato (dimensione normale) ---
    p.set(align="center", bold=False, width=1, height=1)
    p.text(_ascii(settings.get("event_name", "")) + "\n")

    # --- Data e ora leggibili ---
    p.text(_format_created_at(order.get("created_at", "")) + "\n")

    # --- Numero ordine progressivo ---
    p.text(f"Ordine #{order.get('id', '')}\n")

    # --- Separatore ---
    p.set(align="left", bold=False, width=1, height=1)
    p.text(separator + "\n")

    # --- Righe articoli: "  2 x Panino salamella" + totale riga a destra ---
    for item in order.get("items", []):
        qty = item.get("quantity", 0)
        name = _ascii(item.get("product_name", ""))
        line_total = _eur(item.get("line_total_cents", 0))

        left = f"  {qty} x {name}"
        # Allinea il totale a destra entro la larghezza riga; se la parte
        # sinistra e' troppo lunga, manda il totale a capo indentato.
        spaces = _LINE_WIDTH - len(left) - len(line_total)
        if spaces >= 1:
            p.text(left + " " * spaces + line_total + "\n")
        else:
            p.text(left + "\n")
            p.text(" " * (_LINE_WIDTH - len(line_total)) + line_total + "\n")

    # --- Separatore ---
    p.text(separator + "\n")

    # --- Totale complessivo in bold ---
    p.set(align="left", bold=True, width=1, height=1)
    p.text(f"TOTALE: {_eur(order.get('total_cents', 0))}\n")

    # --- Riga vuota + messaggio finale centrato ---
    p.set(align="center", bold=False, width=1, height=1)
    p.text("\n")
    p.text(_ascii(settings.get("footer_message", "")) + "\n")

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
    mode = settings.get("printer_mode")
    try:
        p = get_printer(settings)
        render_receipt(p, order, settings)
        return {"ok": True, "mode": mode, "detail": _dummy_text(p)}
    except Exception as exc:  # noqa: BLE001  (vogliamo non sollevare mai)
        return {"ok": False, "mode": mode, "detail": str(exc)}


def test_print(settings: dict) -> dict:
    """Stampa una breve riga di prova e ritorna lo stesso formato di print_order."""
    mode = settings.get("printer_mode")
    try:
        p = get_printer(settings)
        p.set(align="center", bold=True, width=1, height=1)
        p.text("Test stampa OK\n")
        p.cut()
        return {"ok": True, "mode": mode, "detail": _dummy_text(p)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "mode": mode, "detail": str(exc)}
