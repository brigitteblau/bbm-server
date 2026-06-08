from pathlib import Path
from io import BytesIO
import re
import unicodedata
from uuid import uuid4

import trimesh

from app.models import ProsthesisForm


MM_PER_CM = 10.0


def generate_scaled_stl(
    data: ProsthesisForm,
    base_stl_path: str | Path,
    output_dir: str | Path | None = None,
) -> dict[str, object]:
    """Generate a simple scaled STL from one base mesh and request measurements."""
    base_path = Path(base_stl_path)
    if not base_path.exists():
        raise FileNotFoundError(f"Base STL not found: {base_path}")

    mesh = trimesh.load_mesh(base_path, file_type="stl")
    return _scale_and_export_mesh(data, mesh)


def generate_scaled_stl_from_bytes(
    data: ProsthesisForm,
    base_stl_bytes: bytes,
    output_dir: str | Path | None = None,
) -> dict[str, object]:
    mesh = trimesh.load_mesh(BytesIO(base_stl_bytes), file_type="stl")
    return _scale_and_export_mesh(data, mesh)


def _scale_and_export_mesh(
    data: ProsthesisForm,
    mesh: trimesh.Trimesh,
) -> dict[str, object]:
    if mesh.is_empty:
        raise ValueError("Base STL is empty.")

    bounds = mesh.bounds
    current_width_mm = float(bounds[1][0] - bounds[0][0])
    current_depth_mm = float(bounds[1][1] - bounds[0][1])
    current_length_mm = float(bounds[1][2] - bounds[0][2])

    if current_width_mm == 0 or current_depth_mm == 0 or current_length_mm == 0:
        raise ValueError("Base STL has a zero-sized axis and cannot be scaled.")

    target_length_mm = float(data.stump_length_cm * MM_PER_CM)
    target_proximal_diameter_mm = _circumference_cm_to_diameter_mm(
        data.proximal_circumference_cm
    )
    target_distal_diameter_mm = _circumference_cm_to_diameter_mm(
        data.distal_circumference_cm
    )
    target_average_diameter_mm = (
        target_proximal_diameter_mm + target_distal_diameter_mm
    ) / 2

    scale_x = target_average_diameter_mm / current_width_mm
    scale_y = target_average_diameter_mm / current_depth_mm
    scale_z = target_length_mm / current_length_mm

    mesh.apply_scale([scale_x, scale_y, scale_z])

    generated_filename = f"{_safe_filename_part(data.dog_name)}-{uuid4()}.stl"
    stl_buffer = BytesIO()
    mesh.export(file_obj=stl_buffer, file_type="stl")

    return {
        "generated_filename": generated_filename,
        "generated_stl_bytes": stl_buffer.getvalue(),
        "generation_parameters": {
            "scale_x": scale_x,
            "scale_y": scale_y,
            "scale_z": scale_z,
            "target_length_mm": target_length_mm,
            "target_average_diameter_mm": target_average_diameter_mm,
            "target_proximal_diameter_mm": target_proximal_diameter_mm,
            "target_distal_diameter_mm": target_distal_diameter_mm,
            "base_width_mm": current_width_mm,
            "base_depth_mm": current_depth_mm,
            "base_length_mm": current_length_mm,
        },
        "algorithm_version": "simple-trimesh-scale-v1",
    }


def _circumference_cm_to_diameter_mm(circumference_cm: float) -> float:
    circumference_mm = float(circumference_cm * MM_PER_CM)
    return circumference_mm / 3.141592653589793


def _safe_filename_part(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip())
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", ascii_value.lower())
    cleaned = cleaned.strip("-_")
    return cleaned or "perro"
