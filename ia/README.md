# IA · De la foto a la pata que falta

Módulo **opcional** de Hunda. A partir de una foto lateral del perro:

1. **Detecta los puntos de las patas** (codo/rodilla, carpo/tarso, apoyo) con una red neuronal YOLO11-pose.
2. **Mide en cm** la pata sana y el muñón, usando un marcador ArUco, una referencia o la pata sana medida con cinta como escala.
3. **Predice el largo de la pata que falta** (desde la punta del muñón hasta el suelo) con un modelo entrenado con **11.932 patas reales de 111 razas**.

Todo esto completa el flujo de `/prosthesis`: precarga `limb_position`, `limb_side` y `stump_length_cm`, y agrega un dato que hoy el server no calcula, que es cuánto tiene que medir la prótesis hasta el suelo.

```
foto ──► POST /ia/detect ──► puntos (se corrigen en el front)
                                │
                                ▼
         POST /ia/measure ──► medidas en cm ──► prosthesis_form_hint ──► POST /prosthesis/requests
                                │
                                ▼
         POST /ia/predict-length ──► largo de la pata que falta (± error)
```

## Correr

```bash
pip install -r requirements.txt -r requirements-ia.txt
uvicorn app.main:app --reload            # /docs → sección "ia"
python -m pytest tests/ -v               # test_ia.py se saltea si faltan las dependencias
```

Sin `requirements-ia.txt` el server levanta igual y `/ia` no se monta (mismo criterio que Blender). `GET /ia/status` muestra qué partes están disponibles.

> **Render:** `ultralytics` pesa bastante (torch). Si solo querés la predicción, alcanza con `python-multipart scikit-learn==1.9.1 pandas joblib`. El detector se puede correr aparte o en local.

## Endpoints

| Método | Ruta | Entrada | Salida |
|---|---|---|---|
| `GET` | `/ia/status` | — | qué está disponible |
| `POST` | `/ia/detect` | `foto_perro` (archivo) | puntos en px + caja del perro + escala ArUco si la encuentra |
| `POST` | `/ia/measure` | foto + `puntos` (JSON) + `pata_faltante` (`front_left`…) + escala | medidas en cm + `prosthesis_form_hint` |
| `POST` | `/ia/predict-length` | medidas en cm (JSON) | `largo_faltante_cm`, segmentos, error típico, avisos |

Ejemplo:

```json
POST /ia/predict-length
{ "es_trasera": 0, "sana_sup": 18.2, "sana_inf": 12.0, "munon_largo": 9.5,
  "otro_par_sup": 19.0, "otro_par_inf": 14.5 }
```

## Los datos

[Dog-Pose (Ultralytics)](https://docs.ultralytics.com/datasets/pose/dog-pose/) tiene 8.476 fotos de Stanford Dogs con 24 puntos anatómicos marcados a mano (anotaciones de StanfordExtra).

- **Detector** (`training/entrenar_detector.py`): YOLO11n-pose, entrenado 7 épocas en CPU.
- **Dataset de patas** (`data/patas_reales.csv`, armado con `training/construir_dataset.py`): en cada foto donde se ven las dos patas de un par, una hace de "la que falta" y la otra de "la sana". Salen 11.932 filas de 5.021 fotos.
  - Todo se mide en **U = largo de la pata sana**, así no importa el tamaño del perro ni el zoom.
  - La amputación se **simula**, cortando la pata entre el 20 y el 90 % del segmento superior, porque las fotos son de perros sanos.

| Feature | De dónde sale |
|---|---|
| `es_trasera` | se elige |
| `sana_sup`, `sana_inf` | pata del otro lado (foto) |
| `munon_largo` | muñón (foto, 2 clicks) |
| `otro_par_sup/inf` (opcional) | patas del otro par: corrigen pose y perspectiva |
| `cabeza`, `caja_alto/ancho` (opcional) | tamaño y forma general del perro |

## Resultados

Validación `GroupKFold` por **raza**: se evalúa siempre con razas que el modelo nunca vio, como un mestizo en la vida real.

| Modelo | Error medio | Peor 10 % | En una pata de 30 cm |
|---|---|---|---|
| Espejo (copiar la pata sana, sin IA) | 17,9 % | 37,2 % | 5,4 cm |
| Regresión lineal / Ridge | 13,5 % | 27,6 % | 4,1 cm |
| Red neuronal (MLP 64-32) | 12,9 % | 27,0 % | 3,9 cm |
| **Gradient boosting** (el elegido) | **12,6 %** | **26,5 %** | **3,8 cm** |

- **La IA baja el error un 30 % respecto de copiar la pata sana.**
- **Regresión logística no aplica:** predice clases y acá necesitamos cm.
- **Detector:** encuentra la pata en el 99,8 % de las fotos de validación. El largo que mide tiene un error mediano del 12 % (`models/reporte_detector.txt`), así que los puntos hay que revisarlos.

### Límites (importante)

- **Una foto 2D tiene mucho ruido:** una pata doblada o en diagonal se ve más corta. ±3,8 cm sirve para un prototipo, no para la medida final. Conviene sacar varias fotos, medir con cinta si se puede y dejar el pilón regulable o largo para cortar.
- **El detector necesita más entrenamiento:** con GPU, 100 épocas en Colab gratis (`training/entrenar_detector.py`).
- **No hay datos de perros amputados reales.** Si se consiguen (veterinarias), se agregan a `data/patas_reales.csv` y se corre `python ia/training/entrenar_real.py`.
- Cualquier prótesis tiene que revisarla un veterinario.

## Archivos

```
app/routes/ia.py                 endpoints /ia
app/services/ia/detector.py      YOLO-pose: foto -> puntos
app/services/ia/foto.py          escala (ArUco / referencia / cinta) + puntos -> cm
app/services/ia/prediccion.py    medidas -> largo de la pata que falta
ia/models/                       modelo_real.joblib, detector_patas.pt, reportes
ia/data/patas_reales.csv         dataset de patas reales
ia/training/                     leer Dog-Pose, armar dataset, entrenar y evaluar
ia/fotos_ejemplo/                6 fotos de Stanford Dogs para probar
ia/marcador_aruco.png            imprimir al 100 % (cuadrado negro = 5 cm)
```

Reentrenar desde cero: bajá [dog-pose.zip](https://github.com/ultralytics/assets/releases/download/v0.0.0/dog-pose.zip), descomprimilo y corré `python ia/training/leer_dogpose.py <carpeta>`, después `python ia/training/construir_dataset.py` y por último `python ia/training/entrenar_real.py`.

Licencias: Dog-Pose se distribuye bajo AGPL-3.0 (Ultralytics). Las imágenes de Stanford Dogs/ImageNet son para uso de investigación y educativo.
