"""
Creates front-leg-default.blend: escena Blender con Geometry Nodes que
genera un socket de prótesis canina (cilindro cónico hueco) a partir de
parámetros. El .blend resultante se sube al bucket base-models en Supabase.

Uso:
    python scripts/create_base_blend.py          # requiere: pip install bpy
    blender --background --python scripts/create_base_blend.py
"""
from pathlib import Path

import bpy

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "front-leg-default.blend"

# Valores default: perro mediano, pata delantera
DEFAULT_STUMP_LENGTH_MM = 120.0       # 12cm de largo
DEFAULT_PROXIMAL_RADIUS_MM = 30.0    # ~18.8cm de circunferencia
DEFAULT_DISTAL_RADIUS_MM = 20.0      # ~12.6cm de circunferencia
DEFAULT_WALL_THICKNESS_MM = 3.0      # grosor de pared
DEFAULT_RESOLUTION = 64              # segmentos del círculo


def _node(nodes, node_type, x=0, y=0):
    n = nodes.new(node_type)
    n.location = (x, y)
    return n


def _set_mode(node, mode):
    # En Blender 4.x algunos nodos eliminaron .mode como propiedad;
    # en esos casos el valor default es el que necesitamos igual.
    try:
        node.mode = mode
    except AttributeError:
        pass


