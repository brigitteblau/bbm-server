"""
Construye el dataset REAL de patas a partir de Dog-Pose (fotos de Stanford Dogs con
puntos anatómicos marcados a mano).

Cada fila = una foto + un par de patas (delanteras o traseras) completas:
  - una pata hace de "la que falta"  (objetivo)
  - la otra hace de "la sana"        (entrada)
y se generan las dos direcciones (izq falta / der falta).

Correspondencia anatómica de los puntos de StanfordExtra:
  delantera:  elbow = codo,     knee = carpo,  paw = apoyo
  trasera:    elbow = rodilla,  knee = tarso,  paw = apoyo
  => segmento superior = elbow->knee ; inferior = knee->paw

ESCALA: una foto no tiene cm, así que todo se mide en "patas sanas":
U = largo total de la pata sana (sup + inf) en píxeles. El modelo predice
la pata que falta en múltiplos de U; en la app se multiplica por U en cm.
Eso hace al modelo independiente del zoom / resolución de la foto.

La amputación NO está en las fotos (son perros sanos): el muñón se simula
cortando la pata objetivo a un nivel aleatorio del segmento superior.
"""
import numpy as np
import pandas as pd

PARES = {0: ("front_left", "front_right"), 1: ("rear_left", "rear_right")}

FEATURES = [
    "es_trasera",
    "sana_frac_sup",     # sup/U de la pata sana: proporción entre segmentos
    "otro_par_sup",      # segmentos del otro par (traseras si falta delantera), en U (NaN si no se ven)
    "otro_par_inf",
    "cabeza",            # nariz -> base de orejas, en U
    "caja_alto",         # alto del perro en la foto, en U
    "caja_ancho",
    "munon_frac",        # largo del muñón / U
]
TARGETS = ["faltante_frac", "obj_sup_frac", "obj_inf_frac"]  # en U


def _p(r, n):
    return np.array([r[n + "_x"], r[n + "_y"]])


def _seg(r, leg):
    e, k, p = _p(r, leg + "_elbow"), _p(r, leg + "_knee"), _p(r, leg + "_paw")
    return np.linalg.norm(e - k), np.linalg.norm(k - p)


def _completa(r, leg):
    return all(pd.notna(r[f"{leg}_{j}_x"]) for j in ("paw", "knee", "elbow"))


def construir(kp: pd.DataFrame, semilla=0) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    filas = []
    for _, r in kp.iterrows():
        orejas = [_p(r, n) for n in ("left_ear_base", "right_ear_base") if pd.notna(r[n + "_x"])]
        cabeza_px = (np.linalg.norm(_p(r, "nose") - np.mean(orejas, 0))
                     if orejas and pd.notna(r["nose_x"]) else np.nan)
        for tras, (a, b) in PARES.items():
            if not (_completa(r, a) and _completa(r, b)):
                continue
            otros = [l for l in PARES[1 - tras] if _completa(r, l)]
            o_sup = np.mean([_seg(r, l)[0] for l in otros]) if otros else np.nan
            o_inf = np.mean([_seg(r, l)[1] for l in otros]) if otros else np.nan
            for obj, sana in ((a, b), (b, a)):
                s_sup, s_inf = _seg(r, sana)
                t_sup, t_inf = _seg(r, obj)
                U = s_sup + s_inf
                if U < 20:             # pata de menos de 20 px: foto inservible
                    continue
                nivel = rng.uniform(0.2, 0.9)
                munon = nivel * t_sup
                filas.append({
                    "imagen": r["imagen"], "synset": r["synset"], "split": r["split"],
                    "pata_objetivo": obj, "U_px": U,
                    "es_trasera": tras,
                    "sana_frac_sup": s_sup / U,
                    "otro_par_sup": o_sup / U, "otro_par_inf": o_inf / U,
                    "cabeza": cabeza_px / U,
                    "caja_alto": r["bbox_h"] / U, "caja_ancho": r["bbox_w"] / U,
                    "munon_frac": munon / U,
                    "faltante_frac": (t_sup - munon + t_inf) / U,
                    "obj_sup_frac": t_sup / U, "obj_inf_frac": t_inf / U,
                })
    return pd.DataFrame(filas)


if __name__ == "__main__":
    import os
    import sys
    aqui = os.path.dirname(os.path.abspath(__file__))
    kp = pd.read_pickle(sys.argv[1] if len(sys.argv) > 1 else os.path.join(aqui, "kp.pkl"))
    df = construir(kp)
    df.to_csv(os.path.join(aqui, "..", "data", "patas_reales.csv"), index=False)
    print(len(df), "filas de", df.imagen.nunique(), "fotos,", df.synset.nunique(), "razas")
    print(df.groupby("es_trasera").size())
    ratio = (df.obj_sup_frac + df.obj_inf_frac)
    print("pata objetivo / pata sana  (1 = simétrica):")
    print(ratio.describe(percentiles=[.05, .25, .5, .75, .95]).round(3))
