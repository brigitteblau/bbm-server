"""Bota en Geometry Nodes (blender-gn-v2-bota).

Los tests de diseño corren siempre; los que generan con Blender se saltean si
bpy no está instalado (en Render hoy no está).
"""
import io

import pytest

from app.models import ProsthesisForm
from app.services.generators import blender_gn
from app.services.socket_parameters import SocketParameterGenerator


def _params(**kw):
    base = dict(dog_name="Max", dog_weight_kg=18, limb_position="delantera", limb_side="derecha",
                stump_length_cm=9, proximal_circumference_cm=18, distal_circumference_cm=13)
    base.update(kw)
    form = ProsthesisForm(**base)
    return SocketParameterGenerator().generate(form), form


def test_diseno_usa_las_medidas_del_perro():
    p, _ = _params()
    d = blender_gn.design(p)
    assert d["proximal_radius_mm"] == pytest.approx(28.6)
    assert d["distal_radius_mm"] == pytest.approx(20.7)
    assert d["stump_length_mm"] == 90
    assert d["top_mm"] == pytest.approx(d["cavity_bottom_mm"] + 90 + d["liner_mm"])
    assert d["foot_scale"] == pytest.approx(28.6 / 28.5, abs=1e-3)


def test_diseno_escala_el_pie_con_limites():
    chico, _ = _params(proximal_circumference_cm=6, distal_circumference_cm=5)
    grande, _ = _params(proximal_circumference_cm=60, distal_circumference_cm=50)
    assert blender_gn.design(chico)["foot_scale"] == 0.5
    assert blender_gn.design(grande)["foot_scale"] == 2.0


def test_trasera_e_izquierda():
    p, _ = _params(limb_position="trasera", limb_side="izquierda")
    d = blender_gn.design(p)
    assert d["hind"] and d["mirrored"]


@pytest.mark.skipif(not blender_gn.is_available(), reason="bpy no está instalado")
@pytest.mark.parametrize("pos,side", [("delantera", "derecha"), ("trasera", "izquierda")])
def test_genera_bota_cerrada(pos, side):
    trimesh = pytest.importorskip("trimesh")
    p, form = _params(limb_position=pos, limb_side=side)
    r = blender_gn.generate(p, form)
    mesh = trimesh.load_mesh(io.BytesIO(r["generated_stl_bytes"]), file_type="stl")
    assert r["algorithm_version"] == "blender-gn-v2-bota"
    assert mesh.is_watertight                       # imprimible
    assert mesh.bounds[0][2] == pytest.approx(0, abs=0.05)   # apoyada en el suelo
    assert mesh.extents[2] == pytest.approx(153, abs=6)      # 60 de pie + 90 de muñón + 3 de media


def test_deja_lugar_para_la_media_y_embudo():
    p, _ = _params()
    d = blender_gn.design(p)
    assert d["liner_mm"] == blender_gn.LINER_MM > 0
    assert 0 < d["funnel_height_mm"] <= 15
    assert d["funnel_flare_mm"] > 0
