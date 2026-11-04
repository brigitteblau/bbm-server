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
| `BLENDER_ENABLED` | Opcional. Blender se usa solo si `bpy` está instalado; `false` lo apaga a mano |

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
   - `blender-gn-v2-bota`: la bota completa generada con Geometry Nodes a la medida del perro. Se usa automáticamente si `bpy` está instalado (salvo `BLENDER_ENABLED=false`).
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

`user_id` es **obligatorio** para crear la request (si falta, responde `422`). En el modelo de Pydantic figura como opcional porque `/socket/parameters` no lo necesita. Las medidas se validan al crear la request, así que una geometría imposible da `422` antes de guardarse. El del ejemplo es el usuario de prueba `brigu@test.com`. `limb_position` acepta `delantera` o `trasera`, y `limb_side` acepta `izquierda` o `derecha`.

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

## Generador Blender: la bota en Geometry Nodes

`bpy` 5.x anda con Python 3.13 (probado con 5.2.3). Pesa bastante, así que no está en `requirements.txt`:

```bash
pip install -r requirements.txt bpy
uvicorn app.main:app --reload       # con bpy instalado, usa Blender solo
```

Funciona si `generate` devuelve `"generator_used": "blender-gn-v2-bota"` y `"fallback_reason": null`.

`blender_gn.py` arma **desde cero la misma bota** que `scripts/make_base_models.py`, pero como un grafo de Geometry Nodes, con primitivas y booleanos, y con las medidas reales de cada perro:

| Parte | Cómo se arma | Qué medida usa |
|---|---|---|
| Pie, talón y puntera | 3 elipsoides (UV Sphere + Transform) unidos | escala del pie = radio proximal / 28.5 mm (acotada a 0.5–2) |
| Socket | tubo de sección elíptica: Cone, Mesh Boolean | radios proximal y distal **+ espesor de pared** (según el peso) |
| Cavidad del muñón | cono restado al tubo | radios y **largo del muñón exactos + 3 mm para la media** (alrededor y en la punta) |
| Boca en embudo | puño de la pared y cavidad que se abren 4 mm en los últimos ~15 mm | facilita meter la pata; las ventanas no lo tocan |
| Ventanas de ventilación | 3 pares de ranuras restadas a la pared | ubicadas relativas al largo del muñón; si el muñón es muy corto, se omiten |
| Surcos de dedos | 3 ranuras que solo cortan la cáscara (1.5 mm) | escalan con el pie |
| Dibujo de suela | ranuras transversales de 1.3 mm, lejos del borde | escalan con el pie |
| Trasera | tubo, cavidad y ventanas inclinados 11° hacia atrás | `limb_position` |
| Izquierda | espejado en X | `limb_side` |

- Los booleanos usan el solver `MANIFOLD` (Blender 4.5+): cada bota tarda ~1 s, sale cerrada (watertight), apoyada en z=0, y pesa ~0.4 MB (el modelo base escalado pesa ~6 MB).
- Las piezas se superponen a propósito, sin caras en el mismo plano, para que el booleano no deje caras degeneradas. Al exportar se descartan astillas sueltas, igual que en `make_base_models.py`.
- **Media / liner:** la cavidad deja `LINER_MM = 3` mm de más para una media de silicona o neopreno. Hace más fácil ponerla y sacarla, amortigua y evita roces. Si la media que usan es más gruesa o más fina, se cambia esa constante (o el input `Liner Thickness`).
- Las medidas del muñón (radios, pared y media) quedan como **inputs del grupo de nodos**, así se pueden tocar a mano desde el panel del modifier en Blender.
- Diferencias con el script SDF: las uniones son en ángulo (el SDF las suaviza) y no tiene la línea de partición de la valva superior ni el balancín de la punta.
- `tests/test_blender_bota.py` prueba el diseño siempre y genera botas reales cuando `bpy` está instalado.

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
