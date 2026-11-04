"""Generador paramétrico con Blender Geometry Nodes: la bota completa.

Arma desde cero la misma bota que scripts/make_base_models.py (pie, talón,
puntera, socket ventilado, surcos de dedos y dibujo de suela), pero como un
grafo de Geometry Nodes con primitivas y booleanos, y con las medidas reales
de cada perro:

  - Cavidad del socket: radios proximal/distal y largo del muñón exactos,
    más el espacio para la media/liner que se le pone al perro.
  - Boca en embudo: el borde se abre hacia afuera para que la pata entre guiada.
  - Pared: el espesor que da el peso (socket_parameters.py).
  - Pie: escalado según el radio proximal (el modelo base es para 28.5 mm).
  - Trasera: el tubo del socket inclinado 11° hacia atrás.
  - Izquierda: espejado en X.

Unidades: mm. Perro mirando a +Y, Z arriba, pata DERECHA como referencia.
IMPORTANTE: bpy se importa adentro de las funciones, así el server
levanta aunque bpy no esté instalado.
"""

import math
import tempfile
from pathlib import Path
from uuid import uuid4

from app.models import ProsthesisForm, SocketParameters
from app.utils import safe_filename_part

CM_TO_MM = 10.0
ALGORITHM_VERSION = "blender-gn-v2-bota"

# ── Diseño base (mm), igual que scripts/make_base_models.py ──────────────────
BASE_PROXIMAL_RADIUS = 28.5          # boca interna del socket del modelo base
FOOT_SCALE_LIMITS = (0.5, 2.0)
ELL_Y = 0.9                          # sección del socket aplastada adelante-atrás
CAVITY_BOTTOM = 60.0                 # altura del fondo de la cavidad (escala con el pie)
TUBE_BOTTOM = 30.0                   # donde arranca el tubo, adentro del pie
HIND_TILT_DEG = 11.0                 # trasera: el tubo se inclina hacia atrás
HIND_PIVOT_Z = 45.0
# (centro, radios) de los elipsoides del pie
FOOT = ((1.5, 30.0, 24.0), (29.0, 57.0, 27.0))
HEEL = ((0.0, -8.0, 33.0), (27.5, 28.0, 33.0))
TOE_BOX = ((1.5, 56.0, 15.0), (31.0, 30.0, 19.0))
TOE_GROOVE_ANGLES = (-0.30, -0.02, 0.27)   # rad, desde el empeine hacia +Y
TOE_GROOVE_DEPTH = 1.5
TREAD_PITCH, TREAD_WIDTH, TREAD_DEPTH = 9.0, 3.0, 1.3
# Ventanas de ventilación: (ángulo, posición en la cavidad 0..1, largo relativo)
# ángulo 0 = lateral (+X). Van de a pares, separadas por un travesaño.
VENTS = ((-28.0, 0.76, 0.27), (-28.0, 0.44, 0.22), (180.0 + 28.0, 0.61, 0.25))
VENT_WIDTH, VENT_PAIR_OFFSET = 6.2, 5.6
# Media/liner: el perro se pone una media de silicona o neopreno y la cavidad
# deja ese espacio de más (alrededor y abajo). Facilita ponerla y amortigua.
LINER_MM = 3.0
# Boca en embudo: en los últimos FUNNEL_HEIGHT mm la boca se abre FUNNEL_FLARE mm
# hacia afuera (cavidad y pared), como el puño de una bota.
FUNNEL_HEIGHT_MAX, FUNNEL_HEIGHT_FRAC = 15.0, 0.2
FUNNEL_FLARE_MM = 4.0

SPHERE_SEGMENTS, SPHERE_RINGS = 64, 32
# MANIFOLD (Blender 4.5+) es mucho más rápido que EXACT y da mallas cerradas
# si las entradas son cerradas (todas las primitivas de acá lo son).
BOOLEAN_SOLVER = "MANIFOLD"
TUBE_VERTICES = 64


def is_available() -> bool:
    try:
        import bpy  # noqa: F401
        return True
    except Exception:
        return False


def design(params: SocketParameters) -> dict:
    """Medidas del perro (cm) -> dimensiones de la bota (mm). Sin Blender: se puede testear."""
    proximal = params.top_radius_cm * CM_TO_MM
    distal = params.bottom_radius_cm * CM_TO_MM
    lo, hi = FOOT_SCALE_LIMITS
    s = min(max(proximal / BASE_PROXIMAL_RADIUS, lo), hi)
    cavity_bottom = CAVITY_BOTTOM * s
    stump = params.height_cm * CM_TO_MM
    depth = stump + LINER_MM                 # la media también cubre la punta del muñón
    return {
        "foot_scale": round(s, 4),
        "proximal_radius_mm": proximal,
        "distal_radius_mm": distal,
        "wall_thickness_mm": params.wall_thickness_cm * CM_TO_MM,
        "stump_length_mm": stump,
        "cavity_bottom_mm": cavity_bottom,
        "liner_mm": LINER_MM,
        "cavity_depth_mm": depth,
        "funnel_height_mm": min(FUNNEL_HEIGHT_MAX, FUNNEL_HEIGHT_FRAC * stump),
        "funnel_flare_mm": FUNNEL_FLARE_MM,
        "top_mm": cavity_bottom + depth,
        "hind": params.limb_position == "trasera",
        "mirrored": params.limb_side == "izquierda",
    }


