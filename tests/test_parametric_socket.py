"""La geometría del socket: sin red, sin bpy, sin trimesh."""

import math
import struct

import pytest

from app.models import SocketParameters
from app.services.generators import parametric_socket as ps

CM_TO_MM = 10.0


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
    params(),                                                        # mediano
    params(dog_name="Mini", height_cm=4, top_radius_cm=1.2,
           bottom_radius_cm=1.0, wall_thickness_cm=0.3,
           connector_radius_cm=1.2),                                 # chico
    params(dog_name="Gigante", height_cm=22, top_radius_cm=6.0,
           bottom_radius_cm=5.0, wall_thickness_cm=0.5,
           connector_radius_cm=2.0),                                 # grande
    params(limb_side="izquierda"),                                   # espejado
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c.dog_name}-{c.limb_side}")
def test_malla_cerrada_y_orientada(case):
    mesh, _, _ = ps.build_socket_mesh(case)
    assert ps.is_watertight(mesh), "la malla tiene bordes abiertos: no es imprimible"
    assert ps.signed_volume(mesh) > 0, "las normales apuntan para adentro"


def test_altura_total_igual_al_munon():
    case = params()
    mesh, _, profile = ps.build_socket_mesh(case)
    zs = [v[2] for v in mesh.vertices]
    # la parte hueca mide el largo del muñón; abajo cuelga el conector
    assert max(zs) == pytest.approx(case.height_cm * CM_TO_MM)
    assert min(zs) == pytest.approx(profile.junction_z - profile.post_length)


def test_borde_proximal_tiene_flare():
    profile = ps.SocketProfile.from_params(params())
    assert profile.outer_radius_at(1.0) > profile.outer_radius_at(0.8)
    assert profile.outer_radius_at(0.5) > profile.outer_radius_at(0.0)


def test_seccion_eliptica_no_es_circulo():
    mesh, _, _ = ps.build_socket_mesh(params())
    top_z = max(v[2] for v in mesh.vertices)
    ring = [v for v in mesh.vertices if abs(v[2] - top_z) < 1e-6]
    max_x = max(abs(v[0]) for v in ring)
    max_y = max(abs(v[1]) for v in ring)
    assert max_y / max_x == pytest.approx(ps.ELLIPSE_RATIO, rel=0.02)


def test_hay_ventilacion_en_socket_mediano():
    _, pattern, _ = ps.build_socket_mesh(params())
    assert pattern.columns >= 3 and pattern.rows >= 1


def test_slots_no_quedan_desproporcionados():
    for case in CASES:
        profile = ps.SocketProfile.from_params(case)
        pattern = ps.plan_vents(profile)
        if pattern.columns == 0:
            continue
        mean_radius = (profile.top_radius + profile.bottom_radius) / 2.0
        width_mm = (pattern.angular_half_deg * 2 / 360.0) * 2 * math.pi * mean_radius
        height_mm = pattern.height_half * 2 * profile.wall_height
        assert width_mm >= ps.MIN_SLOT_MM
        assert height_mm >= ps.MIN_SLOT_MM
        assert height_mm <= width_mm * ps.MAX_SLOT_ASPECT + 1e-6


def test_socket_muy_chico_no_se_perfora():
    profile = ps.SocketProfile.from_params(
        params(height_cm=2.5, top_radius_cm=0.9, bottom_radius_cm=0.8,
               wall_thickness_cm=0.3, connector_radius_cm=1.2)
    )
    pattern = ps.plan_vents(profile)
    assert pattern.columns == 0 and pattern.rows == 0


def test_espejado_invierte_el_eje_y():
    derecha, _, _ = ps.build_socket_mesh(params(limb_side="derecha"))
    izquierda, _, _ = ps.build_socket_mesh(params(limb_side="derecha"))
    ps.mirror_y(izquierda)
    assert ps.is_watertight(izquierda)
    assert ps.signed_volume(izquierda) == pytest.approx(ps.signed_volume(derecha))
    assert izquierda.vertices[10][1] == pytest.approx(-derecha.vertices[10][1])


def test_conector_no_se_come_la_pared():
    profile = ps.SocketProfile.from_params(
        params(bottom_radius_cm=1.5, connector_radius_cm=2.0)
    )
    assert profile.connector_radius < profile.bottom_radius - profile.wall


def test_stl_binario_valido():
    mesh, _, _ = ps.build_socket_mesh(params())
    data = ps.export_binary_stl(mesh)
    assert len(data) == 84 + 50 * len(mesh.faces)
    (count,) = struct.unpack("<I", data[80:84])
    assert count == len(mesh.faces)


def test_generate_devuelve_el_contrato_del_selector():
    case = params(limb_side="izquierda")
    result = parametric_generate(case)
    assert result["algorithm_version"] == "parametric-socket-v2"
    assert result["generated_filename"].startswith("copito-")
    assert result["generated_filename"].endswith(".stl")
    assert result["generated_stl_bytes"][:5] == b"hunda"
    assert result["generation_parameters"]["mirrored"] is True
    assert result["generation_parameters"]["triangles"] > 0


def parametric_generate(case: SocketParameters) -> dict:
    return ps.generate(case, form=None)
