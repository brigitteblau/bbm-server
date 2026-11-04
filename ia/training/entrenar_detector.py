"""
Entrena el detector de puntos de patas (YOLO11-pose) con Dog-Pose.

El modelo que viene en ia/models/detector_patas.pt se entrenó solo unas épocas en CPU,
así que funciona pero es mejorable. Para entrenarlo bien conviene usar una GPU:

  Google Colab (gratis): Entorno de ejecución -> Cambiar tipo -> GPU T4, y en una celda:
      !pip install ultralytics
      !python entrenar_detector.py --epocas 100 --img 640 --modelo yolo11s-pose.pt
  (~1-2 h en T4).  Bajá runs/dogpose/weights/best.pt y copialo a ia/models/detector_patas.pt

  Mac con chip M1/M2/M3:   python entrenar_detector.py --device mps

El dataset (≈350 MB, 8.476 fotos de Stanford Dogs con 24 puntos marcados a mano)
se descarga solo la primera vez.
"""
import argparse

from ultralytics import YOLO

ap = argparse.ArgumentParser()
ap.add_argument("--epocas", type=int, default=100)
ap.add_argument("--img", type=int, default=640)
ap.add_argument("--modelo", default="yolo11n-pose.pt", help="n = rápido, s/m = más preciso")
ap.add_argument("--device", default=None, help="0 (GPU), mps (Mac), cpu")
a = ap.parse_args()

YOLO(a.modelo).train(
    data="dog-pose.yaml",   # Ultralytics lo baja de github.com/ultralytics/assets
    epochs=a.epocas, imgsz=a.img, device=a.device, batch=-1,
    project="runs", name="dogpose", exist_ok=True,
)
