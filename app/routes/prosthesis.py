from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.models import ProsthesisForm, SocketParameters
from app.services.socket_parameters import SocketParameterGenerator
from app.services.generators import selector
from app.supabase_client import supabase

router = APIRouter()

parameter_generator = SocketParameterGenerator()

GENERATED_BUCKET = "generated-models"
GENERATED_TABLE = "generated_models"
SIGNED_URL_EXPIRES_SECONDS = 60 * 60 * 24 * 7


@router.post("/socket/parameters", response_model=SocketParameters)
def calculate_socket_parameters(form: ProsthesisForm):
    """Solo calcula parámetros, no genera STL. Sirve para mostrar preview en el front."""
    return parameter_generator.generate(form)


@router.post("/generate")
def generate_prosthesis(form: ProsthesisForm):
    # 1. medidas → parámetros
    params = parameter_generator.generate(form)

    # 2. validación de sentido físico
    issues = selector.validate_geometry(params)
    if issues:
        raise HTTPException(status_code=422, detail=issues)

    # 3. generar (Blender o fallback, lo decide el selector)
    try:
        result = selector.generate(params, form)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Falló la generación del STL: {exc}"
        ) from exc

    # 4. subir a Supabase y registrar
    stl_bytes = result.pop("generated_stl_bytes")
    filename = str(result["generated_filename"])

    try:
        supabase.storage.from_(GENERATED_BUCKET).upload(
            filename,
            stl_bytes,
            {"content-type": "model/stl", "upsert": "false"},
        )
        download_url = _signed_url(filename)
        record = _insert_record(form, params, filename, result)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Falló la subida a Supabase: {exc}"
        ) from exc

    return {
        "success": True,
        "dog_name": form.dog_name,
        "socket_parameters": params,
        "generator_used": result["algorithm_version"],
        "fallback_reason": result["fallback_reason"],
        "generated_model_id": record.get("id") if record else None,
        "storage_path": filename,
        "download_url": download_url,
        "generation_parameters": result["generation_parameters"],
    }


@router.get("/generated/{filename}")
def download_generated_model(filename: str):
    if Path(filename).name != filename or not filename.lower().endswith(".stl"):
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido")
    try:
        return RedirectResponse(_signed_url(filename))
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"STL no encontrado: {exc}") from exc


def _signed_url(storage_path: str) -> str:
    response = supabase.storage.from_(GENERATED_BUCKET).create_signed_url(
        storage_path, SIGNED_URL_EXPIRES_SECONDS
    )
    signed = response.get("signedURL") or response.get("signedUrl")
    if not signed:
        raise RuntimeError("Supabase no devolvió una signed URL")
    return signed


def _insert_record(
    form: ProsthesisForm,
    params: SocketParameters,
    storage_path: str,
    result: dict,
) -> dict | None:
    record = {
        "generated_stl_path": storage_path,
        "algorithm_version": result["algorithm_version"],
        "generation_parameters": result["generation_parameters"],
        "socket_parameters": params.model_dump(),
        "fallback_reason": result["fallback_reason"],
        "status": "generated",
    }
    if form.user_id:
        record["user_id"] = str(form.user_id)
    if form.request_id:
        record["request_id"] = str(form.request_id)

    response = supabase.table(GENERATED_TABLE).insert(record).execute()
    return response.data[0] if response.data else None