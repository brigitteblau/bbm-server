"""Fallback: escala un STL default (front/back) a las medidas del perro."""

from io import BytesIO
from uuid import uuid4

import trimesh

from app.models import ProsthesisForm, SocketParameters
from app.supabase_client import supabase
from app.utils import safe_filename_part

CM_TO_MM = 10.0
BASE_MODELS_BUCKET = "base-models"
ALGORITHM_VERSION = "trimesh-scale-v2"

# Medidas del STL base (mm): boca interna del socket y profundidad útil.
# El escalado se ancla en el socket para no deformar el pie.
BASE_SOCKET_DIAMETER_MM = 57.0
BASE_SOCKET_DEPTH_MM = 118.0
# Cuánto puede estirarse/achicarse el alto respecto del ancho (proporción)
MAX_Z_STRETCH = 0.15

DEFAULT_STL_BY_POSITION = {
  "delantera": "proto.stl",
    "trasera": "default_back.stl",
}


def generate(params: SocketParameters, form: ProsthesisForm) -> dict:
    base_filename = DEFAULT_STL_BY_POSITION[params.limb_position]
    file_bytes = supabase.storage.from_(BASE_MODELS_BUCKET).download(base_filename)

    mesh = trimesh.load_mesh(BytesIO(file_bytes), file_type="stl")
    if mesh.is_empty:
        raise ValueError(f"El STL base '{base_filename}' está vacío.")

    target_height_mm = params.height_cm * CM_TO_MM
    target_diameter_mm = params.top_radius_cm * 2 * CM_TO_MM

    # Escala uniforme según la boca del socket; el alto acompaña el largo del
    # muñón pero acotado, para que la bota no quede como un acordeón.
    scale_xy = target_diameter_mm / BASE_SOCKET_DIAMETER_MM
    scale_z = target_height_mm / BASE_SOCKET_DEPTH_MM
    scale_z = min(
        max(scale_z, scale_xy * (1 - MAX_Z_STRETCH)),
        scale_xy * (1 + MAX_Z_STRETCH),
    )
    scale_x = scale_y = scale_xy
    mesh.apply_scale([scale_x, scale_y, scale_z])

    mirrored = params.limb_side == "izquierda"
    if mirrored:
        # trimesh ya invierte el winding al aplicar una escala negativa
        mesh.apply_scale([-1, 1, 1])

    buffer = BytesIO()
    mesh.export(file_obj=buffer, file_type="stl")

    return {
        "generated_filename": f"{safe_filename_part(params.dog_name)}-{uuid4()}.stl",
        "generated_stl_bytes": buffer.getvalue(),
        "generation_parameters": {
            "base_model": base_filename,
            "scale_x": scale_x,
            "scale_y": scale_y,
            "scale_z": scale_z,
            "target_height_mm": target_height_mm,
            "target_diameter_mm": target_diameter_mm,
            "mirrored": mirrored,
        },
        "algorithm_version": ALGORITHM_VERSION,
    }