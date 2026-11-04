"""Lee las etiquetas YOLO-pose de Dog-Pose y devuelve un DataFrame con los 24 puntos en píxeles."""
import glob, os
import numpy as np, pandas as pd
from PIL import Image

KP = ["front_left_paw","front_left_knee","front_left_elbow","rear_left_paw","rear_left_knee","rear_left_elbow",
      "front_right_paw","front_right_knee","front_right_elbow","rear_right_paw","rear_right_knee","rear_right_elbow",
      "tail_start","tail_end","left_ear_base","right_ear_base","nose","chin","left_ear_tip","right_ear_tip",
      "left_eye","right_eye","withers","throat"]

def leer(raiz):
    filas = []
    for split in ["train", "val"]:
        for lab in sorted(glob.glob(f"{raiz}/labels/{split}/*.txt")):
            nombre = os.path.basename(lab)[:-4]
            img = f"{raiz}/images/{split}/{nombre}.jpg"
            W, H = Image.open(img).size
            lineas = open(lab).read().split("\n")
            lineas = [l for l in lineas if l.strip()]
            if len(lineas) != 1:      # nos quedamos con fotos de UN solo perro
                continue
            v = np.array(lineas[0].split(), float)
            k = v[5:].reshape(24, 3)
            fila = {"imagen": img, "split": split, "synset": nombre.split("_")[0], "W": W, "H": H,
                    "bbox_w": v[3]*W, "bbox_h": v[4]*H}
            for i, n in enumerate(KP):
                vis = k[i, 2] > 0
                fila[n+"_x"] = k[i, 0]*W if vis else np.nan
                fila[n+"_y"] = k[i, 1]*H if vis else np.nan
            filas.append(fila)
    return pd.DataFrame(filas)


if __name__ == "__main__":
    # python leer_dogpose.py <carpeta_dog-pose>  ->  guarda kp.pkl al lado
    import sys
    df = leer(sys.argv[1])
    df.to_pickle(os.path.join(os.path.dirname(os.path.abspath(__file__)), "kp.pkl"))
    print(len(df), "fotos ->", "real/kp.pkl")
