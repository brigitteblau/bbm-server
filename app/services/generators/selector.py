"""Decide qué generador usar. El cliente no elige: el back sabe.

Cadena de generadores, en orden:
  1. Blender Geometry Nodes, si BLENDER_ENABLED=true y bpy está instalado.
  2. Socket paramétrico en Python puro (sin dependencias, siempre disponible).
  3. Escalado del STL base con trimesh (último recurso, necesita Supabase).
"""

import logging
import os

from app.models import ProsthesisForm, SocketParameters
from app.services.generators import blender_gn, parametric_socket, paw_foot, trimesh_scaler

logger = logging.getLogger(__name__)


MIN_WALL_MARGIN = 1.6  # el radio distal tiene que ser al menos esto x la pared


def validate_geometry(params: SocketParameters) -> list[str]:
    """Chequeos de sentido físico antes de generar nada."""
    issues = []
    if params.wall_thickness_cm >= params.bottom_radius_cm:
        issues.append(
            "El espesor de pared es mayor o igual al radio distal: el socket queda macizo."
        )
    elif params.bottom_radius_cm < params.wall_thickness_cm * MIN_WALL_MARGIN:
        issues.append(
            "El radio distal es demasiado chico para el espesor de pared: "
            "la cavidad quedaría casi cerrada."
        )
    if params.bottom_radius_cm > params.top_radius_cm:
        issues.append(
            "El radio distal es mayor que el proximal: el muñón quedaría invertido."
        )
    if params.height_cm <= params.top_radius_cm:
        issues.append(
            "El muñón es más corto que su propio radio proximal: el socket no agarra."
        )
    return issues


def _blender_enabled() -> bool:
    return os.getenv("BLENDER_ENABLED", "false").lower() == "true"


def generate(params: SocketParameters, form: ProsthesisForm) -> dict:
    result = None
    fallback_reason = None

    if not _blender_enabled():
        fallback_reason = "Blender deshabilitado por configuración (BLENDER_ENABLED)"
    elif not blender_gn.is_available():
        fallback_reason = "bpy no está instalado en este entorno"
    else:
        try:
            result = blender_gn.generate(params, form)
        except Exception as exc:
            logger.warning("Blender GN falló, fallback a trimesh: %s", exc)
            fallback_reason = f"Blender falló: {exc}"

    if result is None:
        try:
            result = parametric_socket.generate(params, form)
        except Exception as exc:
            logger.warning("Socket paramétrico falló, fallback a trimesh: %s", exc)
            fallback_reason = _join_reasons(
                fallback_reason, f"Socket paramétrico falló: {exc}"
            )

    if result is None:
        result = trimesh_scaler.generate(params, form)

    result["fallback_reason"] = fallback_reason
    return result


def generate_foot(params: SocketParameters, form: ProsthesisForm) -> dict | None:
    """El pie que encastra en el poste del socket.

    Es una pieza aparte y opcional: si falla, el socket igual se entrega.
    """
    try:
        return paw_foot.generate(params, form)
    except Exception as exc:
        logger.warning("No se pudo generar el pie: %s", exc)
        return None


def _join_reasons(first: str | None, second: str) -> str:
    return f"{first}; {second}" if first else second