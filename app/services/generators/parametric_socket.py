"""Generador paramétrico del socket, en Python puro (sin bpy ni trimesh).

Modela una prótesis canina realista en vez de un cono hueco:

  - Sección transversal elíptica (el muñón no es un círculo perfecto).
  - Pared cónica con flare (evasé) redondeado en el borde proximal, así
    el borde no corta la piel al apoyar.
  - Fondo distal en cúpula elipsoidal hueca: acompaña la punta del muñón
    y reparte la carga, en vez de terminar en un anillo plano.
  - Ventilación: slots redondeados distribuidos en filas/columnas, con
    ligamentos calculados para no debilitar la pieza.
  - Conector distal: poste cilíndrico macizo con chaflán para acoplar el
    pilón/pata.
  - Espejado real para pata izquierda.

La malla se construye como una superficie cerrada (outer + inner + bordes
cosidos), por lo que sale watertight y lista para slicear: no hace falta
ninguna operación booleana.

Todas las medidas internas están en mm.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from uuid import uuid4

from app.models import ProsthesisForm, SocketParameters
from app.utils import safe_filename_part

CM_TO_MM = 10.0
ALGORITHM_VERSION = "parametric-socket-v2"

# Resolución de la malla.
ANGULAR_SEGMENTS = 128      # muestras alrededor del eje
WALL_SEGMENTS = 80         # muestras a lo largo de la pared
DOME_SEGMENTS = 18         # muestras de la cúpula distal
RIM_SEGMENTS = 6           # tramos de la media caña del borde proximal

# Proporciones anatómicas.
ELLIPSE_RATIO = 0.92       # aplastamiento antero-posterior de la sección
FLARE_RATIO = 0.07         # cuánto se abre el borde proximal
FLARE_SPAN = 0.16          # fracción superior de la pared donde se abre
DOME_HEIGHT_RATIO = 0.30   # altura de la cúpula respecto del radio distal
VENT_BAND = (0.14, 0.86)   # franja de la pared donde se permiten slots
VENT_FILL_W = 0.42         # fracción del paso angular ocupada por el slot
VENT_FILL_H = 0.68         # fracción del paso vertical ocupada por el slot
VENT_ROUNDNESS = 2.6       # exponente de la superelipse (2 = elipse, alto = rectángulo)
MIN_LIGAMENT_MM = 3.0      # material mínimo entre slots
MIN_SLOT_MM = 4.0          # slot más chico que esto no vale la pena (y no imprime bien)
MAX_SLOT_ASPECT = 2.0      # el slot no puede ser más de esto de largo respecto del ancho
DONNING_GAP_DEG = 0.0      # abertura longitudinal para calzar (0 = cerrado)
GAP_BAND = (0.18, 0.90)    # tramo de la pared que abarca esa abertura


@dataclass
class Mesh:
    vertices: list[tuple[float, float, float]] = field(default_factory=list)
    faces: list[tuple[int, int, int]] = field(default_factory=list)

    def add_vertex(self, x: float, y: float, z: float) -> int:
        self.vertices.append((x, y, z))
        return len(self.vertices) - 1

    def add_triangle(self, a: int, b: int, c: int) -> None:
        if a == b or b == c or a == c:
            return
        self.faces.append((a, b, c))

    def add_quad(self, a: int, b: int, c: int, d: int) -> None:
        self.add_triangle(a, b, c)
        self.add_triangle(a, c, d)


# ── helpers geométricos ──────────────────────────────────────────────────────

def _sub(p, q):
    return (p[0] - q[0], p[1] - q[1], p[2] - q[2])


def _cross(u, v):
    return (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )


def _dot(u, v):
    return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]


def _norm(u):
    length = math.sqrt(_dot(u, u))
    if length == 0.0:
        return (0.0, 0.0, 0.0)
    return (u[0] / length, u[1] / length, u[2] / length)


def _face_normal(mesh: Mesh, a: int, b: int, c: int):
    va, vb, vc = mesh.vertices[a], mesh.vertices[b], mesh.vertices[c]
    return _norm(_cross(_sub(vb, va), _sub(vc, va)))


def signed_volume(mesh: Mesh) -> float:
    """Volumen con signo (mm³). Positivo = normales hacia afuera."""
    total = 0.0
    for a, b, c in mesh.faces:
        va, vb, vc = mesh.vertices[a], mesh.vertices[b], mesh.vertices[c]
        total += _dot(va, _cross(vb, vc))
    return total / 6.0


def open_edges(mesh: Mesh) -> list[tuple[int, int]]:
    """Aristas que no aparecen exactamente una vez en cada sentido."""
    seen: dict[tuple[int, int], int] = {}
    for a, b, c in mesh.faces:
        for u, v in ((a, b), (b, c), (c, a)):
            seen[(u, v)] = seen.get((u, v), 0) + 1

    bad = []
    for (u, v), count in seen.items():
        if count != 1 or seen.get((v, u), 0) != 1:
            bad.append((u, v))
    return bad


def is_watertight(mesh: Mesh) -> bool:
    return not open_edges(mesh)


# ── perfil del socket ────────────────────────────────────────────────────────

def _smoothstep(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


@dataclass
class SocketProfile:
    """Dimensiones derivadas, todas en mm."""

    total_height: float
    top_radius: float
    bottom_radius: float
    wall: float
    connector_radius: float
    dome_height: float
    wall_height: float
    post_length: float
    rim_bead: float = 0.0

    @classmethod
    def from_params(cls, params: SocketParameters) -> "SocketProfile":
        height = params.height_cm * CM_TO_MM
        top_radius = params.top_radius_cm * CM_TO_MM
        bottom_radius = params.bottom_radius_cm * CM_TO_MM
        wall = params.wall_thickness_cm * CM_TO_MM
        connector_radius = params.connector_radius_cm * CM_TO_MM

        # La cúpula no puede comerse toda la altura ni ser más chata que la pared.
        dome_height = min(bottom_radius * DOME_HEIGHT_RATIO, height * 0.25)
        dome_height = max(dome_height, wall * 1.5)

        # El conector tiene que entrar en el fondo dejando material alrededor.
        connector_radius = min(connector_radius, (bottom_radius - wall) * 0.75)
        connector_radius = max(connector_radius, wall)

        rim_bead = wall / 2.0

        return cls(
            total_height=height,
            top_radius=top_radius,
            bottom_radius=bottom_radius,
            wall=wall,
            connector_radius=connector_radius,
            dome_height=dome_height,
            wall_height=height - dome_height - rim_bead,
            rim_bead=rim_bead,
            post_length=max(2.5 * connector_radius, 12.0),
        )

    def outer_radius_at(self, t: float) -> float:
        """Radio exterior de la pared. t=0 en la unión con la cúpula, t=1 en el borde."""
        base = self.bottom_radius + (self.top_radius - self.bottom_radius) * t
        flare_start = 1.0 - FLARE_SPAN
        if t <= flare_start:
            return base
        eased = _smoothstep((t - flare_start) / FLARE_SPAN)
        return base + self.top_radius * FLARE_RATIO * eased

    def wall_z(self, t: float) -> float:
        return self.dome_height + self.wall_height * t

    @property
    def junction_z(self) -> float:
        """Altura donde la cúpula exterior se encuentra con el poste conector."""
        phi_min = math.asin(min(1.0, self.connector_radius / self.bottom_radius))
        return self.dome_height * (1.0 - math.cos(phi_min))


# ── patrón de ventilación ────────────────────────────────────────────────────

@dataclass
class VentPattern:
    columns: int
    rows: int
    angular_half_deg: float
    height_half: float
    donning_gap_deg: float

    def slots(self):
        """Centros (ángulo, altura normalizada) de cada slot."""
        if self.columns <= 0 or self.rows <= 0:
            return
        band = VENT_BAND[1] - VENT_BAND[0]
        step = band / self.rows
        column_step = 360.0 / self.columns
        for row in range(self.rows):
            t_center = VENT_BAND[0] + step * (row + 0.5)
            # Filas alternadas desfasadas: reparte mejor la tensión.
            offset = 0.0 if row % 2 == 0 else column_step / 2.0
            for column in range(self.columns):
                yield column_step * column + offset, t_center

    def field(self, angle_deg: float, t: float) -> float:
        """Campo con signo: >0 hay material, <0 es agujero, 0 es el borde.

        Está normalizado en "radios de slot", así que sirve tanto para
        decidir si una celda es hueco como para pegar los vértices del
        borde sobre el contorno exacto (y que el slot no salga escalonado).
        """
        value = 1.0

        if self.donning_gap_deg > 0.0:
            angular = abs(_wrap_deg(angle_deg - 180.0)) / (self.donning_gap_deg / 2.0) - 1.0
            # Arranca sobre la cúpula y termina antes del borde: si llegara al
            # borde partiría el bead en dos y el socket perdería el aro rígido.
            vertical = max((GAP_BAND[0] - t), (t - GAP_BAND[1])) / 0.06
            value = min(value, max(angular, vertical))

        for a_center, t_center in self.slots():
            du = _wrap_deg(angle_deg - a_center) / self.angular_half_deg
            dv = (t - t_center) / self.height_half
            if abs(du) > 3.0 or abs(dv) > 3.0:
                continue
            p = VENT_ROUNDNESS
            distance = (abs(du) ** p + abs(dv) ** p) ** (1.0 / p)
            value = min(value, distance - 1.0)

        return value

    def is_hole(self, angle_deg: float, t: float) -> bool:
        return self.field(angle_deg, t) < 0.0


def _wrap_deg(angle: float) -> float:
    return (angle + 180.0) % 360.0 - 180.0


def plan_vents(profile: SocketProfile, donning_gap_deg: float = DONNING_GAP_DEG) -> VentPattern:
    """Elige filas/columnas de slots cuidando que los ligamentos no queden finos."""
    mean_radius = (profile.top_radius + profile.bottom_radius) / 2.0
    circumference = 2.0 * math.pi * mean_radius

    columns = max(0, min(10, int(circumference // 16.0)))
    band_mm = profile.wall_height * (VENT_BAND[1] - VENT_BAND[0])
    rows = max(0, min(5, int(band_mm // 22.0)))

    if columns < 3 or rows < 1:
        # Socket chico: mejor sin perforar que con ligamentos de papel.
        return VentPattern(0, 0, 0.0, 0.0, donning_gap_deg)

    column_step_mm = circumference / columns
    slot_width_mm = column_step_mm * VENT_FILL_W
    if column_step_mm - slot_width_mm < MIN_LIGAMENT_MM:
        slot_width_mm = max(0.0, column_step_mm - MIN_LIGAMENT_MM)
    if slot_width_mm < max(MIN_SLOT_MM, profile.wall):
        return VentPattern(0, 0, 0.0, 0.0, donning_gap_deg)

    angular_half_deg = (slot_width_mm / circumference) * 360.0 / 2.0

    row_step_mm = band_mm / rows
    slot_height_mm = row_step_mm * VENT_FILL_H
    if row_step_mm - slot_height_mm < MIN_LIGAMENT_MM:
        slot_height_mm = max(0.0, row_step_mm - MIN_LIGAMENT_MM)
    # Un slot muy alargado debilita la pared en el eje de carga.
    slot_height_mm = min(slot_height_mm, slot_width_mm * MAX_SLOT_ASPECT)
    if slot_height_mm < max(MIN_SLOT_MM, profile.wall):
        return VentPattern(0, 0, 0.0, 0.0, donning_gap_deg)

    height_half = (slot_height_mm / profile.wall_height) / 2.0

    return VentPattern(columns, rows, angular_half_deg, height_half, donning_gap_deg)


# ── construcción de la malla ─────────────────────────────────────────────────

def _point(mesh: Mesh, radius: float, angle_deg: float, z: float, ellipse: float) -> int:
    angle = math.radians(angle_deg)
    return mesh.add_vertex(radius * math.cos(angle), radius * math.sin(angle) * ellipse, z)


def _ring(mesh: Mesh, radius: float, z: float, segments: int, ellipse: float) -> list[int]:
    ring = []
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        x = radius * math.cos(angle)
        y = radius * math.sin(angle) * ellipse
        ring.append(mesh.add_vertex(x, y, z))
    return ring


def _centroid(mesh: Mesh, indices):
    points = [mesh.vertices[i] for i in indices]
    n = float(len(points))
    return (
        sum(p[0] for p in points) / n,
        sum(p[1] for p in points) / n,
        sum(p[2] for p in points) / n,
    )


def build_socket_mesh(
    params: SocketParameters,
    *,
    angular_segments: int = ANGULAR_SEGMENTS,
    wall_segments: int = WALL_SEGMENTS,
    dome_segments: int = DOME_SEGMENTS,
    rim_segments: int = RIM_SEGMENTS,
    ellipse_ratio: float = ELLIPSE_RATIO,
    donning_gap_deg: float = DONNING_GAP_DEG,
    vents: bool = True,
) -> tuple[Mesh, VentPattern, SocketProfile]:
    profile = SocketProfile.from_params(params)
    pattern = (
        plan_vents(profile, donning_gap_deg)
        if vents
        else VentPattern(0, 0, 0.0, 0.0, donning_gap_deg)
    )

    mesh = Mesh()
    nu = angular_segments
    nv = wall_segments

    # Máscara de material: celda (i, k) sólida o agujero.
    solid = [
        [
            not pattern.is_hole(360.0 * (i + 0.5) / nu, (k + 0.5) / nv)
            for k in range(nv)
        ]
        for i in range(nu)
    ]

    def is_solid(i: int, k: int) -> bool:
        if k < 0:
            return True          # abajo cierra la cúpula
        if k >= nv:
            return False         # arriba está el borde abierto
        return solid[i % nu][k]

    # Parámetros (ángulo, altura) de cada vértice de la grilla. Los que caen
    # sobre el borde de un slot se corren hasta el contorno exacto: sin esto
    # el agujero sale escalonado por la resolución de la malla.
    grid = [
        [(360.0 * i / nu, k / nv) for k in range(nv + 1)]
        for i in range(nu)
    ]
    if pattern.columns or pattern.donning_gap_deg:
        _snap_grid_to_vent_contour(grid, pattern, nu, nv, is_solid)

    outer_rings: list[list[int]] = [[] for _ in range(nv + 1)]
    inner_rings: list[list[int]] = [[] for _ in range(nv + 1)]
    for i in range(nu):
        for k in range(nv + 1):
            angle, t = grid[i][k]
            z = profile.wall_z(t)
            r_out = profile.outer_radius_at(t)
            outer_rings[k].append(_point(mesh, r_out, angle, z, ellipse_ratio))
            inner_rings[k].append(
                _point(mesh, r_out - profile.wall, angle, z, ellipse_ratio)
            )

    for i in range(nu):
        j = (i + 1) % nu
        for k in range(nv):
            if not solid[i][k]:
                continue

            o_lo, o_hi = outer_rings[k], outer_rings[k + 1]
            i_lo, i_hi = inner_rings[k], inner_rings[k + 1]

            # Cara exterior (normal hacia afuera) y cara interior (hacia el eje).
            mesh.add_quad(o_hi[i], o_lo[i], o_lo[j], o_hi[j])
            mesh.add_quad(i_lo[i], i_hi[i], i_hi[j], i_lo[j])

            # Costura del canto contra cada vecino que sea agujero. El sentido
            # de cada quad sale de la geometría del cilindro (r, θ, z), no de
            # comparar normales: con celdas finas eso se equivoca de lado.
            if not is_solid(i, k + 1) and k + 1 < nv:   # canto superior, normal +z
                mesh.add_quad(o_hi[i], o_hi[j], i_hi[j], i_hi[i])
            if not is_solid(i, k - 1):                  # canto inferior, normal -z
                mesh.add_quad(o_lo[i], i_lo[i], i_lo[j], o_lo[j])
            if not is_solid(i + 1, k):                  # canto lateral +θ
                mesh.add_quad(o_lo[j], i_lo[j], i_hi[j], o_hi[j])
            if not is_solid(i - 1, k):                  # canto lateral -θ
                mesh.add_quad(o_lo[i], o_hi[i], i_hi[i], i_lo[i])

    # Borde proximal: bead redondeado en vez de un canto vivo.
    _build_rim_bead(
        mesh,
        profile,
        grid,
        nu,
        nv,
        rim_segments,
        ellipse_ratio,
        outer_top=outer_rings[nv],
        inner_top=inner_rings[nv],
        solid_at_top=[solid[i][nv - 1] for i in range(nu)],
    )

    # Fondo: cúpula hueca + poste conector, como perfil de revolución.
    _build_bottom(
        mesh,
        profile,
        nu,
        dome_segments,
        ellipse_ratio,
        outer_ring=outer_rings[0],
        inner_ring=inner_rings[0],
    )

    if signed_volume(mesh) < 0.0:
        mesh.faces = [(a, c, b) for a, b, c in mesh.faces]

    return mesh, pattern, profile


def _snap_grid_to_vent_contour(grid, pattern: VentPattern, nu: int, nv: int, is_solid) -> None:
    """Corre los vértices del borde de un slot hasta el contorno real.

    Un paso de Newton sobre el campo con signo, acotado a media celda para
    que la malla no se cruce a sí misma.
    """
    d_angle = 360.0 / nu
    d_t = 1.0 / nv

    for i in range(nu):
        for k in range(1, nv + 1):
            # Sólo los vértices que tienen material de un lado y hueco del otro.
            neighbours = [
                is_solid(i - 1, k - 1),
                is_solid(i, k - 1),
                is_solid(i - 1, k),
                is_solid(i, k),
            ]
            if all(neighbours) or not any(neighbours):
                continue

            angle, t = grid[i][k]
            value = pattern.field(angle, t)
            eps_a, eps_t = d_angle * 0.25, d_t * 0.25
            grad_a = (pattern.field(angle + eps_a, t) - pattern.field(angle - eps_a, t)) / (2 * eps_a)
            grad_t = (pattern.field(angle, t + eps_t) - pattern.field(angle, t - eps_t)) / (2 * eps_t)

            norm = grad_a * grad_a + grad_t * grad_t
            if norm < 1e-12:
                continue

            move_a = max(-d_angle * 0.45, min(d_angle * 0.45, -value * grad_a / norm))
            move_t = max(-d_t * 0.45, min(d_t * 0.45, -value * grad_t / norm))
            grid[i][k] = (angle + move_a, min(1.0, max(0.0, t + move_t)))


def _build_rim_bead(
    mesh: Mesh,
    profile: SocketProfile,
    grid,
    nu: int,
    nv: int,
    rim_segments: int,
    ellipse_ratio: float,
    *,
    outer_top: list[int],
    inner_top: list[int],
    solid_at_top: list[bool],
) -> None:
    """Media caña que une el borde exterior con el interior."""
    bead = profile.rim_bead

    rings: list[list[int]] = [outer_top]
    for step in range(1, rim_segments):
        phi = math.pi * step / rim_segments
        ring = []
        for i in range(nu):
            angle, t = grid[i][nv]
            r_out = profile.outer_radius_at(t)
            center_r = r_out - bead
            ring.append(
                _point(
                    mesh,
                    center_r + bead * math.cos(phi),
                    angle,
                    profile.wall_z(t) + bead * math.sin(phi),
                    ellipse_ratio,
                )
            )
        rings.append(ring)
    rings.append(inner_top)

    for lower, upper in zip(rings, rings[1:]):
        for i in range(nu):
            if not solid_at_top[i]:
                continue
            j = (i + 1) % nu
            mesh.add_quad(lower[i], lower[j], upper[j], upper[i])


def _build_bottom(
    mesh: Mesh,
    profile: SocketProfile,
    nu: int,
    dome_segments: int,
    ellipse_ratio: float,
    *,
    outer_ring: list[int],
    inner_ring: list[int],
) -> None:
    """Perfil cerrado: cúpula exterior → poste → base → cúpula interior."""
    dome = profile.dome_height
    r_bot = profile.bottom_radius
    wall = profile.wall
    r_conn = profile.connector_radius

    # Ángulo donde la cúpula exterior alcanza el radio del conector.
    phi_min = math.asin(min(1.0, r_conn / r_bot))  # ver SocketProfile.junction_z

    outer_profile: list[tuple[float, float]] = []
    for s in range(dome_segments + 1):
        phi = math.pi / 2.0 - (math.pi / 2.0 - phi_min) * s / dome_segments
        outer_profile.append((r_bot * math.sin(phi), dome * (1.0 - math.cos(phi))))

    z_junction = outer_profile[-1][1]
    z_post_end = z_junction - profile.post_length
    chamfer = min(1.0, r_conn * 0.25)

    post_profile = [
        (r_conn, z_post_end + chamfer),
        (r_conn - chamfer, z_post_end),
        (0.0, z_post_end),
    ]

    inner_profile: list[tuple[float, float]] = []
    r_in_bot = r_bot - wall
    dome_in = dome - wall
    for s in range(dome_segments + 1):
        phi = (math.pi / 2.0) * s / dome_segments
        inner_profile.append((r_in_bot * math.sin(phi), dome - dome_in * math.cos(phi)))

    # Recorrido completo: baja por afuera, cruza la base, sube por adentro.
    chain = outer_profile + post_profile + inner_profile

    rings: list[list[int] | int] = []
    for radius, z in chain:
        if radius <= 1e-9:
            rings.append(mesh.add_vertex(0.0, 0.0, z))
        else:
            rings.append(_ring(mesh, radius, z, nu, ellipse_ratio))

    # El primer y el último anillo son los de la pared: se comparten.
    rings[0] = outer_ring
    rings[-1] = inner_ring

    for a, b in zip(rings, rings[1:]):
        _strip(mesh, a, b, nu)


def _strip(mesh: Mesh, a, b, nu: int) -> None:
    """Une dos anillos consecutivos del perfil (o un anillo con un ápice)."""
    if isinstance(a, int) and isinstance(b, int):
        return
    for i in range(nu):
        j = (i + 1) % nu
        if isinstance(a, int):
            mesh.add_triangle(a, b[i], b[j])
        elif isinstance(b, int):
            mesh.add_triangle(a[i], b, a[j])
        else:
            mesh.add_quad(a[i], b[i], b[j], a[j])


def drop_to_floor(mesh: Mesh) -> None:
    """Apoya la pieza en z=0 (el poste queda por debajo del origen si no)."""
    if not mesh.vertices:
        return
    min_z = min(v[2] for v in mesh.vertices)
    if abs(min_z) < 1e-9:
        return
    mesh.vertices = [(x, y, z - min_z) for x, y, z in mesh.vertices]


def mirror_y(mesh: Mesh) -> None:
    """Espeja la malla y corrige el sentido de las caras."""
    mesh.vertices = [(x, -y, z) for x, y, z in mesh.vertices]
    mesh.faces = [(a, c, b) for a, b, c in mesh.faces]


def export_binary_stl(mesh: Mesh, header: str = "hunda") -> bytes:
    out = bytearray()
    out += header.encode("ascii", "ignore")[:80].ljust(80, b"\0")
    out += struct.pack("<I", len(mesh.faces))
    for a, b, c in mesh.faces:
        nx, ny, nz = _face_normal(mesh, a, b, c)
        out += struct.pack("<3f", nx, ny, nz)
        for index in (a, b, c):
            out += struct.pack("<3f", *mesh.vertices[index])
        out += struct.pack("<H", 0)
    return bytes(out)


# ── entrada del generador ────────────────────────────────────────────────────

def is_available() -> bool:
    """No necesita nada externo: siempre disponible."""
    return True


def generate(params: SocketParameters, form: ProsthesisForm) -> dict:
    mesh, pattern, profile = build_socket_mesh(params)

    mirrored = params.limb_side == "izquierda"
    if mirrored:
        mirror_y(mesh)

    drop_to_floor(mesh)

    if not is_watertight(mesh):
        raise ValueError("La malla generada no quedó cerrada (no es imprimible).")

    stl_bytes = export_binary_stl(mesh, f"hunda {ALGORITHM_VERSION}")

    return {
        "generated_filename": f"{safe_filename_part(params.dog_name)}-{uuid4()}.stl",
        "generated_stl_bytes": stl_bytes,
        "generation_parameters": {
            "total_height_mm": profile.total_height,
            "proximal_radius_mm": profile.top_radius,
            "distal_radius_mm": profile.bottom_radius,
            "wall_thickness_mm": profile.wall,
            "connector_radius_mm": profile.connector_radius,
            "connector_length_mm": profile.post_length,
            "dome_height_mm": profile.dome_height,
            "ellipse_ratio": ELLIPSE_RATIO,
            "flare_ratio": FLARE_RATIO,
            "vent_columns": pattern.columns,
            "vent_rows": pattern.rows,
            "donning_gap_deg": pattern.donning_gap_deg,
            "angular_segments": ANGULAR_SEGMENTS,
            "wall_segments": WALL_SEGMENTS,
            "triangles": len(mesh.faces),
            "mirrored": mirrored,
        },
        "algorithm_version": ALGORITHM_VERSION,
    }
