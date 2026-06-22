"""Test del modulo di stampa ESC/POS (app.printer) in modalita' Dummy.

Non serve il DB: order e settings sono costruiti a mano.
"""
from __future__ import annotations

from escpos.printer import Dummy

from app.printer import print_order, render_receipt


def _sample_settings() -> dict:
    """Settings di esempio in modalita' dummy (nessun hardware)."""
    return {
        "association_name": "Pro Loco Esempio",
        "event_name": "Sagra del Panino",
        "footer_message": "Grazie e arrivederci!",
        "printer_mode": "dummy",
        "admin_pin": "1234",
    }


def _sample_order() -> dict:
    """Ordine di esempio: 2 panini (400c) + 1 birra (400c)."""
    return {
        "id": 7,
        "created_at": "2026-06-22T20:35:00",
        "total_cents": 1200,
        "printed": 0,
        "note": None,
        "items": [
            {
                "product_name": "Panino salamella",
                "quantity": 2,
                "unit_price_cents": 400,
                "line_total_cents": 800,
            },
            {
                "product_name": "Birra media",
                "quantity": 1,
                "unit_price_cents": 400,
                "line_total_cents": 400,
            },
        ],
    }


def test_render_receipt_contiene_sezioni_attese():
    """render_receipt su Dummy deve produrre tutte le sezioni dello scontrino."""
    p = Dummy()
    render_receipt(p, _sample_order(), _sample_settings())
    text = p.output.decode(errors="ignore")

    assert "Pro Loco Esempio" in text  # nome associazione
    assert "Sagra del Panino" in text  # nome evento
    assert "Ordine #7" in text  # numero ordine
    assert "Panino salamella" in text  # nome prodotto
    assert "TOTALE" in text  # riga totale
    assert "Grazie e arrivederci!" in text  # footer


def test_print_order_dummy_ok_e_detail():
    """print_order in dummy deve ritornare ok=True e il testo nello detail."""
    result = print_order(_sample_order(), _sample_settings())

    assert result["ok"] is True
    assert result["mode"] == "dummy"
    assert result["detail"] is not None
    assert "TOTALE" in result["detail"]


def test_importi_formattati_correttamente():
    """400 cents x2 = 800 cents deve diventare '8.00 EUR'; totale '12.00 EUR'."""
    p = Dummy()
    render_receipt(p, _sample_order(), _sample_settings())
    text = p.output.decode(errors="ignore")

    assert "8.00 EUR" in text  # riga panini (800c)
    assert "4.00 EUR" in text  # riga birra (400c)
    assert "12.00 EUR" in text  # totale (1200c)


def test_normalizzazione_accenti():
    """Gli accenti vengono rimossi (stampante ASCII): 'Caffè' -> 'Caffe'."""
    order = _sample_order()
    order["items"] = [
        {
            "product_name": "Caffè",
            "quantity": 1,
            "unit_price_cents": 100,
            "line_total_cents": 100,
        }
    ]
    order["total_cents"] = 100
    p = Dummy()
    render_receipt(p, order, _sample_settings())
    text = p.output.decode(errors="ignore")

    assert "Caffe" in text
    assert "Caffè" not in text
