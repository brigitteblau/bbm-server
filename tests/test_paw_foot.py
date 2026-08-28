"""El pie: la pieza que encastra en el poste del socket."""

import math

import pytest

from app.models import SocketParameters
from app.services.generators import parametric_socket as ps
from app.services.generators import paw_foot as pf


def params(**overrides) -> SocketParameters:
    base = {
        "dog_name": "Copito",
        "height_cm": 9.0,
        "top_radius_cm": 2.86,
        "bottom_radius_cm": 2.07,
        "wall_thickness_cm": 0.4,
        "connector_radius_cm": 1.6,
        "limb_position": "delantera",
        "limb_side": "derecha",
    }
    base.update(overrides)
    return SocketParameters(**base)


CASES = [
    params(),
    params(dog_name="Mini", height_cm=4, top_radius_cm=1.2, bottom_radius_cm=1.0,
           wall_thickness_cm=0.3, connector_radius_cm=1.2),
    params(dog_name="Gigante", height_cm=22, top_radius_cm=6.0, bottom_radius_cm=5.0,
           wall_thickness_cm=0.5, connector_radius_cm=2.0),
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.dog_name)
def test_malla_cerrada_y_orientada(case):
    socket = ps.SocketProfile.from_params(case)
    mesh, _ = pf.build_foot_mesh(socket)
    assert ps.is_watertight(mesh)
    assert ps.signed_volume(mesh) > 0


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.dog_name)
def test_encastra_en_el_poste_del_socket(case):
    socket = ps.SocketProfile.from_params(case)
    foot = pf.FootProfile.from_socket(socket)

    # entra, con la holgura de impresión
    assert foot.bore_radius == pytest.approx(
        socket.connector_radius + pf.FIT_CLEARANCE_MM
    )
    # el poste llega hasta el fondo del agujero y sobra: apoya a tope
    assert foot.bore_depth < socket.post_length
    # queda pared alrededor del encastre
    assert foot.cup_radius - foot.bore_radius == pytest.approx(pf.CUP_WALL_MM)
    # la huella no es más angosta que el encastre
    assert foot.pad_radius > foot.cup_radius


def test_la_almohadilla_tiene_lobulos():
    socket = ps.SocketProfile.from_params(params())
    mesh, foot = pf.build_foot_mesh(socket)

    base = [v for v in mesh.vertices if v[2] < foot.pad_height * 0.25]
    radios = [math.hypot(v[0], v[1]) for v in base]
    assert max(radios) - min(radios) > 1.0

    # los lóbulos se desdibujan hacia arriba: la copa es redonda
    copa = [v for v in mesh.vertices if v[2] > foot.total_height - 2.0]
    radios_copa = sorted(math.hypot(v[0], v[1]) for v in copa)
    assert radios_copa[-1] - radios_copa[0] < foot.cup_radius * 0.5


def test_apoya_en_el_piso():
    result = pf.generate(params(), form=None)
    assert result["algorithm_version"] == "paw-foot-v1"
    assert "-pie-" in result["generated_filename"]
    assert result["generated_stl_bytes"][:5] == b"hunda"
    assert result["generation_parameters"]["toes"] == pf.TOES
    assert result["generation_parameters"]["fit_clearance_mm"] == pf.FIT_CLEARANCE_MM


def test_espejado_para_pata_izquierda():
    result = pf.generate(params(limb_side="izquierda"), form=None)
    assert result["generation_parameters"]["mirrored"] is True


def test_el_pie_crece_con_el_perro():
    chico = pf.FootProfile.from_socket(ps.SocketProfile.from_params(CASES[1]))
    grande = pf.FootProfile.from_socket(ps.SocketProfile.from_params(CASES[2]))
    assert grande.pad_radius > chico.pad_radius
    assert grande.total_height > chico.total_height
