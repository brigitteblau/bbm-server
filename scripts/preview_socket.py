#!/usr/bin/env python3
"""Genera un STL de prueba sin levantar el server ni tocar Supabase.

    python scripts/preview_socket.py --nombre Copito --peso 18 --largo 9 \
        --proximal 18 --distal 13 --salida copito.stl

Sirve para mirar la pieza en el visor antes de meterla en el flujo del front.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import ProsthesisForm                     # noqa: E402
from app.services.generators import parametric_socket as ps  # noqa: E402
from app.services.generators import paw_foot as pf         # noqa: E402
from app.services.generators import selector              # noqa: E402
from app.services.socket_parameters import SocketParameterGenerator  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nombre", default="Copito")
    parser.add_argument("--peso", type=float, default=18.0, help="kg")
    parser.add_argument("--largo", type=float, default=9.0, help="largo del muñón, cm")
    parser.add_argument("--proximal", type=float, default=18.0, help="circunferencia proximal, cm")
    parser.add_argument("--distal", type=float, default=13.0, help="circunferencia distal, cm")
    parser.add_argument("--pata", default="delantera", choices=["delantera", "trasera"])
    parser.add_argument("--lado", default="derecha", choices=["izquierda", "derecha"])
    parser.add_argument("--salida", default="socket.stl")
    parser.add_argument("--pie", default=None,
                        help="además del socket, escribe el pie en este archivo")
    args = parser.parse_args()

    form = ProsthesisForm(
        dog_name=args.nombre,
        dog_weight_kg=args.peso,
        limb_position=args.pata,
        limb_side=args.lado,
        stump_length_cm=args.largo,
        proximal_circumference_cm=args.proximal,
        distal_circumference_cm=args.distal,
    )

    params = SocketParameterGenerator().generate(form)

    issues = selector.validate_geometry(params)
    if issues:
        for issue in issues:
            print(f"✗ {issue}", file=sys.stderr)
        return 1

    result = ps.generate(params, form)
    Path(args.salida).write_bytes(result["generated_stl_bytes"])

    info = result["generation_parameters"]
    print(f"✓ {args.salida}  ({len(result['generated_stl_bytes']) / 1e6:.1f} MB)")
    print(f"  alto {info['total_height_mm']:.0f} mm · "
          f"radio {info['distal_radius_mm']:.1f}→{info['proximal_radius_mm']:.1f} mm · "
          f"pared {info['wall_thickness_mm']:.1f} mm")
    print(f"  conector ⌀{info['connector_radius_mm'] * 2:.1f} × {info['connector_length_mm']:.0f} mm · "
          f"ventilación {info['vent_columns']}×{info['vent_rows']} · "
          f"{info['triangles']} triángulos"
          + (" · espejado" if info["mirrored"] else ""))

    if args.pie:
        foot = pf.generate(params, form)
        Path(args.pie).write_bytes(foot["generated_stl_bytes"])
        pie = foot["generation_parameters"]
        print(f"✓ {args.pie}  ({len(foot['generated_stl_bytes']) / 1e6:.1f} MB)")
        print(f"  alto {pie['total_height_mm']:.0f} mm · huella ⌀{pie['pad_radius_mm'] * 2:.0f} mm · "
              f"encastre ⌀{pie['bore_radius_mm'] * 2:.1f} × {pie['bore_depth_mm']:.0f} mm "
              f"(holgura {pie['fit_clearance_mm']} mm)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
