"""La versión de una sola pieza: socket y pie fundidos."""

import math

import pytest

from app.models import SocketParameters
from app.services.generators import one_piece as op
from app.services.generators import parametric_socket as ps
from app.services.generators import paw_foot as pf


def params(**overrides) -> SocketParameters:
    base = {
        "dog_name": "Copito",
        "height_cm": 9.0,
        "top_radius_cm": 2.86,
        "bottom_radius_cm": 2.07,
        "wall_thickness_cm": 0.32,
        "connector_radius_cm": 1.6,
        "limb_position": "delantera",
        "limb_side": "derecha",
    }
    base.update(overrides)
    return SocketParameters(**base)


CASES = [
    params(),
    params(dog_name="Mini", height_cm=4, top_radius_cm=1.2, bottom_radius_cm=1.0,
           wall_thickness_cm=0.25, connector_radius_cm=1.2),
    params(dog_name="Gigante", height_cm=22, top_radius_cm=6.0, bottom_radius_cm=5.0,
           wall_thickness_cm=0.42, connector_radius_cm=2.0),
    params(limb_side="izquierda"),
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c.dog_name}-{c.limb_side}")
def test_malla_cerrada_y_orientada(case):
    mesh, _, _ = op.build_one_piece_mesh(case)
    assert ps.is_watertight(mesh)
    assert ps.signed_volume(mesh) > 0


def test_el_pie_es_mas_ancho_que_la_pierna():
    """Si el pie no sobresale del socket no reparte nada al apoyar."""
    for case in CASES:
        _, foot, profile = op.build_one_piece_mesh(case)
        assert foot.pad_radius > profile.bottom_radius
        assert foot.pad_radius > foot.neck_radius


def test_la_punta_se_proyecta_hacia_adelante():
    mesh, foot, _ = op.build_one_piece_mesh(params())
    adelante = max(v[0] for v in mesh.vertices)
    atras = abs(min(v[0] for v in mesh.vertices))
    assert adelante > atras, "la puntera tiene que quedar por delante del eje"


def test_la_cavidad_saca_peso_de_verdad():
    """El bulbo del pie hueco era la mitad del peso de la pieza."""
    case = params()
    hueca, _, _ = op.build_one_piece_mesh(case)

    original = op.FOOT_WALL_MM
    op.FOOT_WALL_MM = 10_000  # pared tan gruesa que no queda cavidad
    try:
        maciza, _, _ = op.build_one_piece_mesh(case)
    finally:
        op.FOOT_WALL_MM = original

    assert ps.is_watertight(maciza)
    ahorro = 1 - ps.signed_volume(hueca) / ps.signed_volume(maciza)
    assert ahorro > 0.25, f"la cavidad sólo sacó {ahorro:.0%}"


def test_pesa_menos_que_socket_y_pie_por_separado():
    """No tiene poste ni copa de encastre: es la opción liviana."""
    case = params()
    entera, _, profile = op.build_one_piece_mesh(case)
    socket, _, _ = ps.build_socket_mesh(case)
    pie, _ = pf.build_foot_mesh(profile)

    assert ps.signed_volume(entera) < ps.signed_volume(socket) + ps.signed_volume(pie)


def test_no_es_un_bloque_macizo():
    """Densidad aparente: cuánto pesa respecto del cilindro que ocupa."""
    mesh, foot, profile = op.build_one_piece_mesh(params())
    radio_cm = max(profile.top_radius, foot.pad_radius) / 10
    alto_cm = (profile.total_height + foot.drop) / 10
    envolvente = math.pi * radio_cm**2 * alto_cm
    assert ps.signed_volume(mesh) / 1000 / envolvente < 0.25


def test_contrato_del_generador():
    result = op.generate(params(limb_side="izquierda"), form=None)
    assert result["algorithm_version"] == "one-piece-v1"
    assert "-entera-" in result["generated_filename"]
    info = result["generation_parameters"]
    assert info["mirrored"] is True
    assert info["estimated_mass_g"] > 0
    assert info["print_hints"]["supports"] is False
