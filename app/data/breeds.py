"""Mini base de datos de razas: defaults de arranque para el formulario.

OJO con qué es esto y qué no es: son **valores de referencia** para
precargar el formulario y para ajustar la rigidez de la pieza, sacados de
rangos de peso y proporciones típicas de cada raza. No reemplazan medir
el muñón del perro: la geometría final sale siempre de las medidas que
carga la persona.

Cada perfil tiene:
  - `size`: categoría de tamaño.
  - `weight_range_kg`: rango típico, para sugerir y para validar.
  - `slenderness`: qué tan finas son las patas respecto del tamaño
    (galgo 0.85, bulldog 1.12). Escala las circunferencias sugeridas.
  - `wall_scale`: factor de espesor. Un perro muy activo o muy macizo
    necesita más pared; uno liviano, menos (y así pesa menos).
  - `material`: filamento sugerido para el socket.
"""

from dataclasses import dataclass, field
import unicodedata

SIZES = ("toy", "chico", "mediano", "grande", "gigante")

# Medidas de arranque por tamaño: (largo del muñón, circunferencia
# proximal, circunferencia distal) en cm, para pata delantera.
BASE_MEASUREMENTS_CM = {
    "toy": (4.5, 9.0, 7.0),
    "chico": (6.5, 13.0, 10.0),
    "mediano": (9.0, 18.0, 13.0),
    "grande": (13.0, 26.0, 19.0),
    "gigante": (16.0, 32.0, 24.0),
}

# La pata trasera deja un muñón un poco más largo y más carnoso.
HIND_LIMB_SCALE = (1.12, 1.06, 1.06)


@dataclass(frozen=True)
class BreedProfile:
    key: str
    name: str
    size: str
    weight_range_kg: tuple[float, float]
    slenderness: float = 1.0
    wall_scale: float = 1.0
    material: str = "petg"
    notes: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)

    def measurements_cm(self, limb_position: str = "delantera") -> dict[str, float]:
        """Medidas sugeridas para precargar el formulario."""
        largo, proximal, distal = BASE_MEASUREMENTS_CM[self.size]

        if limb_position == "trasera":
            largo *= HIND_LIMB_SCALE[0]
            proximal *= HIND_LIMB_SCALE[1]
            distal *= HIND_LIMB_SCALE[2]

        return {
            "stump_length_cm": round(largo, 1),
            "proximal_circumference_cm": round(proximal * self.slenderness, 1),
            "distal_circumference_cm": round(distal * self.slenderness, 1),
        }

    @property
    def typical_weight_kg(self) -> float:
        return round(sum(self.weight_range_kg) / 2, 1)


