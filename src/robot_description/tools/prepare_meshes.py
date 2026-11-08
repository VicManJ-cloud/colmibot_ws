#!/usr/bin/env python3
"""Convierte las STL exportadas de SolidWorks en las mallas de robot_description.

Entrada: una carpeta con una STL por pieza, exportadas desde el ensamble
CLM-EnsambleColmibot con tools/export_stl_solidworks.ps1 (o a mano: PROCESO.md 4.2).
Cada STL conserva su posicion dentro del ensamble.

Que hace:
  1. Rota el marco del CAD al marco de ROS (X adelante, Z arriba) segun
     --up / --forward, y escala a metros.
  2. Detecta las dos llantas, calcula su radio, ancho y centro, y coloca
     base_link en el punto medio del eje.
  3. Agrupa las piezas fijas por tipo (impreso 3D, corte laser, electronica,
     ...) en una STL por grupo para poder colorearlas, y deja cada llanta en su
     propia STL centrada en su eje. La electronica de EXCLUDE_RULES no se dibuja
     y la de BOX_RULES se dibuja como una caja (con --all-parts se dibuja todo).
  4. Localiza camara, IMU y los 3 VL53L1X para los frames de sensores.
  5. Escribe meshes/*.stl y urdf/generated/colmibot_meshes.xacro.

Solo usa la biblioteca estandar de Python.

Ejemplo (Windows, desde la carpeta del paquete):
  python tools/prepare_meshes.py C:/Cad_colmibot2/stl_cad_actual --units mm --up=y --forward=-z --grid 0.2
"""
import argparse
import math
import re
import struct
import sys
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent.parent

# (grupo, regex sobre el nombre normalizado: minusculas sin simbolos).
# Gana la primera coincidencia; editar si cambian los nombres de las piezas en el CAD.
# Tambien acepta STL ya agrupadas y nombradas por grupo (electronica.stl, llanta_izq.stl, ...).
GROUP_RULES = [
    ('rueda', r'llanta|wheel'),
    ('camara', r'c920|logitech|camara'),
    ('placas_laser', r'clmbase(?!cam)|plato|pisocam|placaslaser|laser'),
    ('impreso_3d', r'body|bracket|separador|poste|holder|shield|pi5case|basecam|impreso'),
    ('bateria', r'18650|battery|bateria'),
    ('motores', r'motorreductor|37d|^(?!.*cooler).*motor'),  # el cooler de la Pi trae un "MotorHouse"
    ('ruedas_locas', r'ruedaloca|ballcaster'),
    ('electronica', r'esp32|expansion|cytron|mdd10a|stepup|xl4015|raspi|raspberry|'
                    r'cooler|vl53|imu|bmi270|kcd1|bms|electronica'),
]
# Electronica que no se dibuja (su masa sigue contando: ver tools/compute_inertial.py).
# Escondidas dentro del cuerpo, o tapadas por la carcasa de la Pi (CLM-PI5_Case*, que se queda).
EXCLUDE_RULES = [
    r'cytron|mdd10a',             # driver de motores
    r'bms3s',                     # proteccion de la bateria (no CLM-HolderBMS, que es impreso)
    r'18650battery',              # celdas (no CLM-Holder18650, que es impreso)
    r'raspi5',                    # Raspberry Pi 5 y su cooler
]
# Electronica del piso de arriba que si se ve: se dibuja como una caja de su mismo tamano
BOX_RULES = [
    ('esp32', r'esp32wroom|expansionboard'),   # ESP32 + tarjeta de expansion (no CLM-ShieldESP32)
    ('xl4015', r'stepup|xl4015'),              # convertidor de voltaje
]
ANCHOR_RULES = {
    'camera': r'c920glass|glass|camara',
    'imu': r'bmi270|imu',
    'tof': r'vl53',
}
AXES = {'x': (1, 0, 0), 'y': (0, 1, 0), 'z': (0, 0, 1)}


def normalize(name):
    return re.sub(r'[^a-z0-9]', '', name.lower())


def axis_vector(spec):
    sign = -1 if spec.startswith('-') else 1
    v = AXES[spec.lstrip('+-').lower()]
    return tuple(sign * c for c in v)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def read_stl(path):
    """Devuelve una lista de triangulos [(x1,y1,z1,x2,...,z3), ...]."""
    data = path.read_bytes()
    if len(data) >= 84:
        n = struct.unpack_from('<I', data, 80)[0]
        if len(data) == 84 + 50 * n:
            return [struct.unpack_from('<9f', data, 84 + 50 * i + 12) for i in range(n)]
    verts = [float(v) for xyz in re.findall(
        rb'vertex\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)', data) for v in xyz]
    return [tuple(verts[i:i + 9]) for i in range(0, len(verts) - 8, 9)]


