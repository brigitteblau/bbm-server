from uuid import UUID

from pydantic import BaseModel, Field


class ProsthesisForm(BaseModel):
    """Datos crudos que manda el front: las medidas del perro."""

    user_id: UUID | None = None
    request_id: UUID | None = None
    dog_name: str
    dog_weight_kg: float = Field(gt=0)
    dog_breed: str | None = None
    dog_size: str | None = None
    limb_position: str = Field(pattern="^(front|back)$")
    limb_side: str = Field(pattern="^(left|right)$")
    stump_length_cm: float = Field(gt=0)
    proximal_circumference_cm: float = Field(gt=0)
    distal_circumference_cm: float = Field(gt=0)


class SocketParameters(BaseModel):
    """Parámetros geométricos calculados del socket, en cm."""

    dog_name: str
    height_cm: float
    top_radius_cm: float
    bottom_radius_cm: float
    wall_thickness_cm: float
    connector_radius_cm: float
    limb_position: str
    limb_side: str