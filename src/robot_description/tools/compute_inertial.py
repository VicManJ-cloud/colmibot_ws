#!/usr/bin/env python3
"""Calcula masa, centro de masa e inercia de cada link a partir del CAD.

Entradas (carpeta inertia/):
  componentes_cad.csv  GENERADO por tools/export_mass_solidworks.ps1: forma, volumen,
                       centro de masa, inercia y caja de cada componente del ensamble.
  masas.csv            Lo llena el equipo: masa real de cada pieza, de un subensamble
                       o del robot completo (fila TOTAL). Si no existe, se crea vacio.

Como se elige la masa de cada componente (gana la primera regla que aplique):
  1. "real"        masas.csv trae la masa de esa instancia (ej. CLM-RuedaLoca-1)
                   o de su pieza (ej. CLM-RuedaLoca, por unidad).
  2. "subensamble" masas.csv trae la masa de su subensamble (ej. CLM-EnsBat3S1P):
                   se reparte entre las piezas sin masa propia, segun su masa del CAD.
  3. "cad"         densidad del material del CAD x volumen.
  Si hay fila TOTAL, las masas "cad" se escalan para que el robot sume ese total
  ("cad_escalada"): asi el reparto sigue siendo el del CAD pero el peso es el real.

La forma de cada componente (su centro de masa y su inercia por kg) sale del CAD;
al cambiar la masa solo se escala. Las piezas sin volumen en el CAD (superficies)
se tratan como una caja solida del tamano de su caja envolvente.

Salidas:
  urdf/generated/colmibot_inertial.xacro  macros base_inertial, wheel_left_inertial, wheel_right_inertial
  inertia/masas_usadas.csv                 masa y origen del dato de cada componente

Solo usa la biblioteca estandar de Python.

Ejemplo:
  python tools/compute_inertial.py
"""
import argparse
import csv
import math
import re
import sys
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent.parent
WHEEL_RX = r'llanta|wheel'        # piezas que giran con cada llanta (link propio)
AXES = {'x': (1, 0, 0), 'y': (0, 1, 0), 'z': (0, 0, 1)}


def axis_vector(spec):
    sign = -1 if spec.startswith('-') else 1
    return tuple(sign * c for c in AXES[spec.lstrip('+-').lower()])


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def piece_name(instance):
    """'CLM-PosteM3x40-2' -> 'CLM-PosteM3x40' (nombre de la pieza en el BOM)."""
    return re.sub(r'-\d+$', '', instance)


def num(s):
    try:
        v = float(s)
    except (TypeError, ValueError):
        return math.nan
    return v


def read_components(path):
    lines = path.read_text(encoding='utf-8').splitlines()
    total = next((l for l in lines if l.startswith('# total_solidworks')), '')
    comps = []
    for r in csv.DictReader(l for l in lines if not l.startswith('#')):
        rows = [[num(r['ixx']), num(r['ixy']), num(r['ixz'])],
                [num(r['ixy']), num(r['iyy']), num(r['iyz'])],
                [num(r['ixz']), num(r['iyz']), num(r['izz'])]]
        comps.append({
            'name': r['componente'], 'route': r['ruta'].split('/'),
            'piece': Path(r['archivo']).stem, 'material': r['material'],
            'm_cad': num(r['masa_kg']), 'volume': num(r['volumen_m3']),
            'com': [num(r[f'com_{a}']) for a in 'xyz'], 'I': rows,
            'box': [num(r[f'box_{e}_{a}']) for e in ('min', 'max') for a in 'xyz'],
        })
    return comps, total


def has_shape(c):
    return c['m_cad'] > 0 and c['volume'] > 0 and all(math.isfinite(v) for v in c['com'] + sum(c['I'], []))


