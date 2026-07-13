from app.models import DogProsthesisRequest, SocketParameters
from app.utils.geometry import circumference_to_radius


class SocketParameterGenerator:
    def generate(self, request: DogProsthesisRequest) -> SocketParameters:
        # Socket height follows the measured stump length.
        height_cm = request.stump_length_cm

        # Circumferences define the socket cone radii.
        top_radius_cm = round(
            circumference_to_radius(request.proximal_circumference_cm),
            2,
        )
        bottom_radius_cm = round(
            circumference_to_radius(request.distal_circumference_cm),
            2,
        )

        wall_thickness_cm = self._wall_thickness_for_weight(request.dog_weight_kg)
        connector_radius_cm = self._connector_radius_for_weight(request.dog_weight_kg)

        return SocketParameters(
            dog_name=request.dog_name,
            height_cm=height_cm,
            top_radius_cm=top_radius_cm,
            bottom_radius_cm=bottom_radius_cm,
            wall_thickness_cm=wall_thickness_cm,
            connector_radius_cm=connector_radius_cm,
            limb_position=request.limb_position,
            limb_side=request.limb_side,
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


def generate_socket_stl(parameters: SocketParameters) -> bytes | None:
    # Placeholder for the future Blender/Geometry Nodes socket generation step.
    # This function will receive validated parametric socket data and return STL bytes.
    return None
