from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.models import ProsthesisForm
from app.services.blender_service import generate_gn_stl
from app.services.stl_modifier import generate_scaled_stl, generate_scaled_stl_from_bytes
from app.supabase_client import supabase

router = APIRouter()


GENERATED_MODELS_BUCKET = "generated-models"
SIGNED_URL_EXPIRES_SECONDS = 60 * 60 * 24 * 7
GENERATED_MODELS_TABLE = "generated_models"


def _clean_optional_path(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = value.strip()
    if not cleaned or cleaned.lower() in {"string", "null", "none"}:
        return None

    return cleaned


def _create_generated_model_signed_url(storage_path: str) -> str:
    response = supabase.storage.from_(GENERATED_MODELS_BUCKET).create_signed_url(
        storage_path,
        SIGNED_URL_EXPIRES_SECONDS,
    )
    signed_url = response.get("signedURL") or response.get("signedUrl")
    if not signed_url:
        raise RuntimeError("Supabase did not return a signed URL")

    return signed_url


def _insert_generated_model_record(
    data: ProsthesisForm,
    generated_storage_path: str,
    result: dict[str, object],
) -> dict[str, object] | None:
    record = {
        "generated_stl_path": generated_storage_path,
        "algorithm_version": result["algorithm_version"],
        "generation_parameters": result["generation_parameters"],
        "status": "generated",
    }

    if data.user_id:
        record["user_id"] = str(data.user_id)
    if data.request_id:
        record["request_id"] = str(data.request_id)
    if data.base_model_id:
        record["base_model_id"] = str(data.base_model_id)

    response = supabase.table(GENERATED_MODELS_TABLE).insert(record).execute()

    if not response.data:
        return None

    return response.data[0]


@router.post("/generate")
def generate_prosthesis(data: ProsthesisForm):
    # ── Paso 1: generar el STL ────────────────────────────────────────────────
    try:
        base_stl_path = _clean_optional_path(data.base_stl_path)

        if data.limb_position == "delantera":
            result = generate_gn_stl(data)
            base_source = "procedural-gn"
        elif base_stl_path:
            result = generate_scaled_stl(data, base_stl_path)
            base_source = base_stl_path
        else:
            storage_path = (
                _clean_optional_path(data.base_model_storage_path) or "default.stl"
            )
            file_bytes = supabase.storage.from_("base-models").download(storage_path)
            result = generate_scaled_stl_from_bytes(data, file_bytes)
            base_source = f"supabase://base-models/{storage_path}"
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error generando el STL: {exc}",
        ) from exc

    # ── Paso 2: subir a Supabase ──────────────────────────────────────────────
    try:
        generated_stl_bytes = result.pop("generated_stl_bytes")
        generated_filename = str(result["generated_filename"])
        generated_storage_path = generated_filename
        supabase.storage.from_(GENERATED_MODELS_BUCKET).upload(
            generated_storage_path,
            generated_stl_bytes,
            {
                "content-type": "model/stl",
                "upsert": "false",
            },
        )
        download_url = _create_generated_model_signed_url(generated_storage_path)
        generated_model = _insert_generated_model_record(
            data,
            generated_storage_path,
            result,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"STL generado OK pero falló Supabase: {exc}",
        ) from exc

    return {
        "success": True,
        "message": "STL generado y subido a Supabase",
        "dog_name": data.dog_name,
        "base_source": base_source,
        "generated_storage_bucket": GENERATED_MODELS_BUCKET,
        "generated_storage_path": generated_storage_path,
        "generated_model": generated_model,
        "generated_model_id": generated_model.get("id") if generated_model else None,
        "download_url": download_url,
        **result,
    }


@router.get("/generated/{filename}")
def download_generated_model(filename: str):
    if Path(filename).name != filename or not filename.lower().endswith(".stl"):
        raise HTTPException(status_code=400, detail="Invalid generated STL filename")

    try:
        signed_url = _create_generated_model_signed_url(filename)
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Generated STL not found in Supabase: {exc}",
        ) from exc

    return RedirectResponse(signed_url)