def write_template(path, comps):
    """masas.csv vacio: una fila por pieza del BOM, por subensamble y TOTAL."""
    pieces = {}
    for c in comps:
        p = pieces.setdefault(c['piece'], {'n': 0, 'm': 0.0, 'mat': c['material']})
        p['n'] += 1
        p['m'] += c['m_cad'] if has_shape(c) else 0.0
    subs = {}
    for c in comps:
        for s in c['route'][:-1]:
            q = subs.setdefault(piece_name(s), {'n': set(), 'm': 0.0})
            q['n'].add(s)
            q['m'] += c['m_cad'] if has_shape(c) else 0.0
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['pieza', 'cantidad', 'masa_g', 'fuente', 'masa_cad_g', 'material_cad'])
        w.writerow(['TOTAL', 1, '', '', '', 'peso del robot completo (todas las piezas)'])
        for name, q in sorted(subs.items()):
            w.writerow([name, len(q['n']), '', '', f"{q['m'] / len(q['n']) * 1000:.1f}", 'subensamble'])
        for name, p in sorted(pieces.items(), key=lambda kv: kv[0].lower()):
            w.writerow([name, p['n'], '', '', f"{p['m'] / p['n'] * 1000:.1f}", p['mat']])


def read_masses(path):
    out = {}
    with path.open(encoding='utf-8', newline='') as f:
        for r in csv.DictReader(f):
            g = num(r.get('masa_g'))
            if math.isfinite(g):
                out[r['pieza'].strip()] = (g / 1000.0, (r.get('fuente') or '').strip())
    return out


def assign_masses(comps, masses):
    for c in comps:
        c['m'], c['src'], c['note'] = None, '', ''
        for key in (c['name'], c['piece']):
            if key in masses:
                c['m'], c['src'], c['note'] = masses[key][0], 'real', masses[key][1]
                break

    # Subensambles: el mas interno gana. Se reparte lo que falta segun la masa del CAD.
    subs = sorted({s for c in comps for s in c['route'][:-1]}, key=lambda s: -len(s))
    for s in subs:
        key = s if s in masses else piece_name(s)
        if key not in masses:
            continue
        members = [c for c in comps if s in c['route'][:-1]]   # la masa es por instancia
        free = [c for c in members if c['m'] is None]
        if not free:
            continue
        known = sum(c['m'] for c in members if c['m'] is not None)
        rest = masses[key][0] - known
        if rest < 0:
            sys.exit(f'{key}: sus piezas ya suman {known * 1000:.1f} g y el subensamble dice '
                     f'{masses[key][0] * 1000:.1f} g')
        weight = sum(c['m_cad'] for c in free if has_shape(c))
        for c in free:
            share = (c['m_cad'] / weight if has_shape(c) else 0.0) if weight > 0 else 1 / len(free)
            c['m'], c['src'], c['note'] = rest * share, 'subensamble', masses[key][1]

    for c in comps:
        if c['m'] is None:
            c['m'], c['src'] = (c['m_cad'] if has_shape(c) else 0.0), 'cad'

    if 'TOTAL' in masses:
        total = masses['TOTAL'][0]
        fixed = sum(c['m'] for c in comps if c['src'] != 'cad')
        free = sum(c['m'] for c in comps if c['src'] == 'cad')
        if fixed > total:
            sys.exit(f'TOTAL = {total * 1000:.0f} g, pero las masas reales ya suman {fixed * 1000:.0f} g')
        k = (total - fixed) / free if free > 0 else 0.0
        if free == 0 and abs(total - fixed) > 1e-6:
            print(f'  [aviso] todas las piezas tienen masa real: suman {fixed * 1000:.0f} g y TOTAL dice '
                  f'{total * 1000:.0f} g; se ignora TOTAL')
        for c in comps:
            if c['src'] == 'cad':
                c['m'], c['src'] = c['m'] * k, 'cad_escalada'


def body_props(c):
    """Centro de masa e inercia (en el centro de masa) del componente con su masa asignada."""
    m = c['m']
    if has_shape(c):
        k = m / c['m_cad']
        return c['com'], [[v * k for v in row] for row in c['I']]
    lo, hi = c['box'][:3], c['box'][3:]
    x, y, z = (b - a for a, b in zip(lo, hi))
    com = [(a + b) / 2 for a, b in zip(lo, hi)]
    return com, [[m * (y * y + z * z) / 12, 0, 0], [0, m * (x * x + z * z) / 12, 0], [0, 0, m * (x * x + y * y) / 12]]