def generate(params: SocketParameters, form: ProsthesisForm) -> dict:
    import bpy  # lazy: solo si de verdad vamos a usar Blender

    d = design(params)

    bpy.ops.wm.read_factory_settings(use_empty=True)

    mesh = bpy.data.meshes.new("Prosthesis")
    obj = bpy.data.objects.new("Prosthesis", mesh)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    mod = obj.modifiers.new("GeometryNodes", "NODES")
    ng = bpy.data.node_groups.new("HundaBotaGN", "GeometryNodeTree")

    # IMPORTANTE: construir la interfaz y el grafo ANTES de asignar ng al
    # modifier. Si se asigna primero, Blender crea los inputs del modifier en 0
    # y no los resincroniza con los default_value (exportaba una malla vacía).
    _build_boot(ng, d)
    mod.node_group = ng

    # Espejado para pata izquierda (el diseño es de la derecha)
    if d["mirrored"]:
        obj.scale[0] = -1.0

    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.modifier_apply(modifier="GeometryNodes")

    with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        bpy.ops.wm.stl_export(
            filepath=tmp_path,
            export_selected_objects=True,
            apply_modifiers=True,
        )
        stl_bytes = _largest_body(Path(tmp_path).read_bytes())
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {
        "generated_filename": f"{safe_filename_part(params.dog_name)}-{uuid4()}.stl",
        "generated_stl_bytes": stl_bytes,
        "generation_parameters": {
            **{k: (round(v, 2) if isinstance(v, float) else v) for k, v in d.items()},
            "connector_radius_mm": params.connector_radius_cm * CM_TO_MM,
        },
        "algorithm_version": ALGORITHM_VERSION,
    }


def _largest_body(stl_bytes: bytes) -> bytes:
    """Descarta astillas sueltas que pueden quedar de los booleanos (igual que
    make_base_models.py): nos quedamos con la pieza más grande."""
    from io import BytesIO

    import trimesh

    mesh = trimesh.load_mesh(BytesIO(stl_bytes), file_type="stl")
    try:
        parts = mesh.split(only_watertight=False)
    except ImportError:
        # split necesita networkx o scipy ("no graph engines available"):
        # sin eso devolvemos la malla tal cual, que igual es válida.
        return stl_bytes
    if len(parts) > 1:
        mesh = max(parts, key=lambda m: len(m.faces))
    out = BytesIO()
    mesh.export(file_obj=out, file_type="stl")
    return out.getvalue()


# ── Helpers de nodos ──────────────────────────────────────────────────────────
class _Graph:
    """Envoltorio chico para crear nodos y conectarlos sin repetir código."""

    def __init__(self, ng):
        self.nodes = ng.nodes
        self.links = ng.links
        self.y = 0

    def node(self, node_type: str, **inputs):
        n = self.nodes.new(node_type)
        n.location = (0, self.y)
        self.y -= 220
        for name, value in inputs.items():
            sock = n.inputs[name.replace("_", " ")]
            if hasattr(value, "is_output"):          # un socket: se conecta
                self.links.new(value, sock)
            else:                                     # un valor: se fija
                sock.default_value = value
        return n

    def math(self, op: str, a, b):
        n = self.nodes.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b)):
            if hasattr(v, "is_output"):
                self.links.new(v, n.inputs[i])
            else:
                n.inputs[i].default_value = v
        return n.outputs[0]

    def transform(self, geo, translation=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1)):
        return self.node("GeometryNodeTransform", Geometry=geo, Translation=translation,
                         Rotation=rotation, Scale=scale).outputs["Geometry"]

    def join(self, *geos):
        n = self.nodes.new("GeometryNodeJoinGeometry")
        for g in geos:
            self.links.new(g, n.inputs["Geometry"])
        return n.outputs["Geometry"]

    def boolean(self, op: str, mesh1, *others):
        n = self.nodes.new("GeometryNodeMeshBoolean")
        n.operation = op
        n.solver = BOOLEAN_SOLVER
        if op == "DIFFERENCE":
            self.links.new(mesh1, n.inputs["Mesh 1"])
            targets = others
        else:
            targets = (mesh1, *others)
        for g in targets:
            self.links.new(g, n.inputs["Mesh 2"])
        return n.outputs["Mesh"]

    def ellipsoid(self, center, radii, shrink=0.0):
        sphere = self.node("GeometryNodeMeshUVSphere", Segments=SPHERE_SEGMENTS,
                           Rings=SPHERE_RINGS, Radius=1.0).outputs["Mesh"]
        r = tuple(max(v - shrink, 0.5) for v in radii)
        return self.transform(sphere, translation=center, scale=r)

    def box(self, size, translation=(0, 0, 0), rotation=(0, 0, 0)):
        cube = self.node("GeometryNodeMeshCube", Size=size).outputs["Mesh"]
        return self.transform(cube, translation=translation, rotation=rotation)

    def frustum(self, z0, z1, r_bottom, r_top):
        """Cono truncado entre z0 y z1 (radios pueden ser sockets), sección elíptica."""
        depth = z1 - z0
        cone = self.node("GeometryNodeMeshCone", Vertices=TUBE_VERTICES,
                         Radius_Bottom=r_bottom, Radius_Top=r_top, Depth=depth)
        cone.fill_type = "NGON"
        # En Blender 5.x el primitivo Cone arranca en z=0 (no centrado): lo subimos a z0
        return self.transform(cone.outputs["Mesh"], translation=(0, 0, z0),
                              scale=(1, ELL_Y, 1))


