"""Prótesis de una sola pieza: socket y pie en el mismo STL.

El encastre socket + pie es mejor (el pie va en TPU y se cambia cuando se
gasta), pero necesita dos materiales y ensamblar. Esta versión imprime
todo junto, en el material que haya, y es la que reemplaza directamente
al prototipo que ya anduvo impreso.

Lo que la hace liviana es lo mismo que al socket: pared degradada,
reticulado, y el bulbo del pie hueco por dentro en vez de macizo —que era
donde se iba la mitad del peso.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from app.services.generators.parametric_socket import (
    DOME_SEGMENTS,
    ELLIPSE_RATIO,
    Mesh,
    SocketProfile,
    _ring,
    _strip,
    build_socket_mesh,
    drop_to_floor,
    export_binary_stl,
    is_watertight,
    mirror_y,
    signed_volume,
)
from app.services.generators.paw_foot import (
    CONTACT_RIM_MM,
    FOOT_WALL_MM,
    TOE_DEPTH,
    TOES,
    toe_factor,
)
from app.utils.printing import print_hints
from app.utils import (
    DEFAULT_SOCKET_MATERIAL,
    estimate_mass_g,
    mass_by_material,
    safe_filename_part,
)

if TYPE_CHECKING:  # sólo para tipos
    from app.models import ProsthesisForm, SocketParameters

ALGORITHM_VERSION = "one-piece-v1"

NECK_RADIUS_RATIO = 0.52   # cintura, respecto del radio distal del socket
NECK_HEIGHT_RATIO = 0.85   # alto del cuello, respecto del alto de la almohadilla
PAD_RADIUS_RATIO = 1.90    # ancho de la almohadilla, respecto de la cintura
PAD_VS_SOCKET = 1.35       # …o respecto del radio distal del socket, lo que sea mayor
PAD_HEIGHT_RATIO = 0.72    # alto de la almohadilla, respecto de su radio
TOE_FORWARD = 0.45         # cuánto se proyecta la puntera hacia adelante (+X)
PROFILE_SEGMENTS = 14


def _smooth(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


@dataclass
class IntegratedFoot:
    """Dimensiones del pie fundido al socket, en mm."""

    neck_radius: float
    neck_height: float
    pad_radius: float
    pad_height: float
    flat_radius: float
    cavity_max: float

    @classmethod
    def from_socket(cls, socket: SocketProfile) -> "IntegratedFoot":
        neck_radius = max(
            socket.connector_radius, socket.bottom_radius * NECK_RADIUS_RATIO
        )
        # El pie tiene que ser claramente más ancho que la pierna: es lo que
        # reparte la carga y lo que da estabilidad al apoyar.
        pad_radius = max(
            neck_radius * PAD_RADIUS_RATIO, socket.bottom_radius * PAD_VS_SOCKET
        )
        pad_height = pad_radius * PAD_HEIGHT_RATIO
        flat_radius = pad_radius * 0.70

        return cls(
            neck_radius=neck_radius,
            neck_height=pad_height * NECK_HEIGHT_RATIO,
            pad_radius=pad_radius,
            pad_height=pad_height,
            flat_radius=flat_radius,
            cavity_max=flat_radius - CONTACT_RIM_MM,
        )

    @property
    def drop(self) -> float:
        """Cuánto baja el pie por debajo de la cúpula del socket."""
        return self.neck_height + self.pad_height


def build_one_piece_mesh(
    params: "SocketParameters",
    **socket_kwargs,
) -> tuple[Mesh, IntegratedFoot, SocketProfile]:
    captured: dict[str, IntegratedFoot] = {}

    def bottom_builder(mesh, profile, nu, dome_segments, ellipse_ratio, *, outer_ring, inner_ring):
        captured["foot"] = _build_integrated_bottom(
            mesh,
            profile,
            nu,
            dome_segments,
            ellipse_ratio,
            outer_ring=outer_ring,
            inner_ring=inner_ring,
        )

    mesh, pattern, profile = build_socket_mesh(
        params, bottom_builder=bottom_builder, **socket_kwargs
    )
    return mesh, captured["foot"], profile


def _build_integrated_bottom(
    mesh: Mesh,
    profile: SocketProfile,
    nu: int,
    dome_segments: int,
    ellipse_ratio: float,
    *,
    outer_ring: list[int],
    inner_ring: list[int],
) -> IntegratedFoot:
    """Cúpula → cuello → almohadilla hueca → de vuelta por la cavidad."""
    foot = IntegratedFoot.from_socket(profile)

    dome = profile.dome_height
    r_bot = profile.bottom_radius
    wall = profile.wall

    # La cúpula baja hasta la cintura del cuello.
    phi_min = math.asin(min(1.0, foot.neck_radius / r_bot))

    # (radio, z, mezcla de lóbulos): el contorno exterior, de arriba a abajo.
    outer: list[tuple[float, float, float]] = []
    for step in range(dome_segments + 1):
        phi = math.pi / 2.0 - (math.pi / 2.0 - phi_min) * step / dome_segments
        outer.append((r_bot * math.sin(phi), dome * (1.0 - math.cos(phi)), 0.0))

    z_waist = outer[-1][1]
    z_pad_top = z_waist - foot.neck_height
    z_ground = z_pad_top - foot.pad_height

    # Cuello: curva en S de la cintura al ancho de la almohadilla.
    for step in range(1, PROFILE_SEGMENTS + 1):
        u = step / PROFILE_SEGMENTS
        eased = u * u * (3.0 - 2.0 * u)
        radius = foot.neck_radius + (foot.pad_radius - foot.neck_radius) * eased
        outer.append((radius, z_waist - foot.neck_height * u, 0.45 * eased))

    # Almohadilla: de su ancho máximo al aro de apoyo, redondeando.
    for step in range(1, PROFILE_SEGMENTS + 1):
        phi = (math.pi / 2.0) * step / PROFILE_SEGMENTS
        radius = foot.pad_radius - (foot.pad_radius - foot.flat_radius) * (
            1.0 - math.cos(phi)
        )
        z = z_pad_top - foot.pad_height * math.sin(phi)
        outer.append((radius, z, 0.45 + 0.55 * math.sin(phi)))

    # Cavidad: sigue el contorno por dentro, abierta abajo.
    z_ceiling = z_waist - wall * 1.5
    cavity: list[tuple[float, float, float]] = []
    for radius, z, _ in reversed(outer):
        if z > z_ceiling:
            continue
        # Cerca del piso la cavidad se angosta para dejar el aro de apoyo;
        # más arriba sigue el contorno, así el bulbo queda hueco de verdad
        # (era donde se iba la mitad del peso). La apertura es gradual para
        # que el techo interno no quede en voladizo al imprimir.
        altura = (z - z_ground) / foot.pad_height if foot.pad_height else 1.0
        apertura = _smooth(min(1.0, max(0.0, altura / 0.6)))
        limite = foot.cavity_max + (foot.pad_radius - foot.cavity_max) * apertura
        hueco = min(radius - FOOT_WALL_MM, limite)
        if hueco <= FOOT_WALL_MM:
            continue
        if cavity and abs(cavity[-1][1] - z) < 1e-9:
            continue
        cavity.append((hueco, z, 0.0))

    # `reversed(outer)` ya viene del piso hacia arriba: así tiene que quedar,
    # porque la cadena sigue del contorno exterior a la cavidad sin saltos.
    if cavity and cavity[0][1] > z_ground + 1e-9:
        cavity.insert(0, (cavity[0][0], z_ground, 0.0))
    if cavity:
        cavity.append((min(cavity[-1][0], foot.neck_radius - wall), z_ceiling, 0.0))
        cavity.append((0.0, z_ceiling, 0.0))

    # Cúpula interior del socket: cierra la cavidad del muñón.
    inner: list[tuple[float, float, float]] = []
    r_in_bot = r_bot - wall
    dome_in = dome - wall
    for step in range(dome_segments + 1):
        phi = (math.pi / 2.0) * step / dome_segments
        inner.append(
            (r_in_bot * math.sin(phi), dome - dome_in * math.cos(phi), 0.0)
        )

    chain = outer + cavity + inner

    rings: list[list[int] | int] = []
    for radius, z, blend in chain:
        if radius <= 1e-9:
            rings.append(mesh.add_vertex(0.0, 0.0, z))
        elif blend <= 0.0:
            rings.append(_ring(mesh, radius, z, nu, ellipse_ratio))
        else:
            # La puntera se proyecta hacia adelante, como la de una bota:
            # el apoyo queda por delante del eje, que es donde el perro
            # descarga al dar el paso.
            forward = foot.pad_radius * TOE_FORWARD * blend
            ring = []
            for i in range(nu):
                angle_deg = 360.0 * i / nu
                angle = math.radians(angle_deg)
                r = radius * toe_factor(angle_deg, blend)
                ring.append(
                    mesh.add_vertex(
                        r * math.cos(angle) + forward,
                        r * math.sin(angle) * ellipse_ratio,
                        z,
                    )
                )
            rings.append(ring)

    # El primero y el último son los anillos de la pared: se comparten.
    rings[0] = outer_ring
    rings[-1] = inner_ring

    for a, b in zip(rings, rings[1:]):
        _strip(mesh, a, b, nu)

    return foot


def generate(params: "SocketParameters", form: "ProsthesisForm") -> dict:
    mesh, foot, profile = build_one_piece_mesh(params)

    mirrored = params.limb_side == "izquierda"
    if mirrored:
        mirror_y(mesh)

    drop_to_floor(mesh)

    if not is_watertight(mesh):
        raise ValueError("La pieza entera no quedó cerrada (no es imprimible).")

    volume_mm3 = signed_volume(mesh)
    material = getattr(params, "recommended_material", DEFAULT_SOCKET_MATERIAL)

    return {
        "generated_filename": f"{safe_filename_part(params.dog_name)}-entera-{uuid4()}.stl",
        "generated_stl_bytes": export_binary_stl(mesh, f"hunda {ALGORITHM_VERSION}"),
        "generation_parameters": {
            "total_height_mm": profile.total_height + foot.drop,
            "socket_height_mm": profile.total_height,
            "neck_radius_mm": foot.neck_radius,
            "pad_radius_mm": foot.pad_radius,
            "pad_height_mm": foot.pad_height,
            "contact_rim_mm": CONTACT_RIM_MM,
            "cavity_wall_mm": FOOT_WALL_MM,
            "toes": TOES,
            "toe_depth": TOE_DEPTH,
            "volume_cm3": round(volume_mm3 / 1000.0, 1),
            "estimated_mass_g": estimate_mass_g(volume_mm3, material),
            "material": material,
            "mass_by_material_g": mass_by_material(volume_mm3),
            "triangles": len(mesh.faces),
            "mirrored": mirrored,
            "print_hints": print_hints("one_piece", material, profile.wall),
        },
        "algorithm_version": ALGORITHM_VERSION,
    }
