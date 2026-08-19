"""Fallback: escala un STL default (front/back) a las medidas del perro."""

from io import BytesIO
from uuid import uuid4

import trimesh

from app.models import ProsthesisForm, SocketParameters
from app.supabase_client import supabase
from app.utils import safe_filename_part

CM_TO_MM = 10.0
BASE_MODELS_BUCKET = "base-models"
ALGORITHM_VERSION = "trimesh-scale-v1"

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

    bounds = mesh.bounds
    base_width_mm = float(bounds[1][0] - bounds[0][0])
    base_depth_mm = float(bounds[1][1] - bounds[0][1])
    base_height_mm = float(bounds[1][2] - bounds[0][2])
    if 0 in (base_width_mm, base_depth_mm, base_height_mm):
        raise ValueError("El STL base tiene un eje de tamaño cero.")

    target_height_mm = params.height_cm * CM_TO_MM
    # diámetro objetivo: promedio entre proximal y distal
    target_diameter_mm = (params.top_radius_cm + params.bottom_radius_cm) * CM_TO_MM

    scale_x = target_diameter_mm / base_width_mm
    scale_y = target_diameter_mm / base_depth_mm
    scale_z = target_height_mm / base_height_mm
    mesh.apply_scale([scale_x, scale_y, scale_z])

    mirrored = params.limb_side == "left"
    if mirrored:
        mesh.apply_scale([-1, 1, 1])
        mesh.invert()  # corrige las normales después del espejo

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