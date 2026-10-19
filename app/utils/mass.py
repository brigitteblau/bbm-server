"""Peso estimado de las piezas impresas.

El volumen de la malla por la densidad del material. Es una estimación de
piso: el slicer agrega algo (costuras, falda, tolerancias), pero alcanza
para comparar diseños y para saber qué le estamos colgando al perro.
"""

# g/cm³, filamentos típicos de FDM.
DENSITIES_G_CM3 = {
    "pla": 1.24,
    "petg": 1.27,
    "abs": 1.04,
    "tpu": 1.21,
    "nylon": 1.14,
}

DEFAULT_SOCKET_MATERIAL = "petg"
DEFAULT_FOOT_MATERIAL = "tpu"


def estimate_mass_g(volume_mm3: float, material: str) -> float:
    """Gramos de material para un volumen macizo de pared."""
    if volume_mm3 < 0:
        raise ValueError("El volumen no puede ser negativo.")

    density = DENSITIES_G_CM3.get(material.lower())
    if density is None:
        raise ValueError(
            f"Material desconocido: '{material}'. "
            f"Conocidos: {', '.join(sorted(DENSITIES_G_CM3))}."
        )

    return round(volume_mm3 / 1000.0 * density, 1)


def mass_by_material(volume_mm3: float) -> dict[str, float]:
    """El mismo volumen en cada material, para poder elegir."""
    return {
        material: estimate_mass_g(volume_mm3, material)
        for material in sorted(DENSITIES_G_CM3)
    }
