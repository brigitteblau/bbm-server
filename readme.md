# BBM Server (Hunda)

API para generación de prótesis caninas 3D-printables.

## Correr local
python3 -m venv venv
source venv/bin/activate   # mac
pip install -r requirements.txt
uvicorn app.main:app --reload

## Tests
python -m pytest tests/ -v

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


lo proximo es 

POST
/prosthesis/requests/{request_id}/generate
Generate From Request

Paso 2 del front: genera el STL a partir de una request guardada.

Parameters
Cancel
Name	Description
request_id *
string($uuid)
(path)
f41788d1-d122-4953-82f4-a772f74e1a15
Execute
Clear
Responses
Curl

curl -X 'POST' \
  'http://127.0.0.1:8000/prosthesis/requests/f41788d1-d122-4953-82f4-a772f74e1a15/generate' \
  -H 'accept: application/json' \
  -d ''
Request URL
http://127.0.0.1:8000/prosthesis/requests/f41788d1-d122-4953-82f4-a772f74e1a15/generate
Server response
Code	Details
502
Undocumented
Error: Bad Gateway

Response body
Download
{
  "detail": "Falló la subida a Supabase: {'message': 'null value in column \"base_model_id\" of relation \"generated_models\" violates not-null constraint', 'code': '23502', 'hint': None, 'details': 'Failing row contains (4bbc08d2-353f-4533-b7ec-22613c9c4441, eec346a3-8425-4e56-b077-48f733cf59e1, f41788d1-d122-4953-82f4-a772f74e1a15, null, copito-ae599438-f600-45d6-9476-39b533bffbf9.stl, null, {\"scale_x\": 51.248308722333846, \"scale_y\": 19.71360787708453, \"s..., trimesh-scale-v1, generated, 2026-07-13 02:49:57.302509+00, {\"dog_name\": \"Copito\", \"height_cm\": 9.0, \"limb_side\": \"derecha\",..., Blender deshabilitado por configuración (BLENDER_ENABLED)).'}"
  