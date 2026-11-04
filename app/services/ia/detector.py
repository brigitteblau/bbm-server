"""Detector automático de puntos de las patas (YOLO11-pose entrenado con Dog-Pose).

Devuelve, para el perro más grande de la foto, los puntos anatómicos con su
confianza y la caja del perro. Si ultralytics no está instalado o falta el
modelo, devuelve None y el front usa clicks manuales.
"""
import os

from app.services.ia import MODELS_DIR

PESOS = os.path.join(MODELS_DIR, "detector_patas.pt")

KP = ["front_left_paw", "front_left_knee", "front_left_elbow", "rear_left_paw", "rear_left_knee",
      "rear_left_elbow", "front_right_paw", "front_right_knee", "front_right_elbow", "rear_right_paw",
      "rear_right_knee", "rear_right_elbow", "tail_start", "tail_end", "left_ear_base",
      "right_ear_base", "nose", "chin", "left_ear_tip", "right_ear_tip", "left_eye", "right_eye",
      "withers", "throat"]
# Estos 4 puntos vienen vacíos en todo el dataset: el modelo no aprendió nada útil para ellos.
SIN_DATOS = {"withers", "throat", "left_eye", "right_eye"}

_modelo = None


def disponible() -> bool:
    if not os.path.exists(PESOS):
        return False
    try:
        import ultralytics  # noqa: F401
        return True
    except Exception:
        return False


def detectar(img_bgr, conf_min: float = 0.35) -> dict | None:
    global _modelo
    if not disponible():
        return None
    if _modelo is None:
        from ultralytics import YOLO  # lazy: es pesado
        _modelo = YOLO(PESOS)
    r = _modelo.predict(img_bgr, imgsz=320, verbose=False)[0]
    if r.boxes is None or len(r.boxes) == 0:
        return {"bbox": None, "puntos": {}}
    cajas = r.boxes.xyxy.cpu().numpy()
    i = int(((cajas[:, 2] - cajas[:, 0]) * (cajas[:, 3] - cajas[:, 1])).argmax())
    xy = r.keypoints.xy[i].cpu().numpy()
    cf = r.keypoints.conf[i].cpu().numpy() if r.keypoints.conf is not None else [1.0] * len(KP)
    puntos = {n: [float(xy[j, 0]), float(xy[j, 1]), round(float(cf[j]), 2)]
              for j, n in enumerate(KP) if cf[j] >= conf_min and n not in SIN_DATOS}
    return {"bbox": [float(v) for v in cajas[i]], "puntos": puntos}
