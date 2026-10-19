"""Indicaciones de impresión."""

import pytest

from app.utils.printing import ORIENTATIONS, print_hints


@pytest.mark.parametrize("piece", sorted(ORIENTATIONS))
def test_ninguna_pieza_necesita_soportes(piece):
    hints = print_hints(piece, "petg", 3.2)
    assert hints["supports"] is False
    assert hints["orientation"] == ORIENTATIONS[piece]


def test_el_socket_se_imprime_al_reves():
    assert "boca abajo" in print_hints("socket", "petg", 3.2)["orientation"]


def test_el_pie_se_imprime_parado():
    assert "almohadilla" in print_hints("foot", "tpu", 3.0)["orientation"]


def test_los_perimetros_acompanan_el_espesor():
    fina = print_hints("socket", "petg", 2.0)["perimeters"]
    gruesa = print_hints("socket", "petg", 4.8)["perimeters"]
    assert gruesa > fina >= 2


def test_pieza_desconocida():
    with pytest.raises(ValueError):
        print_hints("cabeza", "petg", 3.0)
