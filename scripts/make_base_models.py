"""Genera los STL base de Hunda (prótesis tipo bota) con SDF + marching cubes.

Unidades: mm. Perro mirando a +Y, Z arriba, pata DERECHA (lateral = +X).
Uso: python scripts/make_base_models.py <delantera|trasera> <out.stl>
Deps extra (no van en requirements): scikit-image, fast-simplification.
"""

import sys

import fast_simplification
import numpy as np
import trimesh
from skimage.measure import marching_cubes

VOX = 0.5

# ── Socket ──────────────────────────────────────────────────────────────────
TOP = 178.0
CAV_BOT = 60.0
R_IN_BOT, R_IN_TOP = 21.0, 28.5
ELL_Y = 0.9          # sección elíptica (aplastada adelante-atrás)
WALL = 3.2


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def ellipsoid(x, y, z, c, r):
    # aproximación de distancia a elipsoide (Inigo Quilez)
    px, py, pz = (x - c[0]) / r[0], (y - c[1]) / r[1], (z - c[2]) / r[2]
    k0 = np.sqrt(px * px + py * py + pz * pz)
    k1 = np.sqrt((px / r[0]) ** 2 + (py / r[1]) ** 2 + (pz / r[2]) ** 2)
    return k0 * (k0 - 1.0) / np.maximum(k1, 1e-6)


def r_in(z):
    t = np.clip((z - CAV_BOT) / (TOP - CAV_BOT), 0.0, 1.2)
    # leve curva: más ancho arriba, que abraza el muñón
    return R_IN_BOT + (R_IN_TOP - R_IN_BOT) * (t ** 0.85)


def sdf(x, y, z, hind: bool):
    # Coordenadas del socket: en la trasera el tubo se inclina hacia atrás
    if hind:
        a = np.radians(-11.0)
        pz0 = 45.0
        ys = y * np.cos(a) - (z - pz0) * np.sin(a)
        zs = y * np.sin(a) + (z - pz0) * np.cos(a) + pz0
    else:
        ys, zs = y, z
    xs = x

    rho_e = np.sqrt(xs ** 2 + (ys / ELL_Y) ** 2)

    # línea de partición entre pieza base y valva superior (más alta adelante)
    split = zs - (86.0 + 0.22 * ys)
    below = 1.0 - sstep(-1.3, 1.3, split)
    lip = sstep(TOP - 7.5, TOP - 5.5, zs)
    r_out = r_in(zs) + WALL + 1.1 * below + 0.9 * lip
    tube = (rho_e - r_out) * 0.97

    # ── Pie ────────────────────────────────────────────────────────────────
    widen = 1.0 + 0.0045 * np.clip(y - 20.0, -30, 70)   # pata más ancha en los dedos
    foot = ellipsoid(x / widen, y, z, (1.5, 30.0, 24.0), (29.0, 57.0, 27.0))
    heel = ellipsoid(x, y, z, (0.0, -8.0, 33.0), (27.5, 28.0, 33.0))
    toe_box = ellipsoid(x / widen, y, z, (1.5, 56.0, 15.0), (31.0, 30.0, 19.0))

    d = smin(foot, heel, 10.0)
    d = smin(d, toe_box, 8.0)
    d = smin(d, tube, 17.0)

    # surcos de dedos que nacen en el empeine
    ang = np.arctan2(x, y - 4.0)
    rh = np.sqrt(x ** 2 + (y - 4.0) ** 2)
    g = np.zeros_like(x)
    for th in (-0.30, -0.02, 0.27):
        s = rh * (ang - th)
        g += np.exp(-(s / 2.3) ** 2)
    fade = sstep(31.0, 44.0, rh) * sstep(12.0, 24.0, z) * (1.0 - sstep(80.0, 92.0, y))
    d = d + 1.5 * g * fade

    # suela con balancín en la punta
    lift = 0.006 * np.maximum(y - 62.0, 0.0) ** 2
    sole = -(z - lift)
    d_body = d
    d_outer = smax(d, sole, 5.0)

    # ranura de la partición
    groove = np.maximum(np.abs(split + 1.6) - 0.7, -(d_outer + 0.8))
    d = np.maximum(d_outer, -groove)

    # dibujo de suela
    tread_y = np.abs(np.mod(y + 2.0, 9.0) - 4.5)
    tread = np.maximum.reduce([
        z - lift - 1.3,
        tread_y - 1.5,
        d_body + 5.0,
    ])
    d = np.maximum(d, -tread)

    # ── Cavidad del muñón ─────────────────────────────────────────────────
    cav = (rho_e - r_in(zs)) * 0.97
    cav = smax(cav, CAV_BOT - zs, 11.0)
    d = smax(d, -cav, 1.2)

    # borde superior redondeado
    d = smax(d, zs - TOP, 1.6)

    # ── Ventanas de ventilación (pares con travesaño) ─────────────────────
    alpha = np.arctan2(ys / ELL_Y, xs)
    r_mid = r_in(zs) + WALL * 0.5
    slots = [
        # (ángulo centro, z centro, largo)  0 = lateral (+X)
        (np.radians(-28), 150.0, 32.0),
        (np.radians(-28), 112.0, 26.0),
        (np.radians(180 + 28), 132.0, 30.0),   # medial
    ]
    for ac, zc, length in slots:
        da = np.angle(np.exp(1j * (alpha - ac)))
        s = r_mid * da
        facing = -np.cos(da) * 60.0
        for off in (-5.6, 5.6):
            w = 6.2
            ss = s - off
            dz = np.maximum(np.abs(zs - zc) - (length - w) / 2.0, 0.0)
            d2 = np.sqrt(ss ** 2 + dz ** 2) - w / 2.0
            d = smax(d, -np.maximum(d2, facing), 0.9)

    return d


def build(position: str) -> trimesh.Trimesh:
    hind = position == "trasera"
    xs = np.arange(-48.13, 48, VOX, dtype=np.float32)
    ys = np.arange(-58.17, 100, VOX, dtype=np.float32)
    zs = np.arange(-3.21, 184, VOX, dtype=np.float32)
    vol = np.empty((len(xs), len(ys), len(zs)), dtype=np.float32)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    for k, zv in enumerate(zs):
        Z = np.full_like(X, zv)
        vol[:, :, k] = sdf(X, Y, Z, hind)

    verts, faces, _, _ = marching_cubes(vol, level=0.0, spacing=(VOX, VOX, VOX))
    verts += np.array([xs[0], ys[0], zs[0]], dtype=np.float32)
    mesh = trimesh.Trimesh(verts, faces[:, ::-1], process=True)
    print("marching cubes:", len(mesh.faces), "caras, watertight", mesh.is_watertight)

    v, f = fast_simplification.simplify(
        mesh.vertices.astype(np.float32), mesh.faces, target_reduction=0.82
    )
    mesh = trimesh.Trimesh(v, f, process=True)
    # quedarnos con la pieza principal (descarta islas por ruido)
    parts = mesh.split(only_watertight=False)
    mesh = max(parts, key=lambda m: len(m.faces))
    if mesh.volume < 0:
        mesh.invert()
    trimesh.repair.fix_normals(mesh)
    return mesh


if __name__ == "__main__":
    position, out = sys.argv[1], sys.argv[2]
    m = build(position)
    m.export(out)
    print(
        out,
        "faces", len(m.faces),
        "watertight", m.is_watertight,
        "vol_cm3", round(m.volume / 1000, 1),
        "bbox_mm", np.round(m.extents, 1).tolist(),
    )
