"""Decide qué generador usar. El cliente no elige: el back sabe.

Política: Blender siempre que bpy esté instalado (no hace falta prenderlo);
si falla o no está, fallback a escalar el STL default con trimesh.
BLENDER_ENABLED=false lo apaga a mano (por ejemplo, para comparar).
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
    # Prendido por defecto: decide si bpy está instalado. Solo "false" lo apaga.
    return os.getenv("BLENDER_ENABLED", "true").lower() != "false"


def generate(params: SocketParameters, form: ProsthesisForm) -> dict:
    result = None
    fallback_reason = None

    if not _blender_enabled():
        fallback_reason = "Blender apagado a mano (BLENDER_ENABLED=false)"
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