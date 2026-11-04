"""Módulo de IA (opcional): foto -> medidas -> predicción de la pata que falta.

Las dependencias pesadas (scikit-learn, opencv, ultralytics) se importan adentro
de cada función, así el server levanta aunque no estén instaladas
(mismo criterio que bpy en blender_gn). Se instalan con requirements-ia.txt.
"""
import os

IA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "ia"))
MODELS_DIR = os.path.join(IA_DIR, "models")
