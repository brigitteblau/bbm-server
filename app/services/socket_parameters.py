from app.data import breeds
from app.models import ProsthesisForm, SocketParameters
from app.utils.geometry import circumference_to_radius
from app.utils.mass import DEFAULT_SOCKET_MATERIAL


class SocketParameterGenerator:
    """Convierte las medidas del perro en parámetros geométricos del socket.

    Única fuente de verdad: los generadores de STL reciben SocketParameters
    y no recalculan nada.
    """

    def generate(self, form: ProsthesisForm) -> SocketParameters:
        # La raza no cambia la geometría —esa sale de las medidas— pero sí
        # cuánta pared conviene: un border collie castiga más que un whippet.
        profile = breeds.resolve(form.dog_breed, form.dog_weight_kg)
        wall = self._wall_thickness_for_weight(form.dog_weight_kg)

        return SocketParameters(
            dog_name=form.dog_name,
            height_cm=form.stump_length_cm,
            top_radius_cm=round(
                circumference_to_radius(form.proximal_circumference_cm), 2
            ),
            bottom_radius_cm=round(
                circumference_to_radius(form.distal_circumference_cm), 2
            ),
            wall_thickness_cm=round(wall * profile.wall_scale, 3),
            connector_radius_cm=self._connector_radius_for_weight(form.dog_weight_kg),
            limb_position=form.limb_position,
            limb_side=form.limb_side,
            breed_key=profile.key,
            breed_size=profile.size,
            recommended_material=profile.material or DEFAULT_SOCKET_MATERIAL,
        )

    @staticmethod
    def _wall_thickness_for_weight(weight_kg: float) -> float:
        """Espesor en la base del socket; hacia el borde se afina solo.

        Son paredes finas a propósito: con el reticulado aguantan, y de
        paso la prótesis pesa y endurece menos (la rigidez a flexión va
        con el cubo del espesor).
        """
        if weight_kg < 10:
            return 0.25
        if weight_kg <= 25:
            return 0.32
        return 0.42

    @staticmethod
    def _connector_radius_for_weight(weight_kg: float) -> float:
        if weight_kg < 10:
            return 1.2
        if weight_kg <= 25:
            return 1.6
        return 2.0