def write_stl(path, tris):
    with open(path, 'wb') as f:
        f.write(b'Colmibot robot_description'.ljust(80, b' '))
        f.write(struct.pack('<I', len(tris)))
        for t in tris:
            u = (t[3] - t[0], t[4] - t[1], t[5] - t[2])
            v = (t[6] - t[0], t[7] - t[1], t[8] - t[2])
            n = cross(u, v)
            length = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
            f.write(struct.pack('<12fH', n[0] / length, n[1] / length, n[2] / length, *t, 0))


def transform(tris, rot, scale, offset=(0.0, 0.0, 0.0)):
    out = []
    for t in tris:
        nt = []
        for i in range(0, 9, 3):
            p = (t[i] * scale, t[i + 1] * scale, t[i + 2] * scale)
            for r, o in zip(rot, offset):
                nt.append(r[0] * p[0] + r[1] * p[1] + r[2] * p[2] - o)
        out.append(tuple(nt))
    return out


def bbox(tris):
    lo = [min(t[i + k] for t in tris for i in (0, 3, 6)) for k in range(3)]
    hi = [max(t[i + k] for t in tris for i in (0, 3, 6)) for k in range(3)]
    return lo, hi


def center(tris):
    lo, hi = bbox(tris)
    return tuple((a + b) / 2 for a, b in zip(lo, hi))


def decimate(tris, grid):
    """Simplificacion por agrupamiento de vertices en una rejilla de `grid` m."""
    if grid <= 0:
        return tris
    out, seen = [], set()
    for t in tris:
        q = tuple(round(c / grid) for c in t)
        a, b, c = q[0:3], q[3:6], q[6:9]
        if a == b or b == c or a == c:
            continue
        key = tuple(sorted((a, b, c)))
        if key in seen:
            continue
        seen.add(key)
        out.append(tuple(v * grid for v in q))
    return out


def cluster_by_y(items, k):
    """Separa piezas en k grupos segun su posicion en Y (de izquierda a derecha).

    Onshape puede partir una pieza en muchos cuerpos (pines, letras...), asi que
    no se puede contar archivos: se corta en los k-1 huecos mas grandes en Y.
    """
    items = sorted(items, key=lambda it: -center(it['tris'])[1])
    ys = [center(it['tris'])[1] for it in items]
    cuts = sorted(sorted(range(1, len(items)), key=lambda i: ys[i - 1] - ys[i])[-(k - 1):]) if k > 1 else []
    bounds = [0] + cuts + [len(items)]
    return [items[a:b] for a, b in zip(bounds, bounds[1:])]


def merge(items):
    return {'name': ', '.join(it['name'] for it in items[:3]) + (' ...' if len(items) > 3 else ''),
            'count': len(items), 'tris': [t for it in items for t in it['tris']]}


