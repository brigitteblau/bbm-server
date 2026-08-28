"""End-to-end: del formulario del front al STL subido y descargable.

Usa el Supabase falso de conftest, así que no toca red ni credenciales.
"""

import struct

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes.prosthesis import GENERATED_BUCKET, GENERATED_TABLE, REQUESTS_TABLE

client = TestClient(app)

COPITO = {
    "user_id": "eec346a3-8425-4e56-b077-48f733cf59e1",
    "dog_name": "Copito",
    "dog_weight_kg": 18,
    "dog_breed": "Caniche",
    "dog_size": "mediano",
    "limb_position": "delantera",
    "limb_side": "derecha",
    "stump_length_cm": 9,
    "proximal_circumference_cm": 18,
    "distal_circumference_cm": 13,
}


def crear_request(payload: dict | None = None) -> str:
    response = client.post("/prosthesis/requests", json=payload or COPITO)
    assert response.status_code == 200, response.text
    return response.json()["request_id"]


# ── flujo feliz ──────────────────────────────────────────────────────────────

def test_flujo_completo_formulario_a_stl(fake_supabase):
    # Paso 1: guardar medidas
    request_id = crear_request()
    assert len(fake_supabase.rows(REQUESTS_TABLE)) == 1

    # Paso 2: generar
    response = client.post(f"/prosthesis/requests/{request_id}/generate")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["success"] is True
    assert body["request_id"] == request_id
    assert body["dog_name"] == "Copito"
    assert body["generator_used"] == "parametric-socket-v2"
    assert body["fallback_reason"] == (
        "Blender deshabilitado por configuración (BLENDER_ENABLED)"
    )

    # parámetros derivados de las medidas, no inventados
    socket = body["socket_parameters"]
    assert socket["height_cm"] == 9
    assert socket["top_radius_cm"] == 2.86
    assert socket["bottom_radius_cm"] == 2.07
    assert socket["wall_thickness_cm"] == 0.4

    # el STL quedó en storage y es un binario válido
    stored = fake_supabase.storage.from_(GENERATED_BUCKET).download(body["storage_path"])
    (triangles,) = struct.unpack("<I", stored[80:84])
    assert triangles > 0
    assert len(stored) == 84 + 50 * triangles

    # el pie viaja como pieza aparte, con su propio STL
    assert body["foot_storage_path"] is not None
    assert "-pie-" in body["foot_storage_path"]
    assert body["foot_download_url"].startswith("https://fake.supabase/")
    pie = fake_supabase.storage.from_(GENERATED_BUCKET).download(body["foot_storage_path"])
    (triangulos_pie,) = struct.unpack("<I", pie[80:84])
    assert len(pie) == 84 + 50 * triangulos_pie

    # y quedó registrado en la tabla
    record = fake_supabase.rows(GENERATED_TABLE)[0]
    assert record["status"] == "generated"
    assert record["algorithm_version"] == "parametric-socket-v2"
    assert record["request_id"] == request_id
    assert record["generation_parameters"]["connector_radius_mm"] > 0
    foot_record = record["generation_parameters"]["foot"]
    assert foot_record["algorithm_version"] == "paw-foot-v1"
    assert foot_record["bore_radius_mm"] > record["generation_parameters"]["connector_radius_mm"]
    assert body["download_url"].startswith("https://fake.supabase/")


def test_pata_izquierda_genera_espejado(fake_supabase):
    request_id = crear_request({**COPITO, "limb_side": "izquierda"})
    response = client.post(f"/prosthesis/requests/{request_id}/generate")
    assert response.status_code == 200, response.text
    record = fake_supabase.rows(GENERATED_TABLE)[0]
    assert record["generation_parameters"]["mirrored"] is True
    assert record["generation_parameters"]["foot"]["mirrored"] is True


def test_dos_generaciones_no_pisan_el_mismo_archivo(fake_supabase):
    request_id = crear_request()
    primero = client.post(f"/prosthesis/requests/{request_id}/generate").json()
    segundo = client.post(f"/prosthesis/requests/{request_id}/generate").json()
    assert primero["storage_path"] != segundo["storage_path"]
    assert primero["foot_storage_path"] != segundo["foot_storage_path"]
    # dos piezas por generación: socket y pie
    assert len(fake_supabase.storage.from_(GENERATED_BUCKET).files) == 4


def test_descarga_redirige_a_la_url_firmada(fake_supabase):
    request_id = crear_request()
    body = client.post(f"/prosthesis/requests/{request_id}/generate").json()

    response = client.get(
        f"/prosthesis/generated/{body['storage_path']}",
        follow_redirects=False,
    )
    assert response.status_code == 307
    assert response.headers["location"].startswith("https://fake.supabase/")


# ── errores ──────────────────────────────────────────────────────────────────

def test_generar_request_inexistente_da_404(fake_supabase):
    response = client.post(
        "/prosthesis/requests/11111111-1111-1111-1111-111111111111/generate"
    )
    assert response.status_code == 404


def test_geometria_imposible_da_422(fake_supabase):
    # distal más grande que proximal: el muñón quedaría invertido
    request_id = crear_request(
        {**COPITO, "proximal_circumference_cm": 13, "distal_circumference_cm": 18}
    )
    response = client.post(f"/prosthesis/requests/{request_id}/generate")
    assert response.status_code == 422
    assert any("invertido" in issue for issue in response.json()["detail"])
    assert fake_supabase.rows(GENERATED_TABLE) == []


def test_supabase_caido_al_crear_request_da_502(fake_supabase):
    fake_supabase.fail_table(REQUESTS_TABLE, "connection refused")
    response = client.post("/prosthesis/requests", json=COPITO)
    assert response.status_code == 502


def test_nombre_de_archivo_invalido_da_400(fake_supabase):
    assert client.get("/prosthesis/generated/../secreto.stl").status_code == 400
    assert client.get("/prosthesis/generated/modelo.txt").status_code == 400


@pytest.mark.parametrize(
    "cambio",
    [
        {"limb_side": "centro"},
        {"limb_position": "arriba"},
        {"stump_length_cm": 0},
        {"dog_weight_kg": -3},
    ],
)
def test_form_invalido_da_422(fake_supabase, cambio):
    assert client.post("/prosthesis/requests", json={**COPITO, **cambio}).status_code == 422


# ── endpoint de preview (no genera STL) ──────────────────────────────────────

def test_preview_de_parametros_no_toca_storage(fake_supabase):
    response = client.post("/prosthesis/socket/parameters", json=COPITO)
    assert response.status_code == 200
    assert response.json()["connector_radius_cm"] == 1.6
    assert fake_supabase.storage.buckets == {}


def test_health():
    assert client.get("/health").json() == {"status": "ok"}
