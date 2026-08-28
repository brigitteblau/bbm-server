"""Pie de la prótesis: la pieza que encastra en el poste del socket.

Es la parte que toca el piso. Se genera junta con el socket y se imprime
aparte, idealmente en material flexible (TPU) para amortiguar.

Forma, de arriba hacia abajo:
  - Copa: agujero ciego que entra a presión en el poste del socket, con
    holgura de impresión y boca achaflanada para que entre derecho.
  - Cuello: transición suave de la copa a la almohadilla.
  - Almohadilla: pata redondeada con lóbulos (los "dedos"), apoyada en
    z=0 y con la base levemente aplanada para que no bailotee.

Misma técnica que el socket: perfil cerrado revolucionado, con el radio
modulado por ángulo. Sale watertight sin booleanas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import uuid4

from typing import TYPE_CHECKING

from app.services.generators.parametric_socket import (
    CM_TO_MM,
    Mesh,
    SocketProfile,
    drop_to_floor,
    export_binary_stl,
    is_watertight,
    mirror_y,
    signed_volume,
)
from app.utils import safe_filename_part

if TYPE_CHECKING:  # sólo para tipos
    from app.models import ProsthesisForm, SocketParameters

ALGORITHM_VERSION = "paw-foot-v1"

ANGULAR_SEGMENTS = 128
PROFILE_SEGMENTS = 14      # muestras de cada tramo curvo del perfil

FIT_CLEARANCE_MM = 0.35    # holgura del encastre (impresión FDM)
CUP_WALL_MM = 2.5          # pared de la copa
CUP_ENGAGE = 0.85          # fracción del poste que entra en la copa
PAD_RADIUS_RATIO = 1.5     # ancho de la almohadilla respecto de la copa
PAD_VS_SOCKET = 0.9        # …o respecto del radio distal del socket, lo que sea mayor
PAD_HEIGHT_RATIO = 0.75    # alto de la almohadilla respecto de su radio
NECK_RATIO = 0.35          # alto del cuello respecto del alto de la almohadilla
TOES = 4                   # lóbulos de la almohadilla
TOE_DEPTH = 0.16           # cuánto marcan los lóbulos
ELLIPSE_RATIO = 0.88       # la pata es más ancha que larga


@dataclass
class FootProfile:
    """Dimensiones del pie, en mm."""

    bore_radius: float
    bore_depth: float
    cup_radius: float
    cup_height: float
    neck_height: float
    pad_radius: float
    pad_height: float

    @classmethod
    def from_socket(cls, socket: SocketProfile) -> "FootProfile":
        bore_radius = socket.connector_radius + FIT_CLEARANCE_MM
        bore_depth = socket.post_length * CUP_ENGAGE
        cup_radius = bore_radius + CUP_WALL_MM
        # La huella acompaña el tamaño del perro, no sólo el del encastre.
        pad_radius = max(cup_radius * PAD_RADIUS_RATIO, socket.bottom_radius * PAD_VS_SOCKET)
        pad_height = pad_radius * PAD_HEIGHT_RATIO

        return cls(
            bore_radius=bore_radius,
            bore_depth=bore_depth,
            cup_radius=cup_radius,
            cup_height=bore_depth + CUP_WALL_MM,
            neck_height=pad_height * NECK_RATIO,
            pad_radius=pad_radius,
            pad_height=pad_height,
        )

    @property
    def total_height(self) -> float:
        return self.pad_height + self.neck_height + self.cup_height


def toe_factor(angle_deg: float, blend: float) -> float:
    """Modulación de los lóbulos. blend=1 en la base, 0 arriba del pie."""
    if blend <= 0.0:
        return 1.0
    lobes = math.cos(math.radians(TOES * angle_deg))
    return 1.0 + TOE_DEPTH * blend * lobes


def build_foot_mesh(
    socket: SocketProfile,
    *,
    angular_segments: int = ANGULAR_SEGMENTS,
    profile_segments: int = PROFILE_SEGMENTS,
    ellipse_ratio: float = ELLIPSE_RATIO,
) -> tuple[Mesh, FootProfile]:
    foot = FootProfile.from_socket(socket)

    z_pad = foot.pad_height
    z_neck = z_pad + foot.neck_height
    z_top = foot.total_height

    chamfer = min(1.2, foot.bore_radius * 0.3)

    # Perfil cerrado (radio, z, mezcla de lóbulos), recorrido desde el centro
    # de la base hacia afuera, arriba por el exterior y de vuelta por el
    # agujero. La mezcla apaga los lóbulos a medida que sube.
    profile: list[tuple[float, float, float]] = [(0.0, 0.0, 1.0)]

    # Base: plano de apoyo hasta el 70% del radio, después redondeo.
    flat_radius = foot.pad_radius * 0.70
    profile.append((flat_radius, 0.0, 1.0))


    for step in range(1, profile_segments + 1):
        phi = (math.pi / 2.0) * step / profile_segments
        radius = flat_radius + (foot.pad_radius - flat_radius) * math.sin(phi)
        z = foot.pad_height * (1.0 - math.cos(phi))
        # Los lóbulos se marcan abajo y se van desdibujando al subir.
        profile.append((radius, z, 1.0 - 0.7 * math.sin(phi)))

    # Cuello: de la almohadilla a la copa, con curva en S.
    for step in range(1, profile_segments + 1):
        u = step / profile_segments
        eased = u * u * (3.0 - 2.0 * u)
        radius = foot.pad_radius + (foot.cup_radius - foot.pad_radius) * eased
        profile.append((radius, z_pad + foot.neck_height * u, 0.45 * (1.0 - eased)))

    # Copa y boca achaflanada.
    profile.append((foot.cup_radius, z_top - chamfer, 0.0))
    profile.append((foot.cup_radius - chamfer * 0.5, z_top, 0.0))
    profile.append((foot.bore_radius + chamfer, z_top, 0.0))
    profile.append((foot.bore_radius, z_top - chamfer, 0.0))

    # Agujero ciego hacia abajo y piso del agujero.
    z_floor = z_top - foot.bore_depth
    profile.append((foot.bore_radius, z_floor, 0.0))
    profile.append((0.0, z_floor, 0.0))

    mesh = Mesh()
    rings: list[list[int] | int] = []
    for radius, z, blend in profile:
        if radius <= 1e-9:
            rings.append(mesh.add_vertex(0.0, 0.0, z))
            continue
        ring = []
        for i in range(angular_segments):
            angle_deg = 360.0 * i / angular_segments
            angle = math.radians(angle_deg)
            r = radius * toe_factor(angle_deg, blend)
            ring.append(
                mesh.add_vertex(r * math.cos(angle), r * math.sin(angle) * ellipse_ratio, z)
            )
        rings.append(ring)

    for lower, upper in zip(rings, rings[1:]):
        _strip(mesh, lower, upper, angular_segments)

    if signed_volume(mesh) < 0.0:
        mesh.faces = [(a, c, b) for a, b, c in mesh.faces]

    return mesh, foot


def _strip(mesh: Mesh, a, b, nu: int) -> None:
    if isinstance(a, int) and isinstance(b, int):
        return
    for i in range(nu):
        j = (i + 1) % nu
        if isinstance(a, int):
            mesh.add_triangle(a, b[j], b[i])
        elif isinstance(b, int):
            mesh.add_triangle(a[j], b, a[i])
        else:
            mesh.add_quad(a[i], a[j], b[j], b[i])


def generate(params: "SocketParameters", form: "ProsthesisForm") -> dict:
    socket = SocketProfile.from_params(params)
    mesh, foot = build_foot_mesh(socket)

    mirrored = params.limb_side == "izquierda"
    if mirrored:
        mirror_y(mesh)

    drop_to_floor(mesh)

    if not is_watertight(mesh):
        raise ValueError("El pie generado no quedó cerrado (no es imprimible).")

    return {
        "generated_filename": f"{safe_filename_part(params.dog_name)}-pie-{uuid4()}.stl",
        "generated_stl_bytes": export_binary_stl(mesh, f"hunda {ALGORITHM_VERSION}"),
        "generation_parameters": {
            "total_height_mm": foot.total_height,
            "bore_radius_mm": foot.bore_radius,
            "bore_depth_mm": foot.bore_depth,
            "fit_clearance_mm": FIT_CLEARANCE_MM,
            "cup_radius_mm": foot.cup_radius,
            "pad_radius_mm": foot.pad_radius,
            "pad_height_mm": foot.pad_height,
            "toes": TOES,
            "ellipse_ratio": ELLIPSE_RATIO,
            "triangles": len(mesh.faces),
            "mirrored": mirrored,
        },
        "algorithm_version": ALGORITHM_VERSION,
    }
