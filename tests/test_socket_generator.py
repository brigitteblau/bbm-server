from fastapi.testclient import TestClient

from app.main import app
from app.models import DogProsthesisRequest
from app.services.socket_generator import SocketParameterGenerator
from app.utils.geometry import circumference_to_radius


def test_circumference_to_radius():
    assert round(circumference_to_radius(18), 2) == 2.86


def test_socket_parameter_generator_for_border_collie_case():
    request = DogProsthesisRequest(
        dog_name="Max",
        dog_weight_kg=18,
        dog_breed="Border Collie",
        limb_position="front",
        limb_side="right",
        stump_length_cm=9,
        proximal_circumference_cm=18,
        distal_circumference_cm=13,
    )

    parameters = SocketParameterGenerator().generate(request)

    assert parameters.model_dump() == {
        "dog_name": "Max",
        "height_cm": 9,
        "top_radius_cm": 2.86,
        "bottom_radius_cm": 2.07,
        "wall_thickness_cm": 0.4,
        "connector_radius_cm": 1.6,
        "limb_position": "front",
        "limb_side": "right",
    }


def test_socket_parameters_endpoint():
    client = TestClient(app)

    response = client.post(
        "/prosthesis/socket/parameters",
        json={
            "dog_name": "Max",
            "dog_weight_kg": 18,
            "dog_breed": "Border Collie",
            "limb_position": "front",
            "limb_side": "right",
            "stump_length_cm": 9,
            "proximal_circumference_cm": 18,
            "distal_circumference_cm": 13,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "dog_name": "Max",
        "height_cm": 9,
        "top_radius_cm": 2.86,
        "bottom_radius_cm": 2.07,
        "wall_thickness_cm": 0.4,
        "connector_radius_cm": 1.6,
        "limb_position": "front",
        "limb_side": "right",
    }


def test_socket_parameters_endpoint_rejects_invalid_side():
    client = TestClient(app)

    response = client.post(
        "/prosthesis/socket/parameters",
        json={
            "dog_name": "Max",
            "dog_weight_kg": 18,
            "limb_position": "front",
            "limb_side": "center",
            "stump_length_cm": 9,
            "proximal_circumference_cm": 18,
            "distal_circumference_cm": 13,
        },
    )

    assert response.status_code == 422
