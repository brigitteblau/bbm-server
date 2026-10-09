# Hunda · BBM Server

API para generar prótesis caninas personalizadas e imprimibles en 3D.
El front manda las medidas del perro y el server devuelve un STL listo para imprimir, guardado en Supabase.

- **Producción:** https://bbm-server-hfq1.onrender.com (docs en `/docs`)
- **Stack:** FastAPI · Supabase (Postgres + Storage) · trimesh · Blender (opcional)

## Correr local

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Abrí http://localhost:8000/docs para probar los endpoints.

### Variables de entorno (`.env`)

| Variable | Para qué |
|---|---|
| `SUPABASE_URL` | URL del proyecto de Supabase |
| `SUPABASE_SECRET_KEY` | Service key (escribe en tablas y storage) |
| `BLENDER_ENABLED` | `true` para usar el generador de Blender. Por defecto `false` |

Sin las variables de Supabase el server levanta igual: el error aparece recién cuando un endpoint necesita Supabase.

## Tests

```bash
python -m pytest tests/ -v
```

## Cómo funciona

```
POST /prosthesis/requests                    → guarda las medidas, devuelve request_id
POST /prosthesis/requests/{request_id}/generate → genera el STL, lo sube y devuelve download_url
```

1. **Medidas → parámetros** ([socket_parameters.py](app/services/socket_parameters.py)). Las circunferencias se convierten en radios y el peso define el espesor de pared y el conector. Es la única fuente de verdad: los generadores no recalculan nada.
2. **Validación física** (`selector.validate_geometry`). Si el socket no tiene sentido (por ejemplo, la pared es más gruesa que el radio), responde `422`.
3. **Generación** ([selector.py](app/services/generators/selector.py)). El cliente no elige el generador, lo decide el back:
   - `blender-gn-v1`: socket paramétrico con Geometry Nodes. Solo se usa si `BLENDER_ENABLED=true` y `bpy` está instalado.
   - `trimesh-scale-v2` (fallback): escala el modelo base según la boca del socket, sin deformar el pie. Si la pata es izquierda, lo espeja.
   - La respuesta incluye `generator_used` y `fallback_reason` para saber qué camino tomó.
4. **Storage.** El STL se sube a `generated-models`, se registra en la tabla `generated_models` y se devuelve una signed URL que dura 7 días.

### Otros endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| `POST` | `/prosthesis/socket/parameters` | Solo calcula los parámetros (preview en el front, no genera STL) |
| `GET` | `/prosthesis/generated/{filename}` | Redirige a una signed URL del STL |
| `GET` | `/health` | Healthcheck |

### Ejemplo de request

```json
{
  "user_id": "eec346a3-8425-4e56-b077-48f733cf59e1",
  "dog_name": "Copito",
  "dog_weight_kg": 18,
  "dog_breed": "Caniche",
  "dog_size": "mediano",
  "limb_position": "delantera",
  "limb_side": "derecha",
  "stump_length_cm": 9,
  "proximal_circumference_cm": 18,
  "distal_circumference_cm": 13
}
```

`user_id` es **obligatorio** para crear la request: la tabla no acepta nulos, aunque el modelo de Pydantic lo marque como opcional. El del ejemplo es el usuario de prueba `brigu@test.com`. `limb_position` acepta `delantera` o `trasera`, y `limb_side` acepta `izquierda` o `derecha`.

## Supabase

| Recurso | Tipo | Contenido |
|---|---|---|
| `prosthesis_requests` | tabla | Medidas cargadas por el usuario |
| `generated_models` | tabla | Un registro por STL generado (parámetros, generador y fallback) |
| `base-models` | bucket | Modelos base: `proto.stl` (delantera) y `default_back.stl` (trasera) |
| `generated-models` | bucket | STL generados para cada perro |

## Modelos base

Los STL de `base-models` se generan por código: es una bota con socket ventilado, talón, surcos de dedos y suela con dibujo. Los modelos están en mm, con Z hacia arriba, el perro mirando a +Y y la pata derecha como referencia.

```bash
pip install scikit-image fast-simplification        # solo para este script
python scripts/make_base_models.py delantera out/proto.stl
python scripts/make_base_models.py trasera   out/default_back.stl
python -m scripts.upload_base_models out/            # sube los dos, con backup local de los anteriores
```

Si cambiás las medidas del socket en el script, actualizá `BASE_SOCKET_DIAMETER_MM` y `BASE_SOCKET_DEPTH_MM` en [trimesh_scaler.py](app/services/generators/trimesh_scaler.py).

## Generador Blender (en progreso)

`bpy` necesita Python 3.11, así que se usa un venv aparte:

```bash
brew install python@3.11
python3.11 -m venv venv311 && source venv311/bin/activate
pip install -r requirements.txt bpy
BLENDER_ENABLED=true uvicorn app.main:app --reload
```

Funciona si `generate` devuelve `"generator_used": "blender-gn-v1"` y `"fallback_reason": null`. Pendiente: medir la RAM durante una generación para decidir cómo deployarlo.

## Estructura

```
app/
  main.py              app FastAPI + CORS
  routes/prosthesis.py endpoints
  services/            medidas → parámetros, generadores de STL
  supabase_client.py   cliente lazy
scripts/               generación y subida de modelos base
docs/                  documentación de la API (HTML)
tests/
```