BREEDS: tuple[BreedProfile, ...] = (
    BreedProfile("chihuahua", "Chihuahua", "toy", (1.5, 3.0),
                 slenderness=0.92, wall_scale=0.95,
                 notes="Huesos muy finos: pared mínima y bordes bien romos."),
    BreedProfile("yorkshire", "Yorkshire Terrier", "toy", (2.0, 3.5),
                 slenderness=0.92, wall_scale=0.95, aliases=("yorkie", "yorky")),
    BreedProfile("pomerania", "Pomerania", "toy", (2.0, 3.5),
                 slenderness=0.95, aliases=("pomeranian", "lulu")),
    BreedProfile("caniche", "Caniche", "chico", (5.0, 11.0),
                 slenderness=0.93, aliases=("poodle", "french poodle")),
    BreedProfile("salchicha", "Salchicha (Dachshund)", "chico", (7.0, 12.0),
                 slenderness=1.05, wall_scale=1.05,
                 notes="Patas cortas y mucha carga por pata: pared algo más gruesa.",
                 aliases=("dachshund", "teckel", "perro salchicha")),
    BreedProfile("shih tzu", "Shih Tzu", "chico", (4.0, 8.0), slenderness=1.02),
    BreedProfile("pug", "Pug", "chico", (6.0, 9.0),
                 slenderness=1.10, wall_scale=1.05),
    BreedProfile("beagle", "Beagle", "mediano", (9.0, 14.0), wall_scale=1.05,
                 notes="Muy activo: conviene no bajar la pared."),
    BreedProfile("bulldog frances", "Bulldog Francés", "mediano", (9.0, 14.0),
                 slenderness=1.12, wall_scale=1.08, aliases=("frenchie", "bulldog frances")),
    BreedProfile("cocker", "Cocker Spaniel", "mediano", (10.0, 15.0),
                 aliases=("cocker spaniel",)),
    BreedProfile("schnauzer", "Schnauzer Mediano", "mediano", (14.0, 20.0)),
    BreedProfile("border collie", "Border Collie", "mediano", (14.0, 20.0),
                 slenderness=0.95, wall_scale=1.10,
                 notes="Perro de trabajo: alto ciclo de carga, pared reforzada."),
    BreedProfile("whippet", "Whippet", "mediano", (10.0, 16.0),
                 slenderness=0.85, wall_scale=0.92,
                 notes="Patas muy finas: socket angosto y liviano."),
    BreedProfile("galgo", "Galgo", "grande", (20.0, 30.0),
                 slenderness=0.85, wall_scale=0.92,
                 aliases=("greyhound", "galgo espanol")),
    BreedProfile("labrador", "Labrador Retriever", "grande", (25.0, 36.0),
                 wall_scale=1.08, aliases=("labrador retriever", "lab")),
    BreedProfile("golden", "Golden Retriever", "grande", (25.0, 34.0),
                 wall_scale=1.08, aliases=("golden retriever",)),
    BreedProfile("ovejero aleman", "Ovejero Alemán", "grande", (22.0, 40.0),
                 wall_scale=1.12,
                 notes="Displasia frecuente: cuidar el apoyo distal.",
                 aliases=("pastor aleman", "german shepherd", "ovejero")),
    BreedProfile("boxer", "Boxer", "grande", (25.0, 32.0), wall_scale=1.08),
    BreedProfile("husky", "Husky Siberiano", "grande", (20.0, 27.0),
                 wall_scale=1.10, aliases=("husky siberiano", "siberian husky")),
    BreedProfile("pitbull", "Pitbull", "grande", (16.0, 27.0),
                 slenderness=1.08, wall_scale=1.15,
                 notes="Mucha fuerza de tracción: el encastre sufre.",
                 aliases=("pit bull", "american pitbull", "american bully")),
    BreedProfile("rottweiler", "Rottweiler", "gigante", (35.0, 60.0),
                 slenderness=1.08, wall_scale=1.15),
    BreedProfile("gran danes", "Gran Danés", "gigante", (45.0, 70.0),
                 slenderness=0.95, wall_scale=1.15, aliases=("great dane",)),
    BreedProfile("mestizo", "Mestizo", "mediano", (8.0, 25.0),
                 notes="Sin raza definida: el tamaño se deduce del peso.",
                 aliases=("criollo", "mezcla", "sin raza", "callejero")),
)

_BY_KEY: dict[str, BreedProfile] = {}
for _profile in BREEDS:
    for _name in (_profile.key, _profile.name, *_profile.aliases):
        _BY_KEY[_name] = _profile


def normalize(value: str) -> str:
    """'Ovejero Alemán' y 'ovejero aleman' son la misma raza."""
    sin_tildes = unicodedata.normalize("NFKD", value.strip().lower())
    limpio = sin_tildes.encode("ascii", "ignore").decode("ascii")
    return " ".join(limpio.replace("-", " ").split())


_NORMALIZED = {normalize(name): profile for name, profile in _BY_KEY.items()}


def size_for_weight(weight_kg: float) -> str:
    if weight_kg < 4:
        return "toy"
    if weight_kg < 12:
        return "chico"
    if weight_kg < 22:
        return "mediano"
    if weight_kg < 40:
        return "grande"
    return "gigante"


def find(breed: str | None) -> BreedProfile | None:
    """Busca por nombre, alias, con o sin tildes. None si no está."""
    if not breed:
        return None

    objetivo = normalize(breed)
    if objetivo in _NORMALIZED:
        return _NORMALIZED[objetivo]

    # 'caniche toy', 'mi labrador': alcanza con que el nombre esté adentro.
    for nombre, profile in _NORMALIZED.items():
        if nombre in objetivo or objetivo in nombre:
            return profile

    return None


def resolve(breed: str | None, weight_kg: float) -> BreedProfile:
    """El perfil de la raza, o uno genérico armado por peso."""
    profile = find(breed)
    if profile is not None:
        return profile

    size = size_for_weight(weight_kg)
    return BreedProfile(
        key=f"generico-{size}",
        name=f"Sin raza identificada ({size})",
        size=size,
        weight_range_kg=(weight_kg, weight_kg),
        notes="No está en la tabla: se usa el tamaño deducido del peso.",
    )


def catalog() -> list[dict]:
    """La tabla entera, para que el front arme el desplegable."""
    return [
        {
            "key": profile.key,
            "name": profile.name,
            "size": profile.size,
            "weight_range_kg": list(profile.weight_range_kg),
            "typical_weight_kg": profile.typical_weight_kg,
            "wall_scale": profile.wall_scale,
            "material": profile.material,
            "notes": profile.notes,
            "measurements_cm": profile.measurements_cm(),
        }
        for profile in BREEDS
    ]
