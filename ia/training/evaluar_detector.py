"""
¿Qué tan bien mide las patas el detector automático?

Sobre fotos de validación (que el detector no vio), compara el largo de cada pata
medido con los puntos DETECTADOS contra el medido con los puntos MARCADOS A MANO.
Error en % del largo de la pata.

Uso: python evaluar_detector.py <raiz_dogpose> [max_fotos]
"""
import os
import sys

import cv2
import numpy as np
import pandas as pd

# raíz del repo, para importar el detector del server
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from app.services.ia import detector  # noqa: E402
from leer_dogpose import leer  # noqa: E402

LEGS = ["front_left", "front_right", "rear_left", "rear_right"]


def largo(p, leg):
    try:
        e, k, w = (np.array(p[f"{leg}_{j}"][:2]) for j in ("elbow", "knee", "paw"))
    except KeyError:
        return None
    return np.linalg.norm(e - k) + np.linalg.norm(k - w)


def main(raiz, n=300):
    kp = leer(raiz)
    val = kp[kp.split == "val"].sample(frac=1, random_state=0).head(n)
    filas, detectados, total = [], 0, 0
    for _, r in val.iterrows():
        det = detector.detectar(cv2.imread(r["imagen"]), conf_min=0.0)
        for leg in LEGS:
            ks = [f"{leg}_{j}" for j in ("elbow", "knee", "paw")]
            if not all(pd.notna(r[k + "_x"]) for k in ks):
                continue
            total += 1
            verdad = {k: (r[k + "_x"], r[k + "_y"]) for k in ks}
            L = largo(verdad, leg)
            if det is None or not all(k in det["puntos"] for k in ks):
                continue
            detectados += 1
            conf = min(det["puntos"][k][2] for k in ks)
            err_pt = np.mean([np.hypot(det["puntos"][k][0] - verdad[k][0],
                                       det["puntos"][k][1] - verdad[k][1]) for k in ks])
            filas.append({"pata": leg, "conf": conf,
                          "err_largo_pct": abs(largo(det["puntos"], leg) - L) / L * 100,
                          "err_punto_pct": err_pt / L * 100})
    df = pd.DataFrame(filas)
    print(f"Patas evaluadas: {total} · con los 3 puntos detectados: {detectados}")
    for umbral in (0.0, 0.5, 0.7):
        d = df[df.conf >= umbral]
        print(f"confianza ≥ {umbral}: {len(d):4d} patas · error del largo: mediana "
              f"{d.err_largo_pct.median():.1f} %, media {d.err_largo_pct.mean():.1f} % · "
              f"error por punto: mediana {d.err_punto_pct.median():.1f} % de la pata")
    return df


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 300)