def _build_gn(ng):
    """
    Construye el node graph dentro del node group ng.

    Estructura:
      - Spine: línea de Z=0 a Z=Stump Length, remuestreada en 128 puntos
      - Factor: SplineParameter.Factor (0=distal, 1=proximal)
      - outer_r(t) = Distal + (Proximal - Distal) * t
      - inner_r(t) = outer_r(t) - Wall Thickness
      - CurveToMesh outer + inner (flip normas) + caps cerrados abajo
      - JoinGeometry + MergeByDistance para cerrar costuras
    """
    nodes = ng.nodes
    links = ng.links
    nodes.clear()

    # ── Interface ────────────────────────────────────────────────────────────
    iface = ng.interface

    iface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    s_stump = iface.new_socket("Stump Length", in_out="INPUT", socket_type="NodeSocketFloat")
    s_stump.default_value = DEFAULT_STUMP_LENGTH_MM

    s_prox = iface.new_socket("Proximal Radius", in_out="INPUT", socket_type="NodeSocketFloat")
    s_prox.default_value = DEFAULT_PROXIMAL_RADIUS_MM

    s_dist = iface.new_socket("Distal Radius", in_out="INPUT", socket_type="NodeSocketFloat")
    s_dist.default_value = DEFAULT_DISTAL_RADIUS_MM

    s_wall = iface.new_socket("Wall Thickness", in_out="INPUT", socket_type="NodeSocketFloat")
    s_wall.default_value = DEFAULT_WALL_THICKNESS_MM

    s_res = iface.new_socket("Resolution", in_out="INPUT", socket_type="NodeSocketInt")
    s_res.default_value = DEFAULT_RESOLUTION

    # ── Nodos Group I/O ───────────────────────────────────────────────────────
    gi = _node(nodes, "NodeGroupInput", x=-900, y=0)
    go = _node(nodes, "NodeGroupOutput", x=1500, y=0)

    # ── Punto final de la spine: (0, 0, Stump Length) ─────────────────────────
    combine_end = _node(nodes, "ShaderNodeCombineXYZ", x=-700, y=0)
    links.new(gi.outputs["Stump Length"], combine_end.inputs["Z"])

    # ── Spine: línea desde (0,0,0) hasta (0,0,stump_length) ──────────────────
    spine = _node(nodes, "GeometryNodeCurvePrimitiveLine", x=-500, y=0)
    _set_mode(spine, "POINTS")
    links.new(combine_end.outputs["Vector"], spine.inputs["End"])

    # ── Remuestrear spine (128 puntos) ────────────────────────────────────────
    resample = _node(nodes, "GeometryNodeResampleCurve", x=-300, y=0)
    _set_mode(resample, "COUNT")
    resample.inputs["Count"].default_value = 128
    links.new(spine.outputs["Curve"], resample.inputs["Curve"])

    # ── Factor a lo largo de la spine (0=distal, 1=proximal) ─────────────────
    spline_param = _node(nodes, "GeometryNodeSplineParameter", x=-300, y=-300)

    # ── outer_r = Distal + (Proximal - Distal) * Factor ──────────────────────
    radius_range = _node(nodes, "ShaderNodeMath", x=-100, y=-300)
    radius_range.operation = "SUBTRACT"
    links.new(gi.outputs["Proximal Radius"], radius_range.inputs[0])
    links.new(gi.outputs["Distal Radius"], radius_range.inputs[1])

    t_scaled = _node(nodes, "ShaderNodeMath", x=100, y=-300)
    t_scaled.operation = "MULTIPLY"
    links.new(radius_range.outputs[0], t_scaled.inputs[0])
    links.new(spline_param.outputs["Factor"], t_scaled.inputs[1])

    outer_r = _node(nodes, "ShaderNodeMath", x=300, y=-300)
    outer_r.operation = "ADD"
    links.new(gi.outputs["Distal Radius"], outer_r.inputs[0])
    links.new(t_scaled.outputs[0], outer_r.inputs[1])

    # ── inner_r = outer_r - Wall Thickness ────────────────────────────────────
    inner_r = _node(nodes, "ShaderNodeMath", x=300, y=-500)
    inner_r.operation = "SUBTRACT"
    links.new(outer_r.outputs[0], inner_r.inputs[0])
    links.new(gi.outputs["Wall Thickness"], inner_r.inputs[1])

    # ── Perfil circular unitario (escalado por el radio de la curva) ──────────
    unit_circle = _node(nodes, "GeometryNodeCurvePrimitiveCircle", x=-100, y=-600)
    _set_mode(unit_circle, "RADIUS")
    unit_circle.inputs["Radius"].default_value = 1.0
    links.new(gi.outputs["Resolution"], unit_circle.inputs["Resolution"])

    # ── SHELL EXTERIOR ────────────────────────────────────────────────────────
    set_r_outer = _node(nodes, "GeometryNodeSetCurveRadius", x=550, y=200)
    links.new(resample.outputs["Curve"], set_r_outer.inputs["Curve"])
    links.new(outer_r.outputs[0], set_r_outer.inputs["Radius"])

    ctm_outer = _node(nodes, "GeometryNodeCurveToMesh", x=750, y=200)
    ctm_outer.inputs["Fill Caps"].default_value = False
    links.new(set_r_outer.outputs["Curve"], ctm_outer.inputs["Curve"])
    links.new(unit_circle.outputs["Curve"], ctm_outer.inputs["Profile Curve"])

    # ── SHELL INTERIOR (normales invertidas) ──────────────────────────────────
    set_r_inner = _node(nodes, "GeometryNodeSetCurveRadius", x=550, y=-100)
    links.new(resample.outputs["Curve"], set_r_inner.inputs["Curve"])
    links.new(inner_r.outputs[0], set_r_inner.inputs["Radius"])

    ctm_inner = _node(nodes, "GeometryNodeCurveToMesh", x=750, y=-100)
    ctm_inner.inputs["Fill Caps"].default_value = False
    links.new(set_r_inner.outputs["Curve"], ctm_inner.inputs["Curve"])
    links.new(unit_circle.outputs["Curve"], ctm_inner.inputs["Profile Curve"])

    flip_inner = _node(nodes, "GeometryNodeFlipFaces", x=950, y=-100)
    links.new(ctm_inner.outputs[0], flip_inner.inputs["Mesh"])

    # ── CAP INFERIOR EXTERIOR (disco lleno al radio distal) ───────────────────
    outer_cap_curve = _node(nodes, "GeometryNodeCurvePrimitiveCircle", x=100, y=-800)
    _set_mode(outer_cap_curve, "RADIUS")
    links.new(gi.outputs["Distal Radius"], outer_cap_curve.inputs["Radius"])
    links.new(gi.outputs["Resolution"], outer_cap_curve.inputs["Resolution"])

    outer_cap_fill = _node(nodes, "GeometryNodeFillCurve", x=300, y=-800)
    links.new(outer_cap_curve.outputs["Curve"], outer_cap_fill.inputs["Curve"])

    # ── CAP INFERIOR INTERIOR (disco flipped para crear el agujero del cap) ───
    inner_distal_r = _node(nodes, "ShaderNodeMath", x=100, y=-1000)
    inner_distal_r.operation = "SUBTRACT"
    links.new(gi.outputs["Distal Radius"], inner_distal_r.inputs[0])
    links.new(gi.outputs["Wall Thickness"], inner_distal_r.inputs[1])

    inner_cap_curve = _node(nodes, "GeometryNodeCurvePrimitiveCircle", x=300, y=-1000)
    _set_mode(inner_cap_curve, "RADIUS")
    links.new(inner_distal_r.outputs[0], inner_cap_curve.inputs["Radius"])
    links.new(gi.outputs["Resolution"], inner_cap_curve.inputs["Resolution"])

    inner_cap_fill = _node(nodes, "GeometryNodeFillCurve", x=500, y=-1000)
    links.new(inner_cap_curve.outputs["Curve"], inner_cap_fill.inputs["Curve"])

    flip_inner_cap = _node(nodes, "GeometryNodeFlipFaces", x=700, y=-1000)
    links.new(inner_cap_fill.outputs[0], flip_inner_cap.inputs["Mesh"])

    # ── JOIN ALL + MERGE ──────────────────────────────────────────────────────
    join = _node(nodes, "GeometryNodeJoinGeometry", x=1150, y=0)
    links.new(ctm_outer.outputs[0], join.inputs["Geometry"])
    links.new(flip_inner.outputs[0], join.inputs["Geometry"])
    links.new(outer_cap_fill.outputs[0], join.inputs["Geometry"])
    links.new(flip_inner_cap.outputs[0], join.inputs["Geometry"])

    merge = _node(nodes, "GeometryNodeMergeByDistance", x=1300, y=0)
    merge.inputs["Distance"].default_value = 0.01
    links.new(join.outputs["Geometry"], merge.inputs["Geometry"])

    links.new(merge.outputs["Geometry"], go.inputs["Geometry"])


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)

    mesh = bpy.data.meshes.new("Prosthesis")
    obj = bpy.data.objects.new("Prosthesis", mesh)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj

    mod = obj.modifiers.new("GeometryNodes", "NODES")
    ng = bpy.data.node_groups.new("ProsthesisSocketGN", "GeometryNodeTree")
    mod.node_group = ng

    _build_gn(ng)

    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_FILE))
    print(f"Guardado: {OUTPUT_FILE}")
    print("Próximo paso: subir ese archivo a Supabase bucket 'base-models' como 'front-leg-default.blend'")


if __name__ == "__main__":
    main()
