"""Predice la pata que falta con el modelo entrenado con perros REALES (Dog-Pose).

El modelo trabaja en proporciones: todo se divide por U = largo de la pata sana
(sup + inf), así no importa el tamaño del perro ni el zoom de la foto.
Validación por raza (razas que el modelo no vio): 12.6 % de error medio vs
17.9 % de copiar la pata sana. Ver ia/README.md.
"""
import math
import os

from app.services.ia import MODELS_DIR

MODELO = os.path.join(MODELS_DIR, "modelo_real.joblib")
OBLIGATORIAS = ["es_trasera", "sana_sup", "sana_inf", "munon_largo"]
OPCIONALES = ["otro_par_sup", "otro_par_inf", "cabeza", "caja_alto", "caja_ancho"]

_cache = {}


def disponible() -> bool:
    if not os.path.exists(MODELO):
        return False
    try:
        import joblib  # noqa: F401
        import sklearn  # noqa: F401
        return True
    except Exception:
        return False


def _cargar():
    if "m" not in _cache:
        import joblib
        _cache["m"] = joblib.load(MODELO)
    return _cache["m"]


def predecir(med: dict) -> dict:
    import pandas as pd

    faltan = [f for f in OBLIGATORIAS if med.get(f) is None]
    if faltan:
        raise ValueError(f"Faltan medidas: {', '.join(faltan)}")
    m = _cargar()
    U = float(med["sana_sup"]) + float(med["sana_inf"])
    if U <= 0:
        raise ValueError("El largo de la pata sana tiene que ser mayor a 0")

    def rel(k):
        return float(med[k]) / U if med.get(k) is not None else math.nan

    fila = {
        "es_trasera": int(med["es_trasera"]),
        "sana_frac_sup": float(med["sana_sup"]) / U,
        "otro_par_sup": rel("otro_par_sup"), "otro_par_inf": rel("otro_par_inf"),
        "cabeza": rel("cabeza"), "caja_alto": rel("caja_alto"), "caja_ancho": rel("caja_ancho"),
        "munon_frac": float(med["munon_largo"]) / U,
    }
    X = pd.DataFrame([fila])[m["features"]]
    y = dict(zip(m["targets"], m["modelo"].predict(X)[0]))

    avisos = [f"{k} fuera de lo visto en el entrenamiento" for k, (lo, hi) in m["rangos"].items()
              if not math.isnan(fila[k]) and not lo <= fila[k] <= hi]
    if fila["munon_frac"] > 0.85:
        avisos.append("El muñón es casi tan largo como la pata sana: revisá los puntos.")

    return {
        "largo_faltante_cm": round(y["faltante_frac"] * U, 2),   # punta del muñón -> suelo
        "segmento_sup_cm": round(y["obj_sup_frac"] * U, 2),
        "segmento_inf_cm": round(y["obj_inf_frac"] * U, 2),
        "espejo_largo_cm": round(U - float(med["munon_largo"]), 2),  # copiar la pata sana
        "error_tipico_cm": round(m["error_MAE_U"] * U, 2),
        "error_p90_cm": round(m["error_p90_U"] * U, 2),
        "modelo": m["nombre"],
        "entrenado_con": f"{m['n_filas']} patas reales, {m['n_razas']} razas",
        "medidas_opcionales_usadas": [k for k in OPCIONALES if med.get(k) is not None],
        "avisos": avisos,
    }
