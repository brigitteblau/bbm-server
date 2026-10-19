#!/usr/bin/env python3
"""Chequeo de la geometría sin instalar nada.

    python scripts/selfcheck.py

No necesita pytest, ni pydantic, ni fastapi: sólo Python. Sirve para saber
que las piezas salen bien imprimibles aunque no tengas el entorno armado.
La suite completa (incluido el flujo de la API) sigue siendo:

    python -m pytest tests/ -v
"""

import math
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.generators import parametric_socket as ps   # noqa: E402
from app.services.generators import one_piece as op            # noqa: E402
from app.services.generators import paw_foot as pf            # noqa: E402
from app.utils.mass import estimate_mass_g                    # noqa: E402


@dataclass
class Medidas:
    """Los mismos campos que SocketParameters, sin depender de pydantic."""

    dog_name: str
    height_cm: float
    top_radius_cm: float
    bottom_radius_cm: float
    wall_thickness_cm: float
    connector_radius_cm: float
    limb_position: str = "delantera"
    limb_side: str = "derecha"


PERROS = [
    Medidas("Chico", 4, 1.2, 1.0, 0.25, 1.2),
    Medidas("Mediano", 9, 2.86, 2.07, 0.32, 1.6),
    Medidas("Grande", 22, 6.0, 5.0, 0.42, 2.0),
    Medidas("Zurdo", 9, 2.86, 2.07, 0.32, 1.6, limb_side="izquierda"),
]

fallos: list[str] = []


def check(condicion: bool, descripcion: str) -> None:
    print(f"  {'✓' if condicion else '✗'} {descripcion}")
    if not condicion:
        fallos.append(descripcion)


def revisar(medidas: Medidas) -> None:
    print(f"\n{medidas.dog_name} ({medidas.limb_side}):")

    socket, patron, perfil = ps.build_socket_mesh(medidas)
    if medidas.limb_side == "izquierda":
        ps.mirror_y(socket)
    ps.drop_to_floor(socket)

    check(ps.is_watertight(socket), "el socket es una malla cerrada")
    check(ps.signed_volume(socket) > 0, "las normales del socket miran para afuera")
    check(
        max(v[2] for v in socket.vertices) - min(v[2] for v in socket.vertices)
        > medidas.height_cm * 10,
        "el socket mide el largo del muñón más el poste",
    )

    pie, foot = pf.build_foot_mesh(perfil)
    ps.drop_to_floor(pie)

    check(ps.is_watertight(pie), "el pie es una malla cerrada")
    check(ps.signed_volume(pie) > 0, "las normales del pie miran para afuera")
    check(
        foot.bore_radius > perfil.connector_radius,
        "el agujero del pie es más grande que el poste (entra)",
    )
    check(
        foot.bore_depth < perfil.post_length,
        "el poste es más largo que el agujero (apoya a fondo)",
    )

    radios = [math.hypot(x, y) for x, y, z in pie.vertices if z < foot.pad_height * 0.3]
    check(max(radios) - min(radios) > 1.0, "la almohadilla tiene los lóbulos marcados")

    entera, foot_entera, _ = op.build_one_piece_mesh(medidas)
    ps.drop_to_floor(entera)
    check(ps.is_watertight(entera), "la versión de una pieza es una malla cerrada")
    check(
        foot_entera.pad_radius > perfil.bottom_radius,
        "el pie de la versión entera es más ancho que la pierna",
    )
    entera_g = estimate_mass_g(ps.signed_volume(entera), "pla")

    stl = ps.export_binary_stl(socket)
    (triangulos,) = struct.unpack("<I", stl[80:84])
    check(len(stl) == 84 + 50 * triangulos, "el STL binario del socket es válido")

    socket_g = estimate_mass_g(ps.signed_volume(socket), "petg")
    pie_g = estimate_mass_g(ps.signed_volume(pie), "tpu")
    # Densidad aparente: cuánto pesa respecto del cilindro que ocupa. Es la
    # medida honesta de "qué tan hueca quedó" — la masa escala con el cubo
    # del tamaño, así que comparar gramos entre perros no dice nada.
    envolvente_cm3 = math.pi * (perfil.top_radius / 10) ** 2 * (perfil.total_height / 10)
    aparente = socket_g / envolvente_cm3
    check(aparente < 0.35, f"el socket es hueco y liviano ({aparente:.2f} g/cm³ aparente)")
    print(
        f"    reticulado {patron.columns}×{patron.rows} · "
        f"socket {socket_g:.0f} g PETG + pie {pie_g:.0f} g TPU = "
        f"{socket_g + pie_g:.0f} g  ·  de una pieza: {entera_g:.0f} g PLA"
    )


def main() -> int:
    print("Chequeo de geometría (sin dependencias)")
    for medidas in PERROS:
        revisar(medidas)

    print()
    if fallos:
        print(f"✗ {len(fallos)} chequeo(s) fallaron:")
        for fallo in fallos:
            print(f"   - {fallo}")
        return 1

    print("✓ Todo bien.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
