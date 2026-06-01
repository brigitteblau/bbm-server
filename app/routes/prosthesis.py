from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.models import ProsthesisForm
from app.services.stl_modifier import generate_scaled_stl, generate_scaled_stl_from_bytes
from app.supabase_client import supabase

router = APIRouter()


@router.post("/generate")
def generate_prosthesis(data: ProsthesisForm):
    project_root = Path(__file__).resolve().parents[2]
    output_dir = project_root / "app" / "generated_models"

    try:
        if data.base_stl_path:
            result = generate_scaled_stl(data, data.base_stl_path, output_dir)
            base_source = data.base_stl_path
        else:
            storage_path = data.base_model_storage_path or "default.stl"
            file_bytes = supabase.storage.from_("base-models").download(storage_path)
            result = generate_scaled_stl_from_bytes(data, file_bytes, output_dir)
            base_source = f"supabase://base-models/{storage_path}"
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo descargar el STL base desde Supabase: {exc}",
        ) from exc

    return {
        "success": True,
        "message": "STL generado localmente",
        "dog_name": data.dog_name,
        "base_source": base_source,
        **result,
    }