def fmt(x):
    return f'{x:.5f}'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('stl_dir', type=Path, help='carpeta con las STL exportadas de SolidWorks')
    ap.add_argument('--units', choices=['m', 'mm', 'in'], default='mm',
                    help='unidades de las STL exportadas (default: mm)')
    ap.add_argument('--up', default='y', help='eje del CAD que apunta hacia arriba (default: y)')
    ap.add_argument('--forward', default='-z',
                    help='eje del CAD que apunta al frente del robot, ej. --forward=-z (default: -z)')
    ap.add_argument('--grid', type=float, default=0.0,
                    help='simplificar mallas con una rejilla de este tamano en mm (ej. 0.5)')
    ap.add_argument('--out', type=Path, default=PKG_DIR, help='raiz del paquete robot_description')
    ap.add_argument('--all-parts', action='store_true',
                    help='dibujar todas las piezas (no aplicar EXCLUDE_RULES ni BOX_RULES)')
    args = ap.parse_args()

    scale = {'m': 1.0, 'mm': 0.001, 'in': 0.0254}[args.units]
    fwd, up = axis_vector(args.forward), axis_vector(args.up)
    if any(a * b for a, b in zip(fwd, up)):
        sys.exit('--up y --forward deben ser ejes distintos')
    rot = (fwd, cross(up, fwd), up)  # filas: X, Y, Z de ROS expresados en el CAD

    files = sorted(p for p in args.stl_dir.iterdir() if p.suffix.lower() == '.stl')
    if not files:
        sys.exit(f'No hay archivos .stl en {args.stl_dir}')

    parts = []
    for p in files:
        tris = read_stl(p)
        if not tris:
            print(f'  [aviso] {p.name}: sin triangulos, se omite')
            continue
        key = normalize(p.stem)
        group = next((g for g, rx in GROUP_RULES if re.search(rx, key)), 'otros')
        parts.append({'name': p.name, 'key': key, 'group': group,
                      'tris': transform(tris, rot, scale)})

    wheel_parts = [p for p in parts if p['group'] == 'rueda']
    if len(wheel_parts) < 2:
        sys.exit(f'Se esperaban al menos 2 STL de llanta y se encontraron {len(wheel_parts)}: '
                 f'{[w["name"] for w in wheel_parts]}. Revisa GROUP_RULES.')
    wheels = [merge(c) for c in cluster_by_y(wheel_parts, 2)]

    for w in wheels:
        lo, hi = bbox(w['tris'])
        w['center'] = center(w['tris'])
        w['size'] = [b - a for a, b in zip(lo, hi)]
    if min(range(3), key=lambda k: wheels[0]['size'][k]) != 1:
        print('  [aviso] el eje de las llantas no quedo sobre Y: revisa --up / --forward')
    wheels.sort(key=lambda w: -w['center'][1])
    left, right = wheels
    if math.dist(left['center'], right['center']) < 0.01:
        sys.exit('Las dos llantas estan en el mismo lugar: las STL no conservaron la posicion del '
                 'ensamble. Exporta desde la pestana del ensamble, no desde cada pieza.')
    axle = tuple((a + b) / 2 for a, b in zip(left['center'], right['center']))
    radius = max(max(w['size'][0], w['size'][2]) for w in wheels) / 2
    width = max(w['size'][1] for w in wheels)

    for p in parts:
        p['tris'] = transform(p['tris'], ((1, 0, 0), (0, 1, 0), (0, 0, 1)), 1.0, axle)
    for w in wheels:
        # merge() hace copias: las llantas no recibieron el desplazamiento de arriba
        w['tris'] = transform(w['tris'], ((1, 0, 0), (0, 1, 0), (0, 0, 1)), 1.0, axle)
        w['center'] = tuple(c - a for c, a in zip(w['center'], axle))

    boxes = []
    if not args.all_parts:
        print('\nSe quitan de las mallas:')
        for p in parts:
            if any(re.search(rx, p['key']) for rx in EXCLUDE_RULES):
                p['group'] = None
        for name, rx in BOX_RULES:
            hits = [p for p in parts if re.search(rx, p['key'])]
            if not hits:
                print(f'  [aviso] caja {name}: ninguna pieza coincide con {rx}')
                continue
            lo, hi = bbox([t for h in hits for t in h['tris']])
            boxes.append({'name': name, 'center': [(a + b) / 2 for a, b in zip(lo, hi)],
                          'size': [b - a for a, b in zip(lo, hi)]})
            for h in hits:
                h['group'] = name
        removed = [p for p in parts if p['group'] is None or p['group'] in {b['name'] for b in boxes}]
        for p in removed:
            print(f'  {"caja " + p["group"] if p["group"] else "quitada":12s} {p["name"]}')
        print(f'  ({len(removed)} STL; quedan {len(parts) - len(removed)})')

    mesh_dir = args.out / 'meshes'
    gen_dir = args.out / 'urdf' / 'generated'
    mesh_dir.mkdir(parents=True, exist_ok=True)
    gen_dir.mkdir(parents=True, exist_ok=True)
    grid = args.grid * 0.001

    print(f'\nLlantas: radio={radius * 1000:.1f} mm  ancho={width * 1000:.1f} mm  '
          f'separacion={(left["center"][1] - right["center"][1]) * 1000:.1f} mm')
    for side, w in (('left', left), ('right', right)):
        tris = decimate(transform(w['tris'], ((1, 0, 0), (0, 1, 0), (0, 0, 1)), 1.0, w['center']), grid)
        write_stl(mesh_dir / f'wheel_{side}.stl', tris)
        print(f'  wheel_{side}.stl  <- {w["count"]} STL: {w["name"]}  ({len(tris)} triangulos)')

    box_names = {b['name'] for b in boxes}
    groups = {}
    for p in parts:
        if p['group'] is not None and p['group'] != 'rueda' and p['group'] not in box_names:
            groups.setdefault(p['group'], []).append(p)
    print('\nGrupos:')
    for g, members in sorted(groups.items()):
        tris = decimate([t for m in members for t in m['tris']], grid)
        write_stl(mesh_dir / f'{g}.stl', tris)
        print(f'  {g}.stl  ({len(tris)} triangulos)')
        for m in members[:8]:
            print(f'      {m["name"]}')
        if len(members) > 8:
            print(f'      ... y {len(members) - 8} mas')

    all_lo, all_hi = bbox([t for p in parts for t in p['tris']])
    floor_gap = (all_lo[2] + radius) * 1000
    print(f'\nRobot: largo={(all_hi[0] - all_lo[0]) * 1000:.0f} mm  ancho={(all_hi[1] - all_lo[1]) * 1000:.0f} mm  '
          f'alto={(all_hi[2] - all_lo[2]) * 1000:.0f} mm')
    if abs(floor_gap) > 3:
        print(f'  [aviso] el punto mas bajo queda {floor_gap:.1f} mm respecto al piso de las llantas; '
              'revisa --up o la altura de las ruedas locas')

    # Caja de colision del cuerpo: todo menos las llantas
    body_lo, body_hi = bbox([t for p in parts if p['group'] != 'rueda' for t in p['tris']])
    props = {
        'wheel_radius': radius, 'wheel_width': width,
        'wheel_left_x': left['center'][0], 'wheel_left_y': left['center'][1], 'wheel_left_z': left['center'][2],
        'wheel_right_x': right['center'][0], 'wheel_right_y': right['center'][1],
        'wheel_right_z': right['center'][2],
        'chassis_length': body_hi[0] - body_lo[0], 'chassis_width': body_hi[1] - body_lo[1],
        'chassis_height': body_hi[2] - body_lo[2], 'chassis_z': (body_hi[2] + body_lo[2]) / 2,
    }

    print('\nSensores:')
    for anchor, rx in ANCHOR_RULES.items():
        hits = [p for p in parts if re.search(rx, p['key'])]
        if anchor == 'tof':
            if len(hits) >= 3:
                for side, c in zip(('left', 'center', 'right'), cluster_by_y(hits, 3)):
                    x, y, z = center(merge(c)['tris'])
                    props.update({f'tof_{side}_x': x, f'tof_{side}_y': y, f'tof_{side}_z': z})
                print(f'  tof_left/center/right: OK ({len(hits)} STL)')
            else:
                print(f'  [aviso] se esperaban 3 VL53L1X y hay {len(hits)}; se usan los valores de colmibot_params.xacro')
        elif hits:
            x, y, z = center(merge(hits)['tris'])
            props.update({f'{anchor}_x': x, f'{anchor}_y': y, f'{anchor}_z': z})
            print(f'  {anchor}: OK ({len(hits)} STL)')
        else:
            print(f'  [aviso] no se encontro pieza para {anchor}; se usan los valores de colmibot_params.xacro')

    lines = [
        '<?xml version="1.0"?>',
        '<!-- GENERADO por tools/prepare_meshes.py. No editar a mano: volver a correr el script. -->',
        f'<!-- Opciones: units={args.units} up={args.up} forward={args.forward} grid={args.grid} mm -->',
        '<robot xmlns:xacro="http://www.ros.org/wiki/xacro">',
        '',
    ]
    lines += [f'  <xacro:property name="{k}" value="{fmt(v)}"/>' for k, v in props.items()]
    # Un link fijo por grupo (una sola visual cada uno): RViz2 puede pintar todas las
    # visuales de un link con el material de la primera, asi que no se juntan en base_link.
    lines += ['', '  <xacro:macro name="body_mesh_links" params="parent">']

    def vis_link(name, origin, geometry, material, comment=None):
        out = [f'    <!-- {comment} -->'] if comment else []
        return out + [
            f'    <link name="vis_{name}">',
            '      <visual>',
            f'        <origin xyz="{origin}" rpy="0 0 0"/>',
            f'        <geometry>{geometry}</geometry>',
            f'        <material name="{material}"/>',
            '      </visual>',
            '    </link>',
            f'    <joint name="vis_{name}_joint" type="fixed">',
            '      <parent link="${parent}"/>',
            f'      <child link="vis_{name}"/>',
            '    </joint>',
        ]

    for g in sorted(groups):
        lines += vis_link(g, '0 0 0',
                          f'<mesh filename="package://robot_description/meshes/{g}.stl"/>', g)
    for b in boxes:
        c, sz = b['center'], b['size']
        lines += vis_link(b['name'], f'{fmt(c[0])} {fmt(c[1])} {fmt(c[2])}',
                          f'<box size="{fmt(sz[0])} {fmt(sz[1])} {fmt(sz[2])}"/>', 'electronica',
                          comment=f'caja en lugar de: {b["name"]} (BOX_RULES)')
    lines += ['  </xacro:macro>', '', '</robot>', '']
    (gen_dir / 'colmibot_meshes.xacro').write_text('\n'.join(lines), encoding='utf-8')
    print(f'\nEscrito: {gen_dir / "colmibot_meshes.xacro"}')


if __name__ == '__main__':
    main()
