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
    """render_receipt su Dummy deve produrre le sezioni del nuovo layout."""
    p = Dummy()
    render_receipt(p, _sample_order(), _sample_settings())
    text = p.output.decode(errors="ignore")

    assert "Sagra del Panino" in text  # nome evento
    assert "2 x Panino salamella" in text  # quantita' + nome prodotto
    assert "Seguici su instagram!" in text  # invito Instagram
    assert "@eca_associazione" in text  # handle Instagram


def test_render_receipt_senza_prezzi_e_totale():
    """Il nuovo scontrino non mostra prezzi di riga, totale ne' numero ordine."""
    p = Dummy()
    render_receipt(p, _sample_order(), _sample_settings())
    text = p.output.decode(errors="ignore")

    assert "EUR" not in text  # nessun prezzo
    assert "TOTALE" not in text  # nessun totale
    assert "Ordine #" not in text  # nessun numero ordine
    assert "Pro Loco Esempio" not in text  # associazione rappresentata dal logo


def test_print_order_dummy_ok_e_detail():
    """print_order in dummy deve ritornare ok=True e il testo nello detail."""
    result = print_order(_sample_order(), _sample_settings())

    assert result["ok"] is True
    assert result["mode"] == "dummy"
    assert result["detail"] is not None
    assert "Seguici su instagram!" in result["detail"]


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
