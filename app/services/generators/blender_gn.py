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
    mod.node_group = ng

    _build_gn(ng, gn_params)

    # Espejado para pata izquierda (los defaults se modelan como derecha)
    if params.limb_side == "left":
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
            "mirrored":           params.limb_side == "left",
        },
        "algorithm_version": ALGORITHM_VERSION,
    }
def _set_mode(node, mode: str) -> None:
    # En Blender 4.x algunos nodos eliminaron .mode como propiedad;
    # en esos casos el valor default ya es el que necesitamos.
    try:
        node.mode = mode
    except AttributeError:
        pass


def _n(nodes, node_type: str, x: int = 0, y: int = 0):
    n = nodes.new(node_type)
    n.location = (x, y)
    return n


def _build_gn(ng, params: dict) -> None:
    """
    Construye el node graph dentro de ng.

    Geometría: cilindro cónico hueco (socket de prótesis).
      - Shell exterior: de Distal Radius (z=0) a Proximal Radius (z=Stump Length)
      - Shell interior: mismo cono desplazado -Wall Thickness (normales invertidas)
      - Cap inferior: anillo cerrado en z=0
      - Top abierto: encaja el muñón
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
    go = _n(nodes, "NodeGroupOutput", x=1500, y=0)

    # ── Spine: línea de (0,0,0) a (0,0,Stump Length) ────────────────────────
    end_xyz = _n(nodes, "ShaderNodeCombineXYZ", x=-700, y=0)
    links.new(gi.outputs["Stump Length"], end_xyz.inputs["Z"])

    spine = _n(nodes, "GeometryNodeCurvePrimitiveLine", x=-500, y=0)
    _set_mode(spine, "POINTS")
    links.new(end_xyz.outputs["Vector"], spine.inputs["End"])

    resample = _n(nodes, "GeometryNodeResampleCurve", x=-300, y=0)
    _set_mode(resample, "COUNT")
    resample.inputs["Count"].default_value = 128
    links.new(spine.outputs["Curve"], resample.inputs["Curve"])

    # ── Factor 0→1 a lo largo de la spine (0=distal, 1=proximal) ────────────
    spline_param = _n(nodes, "GeometryNodeSplineParameter", x=-300, y=-300)

    # outer_r(t) = Distal + (Proximal - Distal) * t
    r_range = _n(nodes, "ShaderNodeMath", x=-100, y=-300)
    r_range.operation = "SUBTRACT"
    links.new(gi.outputs["Proximal Radius"], r_range.inputs[0])
    links.new(gi.outputs["Distal Radius"],   r_range.inputs[1])

    r_scaled = _n(nodes, "ShaderNodeMath", x=100, y=-300)
    r_scaled.operation = "MULTIPLY"
    links.new(r_range.outputs[0],             r_scaled.inputs[0])
    links.new(spline_param.outputs["Factor"], r_scaled.inputs[1])

    outer_r = _n(nodes, "ShaderNodeMath", x=300, y=-300)
    outer_r.operation = "ADD"
    links.new(gi.outputs["Distal Radius"], outer_r.inputs[0])
    links.new(r_scaled.outputs[0],         outer_r.inputs[1])

    # inner_r(t) = outer_r(t) - Wall Thickness
    inner_r = _n(nodes, "ShaderNodeMath", x=300, y=-500)
    inner_r.operation = "SUBTRACT"
    links.new(outer_r.outputs[0],           inner_r.inputs[0])
    links.new(gi.outputs["Wall Thickness"], inner_r.inputs[1])

    # ── Perfil: círculo unitario (escalado por el radio de la curva) ─────────
    unit_circle = _n(nodes, "GeometryNodeCurvePrimitiveCircle", x=-100, y=-600)
    _set_mode(unit_circle, "RADIUS")
    unit_circle.inputs["Radius"].default_value = 1.0
    links.new(gi.outputs["Resolution"], unit_circle.inputs["Resolution"])

    # ── Shell exterior ────────────────────────────────────────────────────────
    set_r_out = _n(nodes, "GeometryNodeSetCurveRadius", x=550, y=200)
    links.new(resample.outputs["Curve"], set_r_out.inputs["Curve"])
    links.new(outer_r.outputs[0],        set_r_out.inputs["Radius"])

    ctm_out = _n(nodes, "GeometryNodeCurveToMesh", x=750, y=200)
    ctm_out.inputs["Fill Caps"].default_value = False
    links.new(set_r_out.outputs["Curve"],   ctm_out.inputs["Curve"])
    links.new(unit_circle.outputs["Curve"], ctm_out.inputs["Profile Curve"])

    # ── Shell interior (normales invertidas) ──────────────────────────────────
    set_r_in = _n(nodes, "GeometryNodeSetCurveRadius", x=550, y=-100)
    links.new(resample.outputs["Curve"], set_r_in.inputs["Curve"])
    links.new(inner_r.outputs[0],        set_r_in.inputs["Radius"])

    ctm_in = _n(nodes, "GeometryNodeCurveToMesh", x=750, y=-100)
    ctm_in.inputs["Fill Caps"].default_value = False
    links.new(set_r_in.outputs["Curve"],    ctm_in.inputs["Curve"])
    links.new(unit_circle.outputs["Curve"], ctm_in.inputs["Profile Curve"])

    flip_in = _n(nodes, "GeometryNodeFlipFaces", x=950, y=-100)
    links.new(ctm_in.outputs[0], flip_in.inputs["Mesh"])

    # ── Cap inferior: disco exterior ──────────────────────────────────────────
    cap_out_curve = _n(nodes, "GeometryNodeCurvePrimitiveCircle", x=100, y=-800)
    _set_mode(cap_out_curve, "RADIUS")
    links.new(gi.outputs["Distal Radius"], cap_out_curve.inputs["Radius"])
    links.new(gi.outputs["Resolution"],    cap_out_curve.inputs["Resolution"])

    cap_out_fill = _n(nodes, "GeometryNodeFillCurve", x=300, y=-800)
    links.new(cap_out_curve.outputs["Curve"], cap_out_fill.inputs["Curve"])

    # ── Cap inferior: disco interior flipped (crea el hueco del cap) ─────────
    inner_distal = _n(nodes, "ShaderNodeMath", x=100, y=-1000)
    inner_distal.operation = "SUBTRACT"
    links.new(gi.outputs["Distal Radius"],  inner_distal.inputs[0])
    links.new(gi.outputs["Wall Thickness"], inner_distal.inputs[1])

    cap_in_curve = _n(nodes, "GeometryNodeCurvePrimitiveCircle", x=300, y=-1000)
    _set_mode(cap_in_curve, "RADIUS")
    links.new(inner_distal.outputs[0],  cap_in_curve.inputs["Radius"])
    links.new(gi.outputs["Resolution"], cap_in_curve.inputs["Resolution"])

    cap_in_fill = _n(nodes, "GeometryNodeFillCurve", x=500, y=-1000)
    links.new(cap_in_curve.outputs["Curve"], cap_in_fill.inputs["Curve"])

    flip_cap = _n(nodes, "GeometryNodeFlipFaces", x=700, y=-1000)
    links.new(cap_in_fill.outputs[0], flip_cap.inputs["Mesh"])

    # ── Join + merge ──────────────────────────────────────────────────────────
    join = _n(nodes, "GeometryNodeJoinGeometry", x=1150, y=0)
    links.new(ctm_out.outputs[0],      join.inputs["Geometry"])
    links.new(flip_in.outputs[0],      join.inputs["Geometry"])
    links.new(cap_out_fill.outputs[0], join.inputs["Geometry"])
    links.new(flip_cap.outputs[0],     join.inputs["Geometry"])

    merge = _n(nodes, "GeometryNodeMergeByDistance", x=1300, y=0)
    merge.inputs["Distance"].default_value = 0.01
    links.new(join.outputs["Geometry"], merge.inputs["Geometry"])

    links.new(merge.outputs["Geometry"], go.inputs["Geometry"])
    