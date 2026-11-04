"""
Entrena con el dataset REAL (datos/patas_reales.csv) y compara modelos.

Validación: GroupKFold por RAZA -> el modelo se evalúa siempre en razas que no vio
al entrenar. Es lo honesto: en la vida real te va a llegar un mestizo o una raza nueva.
(Dividir al azar daría números más lindos pero engañosos, porque la misma foto
aparece dos veces, izq->der y der->izq.)

Errores en "U" = largo de la pata sana. 0.10 U = 10 % del largo de la pata.
"""
import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.model_selection import GroupKFold
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from construir_dataset import FEATURES, TARGETS

AQUI = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(AQUI, "..", "data", "patas_reales.csv")
SALIDA = os.path.join(AQUI, "..", "models")


def espejo(X):
    # la pata que falta = la sana: sup = sana_sup, inf = sana_inf
    sup, inf = X["sana_frac_sup"].values, 1 - X["sana_frac_sup"].values
    return np.column_stack([sup - X["munon_frac"].values + inf, sup, inf])


def modelos():
    imp = lambda: SimpleImputer(strategy="median", add_indicator=True)
    return {
        "lineal": make_pipeline(imp(), StandardScaler(), LinearRegression()),
        "ridge": make_pipeline(imp(), StandardScaler(), Ridge(alpha=10)),
        "red_neuronal": make_pipeline(imp(), StandardScaler(), MLPRegressor(
            hidden_layer_sizes=(64, 32), alpha=1e-2, learning_rate_init=1e-3,
            early_stopping=True, max_iter=2000, random_state=0)),
        "gradient_boosting": MultiOutputRegressor(HistGradientBoostingRegressor(
            max_iter=300, learning_rate=0.05, max_leaf_nodes=15, l2_regularization=1.0,
            loss="absolute_error", random_state=0)),
    }


def main():
    df = pd.read_csv(CSV)
    X, y, g = df[FEATURES], df[TARGETS].values, df["synset"].values
    cv = GroupKFold(n_splits=5)

    pred = {"espejo (sin IA)": np.zeros_like(y)}
    for k in modelos():
        pred[k] = np.zeros_like(y)
    for tr, te in cv.split(X, y, g):
        pred["espejo (sin IA)"][te] = espejo(X.iloc[te])
        for k, m in modelos().items():
            m.fit(X.iloc[tr], y[tr])
            pred[k][te] = m.predict(X.iloc[te])

    res = {}
    for k, p in pred.items():
        err = np.abs(p[:, 0] - y[:, 0])
        res[k] = {
            "MAE_U": round(float(err.mean()), 4),
            "mediana_U": round(float(np.median(err)), 4),
            "p90_U": round(float(np.percentile(err, 90)), 4),
            "MAE_cm_pata_30cm": round(float(err.mean() * 30), 2),
        }
    mejor = min((k for k in res if k != "espejo (sin IA)"), key=lambda k: res[k]["MAE_U"])

    print(f"{'modelo':20} {'MAE':>7} {'mediana':>8} {'p90':>7}   (en % del largo de la pata sana)   cm si la pata mide 30")
    for k, r in res.items():
        print(f"{k:20} {r['MAE_U']*100:6.1f}% {r['mediana_U']*100:7.1f}% {r['p90_U']*100:6.1f}%   {r['MAE_cm_pata_30cm']:>30} cm")
    print("\nElegido:", mejor)

    final = modelos()[mejor].fit(X, y)
    os.makedirs(SALIDA, exist_ok=True)
    joblib.dump({"modelo": final, "nombre": mejor, "features": FEATURES, "targets": TARGETS,
                 "error_MAE_U": res[mejor]["MAE_U"], "error_p90_U": res[mejor]["p90_U"],
                 "n_filas": len(df), "n_razas": int(df.synset.nunique()),
                 "rangos": {f: (float(X[f].min()), float(X[f].max())) for f in FEATURES}},
                os.path.join(SALIDA, "modelo_real.joblib"))
    with open(os.path.join(SALIDA, "reporte_real.json"), "w") as f:
        json.dump({"validacion": "GroupKFold(5) por raza", "elegido": mejor, "resultados": res,
                   "n_filas": len(df), "n_fotos": int(df.imagen.nunique()),
                   "n_razas": int(df.synset.nunique())}, f, indent=2)


if __name__ == "__main__":
    main()
