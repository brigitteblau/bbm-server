"""Cómo imprimir cada pieza.

Las piezas están diseñadas para salir sin soportes **en la orientación
correcta**, que no es la misma para todas:

- El socket de dos piezas va boca abajo (el borde proximal apoyado en la
  cama): así el poste conector apunta hacia arriba y la cúpula distal
  queda como un cono ascendente, sin voladizos.
- El pie y la pieza entera van parados, como se usan: la cavidad abre
  hacia abajo y se cierra de a poco, sin techos planos que colgar.

Las paredes son finas a propósito, así que el relleno casi no interviene:
lo que importa es que los perímetros alcancen a llenar la pared.
"""

ORIENTATIONS = {
    "socket": "boca abajo, con el borde proximal apoyado en la cama",
    "foot": "parado, con la almohadilla apoyada en la cama",
    "one_piece": "parado, como se usa: la almohadilla apoyada en la cama",
}


def print_hints(piece: str, material: str, wall_mm: float) -> dict:
    if piece not in ORIENTATIONS:
        raise ValueError(f"Pieza desconocida: '{piece}'.")

    # Boquilla de 0.4: tantos perímetros como haga falta para llenar la
    # pared desde las dos caras.
    perimetros = max(2, round(wall_mm / 2 / 0.4))

    return {
        "orientation": ORIENTATIONS[piece],
        "supports": False,
        "material": material,
        "layer_height_mm": 0.2,
        "perimeters": perimetros,
        "infill_percent": 20,
        "note": (
            "Las paredes son finas: con esos perímetros quedan macizas y el "
            "relleno casi no se usa. Si al imprimir el reticulado se ve frágil, "
            "subí perímetros antes que relleno."
        ),
    }