def _scaled(spec, s):
    (c, r) = spec
    return tuple(v * s for v in c), tuple(v * s for v in r)


def _build_boot(ng, d: dict) -> None:
    """Grafo de la bota. Las medidas del muñón son inputs del grupo (se ven y
    se pueden tocar en el panel del modifier en Blender)."""
    g = _Graph(ng)
    g.nodes.clear()
    s = d["foot_scale"]

    # ── Interfaz: medidas del perro ──────────────────────────────────────────
    iface = ng.interface
    iface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    for name, key in (("Proximal Radius", "proximal_radius_mm"),
                      ("Distal Radius", "distal_radius_mm"),
                      ("Wall Thickness", "wall_thickness_mm"),
                      ("Liner Thickness", "liner_mm")):
        sock = iface.new_socket(name, in_out="INPUT", socket_type="NodeSocketFloat")
        sock.default_value = d[key]
    gi = g.nodes.new("NodeGroupInput")
    go = g.nodes.new("NodeGroupOutput")
    wall, liner = gi.outputs["Wall Thickness"], gi.outputs["Liner Thickness"]
    # Radios de la cavidad = muñón + media
    proximal = g.math("ADD", gi.outputs["Proximal Radius"], liner)
    distal = g.math("ADD", gi.outputs["Distal Radius"], liner)

    z_cav, z_top = d["cavity_bottom_mm"], d["top_mm"]
    z_tube = TUBE_BOTTOM * s

    # ── Pie: pie + talón + puntera ────────────────────────────────────────────
    foot_parts = [g.ellipsoid(*_scaled(p, s)) for p in (FOOT, HEEL, TOE_BOX)]

    # ── Tubo del socket (pared = radio del muñón + espesor) ───────────────────
    outer_bottom = g.math("ADD", distal, wall)
    outer_top = g.math("ADD", proximal, wall)
    # Las piezas se superponen (nunca caras en el mismo plano): si no, el
    # booleano deja caras degeneradas y la malla no queda cerrada.
    depth = d["cavity_depth_mm"]
    slope = (d["proximal_radius_mm"] - d["distal_radius_mm"]) / max(depth, 1.0)
    h, flare = d["funnel_height_mm"], d["funnel_flare_mm"]
    z_f = z_top - h                                   # donde arranca el embudo

    def at(radius, z, extra=0.0):
        """Radio del cono (socket de Blender) a la altura z, + extra."""
        return g.math("ADD", radius, slope * (z - z_cav) + extra)

    # Embudo de afuera: un puño que se abre `flare` mm en el borde.
    # Arranca 2 mm más abajo y 0.3 mm más adentro para no compartir caras.
    cuff = g.frustum(z_f - 2.0, z_top, at(outer_bottom, z_f - 2.0, -0.3),
                     g.math("ADD", outer_top, flare))
    tube = g.boolean(
        "UNION",
        g.frustum(z_tube, z_cav + 3.0, outer_bottom, outer_bottom),
        g.frustum(z_cav, z_top - 0.5, outer_bottom, at(outer_bottom, z_top - 0.5)),
        cuff,
    )
    # Cavidad: muñón + media. Sigue 20 mm por arriba del borde para abrir la
    # boca sin caras coplanares; el embudo la ensancha en los últimos h mm.
    extra = 20.0
    # UNION y no join: dos piezas superpuestas en un solo mesh confunden al
    # booleano (la zona en común se cuenta doble y la boca quedaba tapada).
    cavity = g.boolean(
        "UNION",
        g.frustum(z_cav, z_top + extra, distal, at(distal, z_top + extra)),
        g.frustum(z_f - 2.0, z_top + extra, at(distal, z_f - 2.0, -0.3),
                  at(distal, z_top + extra, flare * (h + extra) / h)),
    )
    vents = _vents(g, d)

    if d["hind"]:
        tilt = math.radians(HIND_TILT_DEG)
        pivot = HIND_PIVOT_Z * s
        tube, cavity, vents = (
            g.transform(g.transform(x, translation=(0, 0, -pivot)),
                        rotation=(tilt, 0, 0), translation=(0, 0, pivot))
            for x in (tube, cavity, vents)
        )

    body = g.boolean("UNION", *foot_parts, tube)

    # ── Surcos de dedos: solo la cáscara (pie achicado 1.5 mm no se toca) ─────
    shrunk = g.boolean("UNION", *(g.ellipsoid(*_scaled(p, s), shrink=TOE_GROOVE_DEPTH)
                                  for p in (FOOT, HEEL, TOE_BOX)))
    grooves = g.join(*(
        g.box((2.6 * s, 50.0 * s, 60.0 * s),
              translation=(58.0 * s * math.sin(th), 4.0 * s + 58.0 * s * math.cos(th), 42.0 * s),
              rotation=(0, 0, -th))
        for th in TOE_GROOVE_ANGLES
    ))
    groove_cutter = g.boolean("DIFFERENCE", grooves, shrunk)

    # ── Dibujo de suela: ranuras transversales, lejos del borde ──────────────
    inner5 = g.boolean("UNION", *(g.ellipsoid(*_scaled(p, s), shrink=5.0 * s)
                                  for p in (FOOT, HEEL, TOE_BOX)))
    y_min, y_max = -36.0 * s, 87.0 * s
    k0 = math.ceil((y_min / s - 2.5) / TREAD_PITCH)
    k1 = math.floor((y_max / s - 2.5) / TREAD_PITCH)
    treads = g.join(*(
        g.box((90.0 * s, TREAD_WIDTH * s, 2 * TREAD_DEPTH * s),
              translation=(0, (2.5 + TREAD_PITCH * k) * s, 0))
        for k in range(k0, k1 + 1)
    ))
    tread_cutter = g.boolean("INTERSECT", treads, inner5)

    # ── Suela plana en z=0 ───────────────────────────────────────────────────
    below = g.box((400.0, 400.0, 100.0), translation=(0, 0, -50.0))

    boot = g.boolean("DIFFERENCE", body, below, cavity, groove_cutter, tread_cutter, vents)
    g.links.new(boot, go.inputs["Geometry"])


