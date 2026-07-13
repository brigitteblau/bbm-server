from fastapi import APIRouter

from app.models import ProsthesisForm, SocketParameters
from app.services.socket_parameters import SocketParameterGenerator

router = APIRouter()

parameter_generator = SocketParameterGenerator()


@router.post("/socket/parameters", response_model=SocketParameters)
def calculate_socket_parameters(form: ProsthesisForm):
    """Calcula los parámetros del socket sin generar nada. Útil para preview."""
    return parameter_generator.generate(form)