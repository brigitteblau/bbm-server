from app.models import ProsthesisForm, SocketParameters
from app.utils.geometry import circumference_to_radius


class SocketParameterGenerator:
    """Convierte las medidas del perro en parámetros geométricos del socket.

    Única fuente de verdad: los generadores de STL reciben SocketParameters
    y no recalculan nada.
    """

    def generate(self, form: ProsthesisForm) -> SocketParameters:
        return SocketParameters(
            dog_name=form.dog_name,
            height_cm=form.stump_length_cm,
            top_radius_cm=round(
                circumference_to_radius(form.proximal_circumference_cm), 2
            ),
            bottom_radius_cm=round(
                circumference_to_radius(form.distal_circumference_cm), 2
            ),
            wall_thickness_cm=self._wall_thickness_for_weight(form.dog_weight_kg),
            connector_radius_cm=self._connector_radius_for_weight(form.dog_weight_kg),
            limb_position=form.limb_position,
            limb_side=form.limb_side,
        )

    @staticmethod
    def _wall_thickness_for_weight(weight_kg: float) -> float:
        if weight_kg < 10:
            return 0.3
        if weight_kg <= 25:
            return 0.4
        return 0.5

    @staticmethod
    def _connector_radius_for_weight(weight_kg: float) -> float:
        if weight_kg < 10:
            return 1.2
        if weight_kg <= 25:
            return 1.6
        return 2.0