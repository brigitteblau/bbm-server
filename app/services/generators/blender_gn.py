"""Generador paramétrico con Blender Geometry Nodes.

Genera el socket desde cero (cono hueco con espesor real).
IMPORTANTE: bpy se importa adentro de la función, así el server
levanta aunque bpy no esté instalado.
"""

import math
import tempfile
from pathlib import Path
from uuid import uuid4

from app.models import ProsthesisForm, SocketParameters
from app.utils import safe_filename_part

CM_TO_MM = 10.0
DEFAULT_RESOLUTION = 64
ALGORITHM_VERSION = "blender-gn-v1"


def is_available() -> bool:
    try:
        import bpy  # noqa: F401
        return True
    except Exception:
        return False


def generate(params: SocketParameters, form: ProsthesisForm) -> dict:
    import bpy  # lazy: solo si de verdad vamos a usar Blender

    # Única conversión de unidades: SocketParameters viene en cm, acá pasamos a mm
    gn_params = {
        "Stump Length":    params.height_cm * CM_TO_MM,
        "Proximal Radius": params.top_radius_cm * CM_TO_MM,
        "Distal Radius":   params.bottom_radius_cm * CM_TO_MM,
        "Wall Thickness":  params.wall_thickness_cm * CM_TO_MM,
        "Resolution":      DEFAULT_RESOLUTION,
    }

    bpy.ops.wm.read_factory_settings(use_empty=True)

    mesh = bpy.data.meshes.new("Prosthesis")
    obj = bpy.data.objects.new("Prosthesis", mesh)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    mod = obj.modifiers.new("GeometryNodes", "NODES")
    ng = bpy.data.node_groups.new("ProsthesisSocketGN", "GeometryNodeTree")

    # IMPORTANTE: construir la interfaz y el grafo de nodos ANTES de asignar
    # ng al modifier. Si se asigna primero (como estaba antes), Blender crea
    # los inputs del modifier (Socket_1, Socket_2, ...) en 0 y no los
    # resincroniza con los default_value de la interfaz creados después,
    # por lo que el socket quedaba con Stump Length/Radios/Resolution = 0
    # y exportaba una malla vacía (STL de 84 bytes, 0 triángulos).
    _build_gn(ng, gn_params)
    mod.node_group = ng

    # Espejado para pata izquierda (los defaults se modelan como derecha)
    if params.limb_side == "izquierda":
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
        stl_bytes = Path(tmp_path).read_bytes()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {
        "generated_filename": f"{safe_filename_part(params.dog_name)}-{uuid4()}.stl",
        "generated_stl_bytes": stl_bytes,
        "generation_parameters": {
            "stump_length_mm":    gn_params["Stump Length"],
            "proximal_radius_mm": gn_params["Proximal Radius"],
            "distal_radius_mm":   gn_params["Distal Radius"],
            "wall_thickness_mm":  gn_params["Wall Thickness"],
            "connector_radius_mm": params.connector_radius_cm * CM_TO_MM,
            "resolution":         gn_params["Resolution"],
            "mirrored":           params.limb_side == "izquierda",
        },
        "algorithm_version": ALGORITHM_VERSION,
    }


def _n(nodes, node_type: str, x: int = 0, y: int = 0):
    n = nodes.new(node_type)
    n.location = (x, y)
    return n


def _math(nodes, links, operation: str, a, b, x: int = 0, y: int = 0):
    n = _n(nodes, "ShaderNodeMath", x=x, y=y)
    n.operation = operation
    links.new(a, n.inputs[0])
    links.new(b, n.inputs[1])
    return n.outputs[0]


def _translate_z(nodes, links, geometry, z, x: int = 0, y: int = 0):
    shift = _n(nodes, "ShaderNodeCombineXYZ", x=x, y=y - 200)
    links.new(z, shift.inputs["Z"])

    move = _n(nodes, "GeometryNodeTransform", x=x, y=y)
    links.new(geometry, move.inputs["Geometry"])
    links.new(shift.outputs["Vector"], move.inputs["Translation"])
    return move.outputs["Geometry"]


def _cone(nodes, links, gi, radius_bottom, radius_top, x: int = 0, y: int = 0):
    """Cono con tapas, de alto Stump Length."""
    cone = _n(nodes, "GeometryNodeMeshCone", x=x, y=y)
    cone.fill_type = "NGON"
    links.new(gi.outputs["Resolution"],   cone.inputs["Vertices"])
    links.new(gi.outputs["Stump Length"], cone.inputs["Depth"])
    links.new(radius_bottom,              cone.inputs["Radius Bottom"])
    links.new(radius_top,                 cone.inputs["Radius Top"])
    return cone.outputs["Mesh"]


