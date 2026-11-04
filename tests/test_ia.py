"""Tests de los endpoints de IA. Se saltean si no están las dependencias de requirements-ia.txt."""
import pytest

pytest.importorskip("sklearn")
pytest.importorskip("multipart")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)

# Perro de ~30 cm de pata delantera, le falta la izquierda desde la mitad del antebrazo
MEDIDAS = {"es_trasera": 0, "sana_sup": 18.2, "sana_inf": 12.0, "munon_largo": 9.5,
           "otro_par_sup": 19.0, "otro_par_inf": 14.5}


def test_status():
    r = client.get("/ia/status")
    assert r.status_code == 200
    assert r.json()["prediccion"] is True


def test_predice_largo_razonable():
    r = client.post("/ia/predict-length", json=MEDIDAS)
    assert r.status_code == 200
    body = r.json()
    # tiene que estar cerca de copiar la pata sana (30.2 - 9.5 = 20.7 cm)
    assert 15 < body["largo_faltante_cm"] < 26
    assert body["espejo_largo_cm"] == 20.7
    assert body["error_tipico_cm"] > 0


def test_funciona_sin_opcionales():
    r = client.post("/ia/predict-length", json={k: MEDIDAS[k] for k in
                                                 ("es_trasera", "sana_sup", "sana_inf", "munon_largo")})
    assert r.status_code == 200
    assert r.json()["medidas_opcionales_usadas"] == []


def test_valida_medidas():
    r = client.post("/ia/predict-length", json={**MEDIDAS, "sana_sup": -1})
    assert r.status_code == 422