def _vents(g: _Graph, d: dict):
    """Ventanas de a pares en la pared del socket, ubicadas relativas a la cavidad."""
    z_cav, stump = d["cavity_bottom_mm"], d["stump_length_mm"]
    r_mid = ((d["distal_radius_mm"] + d["proximal_radius_mm"]) / 2 + d["liner_mm"]
             + d["wall_thickness_mm"] / 2)
    top_margin = d["funnel_height_mm"] + 4.0        # las ventanas no tocan el embudo
    depth = d["wall_thickness_mm"] * 4 + 4.0      # atraviesa la pared, no llega al otro lado
    cutters = []
    # Tramo útil de la pared: 6 mm sobre el fondo y por debajo del embudo.
    # Las ventanas se reparten proporcionalmente ahí, así nunca se pisan entre sí.
    lo, hi = z_cav + 6.0, z_cav + stump - top_margin
    usable = hi - lo
    if usable < 20.0:
        return _nothing(g)                          # muñón muy corto: sin ventanas
    for angle_deg, frac, rel_len in VENTS:
        length = rel_len * usable
        zc = lo + frac * usable
        if length < 6.0:
            continue
        a = math.radians(angle_deg)
        for off in (-VENT_PAIR_OFFSET, VENT_PAIR_OFFSET):
            x = r_mid * math.cos(a) - off * math.sin(a)
            y = ELL_Y * r_mid * math.sin(a) + off * math.cos(a)
            cutters.append(g.box((depth, VENT_WIDTH, length), translation=(x, y, zc),
                                 rotation=(0, 0, a)))
    return g.join(*cutters) if cutters else _nothing(g)


def _nothing(g: _Graph):
    """Un cubito lejísimo: 'nada que cortar' sin romper el booleano."""
    return g.box((0.01, 0.01, 0.01), translation=(0, 0, -1000))