def to_ros(com, I, rot, scale, origin):
    p = [sum(rot[i][j] * com[j] for j in range(3)) * scale - origin[i] for i in range(3)]
    s2 = scale * scale
    Ir = [[sum(rot[i][k] * I[k][l] * rot[j][l] for k in range(3) for l in range(3)) * s2
           for j in range(3)] for i in range(3)]
    return p, Ir


def combine(parts):
    """Suma (masa, com, I) con el teorema de ejes paralelos."""
    m = sum(p[0] for p in parts)
    if m <= 0:
        return 0.0, [0.0, 0.0, 0.0], [[0.0] * 3 for _ in range(3)]
    com = [sum(p[0] * p[1][i] for p in parts) / m for i in range(3)]
    I = [[0.0] * 3 for _ in range(3)]
    for mi, ci, Ii in parts:
        d = [ci[i] - com[i] for i in range(3)]
        dd = sum(v * v for v in d)
        for a in range(3):
            for b in range(3):
                I[a][b] += Ii[a][b] + mi * ((dd if a == b else 0.0) - d[a] * d[b])
    return m, com, I


def fmt(x):
    return f'{x:.6g}'


def inertial_macro(name, m, com, I, origin=(0, 0, 0)):
    o = [c - q for c, q in zip(com, origin)]
    return [
        f'  <xacro:macro name="{name}">',
        '    <inertial>',
        f'      <origin xyz="{fmt(o[0])} {fmt(o[1])} {fmt(o[2])}" rpy="0 0 0"/>',
        f'      <mass value="{fmt(m)}"/>',
        f'      <inertia ixx="{fmt(I[0][0])}" ixy="{fmt(I[0][1])}" ixz="{fmt(I[0][2])}"',
        f'               iyy="{fmt(I[1][1])}" iyz="{fmt(I[1][2])}" izz="{fmt(I[2][2])}"/>',
        '    </inertial>',
        '  </xacro:macro>',
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dir', type=Path, default=PKG_DIR / 'inertia', help='carpeta con los CSV')
    ap.add_argument('--units', choices=['m', 'mm'], default='m', help='unidades de componentes_cad.csv')
    ap.add_argument('--up', default='y', help='eje del CAD que apunta hacia arriba (default: y)')
    ap.add_argument('--forward', default='-z', help='eje del CAD que apunta al frente (default: -z)')
    ap.add_argument('--out', type=Path, default=PKG_DIR, help='raiz del paquete robot_description')
    args = ap.parse_args()

    comps, sw_total = read_components(args.dir / 'componentes_cad.csv')
    masses_path = args.dir / 'masas.csv'
    if not masses_path.exists():
        write_template(masses_path, comps)
        print(f'Creado {masses_path} (vacio): llenar masa_g y volver a correr.')
    masses = read_masses(masses_path)
    names = {c['name'] for c in comps} | {c['piece'] for c in comps} | \
            {s for c in comps for s in c['route'][:-1]} | {piece_name(s) for c in comps for s in c['route'][:-1]}
    for k in masses:
        if k != 'TOTAL' and k not in names:
            print(f'  [aviso] masas.csv: "{k}" no coincide con ninguna pieza del CAD')
    assign_masses(comps, masses)

    scale = {'m': 1.0, 'mm': 0.001}[args.units]
    fwd, up = axis_vector(args.forward), axis_vector(args.up)
    rot = (fwd, cross(up, fwd), up)  # filas: X, Y, Z de ROS expresados en el CAD

    wheels = [c for c in comps if re.search(WHEEL_RX, c['piece'].lower())]
    if len(wheels) != 2:
        sys.exit(f'Se esperaban 2 llantas y hay {len(wheels)}: {[w["name"] for w in wheels]}')
    # Centro de cada llanta = centro de su caja envolvente; base_link en el punto medio
    centers = []
    for w in wheels:
        mid = [(a + b) / 2 for a, b in zip(w['box'][:3], w['box'][3:])]
        centers.append([sum(rot[i][j] * mid[j] for j in range(3)) * scale for i in range(3)])
    origin = [(a + b) / 2 for a, b in zip(*centers)]

    links = {'base': [], 'wheel_left': [], 'wheel_right': []}
    wheel_center = {}
    for c in comps:
        com, I = body_props(c)
        p, Ir = to_ros(com, I, rot, scale, origin)
        c['ros_com'] = p
        if c in wheels:
            side = 'wheel_left' if p[1] > 0 else 'wheel_right'
            links[side].append((c['m'], p, Ir))
            wheel_center[side] = [ce - o for ce, o in zip(centers[wheels.index(c)], origin)]
        else:
            links['base'].append((c['m'], p, Ir))
    if len(wheel_center) != 2:
        sys.exit('Las dos llantas quedaron del mismo lado en Y: revisa --up / --forward')

    result = {k: combine(v) for k, v in links.items()}

    # Reporte por componente
    with (args.dir / 'masas_usadas.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['componente', 'pieza', 'link', 'masa_g', 'origen_dato', 'nota', 'masa_cad_g',
                    'com_ros_x', 'com_ros_y', 'com_ros_z'])
        for c in sorted(comps, key=lambda c: -c['m']):
            link = 'base' if c not in wheels else ('wheel_left' if c['ros_com'][1] > 0 else 'wheel_right')
            w.writerow([c['name'], c['piece'], link, f"{c['m'] * 1000:.2f}", c['src'], c['note'],
                        f"{(c['m_cad'] if has_shape(c) else 0) * 1000:.2f}"] + [f'{v:.5f}' for v in c['ros_com']])

    counts = {}
    for c in comps:
        counts[c['src']] = counts.get(c['src'], 0) + 1
    total = sum(r[0] for r in result.values())
    print(f'\nComponentes: {len(comps)}  origen de la masa: ' +
          ', '.join(f'{k}={v}' for k, v in sorted(counts.items())))
    if sw_total:
        print(f'  ({sw_total.lstrip("# ")})')
    print(f'Robot: {total * 1000:.0f} g')
    for k, (m, com, I) in result.items():
        print(f'  {k:12s} {m * 1000:8.1f} g   com = ({com[0] * 1000:6.1f}, {com[1] * 1000:6.1f}, '
              f'{com[2] * 1000:6.1f}) mm   Ixx Iyy Izz = {I[0][0]:.3e} {I[1][1]:.3e} {I[2][2]:.3e}')
    no_shape = [c['name'] for c in comps if not has_shape(c)]
    if no_shape:
        print(f'  [aviso] sin volumen en el CAD (se tratan como caja): {", ".join(no_shape)}')

    lines = [
        '<?xml version="1.0"?>',
        '<!-- GENERADO por tools/compute_inertial.py. No editar a mano: editar inertia/masas.csv y',
        '     volver a correr el script. Marco de ROS: origen en base_link (centro del eje de las llantas). -->',
        f'<!-- Robot: {total * 1000:.0f} g. Origen de las masas: ' +
        ', '.join(f'{k}={v}' for k, v in sorted(counts.items())) + ' componentes -->',
        '<robot xmlns:xacro="http://www.ros.org/wiki/xacro">',
        '',
    ]
    m, com, I = result['base']
    lines += inertial_macro('base_inertial', m, com, I)
    for side in ('wheel_left', 'wheel_right'):
        m, com, I = result[side]
        lines += [''] + inertial_macro(f'{side}_inertial', m, com, I, wheel_center[side])
    lines += ['', '</robot>', '']
    gen = args.out / 'urdf' / 'generated'
    gen.mkdir(parents=True, exist_ok=True)
    (gen / 'colmibot_inertial.xacro').write_text('\n'.join(lines), encoding='utf-8')
    print(f'\nEscrito: {gen / "colmibot_inertial.xacro"}')
    print(f'Escrito: {args.dir / "masas_usadas.csv"}')


if __name__ == '__main__':
    main()
