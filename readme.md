#todo

python -m venv venv
venv\Scripts\activate 
pip install -r requirements.txt
 {
  "dog_name": "Luna",
  "dog_weight_kg": 12,
  "dog_size": "mediano",
  "limb_position": "delantera",
  "limb_side": "izquierda",
  "stump_length_cm": 8,
  "proximal_circumference_cm": 15,
  "distal_circumference_cm": 12
}

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

 uvicorn app.main:app --reload
correrlo con tu propio wifi si podes :=
{
  "dog_name": "Toby",
  "dog_weight_kg": 18,
  "dog_breed": "mestizo",
  "dog_size": "mediano",
  "limb_position": "delantera",
  "limb_side": "izquierda",
  "stump_length_cm": 12,
  "proximal_circumference_cm": 18,
  "distal_circumference_cm": 14,
  "base_model_name": "Modelo Default",
  "base_model_storage_path": "default.stl"
}


Tambien se puede pedir una nueva signed URL con:

GET /prosthesis/generated/{generated_filename}

Columnas esperadas en generated_models:

- id uuid primary key default gen_random_uuid()
- created_at timestamptz default now()
- user_id uuid null references profiles(id)
- request_id uuid null references prosthesis_requests(id)
- base_model_id uuid null references base_models(id)
- generated_stl_path text
- preview_image_path text
- algorithm_version text
- generation_parameters jsonb
- status text default 'generated'

