from fastapi import APIRouter
from app.models import ProsthesisForm
from app.supabase_client import supabase
from stl import mesh
import tempfile
import uuid

router = APIRouter()


@router.post("/generate")
def generate_prosthesis(data: ProsthesisForm):

    generated_id = str(uuid.uuid4())

    # 1. Descargar STL default
    file_bytes = supabase.storage.from_("base-models").download(
        "default.stl"
    )

    # 2. Guardar STL temporalmente
    with tempfile.NamedTemporaryFile(delete=False, suffix=".stl") as input_file:
        input_file.write(file_bytes)
        input_path = input_file.name

    # 3. Leer STL
    prosthesis_mesh = mesh.Mesh.from_file(input_path)

    # 4. Escalar STL según largo del muñón
    target_length_mm = data.stump_length_cm * 10

    current_length_mm = (
        prosthesis_mesh.z.max() - prosthesis_mesh.z.min()
    )

    scale_factor = target_length_mm / current_length_mm

    prosthesis_mesh.vectors *= scale_factor

    # 5. Guardar STL generado temporalmente
    with tempfile.NamedTemporaryFile(delete=False, suffix=".stl") as output_file:
        output_path = output_file.name

    prosthesis_mesh.save(output_path)

    # 6. Subir STL generado
    generated_path = f"{generated_id}.stl"

    with open(output_path, "rb") as f:

        supabase.storage.from_("generated-models").upload(
            generated_path,
            f,
            {
                "content-type": "model/stl",
                "upsert": "true"
            }
        )

    return {
        "success": True,
        "message": "STL generado correctamente",
        "dog_name": data.dog_name,
        "scale_factor": scale_factor,
        "generated_path": generated_path
    }