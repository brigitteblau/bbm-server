"""Endpoints de IA (opcionales). Se montan en /ia solo si están las dependencias
de requirements-ia.txt (ver app/main.py).

Flujo pensado para el front:
  1. POST /ia/detect          foto -> puntos automáticos (para mostrarlos y dejar corregirlos)
  2. POST /ia/measure         foto + puntos corregidos -> medidas en cm
                              (+ sugerencia de campos para POST /prosthesis/requests)
  3. POST /ia/predict-length  medidas -> largo de la pata que falta
"""
import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.services.ia import detector, foto, prediccion

router = APIRouter()

PATAS = {
    "front_left": ("delantera", "izquierda"),
    "front_right": ("delantera", "derecha"),
    "rear_left": ("trasera", "izquierda"),
    "rear_right": ("trasera", "derecha"),
}


class LengthInput(BaseModel):
    """Medidas en cm. Las opcionales mejoran la predicción (corrigen pose y perspectiva)."""

    es_trasera: int = Field(ge=0, le=1)
    sana_sup: float = Field(gt=0, description="pata sana: codo->carpo / rodilla->tarso")
    sana_inf: float = Field(gt=0, description="pata sana: carpo/tarso -> apoyo")
    munon_largo: float = Field(gt=0, description="desde la articulación de arriba hasta la punta")
    otro_par_sup: float | None = Field(default=None, gt=0)
    otro_par_inf: float | None = Field(default=None, gt=0)
    cabeza: float | None = Field(default=None, gt=0)
    caja_alto: float | None = Field(default=None, gt=0)
    caja_ancho: float | None = Field(default=None, gt=0)


async def _imagen(archivo: UploadFile):
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="opencv no está instalado (requirements-ia.txt)") from exc

    img = cv2.imdecode(np.frombuffer(await archivo.read(), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="No se pudo leer la imagen")
    return img


@router.get("/status")
def status():
    """Qué partes de la IA están disponibles en este entorno."""
    try:
        import cv2  # noqa: F401
        medicion = True
    except ImportError:
        medicion = False
    return {"detector": detector.disponible(), "medicion_foto": medicion,
            "prediccion": prediccion.disponible()}


@router.post("/detect")
async def detect(foto_perro: UploadFile = File(...), lado_aruco_cm: float = Form(5.0)):
    img = await _imagen(foto_perro)
    det = detector.detectar(img)
    px = foto.escala_aruco(img, lado_aruco_cm)
    return {
        "detector_disponible": det is not None,
        "bbox": det["bbox"] if det else None,
        "puntos": det["puntos"] if det else {},
        "aruco_px_por_cm": round(px, 2) if px else None,
    }


@router.post("/measure")
async def measure(
    foto_perro: UploadFile = File(...),
    puntos: str = Form(..., description='JSON {"front_right_elbow": [x, y], ...} en px'),
    pata_faltante: str = Form(..., pattern="^(front|rear)_(left|right)$"),
    bbox: str = Form("null"),
    lado_aruco_cm: float = Form(5.0),
    ref_cm: float | None = Form(None),
    sana_cm: float | None = Form(None),
):
    img = await _imagen(foto_perro)
    try:
        pts = json.loads(puntos)
        caja = json.loads(bbox)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"JSON inválido: {exc}") from exc

    esc = foto.escala(img, pts, pata_faltante, lado_aruco_cm, ref_cm, sana_cm)
    if esc is None:
        raise HTTPException(
            status_code=400,
            detail="Falta la escala: no hay marcador ArUco. Mandá ref_a/ref_b + ref_cm, "
                   "o el largo de la pata sana medido con cinta (sana_cm).",
        )
    px_cm, metodo = esc
    medidas = foto.medidas_desde_puntos(pts, px_cm, pata_faltante, caja)
    position, side = PATAS[pata_faltante]
    return {
        "metodo_escala": metodo,
        "px_por_cm": round(px_cm, 2),
        "medidas": medidas,
        # Lo que se puede precargar en POST /prosthesis/requests. Peso y circunferencias van a mano.
        "prosthesis_form_hint": {
            "limb_position": position,
            "limb_side": side,
            "stump_length_cm": medidas.get("munon_largo"),
        },
    }


@router.post("/predict-length")
def predict_length(medidas: LengthInput):
    if not prediccion.disponible():
        raise HTTPException(status_code=503, detail="Modelo de IA no disponible en este entorno")
    try:
        return prediccion.predecir(medidas.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