def _build_gn(ng, params: dict) -> None:
    """
    Construye el node graph dentro de ng.

    Geometría: vaso cónico (socket de prótesis) = cono exterior − cono interior.
      - Exterior: de Distal Radius (z=0) a Proximal Radius (z=Stump Length)
      - Interior: el mismo cono corrido Wall Thickness hacia adentro y hacia
        arriba, así el fondo queda con el mismo espesor que la pared
      - Top abierto: el interior sobresale por arriba y el boolean abre la boca
    El boolean exacto deja una malla cerrada (watertight), lista para imprimir.
    """
    nodes = ng.nodes
    links = ng.links
    nodes.clear()

    # ── Sockets de entrada/salida ────────────────────────────────────────────
    iface = ng.interface
    iface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    s = iface.new_socket("Stump Length",    in_out="INPUT", socket_type="NodeSocketFloat")
    s.default_value = params["Stump Length"]
    s = iface.new_socket("Proximal Radius", in_out="INPUT", socket_type="NodeSocketFloat")
    s.default_value = params["Proximal Radius"]
    s = iface.new_socket("Distal Radius",   in_out="INPUT", socket_type="NodeSocketFloat")
    s.default_value = params["Distal Radius"]
    s = iface.new_socket("Wall Thickness",  in_out="INPUT", socket_type="NodeSocketFloat")
    s.default_value = params["Wall Thickness"]
    s = iface.new_socket("Resolution",      in_out="INPUT", socket_type="NodeSocketInt")
    s.default_value = params["Resolution"]

    gi = _n(nodes, "NodeGroupInput",  x=-900, y=0)
    go = _n(nodes, "NodeGroupOutput", x=1150, y=0)

    length = gi.outputs["Stump Length"]
    proximal = gi.outputs["Proximal Radius"]
    distal = gi.outputs["Distal Radius"]
    wall = gi.outputs["Wall Thickness"]

    # ── Cono exterior ─────────────────────────────────────────────────────────
    outer = _cone(nodes, links, gi, distal, proximal, x=-200, y=300)

    # ── Cono interior ─────────────────────────────────────────────────────────
    # Al subirlo Wall Thickness, el radio tiene que crecer lo que crece el cono
    # en esa altura (k = pendiente * Wall Thickness) para que la pared quede pareja.
    r_range = _math(nodes, links, "SUBTRACT", proximal, distal, x=-700, y=-300)
    slope = _math(nodes, links, "DIVIDE", r_range, length, x=-550, y=-300)
    k = _math(nodes, links, "MULTIPLY", slope, wall, x=-400, y=-300)
    k_minus_wall = _math(nodes, links, "SUBTRACT", k, wall, x=-250, y=-300)
    inner_bottom = _math(nodes, links, "ADD", distal, k_minus_wall, x=-100, y=-200)
    inner_top = _math(nodes, links, "ADD", proximal, k_minus_wall, x=-100, y=-400)
    inner = _cone(nodes, links, gi, inner_bottom, inner_top, x=100, y=-300)
    inner = _translate_z(nodes, links, inner, wall, x=300, y=-300)

    # ── Exterior − interior ───────────────────────────────────────────────────
    boolean = _n(nodes, "GeometryNodeMeshBoolean", x=500, y=0)
    boolean.operation = "DIFFERENCE"
    boolean.solver = "EXACT"
    links.new(outer, boolean.inputs["Mesh 1"])
    links.new(inner, boolean.inputs["Mesh 2"])

    # ── Apoyar la base en z=0 ─────────────────────────────────────────────────
    # Según la versión de Blender el primitivo Cone viene centrado o apoyado en
    # z=0: alineamos por el bounding box para no depender de eso.
    bbox = _n(nodes, "GeometryNodeBoundBox", x=500, y=-300)
    links.new(boolean.outputs["Mesh"], bbox.inputs["Geometry"])

    min_xyz = _n(nodes, "ShaderNodeSeparateXYZ", x=650, y=-300)
    links.new(bbox.outputs["Min"], min_xyz.inputs[0])

    neg_min_z = _n(nodes, "ShaderNodeMath", x=800, y=-300)
    neg_min_z.operation = "MULTIPLY"
    neg_min_z.inputs[1].default_value = -1.0
    links.new(min_xyz.outputs["Z"], neg_min_z.inputs[0])

    grounded = _translate_z(
        nodes, links, boolean.outputs["Mesh"], neg_min_z.outputs[0], x=950, y=0
    )
    links.new(grounded, go.inputs["Geometry"])
