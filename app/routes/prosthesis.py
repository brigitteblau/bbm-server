from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.models import (
    ProsthesisForm,
    ProsthesisRequestRecord,
    SocketParameters,
)
from app.services.socket_parameters import SocketParameterGenerator
from app.services.generators import selector
from app.supabase_client import supabase

router = APIRouter()

parameter_generator = SocketParameterGenerator()

GENERATED_BUCKET = "generated-models"
GENERATED_TABLE = "generated_models"
REQUESTS_TABLE = "prosthesis_requests"

SIGNED_URL_EXPIRES_SECONDS = 60 * 60 * 24 * 7


@router.post("/socket/parameters", response_model=SocketParameters)
def calculate_socket_parameters(form: ProsthesisForm):
    """Solo calcula parámetros, no genera STL. Sirve para mostrar preview en el front."""
    return parameter_generator.generate(form)


@router.post("/requests", response_model=ProsthesisRequestRecord)
def create_request(form: ProsthesisForm):
    """Paso 1 del front: guarda las medidas y devuelve el id."""
    record = {
        "dog_name": form.dog_name,
        "dog_weight_kg": form.dog_weight_kg,
        "dog_breed": form.dog_breed,
        "dog_size": form.dog_size,
        "limb_position": form.limb_position,
        "limb_side": form.limb_side,
        "stump_length_cm": form.stump_length_cm,
        "proximal_circumference_cm": form.proximal_circumference_cm,
        "distal_circumference_cm": form.distal_circumference_cm,
    }

    if form.user_id:
        record["user_id"] = str(form.user_id)

    try:
        response = supabase.table(REQUESTS_TABLE).insert(record).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo guardar la request: {exc}",
        ) from exc

    if not response.data:
        raise HTTPException(
            status_code=502,
            detail="Supabase no devolvió la request creada",
        )

    row = response.data[0]

    return ProsthesisRequestRecord(
        request_id=row["id"],
        dog_name=row["dog_name"],
    )


@router.post("/requests/{request_id}/generate")
def generate_from_request(request_id: UUID):
    """Paso 2 del front: genera el STL a partir de una request guardada."""

    # 1. Leer la request desde la DB.
    # No confiamos en que el front vuelva a mandar las medidas.
    try:
        response = (
            supabase.table(REQUESTS_TABLE)
            .select("*")
            .eq("id", str(request_id))
            .single()
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Request no encontrada: {exc}",
        ) from exc

    row = response.data

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Request no encontrada",
        )

    form = ProsthesisForm(
        user_id=row.get("user_id"),
        request_id=row["id"],
        dog_name=row["dog_name"],
        dog_weight_kg=row["dog_weight_kg"],
        dog_breed=row.get("dog_breed"),
        dog_size=row.get("dog_size"),
        limb_position=row["limb_position"],
        limb_side=row["limb_side"],
        stump_length_cm=row["stump_length_cm"],
        proximal_circumference_cm=row["proximal_circumference_cm"],
        distal_circumference_cm=row["distal_circumference_cm"],
    )

    # 2. Medidas → parámetros
    params = parameter_generator.generate(form)

    # 3. Validación de sentido físico
    issues = selector.validate_geometry(params)

    if issues:
        raise HTTPException(
            status_code=422,
            detail=issues,
        )

    # 4. Generar STL con Blender o fallback
    try:
        result = selector.generate(params, form)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Falló la generación del STL: {exc}",
        ) from exc

    stl_bytes = result.pop("generated_stl_bytes")
    filename = str(result["generated_filename"])

    # 5. El pie es una pieza aparte: encastra en el poste del socket.
    foot = selector.generate_foot(params, form)

    # 6. Subir a Supabase y registrar el modelo
    try:
        _upload(filename, stl_bytes)
        download_url = _signed_url(filename)

        foot_filename = None
        foot_download_url = None
        if foot is not None:
            foot_filename = str(foot["generated_filename"])
            _upload(foot_filename, foot.pop("generated_stl_bytes"))
            foot_download_url = _signed_url(foot_filename)
            result["generation_parameters"]["foot"] = {
                "storage_path": foot_filename,
                "algorithm_version": foot["algorithm_version"],
                **foot["generation_parameters"],
            }

        record = _insert_record(
            form,
            params,
            filename,
            result,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Falló la subida a Supabase: {exc}",
        ) from exc

    return {
        "success": True,
        "request_id": str(request_id),
        "dog_name": form.dog_name,
        "socket_parameters": params,
        "generator_used": result["algorithm_version"],
        "fallback_reason": result["fallback_reason"],
        "generated_model_id": record.get("id") if record else None,
        "storage_path": filename,
        "download_url": download_url,
        "foot_storage_path": foot_filename,
        "foot_download_url": foot_download_url,
    }


@router.get("/generated/{filename}")
def download_generated_model(filename: str):
    if Path(filename).name != filename or not filename.lower().endswith(".stl"):
        raise HTTPException(
            status_code=400,
            detail="Nombre de archivo inválido",
        )

    try:
        return RedirectResponse(_signed_url(filename))
    except Exception as exc:
        raise HTTPException(
            status_code=404,
            detail=f"STL no encontrado: {exc}",
        ) from exc


def _upload(storage_path: str, stl_bytes: bytes) -> None:
    supabase.storage.from_(GENERATED_BUCKET).upload(
        storage_path,
        stl_bytes,
        {
            "content-type": "model/stl",
            "upsert": "false",
        },
    )


def _signed_url(storage_path: str) -> str:
    response = supabase.storage.from_(GENERATED_BUCKET).create_signed_url(
        storage_path,
        SIGNED_URL_EXPIRES_SECONDS,
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

    response = (
        supabase.table(GENERATED_TABLE)
        .insert(record)
        .execute()
    )

    return response.data[0] if response.data else None