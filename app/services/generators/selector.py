"""Decide qué generador usar. El cliente no elige: el back sabe.

Política: Blender si está disponible y los parámetros son válidos;
si falla o no está, fallback a escalar el STL default con trimesh.
"""

import logging
import os

from app.models import ProsthesisForm, SocketParameters
from app.services.generators import blender_gn, trimesh_scaler

logger = logging.getLogger(__name__)


def validate_geometry(params: SocketParameters) -> list[str]:
    """Chequeos de sentido físico antes de generar nada."""
    issues = []
    if params.wall_thickness_cm >= params.bottom_radius_cm:
        issues.append(
            "El espesor de pared es mayor o igual al radio distal: el cono queda sin hueco."
        )
    if params.bottom_radius_cm > params.top_radius_cm:
        issues.append(
            "El radio distal es mayor que el proximal: el muñón quedaría invertido."
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
        result = trimesh_scaler.generate(params, form)

    result["fallback_reason"] = fallback_reason
    return result