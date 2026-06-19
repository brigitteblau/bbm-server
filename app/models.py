from uuid import UUID

from pydantic import BaseModel, Field


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


class DogProsthesisRequest(BaseModel):
    dog_name: str
    dog_weight_kg: float = Field(gt=0)
    dog_breed: str | None = None

    limb_position: str = Field(pattern="^(front|back)$")
    limb_side: str = Field(pattern="^(left|right)$")

    stump_length_cm: float = Field(gt=0)
    proximal_circumference_cm: float = Field(gt=0)
    distal_circumference_cm: float = Field(gt=0)


class SocketParameters(BaseModel):
    dog_name: str
    height_cm: float
    top_radius_cm: float
    bottom_radius_cm: float
    wall_thickness_cm: float
    connector_radius_cm: float
    limb_position: str
    limb_side: str

