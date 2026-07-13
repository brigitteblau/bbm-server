from fastapi.testclient import TestClient

from app.main import app
from app.models import ProsthesisForm
from app.services.socket_parameters import SocketParameterGenerator
from app.utils.geometry import circumference_to_radius

client = TestClient(app)

MAX_PAYLOAD = {
    "dog_name": "Max",
    "dog_weight_kg": 18,
    "dog_breed": "Border Collie",
    "limb_position": "front",
    "limb_side": "right",
    "stump_length_cm": 9,
    "proximal_circumference_cm": 18,
    "distal_circumference_cm": 13,
}


def test_circumference_to_radius():
    assert round(circumference_to_radius(18), 2) == 2.86


def test_parametros_para_max():
    form = ProsthesisForm(**MAX_PAYLOAD)
    params = SocketParameterGenerator().generate(form)

    assert params.height_cm == 9
    assert params.top_radius_cm == 2.86
    assert params.bottom_radius_cm == 2.07
    assert params.wall_thickness_cm == 0.4
    assert params.connector_radius_cm == 1.6


def test_endpoint_parametros():
    response = client.post("/prosthesis/socket/parameters", json=MAX_PAYLOAD)
    assert response.status_code == 200
    body = response.json()
    assert body["top_radius_cm"] == 2.86
    assert body["limb_side"] == "right"


def test_endpoint_rechaza_lado_invalido():
    payload = {**MAX_PAYLOAD, "limb_side": "center"}
    response = client.post("/prosthesis/socket/parameters", json=payload)
    assert response.status_code == 422