from uuid import UUID

from pydantic import BaseModel


class ProsthesisForm(BaseModel):
    user_id: UUID | None = None

    dog_name: str
    dog_weight_kg: float
    dog_breed: str | None = None
    dog_size: str

    limb_position: str
    limb_side: str

    stump_length_cm: float
    proximal_circumference_cm: float
    distal_circumference_cm: float
    base_stl_path: str | None = None
    base_model_id: UUID | None = None
    request_id: UUID | None = None
    base_model_name: str | None = None
    base_model_storage_path: str | None = None

