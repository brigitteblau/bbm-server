"""Medición del perro a partir de una foto lateral.

ESCALA (una foto no tiene cm), en este orden de prioridad:
  A) Marcador ArUco impreso (ia/marcador_aruco.png, cuadrado negro de 5 cm): se detecta solo.
  B) Objeto de largo conocido: 2 puntos (ref_a, ref_b) + su largo en cm.
  C) Largo de la pata sana medido con cinta.

PUNTOS (nombres de Dog-Pose; los detecta detector.py y se pueden corregir):
  <pata>_elbow = codo (delantera) / rodilla (trasera)
  <pata>_knee  = carpo (delantera) / tarso (trasera)
  <pata>_paw   = apoyo,    con <pata> en front_left, front_right, rear_left, rear_right
  nose, left_ear_base, right_ear_base  -> tamaño de cabeza
  munon_art, munon_punta               -> muñón (siempre a mano)

Circunferencias y peso NO salen de una foto 2D: van con cinta y balanza.
"""
import math

CONTRARIA = {"front_left": "front_right", "front_right": "front_left",
             "rear_left": "rear_right", "rear_right": "rear_left"}


def escala_aruco(img_bgr, lado_cm: float) -> float | None:
    """Píxeles por cm según un marcador ArUco (DICT_4X4_50), o None si no hay."""
    import cv2
    import numpy as np

    dic = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    det = cv2.aruco.ArucoDetector(dic, cv2.aruco.DetectorParameters())
    esquinas, ids, _ = det.detectMarkers(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY))
    if ids is None or len(esquinas) == 0:
        return None
    c = esquinas[0].reshape(4, 2)
    return float(np.mean([np.linalg.norm(c[i] - c[(i + 1) % 4]) for i in range(4)])) / lado_cm


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _pata(p: dict, leg: str):
    ks = [f"{leg}_elbow", f"{leg}_knee", f"{leg}_paw"]
    if all(k in p for k in ks):
        return _dist(p[ks[0]], p[ks[1]]), _dist(p[ks[1]], p[ks[2]])
    return None


def largo_pata_px(p: dict, leg: str) -> float | None:
    s = _pata(p, leg)
    return s[0] + s[1] if s else None


def escala(img_bgr, puntos: dict, pata_faltante: str, lado_aruco_cm=5.0,
           ref_cm=None, sana_cm=None) -> tuple[float, str] | None:
    px = escala_aruco(img_bgr, lado_aruco_cm)
    if px:
        return px, "aruco"
    if ref_cm and "ref_a" in puntos and "ref_b" in puntos:
        return _dist(puntos["ref_a"], puntos["ref_b"]) / ref_cm, "referencia"
    sana_px = largo_pata_px(puntos, CONTRARIA[pata_faltante])
    if sana_cm and sana_px:
        return sana_px / sana_cm, "pata sana medida con cinta"
    return None


def medidas_desde_puntos(puntos: dict, px_por_cm: float, pata_faltante: str, bbox=None) -> dict:
    """Puntos en px -> medidas en cm, con los nombres que espera prediccion.predecir."""
    def cm(v):
        return None if v is None else round(v / px_por_cm, 2)

    sana = _pata(puntos, CONTRARIA[pata_faltante])
    tras = pata_faltante.startswith("rear")
    otro_par = ("front_left", "front_right") if tras else ("rear_left", "rear_right")
    otras = [o for o in (_pata(puntos, l) for l in otro_par) if o]
    orejas = [puntos[k] for k in ("left_ear_base", "right_ear_base") if k in puntos]

    cabeza = None
    if orejas and "nose" in puntos:
        cx = sum(o[0] for o in orejas) / len(orejas)
        cy = sum(o[1] for o in orejas) / len(orejas)
        cabeza = _dist(puntos["nose"], (cx, cy))

    out = {
        "es_trasera": int(tras),
        "sana_sup": cm(sana[0]) if sana else None,
        "sana_inf": cm(sana[1]) if sana else None,
        "otro_par_sup": cm(sum(o[0] for o in otras) / len(otras)) if otras else None,
        "otro_par_inf": cm(sum(o[1] for o in otras) / len(otras)) if otras else None,
        "cabeza": cm(cabeza),
        "caja_alto": cm(bbox[3] - bbox[1]) if bbox else None,
        "caja_ancho": cm(bbox[2] - bbox[0]) if bbox else None,
        "munon_largo": cm(_dist(puntos["munon_art"], puntos["munon_punta"]))
                       if "munon_art" in puntos and "munon_punta" in puntos else None,
    }
    return {k: v for k, v in out.items() if v is not None}
