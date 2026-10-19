"""Peso estimado de las piezas."""

import pytest

from app.utils.mass import DENSITIES_G_CM3, estimate_mass_g, mass_by_material


def test_un_centimetro_cubico_de_pla():
    assert estimate_mass_g(1000, "pla") == 1.2


def test_no_le_importan_las_mayusculas():
    assert estimate_mass_g(5000, "PLA") == estimate_mass_g(5000, "pla")


def test_material_desconocido_avisa_cuales_hay():
    with pytest.raises(ValueError, match="madera"):
        estimate_mass_g(1000, "madera")


def test_volumen_negativo_es_un_error():
    with pytest.raises(ValueError):
        estimate_mass_g(-1, "pla")


def test_compara_todos_los_materiales():
    pesos = mass_by_material(50_000)
    assert set(pesos) == set(DENSITIES_G_CM3)
    assert pesos["abs"] < pesos["petg"]
