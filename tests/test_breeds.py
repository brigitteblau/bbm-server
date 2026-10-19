"""La tabla de razas: defaults de arranque, no medidas."""

import pytest

from app.data import breeds
from app.models import ProsthesisForm
from app.services.socket_parameters import SocketParameterGenerator


def test_encuentra_con_y_sin_tildes():
    assert breeds.find("Ovejero Alemán") is breeds.find("ovejero aleman")
    assert breeds.find("OVEJERO ALEMAN").key == "ovejero aleman"


def test_encuentra_por_alias_y_dentro_de_una_frase():
    assert breeds.find("german shepherd").key == "ovejero aleman"
    assert breeds.find("mi labrador hermoso").key == "labrador"
    assert breeds.find("poodle").key == "caniche"


def test_raza_desconocida_cae_por_peso():
    perfil = breeds.resolve("perro de la nieve tibetano", 30)
    assert perfil.size == "grande"
    assert perfil.key.startswith("generico-")
    assert breeds.resolve(None, 2.5).size == "toy"
    assert breeds.resolve("", 50).size == "gigante"


@pytest.mark.parametrize("profile", breeds.BREEDS, ids=lambda p: p.key)
def test_cada_perfil_es_coherente(profile):
    minimo, maximo = profile.weight_range_kg
    assert 0 < minimo <= maximo
    assert profile.size in breeds.SIZES
    # El tamaño de la tabla y el deducido del peso pueden diferir en una
    # categoría: un beagle pesa como un perro chico pero es de cuerpo
    # mediano. Más de una categoría de diferencia sí sería un error de carga.
    esperado = breeds.SIZES.index(breeds.size_for_weight(profile.typical_weight_kg))
    assert abs(breeds.SIZES.index(profile.size) - esperado) <= 1
    assert 0.8 <= profile.wall_scale <= 1.25
    assert 0.8 <= profile.slenderness <= 1.2

    medidas = profile.measurements_cm()
    assert medidas["proximal_circumference_cm"] > medidas["distal_circumference_cm"]
    assert medidas["stump_length_cm"] > 0


def test_la_pata_trasera_sugiere_un_munon_mas_largo():
    perfil = breeds.find("labrador")
    assert (
        perfil.measurements_cm("trasera")["stump_length_cm"]
        > perfil.measurements_cm("delantera")["stump_length_cm"]
    )


def test_el_preset_de_una_raza_genera_una_protesis_valida():
    """El preset tiene que poder entrar tal cual en el formulario."""
    from app.services.generators import selector

    for perfil in breeds.BREEDS:
        form = ProsthesisForm(
            dog_name="Test",
            dog_breed=perfil.name,
            dog_weight_kg=perfil.typical_weight_kg,
            limb_position="delantera",
            limb_side="derecha",
            **perfil.measurements_cm(),
        )
        params = SocketParameterGenerator().generate(form)
        assert selector.validate_geometry(params) == [], perfil.key


def test_la_raza_ajusta_la_pared_pero_no_la_forma():
    base = {
        "dog_name": "Test",
        "dog_weight_kg": 18,
        "limb_position": "delantera",
        "limb_side": "derecha",
        "stump_length_cm": 9,
        "proximal_circumference_cm": 18,
        "distal_circumference_cm": 13,
    }
    collie = SocketParameterGenerator().generate(
        ProsthesisForm(**base, dog_breed="Border Collie")
    )
    whippet = SocketParameterGenerator().generate(
        ProsthesisForm(**base, dog_breed="Whippet")
    )

    # mismo muñón, misma forma
    assert collie.top_radius_cm == whippet.top_radius_cm
    assert collie.height_cm == whippet.height_cm
    # distinta exigencia, distinta pared
    assert collie.wall_thickness_cm > whippet.wall_thickness_cm
    assert collie.breed_key == "border collie"


def test_catalogo_para_el_front():
    catalogo = breeds.catalog()
    assert len(catalogo) == len(breeds.BREEDS)
    primero = catalogo[0]
    assert {"key", "name", "size", "measurements_cm", "material"} <= set(primero)
