import math
import tempfile
from pathlib import Path
from uuid import uuid4

import bpy

from app.models import ProsthesisForm
from app.utils import safe_filename_part

MM_PER_CM = 10.0


def _circumference_cm_to_radius_mm(circumference_cm: float) -> float:
    return (circumference_cm * MM_PER_CM) / (2 * math.pi)


def generate_gn_stl(data: ProsthesisForm, blend_bytes: bytes) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".blend", delete=False) as tmp_blend:
        tmp_blend.write(blend_bytes)
        tmp_blend_path = tmp_blend.name

    try:
        bpy.ops.wm.open_mainfile(filepath=tmp_blend_path)
    finally:
        Path(tmp_blend_path).unlink(missing_ok=True)

    obj = bpy.data.objects["Prosthesis"]
    mod = obj.modifiers["GeometryNodes"]
    ng = mod.node_group

    params = {
        "Stump Length": data.stump_length_cm * MM_PER_CM,
        "Proximal Radius": _circumference_cm_to_radius_mm(data.proximal_circumference_cm),
        "Distal Radius": _circumference_cm_to_radius_mm(data.distal_circumference_cm),
        "Wall Thickness": data.wall_thickness_mm,
        "Resolution": 64,
    }

    for item in ng.interface.items_tree:
        if item.name in params:
            mod[item.identifier] = params[item.name]

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp_stl:
        tmp_stl_path = tmp_stl.name

    try:
        bpy.ops.wm.stl_export(
            filepath=tmp_stl_path,
            use_selection=True,
            apply_modifiers=True,
        )
        stl_bytes = Path(tmp_stl_path).read_bytes()
    finally:
        Path(tmp_stl_path).unlink(missing_ok=True)

    filename = f"{safe_filename_part(data.dog_name)}-{uuid4()}.stl"

    return {
        "generated_filename": filename,
        "generated_stl_bytes": stl_bytes,
        "generation_parameters": {
            "stump_length_mm": params["Stump Length"],
            "proximal_radius_mm": params["Proximal Radius"],
            "distal_radius_mm": params["Distal Radius"],
            "wall_thickness_mm": params["Wall Thickness"],
            "resolution": params["Resolution"],
        },
        "algorithm_version": "geometry-nodes-blender-v1",
    }
