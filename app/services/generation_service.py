from app.models import ProsthesisForm


def generate_prosthesis(data: ProsthesisForm) -> dict[str, str]:
    return {
        "message": "received",
        "dog_name": data.dog_name,
    }
