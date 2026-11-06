#!/usr/bin/env python3
"""
generar_modelo.py
=================
Genera el paquete ROS 2 `robot_description` a partir de las STL exportadas
desde SolidWorks, usando `robot.yaml` como unica fuente de diseño.

    python3 generar_modelo.py robot.yaml <carpeta_stl> <carpeta_salida>

Que hace, en orden:
  1. Agrupa las STL sueltas en modulos (segun 'patrones' del YAML).
  2. Rota del sistema del CAD al de ROS (REP-103: X frente, Y izquierda, Z arriba).
  3. Convierte milimetros a metros.
  4. Centra cada malla en su propio centroide -> ese centroide es el origen del eslabon.
  5. Decima la malla visual; calcula una primitiva de colision (caja o cilindro).
  6. Calcula masa y tensor de inercia desde el volumen y la densidad del material.
  7. Deduce la direccion de medicion de los sensores desde su geometria.
  8. Escribe colmibot.urdf.xacro + meshes/ + launch/ + rviz/ + package.xml + CMakeLists.txt

Las medidas NO se teclean nunca: se miden. Para mover una pieza, se mueve en el
CAD y se vuelve a correr este script.
"""

import argparse
import os
import sys

import numpy as np
import trimesh
import yaml

EJES = {
    "x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1),
    "-x": (-1, 0, 0), "-y": (0, -1, 0), "-z": (0, 0, -1),
}

FACTOR_UNIDAD = {"mm": 0.001, "cm": 0.01, "m": 1.0}


# --------------------------------------------------------------------------
# Geometria
# --------------------------------------------------------------------------

def matriz_cad_a_ros(frente, arriba):
    """Rotacion R tal que p_ros = R @ p_cad.

    En ROS (REP-103) X apunta al frente, Y a la izquierda y Z arriba.
    Se construye a partir de que ejes del CAD cumplen ese papel.
    """
    if frente not in EJES or arriba not in EJES:
        raise ValueError(f"ejes invalidos: frente={frente}, arriba={arriba}")

    f = np.array(EJES[frente], dtype=float)
    u = np.array(EJES[arriba], dtype=float)

    if abs(float(np.dot(f, u))) > 1e-9:
        raise ValueError("'frente' y 'arriba' deben ser perpendiculares")

    izquierda = np.cross(u, f)
    R = np.vstack([f, izquierda, u])

    det = float(np.linalg.det(R))
    if abs(det - 1.0) > 1e-6:
        raise ValueError(f"la rotacion resultante no es valida (det={det:.3f})")
    return R


def cargar_grupo(carpeta, patrones, archivos):
    """Une en una sola malla todas las STL cuyo nombre contenga algun patron."""
    seleccion = sorted(
        f for f in archivos if any(p in f for p in patrones)
    )
    if not seleccion:
        return None, []

    mallas = []
    for nombre in seleccion:
        m = trimesh.load(os.path.join(carpeta, nombre), force="mesh")
        if m is not None and len(m.faces) > 0:
            mallas.append(m)

    if not mallas:
        return None, seleccion
    return trimesh.util.concatenate(mallas), seleccion


def decimar(malla, max_caras):
    """Reduce triangulos conservando la silueta. Si no se puede, devuelve igual."""
    if len(malla.faces) <= max_caras:
        return malla, False

    # Las STL de CAD traen vertices repetidos (cada triangulo con los suyos) y
    # caras de area cero. El decimador no puede colapsar aristas que no sabe
    # que son la misma, asi que se cose la malla antes de reducirla.
    try:
        malla.merge_vertices()
        malla.update_faces(malla.nondegenerate_faces())
        malla.remove_unreferenced_vertices()
    except Exception:  # noqa: BLE001
        pass

    if len(malla.faces) <= max_caras:
        return malla, True
    try:
        reducida = malla.simplify_quadric_decimation(face_count=max_caras)
        if reducida is not None and len(reducida.faces) > 0:
            return reducida, True
    except Exception as exc:  # noqa: BLE001
        print(f"      aviso: no se pudo decimar ({exc})")
    return malla, False


def _inercia_caja(masa, ex):
    """Tensor de inercia de una caja maciza respecto a su propio centro."""
    ixx = masa * (ex[1] ** 2 + ex[2] ** 2) / 12.0
    iyy = masa * (ex[0] ** 2 + ex[2] ** 2) / 12.0
    izz = masa * (ex[0] ** 2 + ex[1] ** 2) / 12.0
    return np.diag([ixx, iyy, izz])


def inercia_de(malla, densidad):
    """Masa y tensor de inercia respecto al centroide del modulo.

    Si la malla esta cerrada se usa su volumen real. Si no, se aproxima
    pieza por pieza: una caja envolvente POR COMPONENTE suelto, no una caja
    global. La caja global de un grupo disperso (p.ej. cinco tarjetas
    separadas) encierra tambien el aire entre ellas y dispara la masa.

    Devuelve (masa, tensor 3x3, metodo).
    """
    if malla.is_watertight and malla.volume > 1e-12:
        malla.density = densidad
        m = float(malla.mass)
        I = np.array(malla.moment_inertia, dtype=float)
        if m > 0 and np.all(np.isfinite(I)):
            return m, I, "malla"

    try:
        piezas = malla.split(only_watertight=False)
    except Exception:  # noqa: BLE001
        piezas = []
    if len(piezas) == 0:
        piezas = [malla]

    centro_grupo = np.asarray(malla.centroid, dtype=float)
    masa_total = 0.0
    I_total = np.zeros((3, 3))

    for pieza in piezas:
        usar_malla = False
        if pieza.is_watertight and pieza.volume > 1e-12:
            pieza.density = densidad
            m_i = float(pieza.mass)
            I_i = np.array(pieza.moment_inertia, dtype=float)
            # Un solido degenerado o con normales invertidas produce masa <= 0
            # o inercia no finita. Un NaN en el URDF rompe Gazebo sin decir
            # por que, asi que esos casos caen a la caja envolvente.
            usar_malla = m_i > 0 and bool(np.all(np.isfinite(I_i)))

        if not usar_malla:
            ex = np.maximum(np.asarray(pieza.bounding_box.extents, dtype=float), 1e-5)
            m_i = float(densidad * ex[0] * ex[1] * ex[2])
            I_i = _inercia_caja(m_i, ex)

        # Teorema de ejes paralelos: trasladar al centroide del modulo.
        d = np.asarray(pieza.centroid, dtype=float) - centro_grupo
        I_total += I_i + m_i * (float(d @ d) * np.eye(3) - np.outer(d, d))
        masa_total += m_i

    return masa_total, I_total, f"piezas({len(piezas)})"


def quitar_piezas_diminutas(malla, volumen_min_mm3):
    """Descarta solidos sueltos mas chicos que el umbral (tornillos, pines).

    Un modelo de CAD de una tarjeta trae cientos de solidos minusculos que no
    cambian como se ve la pieza pero si cuestan decenas de miles de triangulos.

    Devuelve (malla filtrada, cuantas se quitaron).
    """
    if volumen_min_mm3 <= 0:
        return malla, 0
    umbral_m3 = volumen_min_mm3 * 1e-9      # la malla ya esta en metros
    try:
        piezas = malla.split(only_watertight=False)
    except Exception:  # noqa: BLE001
        return malla, 0
    if len(piezas) < 2:
        return malla, 0

    grandes = [p for p in piezas
               if float(np.prod(p.bounding_box.extents)) >= umbral_m3]
    quitadas = len(piezas) - len(grandes)
    if not grandes or quitadas == 0:
        return malla, 0
    return trimesh.util.concatenate(grandes), quitadas


def colision_de(malla, tipo, eje_cilindro="z"):
    """Primitiva de colision a partir de la caja envolvente de la malla centrada."""
    ex = np.asarray(malla.bounding_box.extents, dtype=float)
    if tipo == "cilindro":
        idx = {"x": 0, "y": 1, "z": 2}[eje_cilindro]
        largo = float(ex[idx])
        radio = float(max(ex[i] for i in range(3) if i != idx) / 2.0)
        # El cilindro de URDF nace sobre Z; se gira para alinearlo con su eje.
        rpy = {"x": (0.0, 1.5707963, 0.0),
               "y": (1.5707963, 0.0, 0.0),
               "z": (0.0, 0.0, 0.0)}[eje_cilindro]
        return {"tipo": "cilindro", "radio": radio, "largo": largo, "rpy": rpy}
    return {"tipo": "caja", "ex": ex, "rpy": (0.0, 0.0, 0.0)}


def direccion_sensor(malla, centroide):
    """Direccion en la que apunta una placa delgada (normal a su cara mayor).

    Se toma la caja orientada de la malla: su eje mas corto es el grosor de la
    placa, asi que ese eje es la normal. El signo se elige hacia afuera del robot.
    Devuelve (vector unitario, grosor, confianza).
    """
    normal = None
    metodo = None
    confianza = 0.0

    # 1) Metodo preferido: la cara plana mas grande de la placa.
    #    La normal de esa cara ES la direccion de medicion, sin sesgo. Los
    #    ejes principales se desvian varios grados cuando la placa trae un
    #    conector alto, porque ese bulto corre la dispersion de los vertices.
    try:
        areas = np.asarray(malla.facets_area, dtype=float)
        if areas.size:
            i = int(np.argmax(areas))
            fraccion = float(areas[i] / max(areas.sum(), 1e-12))
            if fraccion > 0.05:
                normal = np.asarray(
                    malla.face_normals[malla.facets[i][0]], dtype=float)
                metodo = f"cara plana ({fraccion*100:.0f}% del area)"
                confianza = float(min(1.0, 2.5 * fraccion))
    except Exception:  # noqa: BLE001
        pass

    # 2) Respaldo: ejes principales de los vertices. Siempre funciona, pero
    #    con sesgo si la placa no es simetrica. Se marca como tal.
    if normal is None:
        V = np.asarray(malla.vertices, dtype=float)
        if len(V) < 4:
            return None, None, 0.0, "sin vertices suficientes"
        V = V - V.mean(axis=0)
        valores, vectores = np.linalg.eigh(V.T @ V / len(V))
        normal = vectores[:, 0]
        ex = np.sqrt(np.maximum(valores, 0.0))
        confianza = float(1.0 - ex[0] / ex[1]) if ex[1] > 1e-12 else 0.0
        confianza = min(confianza, 0.49)   # nunca "alta": tiene sesgo conocido
        metodo = "ejes principales (sesgado, verificar)"

    n = float(np.linalg.norm(normal))
    if n < 1e-12:
        return None, None, 0.0, "normal degenerada"
    normal = normal / n

    # La normal de una cara no distingue frente de reverso: hay que elegir el
    # sentido. Se asume que el sensor mira hacia AFUERA del robot, asi que su
    # normal debe apuntar en el mismo sentido que su posicion respecto al eje
    # vertical del chasis.
    radial = np.array(centroide, dtype=float)
    radial[2] = 0.0                      # el sentido util es horizontal
    norma_radial = float(np.linalg.norm(radial))
    if norma_radial > 1e-6:
        alineacion = float(np.dot(normal, radial / norma_radial))
        if alineacion < 0:
            normal = -normal
            alineacion = -alineacion
        # Si la normal es casi perpendicular a la radial, el criterio no
        # decide y el sentido puede quedar invertido.
        if alineacion < 0.25:
            confianza = min(confianza, 0.40)
            metodo += " [sentido ambiguo]"
    else:
        confianza = min(confianza, 0.40)
        metodo += " [sensor sobre el eje: sentido ambiguo]"

    return normal, None, confianza, metodo


def rpy_desde_direccion(d):
    """RPY que lleva el eje X a apuntar en la direccion d (convencion de sensores)."""
    d = np.asarray(d, dtype=float)
    d = d / np.linalg.norm(d)
    yaw = float(np.arctan2(d[1], d[0]))
    pitch = float(-np.arcsin(np.clip(d[2], -1.0, 1.0)))
    return (0.0, pitch, yaw)


# --------------------------------------------------------------------------
# Emision del xacro
# --------------------------------------------------------------------------

def f(x):
    """Formato para numeros en XML, con cifras significativas.

    No se usa formato de punto fijo: las inercias de las piezas chicas valen
    del orden de 1e-9 kg*m2 y con seis decimales se escribirian como "0".
    Una inercia en cero hace que Gazebo rechace el eslabon.
    """
    v = float(x)
    if v == 0.0:
        return "0"
    return f"{v:.9g}"


def bloque_colision(col):
    r, p, y = col["rpy"]
    origen = f'<origin xyz="0 0 0" rpy="{f(r)} {f(p)} {f(y)}"/>'
    if col["tipo"] == "cilindro":
        geom = f'<cylinder radius="{f(col["radio"])}" length="{f(col["largo"])}"/>'
    else:
        ex = col["ex"]
        geom = f'<box size="{f(ex[0])} {f(ex[1])} {f(ex[2])}"/>'
    return (
        "    <collision>\n"
        f"      {origen}\n"
        f"      <geometry>{geom}</geometry>\n"
        "    </collision>"
    )


def bloque_inercial(masa, I):
    return (
        "    <inertial>\n"
        '      <origin xyz="0 0 0" rpy="0 0 0"/>\n'
        f'      <mass value="{f(masa)}"/>\n'
        f'      <inertia ixx="{f(I[0,0])}" ixy="{f(I[0,1])}" ixz="{f(I[0,2])}"'
        f' iyy="{f(I[1,1])}" iyz="{f(I[1,2])}" izz="{f(I[2,2])}"/>\n'
        "    </inertial>"
    )


def validar_modulos(modulos):
    """Revisa lo que suele romperse en silencio. Devuelve lista de problemas."""
    problemas = []
    for m in modulos:
        nombre = m["link"]
        masa = float(m["masa"])
        I = np.asarray(m["inercia"], dtype=float)

        if not np.isfinite(masa) or masa <= 0:
            problemas.append(f"{nombre}: masa invalida ({masa})")
        if not np.all(np.isfinite(I)):
            problemas.append(f"{nombre}: inercia con NaN o infinito")
        else:
            diag = np.diag(I)
            if np.any(diag <= 0):
                problemas.append(f"{nombre}: inercia con diagonal <= 0")
            # Lo que se escribe en el XML es el texto, no el float: si el
            # formato lo manda a cero, Gazebo recibe un eslabon invalido.
            elif any(float(f(v)) == 0.0 for v in diag):
                problemas.append(f"{nombre}: inercia se escribe como 0 en el XML")

        col = m["colision"]
        dims = ([col["radio"], col["largo"]] if col["tipo"] == "cilindro"
                else list(col["ex"]))
        if any((not np.isfinite(d)) or d <= 0 for d in dims):
            problemas.append(f"{nombre}: colision con dimension invalida")

        if not np.all(np.isfinite(np.asarray(m["origen"], dtype=float))):
            problemas.append(f"{nombre}: origen de la junta no finito")
    return problemas


def escribir_geometria(ruta, nombre_robot, modulos, avisos):
    """Archivo GENERADO: solo geometria medida. Se sobrescribe en cada corrida."""
    L = []
    A = L.append
    A('<?xml version="1.0"?>')
    A("<!-- ARCHIVO GENERADO - NO EDITAR A MANO -->")
    A("<!-- Lo escribe tools/generar_modelo.py desde el CAD y se sobrescribe. -->")
    A("<!-- Para cambiar geometria: mover la pieza en SolidWorks y regenerar.  -->")
    A("<!-- Para cambiar parametros: editar urdf/colmibot.urdf.xacro.          -->")
    A(f'<robot name="{nombre_robot}" xmlns:xacro="http://www.ros.org/wiki/xacro">')
    A("")
    A('  <material name="gris"><color rgba="0.75 0.75 0.78 1"/></material>')
    A('  <material name="oscuro"><color rgba="0.25 0.25 0.28 1"/></material>')
    A("")
    A("  <!-- ===================== MARCO DE SUELO ========================== -->")
    A('  <link name="base_footprint"/>')
    A('  <joint name="joint_base_footprint" type="fixed">')
    A('    <parent link="base_footprint"/>')
    A('    <child link="base_link"/>')
    A('    <origin xyz="0 0 ${altura_chasis}" rpy="0 0 0"/>')
    A("  </joint>")
    A("")
    A("  <!-- ===================== ESLABONES =============================== -->")

    for m in modulos:
        nombre = m["link"]
        A("")
        A(f'  <link name="{nombre}">')
        A("    <visual>")
        A('      <origin xyz="0 0 0" rpy="0 0 0"/>')
        A("      <geometry>")
        A(f'        <mesh filename="package://robot_description/meshes/{m["archivo"]}"/>')
        A("      </geometry>")
        A(f'      <material name="{m["color"]}"/>')
        A("    </visual>")
        A(bloque_colision(m["colision"]))
        A(bloque_inercial(m["masa"], m["inercia"]))
        A("  </link>")

        if m["padre"] is None:
            continue

        x, y, z = m["origen"]
        A("")
        A(f'  <joint name="joint_{nombre}" type="{m["junta"]}">')
        A(f'    <parent link="{m["padre"]}"/>')
        A(f'    <child link="{nombre}"/>')
        if m.get("origen_expr"):
            A(f'    <origin xyz="{m["origen_expr"]}" rpy="0 0 0"/>')
        else:
            A(f'    <origin xyz="{f(x)} {f(y)} {f(z)}" rpy="0 0 0"/>')
        if m["junta"] == "continuous":
            ex, ey, ez = m["eje"]
            A(f'    <axis xyz="{f(ex)} {f(ey)} {f(ez)}"/>')
            A('    <dynamics damping="0.01" friction="0.001"/>')
        A("  </joint>")

        for s in m.get("frames", []):
            A("")
            A(f'  <link name="{s["nombre"]}"/>')
            A(f'  <joint name="joint_{s["nombre"]}" type="fixed">')
            A(f'    <parent link="{nombre}"/>')
            A(f'    <child link="{s["nombre"]}"/>')
            r, p, yw = s["rpy"]
            A(f'    <origin xyz="0 0 0" rpy="{f(r)} {f(p)} {f(yw)}"/>')
            A("  </joint>")

    if avisos:
        A("")
        A("  <!-- ===================== REVISAR ================================= -->")
        for a in avisos:
            A(f"  <!-- {a} -->")

    A("")
    A("</robot>")

    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


def escribir_principal(ruta, nombre_robot, parametros):
    """Archivo del equipo: parametros + includes. Solo se crea si no existe."""
    if os.path.exists(ruta):
        return False

    L = ['<?xml version="1.0"?>',
         "<!-- Archivo principal del modelo. Este SI se edita a mano.        -->",
         "<!-- La geometria vive en generated/ y la regenera el script.      -->",
         f'<robot name="{nombre_robot}" xmlns:xacro="http://www.ros.org/wiki/xacro">',
         "",
         "  <!-- ============== PARAMETROS DEL ROBOT (editables) ============== -->",
         "  <!-- Cambiar un valor y recompilar; el efecto se ve en RViz.       -->"]
    for clave, (valor, nota) in parametros.items():
        L.append(f'  <xacro:property name="{clave}" value="{f(valor)}"/>   <!-- {nota} -->')
    L += ["",
          "  <!-- ============== GEOMETRIA MEDIDA DESDE EL CAD ================= -->",
          '  <xacro:include filename="$(find robot_description)/urdf/generated/colmibot_geometria.urdf.xacro"/>',
          "",
          "  <!-- ============== AGREGADOS DEL EQUIPO ========================== -->",
          "  <!-- Aqui van sensores extra, plugins de Gazebo, frames propios.   -->",
          "  <!-- Nada de esto se pierde al regenerar la geometria.             -->",
          "",
          "</robot>", ""]
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    return True


def escribir_soporte(salida, nombre_robot):
    """package.xml, CMakeLists.txt, launch y configuracion de RViz."""
    with open(os.path.join(salida, "package.xml"), "w", encoding="utf-8") as fh:
        fh.write(f"""<?xml version="1.0"?>
<package format="3">
  <name>robot_description</name>
  <version>0.1.0</version>
  <description>Representacion virtual del robot {nombre_robot} para ROS 2.</description>
  <maintainer email="equipo@itam.mx">Equipo Colmibot</maintainer>
  <license>MIT</license>

  <buildtool_depend>ament_cmake</buildtool_depend>

  <exec_depend>robot_state_publisher</exec_depend>
  <exec_depend>joint_state_publisher_gui</exec_depend>
  <exec_depend>rviz2</exec_depend>
  <exec_depend>xacro</exec_depend>
  <exec_depend>launch</exec_depend>
  <exec_depend>launch_ros</exec_depend>

  <export><build_type>ament_cmake</build_type></export>
</package>
""")

    with open(os.path.join(salida, "CMakeLists.txt"), "w", encoding="utf-8") as fh:
        fh.write("""cmake_minimum_required(VERSION 3.8)
project(robot_description)

find_package(ament_cmake REQUIRED)

install(DIRECTORY urdf meshes launch rviz
        DESTINATION share/${PROJECT_NAME})

ament_package()
""")

    with open(os.path.join(salida, "launch", "display.launch.py"), "w",
              encoding="utf-8") as fh:
        fh.write('''"""Carga el modelo y lo abre en RViz con los sliders de articulaciones."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg = get_package_share_directory('robot_description')
    modelo = os.path.join(pkg, 'urdf', 'colmibot.urdf.xacro')
    rviz_cfg = os.path.join(pkg, 'rviz', 'colmibot.rviz')

    # xacro se procesa al vuelo: no hay que regenerar un .urdf a mano.
    robot_description = ParameterValue(
        Command(['xacro ', LaunchConfiguration('modelo')]),
        value_type=str,
    )

    return LaunchDescription([
        DeclareLaunchArgument('modelo', default_value=modelo),
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            parameters=[{'robot_description': robot_description}],
        ),
        Node(
            package='joint_state_publisher_gui',
            executable='joint_state_publisher_gui',
        ),
        Node(
            package='rviz2',
            executable='rviz2',
            arguments=['-d', rviz_cfg],
        ),
    ])
''')

    with open(os.path.join(salida, "rviz", "colmibot.rviz"), "w",
              encoding="utf-8") as fh:
        fh.write("""Panels:
  - Class: rviz_common/Displays
    Name: Displays
Visualization Manager:
  Global Options:
    Fixed Frame: base_footprint
    Background Color: 48; 48; 48
  Displays:
    - Class: rviz_default_plugins/Grid
      Name: Grid
      Enabled: true
      Cell Size: 0.1
    - Class: rviz_default_plugins/RobotModel
      Name: RobotModel
      Enabled: true
      Description Topic:
        Value: /robot_description
    - Class: rviz_default_plugins/TF
      Name: TF
      Enabled: true
      Marker Scale: 0.2
  Views:
    Current:
      Class: rviz_default_plugins/Orbit
      Distance: 0.8
      Focal Point: {X: 0, Y: 0, Z: 0.05}
      Pitch: 0.4
      Yaw: 0.9
""")


# --------------------------------------------------------------------------
# Principal
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("config", help="robot.yaml")
    ap.add_argument("stl", help="carpeta con las STL exportadas de SolidWorks")
    ap.add_argument("salida", help="carpeta del paquete robot_description")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    nombre_robot = cfg.get("robot", "robot")
    cad = cfg["cad"]
    escala = FACTOR_UNIDAD[cad.get("unidades", "mm")]
    R = matriz_cad_a_ros(cad["frente"], cad["arriba"])
    densidades = cfg["materiales"]
    max_caras = int(cfg.get("decimado_max_caras", 4000))

    T = np.eye(4)
    T[:3, :3] = R * escala          # rotar al marco de ROS y pasar a metros

    for sub in ("meshes", "urdf", os.path.join("urdf", "generated"),
                "launch", "rviz", "tools"):
        os.makedirs(os.path.join(args.salida, sub), exist_ok=True)

    archivos = [f for f in os.listdir(args.stl) if f.lower().endswith(".stl")]
    if not archivos:
        sys.exit(f"No hay archivos .stl en {args.stl}")

    usados = set()
    centroides = {}
    modulos = []
    avisos = []

    print(f"\n{len(archivos)} STL encontradas en {args.stl}\n")

    for nombre, spec in cfg["modulos"].items():
        malla, seleccion = cargar_grupo(args.stl, spec["patrones"], archivos)
        if malla is None:
            avisos.append(f"modulo '{nombre}': ninguna STL coincidio con sus patrones")
            print(f"  [ ] {nombre}: SIN ARCHIVOS")
            continue
        usados.update(seleccion)

        malla.apply_transform(T)
        centroide = np.array(malla.centroid, dtype=float)
        malla.apply_translation(-centroide)      # el eslabon nace en su centroide
        centroides[nombre] = centroide

        # Quitar tornillos y pines sueltos ANTES de medir y decimar: no cambian
        # como se ve la pieza pero inflan el conteo de triangulos.
        umbral = float(spec.get("descartar_menores_mm3",
                                cfg.get("descartar_menores_mm3", 0)))
        malla, n_quitadas = quitar_piezas_diminutas(malla, umbral)

        densidad = densidades.get(spec.get("material", "generico"), 1000)
        masa, I, metodo_inercia = inercia_de(malla, densidad)

        # Masa real declarada en el YAML (hoja de datos del fabricante) gana
        # sobre la estimada: la inercia se reescala conservando su forma.
        masa_decl = spec.get("masa_g")
        if masa_decl:
            masa_decl = float(masa_decl) / 1000.0
            if masa > 1e-9:
                I = I * (masa_decl / masa)
            masa = masa_decl
            metodo_inercia = "declarada"

        col = colision_de(malla, spec.get("colision", "caja"),
                          spec.get("cilindro_eje", "z"))

        # La direccion del sensor se mide ANTES de decimar: el decimado puede
        # mover vertices y girar ligeramente la normal de la placa.
        frames = []
        tipo_sensor = spec.get("sensor")
        if tipo_sensor == "tof":
            d, grosor, conf, metodo = direccion_sensor(malla, centroide)
            if d is None:
                # Nunca fallar en silencio: sin frame el sensor apunta mal.
                print(f"      NO SE PUDO deducir la direccion ({metodo})")
                avisos.append(
                    f"{nombre}: no se pudo deducir la direccion ({metodo}); "
                    f"medir el angulo en SolidWorks y ponerlo a mano")
            else:
                ang = np.degrees(np.arctan2(d[1], d[0]))
                frames.append({"nombre": f"{nombre}_frame",
                               "rpy": rpy_desde_direccion(d)})
                marca = "" if conf > 0.5 else "  <-- VERIFICAR EN CAD"
                print(f"      direccion medida: {ang:+.1f} deg en el plano XY "
                      f"(confianza {conf:.2f}, {metodo}){marca}")
                if conf <= 0.5:
                    avisos.append(
                        f"{nombre}: direccion deducida con baja confianza "
                        f"({conf:.2f}); confirmar el angulo en SolidWorks")
        elif tipo_sensor == "camara":
            # REP-103: el frame optico tiene Z al frente, X a la derecha, Y abajo.
            frames.append({"nombre": f"{nombre}_optical_frame",
                           "rpy": (-1.5707963, 0.0, -1.5707963)})

        # Ya medido todo: ahora si aligerar la malla visual y escribirla.
        caras_antes = len(malla.faces)
        malla, se_decimo = decimar(malla, max_caras)
        archivo = f"{nombre}.stl"
        malla.export(os.path.join(args.salida, "meshes", archivo))

        modulos.append({
            "link": nombre if nombre != "base" else "base_link",
            "archivo": archivo,
            "padre": None if spec.get("padre") is None else (
                "base_link" if spec["padre"] == "base" else spec["padre"]),
            "junta": spec.get("junta", "fixed"),
            "eje": spec.get("eje", [0, 0, 1]),
            "origen": centroide,
            "masa": masa,
            "inercia": I,
            "colision": col,
            "color": "oscuro" if "llanta" in nombre else "gris",
            "frames": frames,
            "_nombre_cfg": nombre,
        })

        nota = f"{caras_antes}->{len(malla.faces)} caras" if se_decimo else f"{caras_antes} caras"
        if n_quitadas:
            nota += f" | -{n_quitadas} piezas diminutas"
        print(f"  [x] {nombre}: {len(seleccion)} piezas | {masa*1000:7.1f} g "
              f"({metodo_inercia}) | {nota}")

    # Origenes relativos al padre -------------------------------------------
    for m in modulos:
        if m["padre"] is None:
            m["origen"] = np.zeros(3)
            continue
        padre_cfg = next(k for k, v in cfg["modulos"].items()
                         if (("base_link" if k == "base" else k) == m["padre"]))
        m["origen"] = centroides[m["_nombre_cfg"]] - centroides[padre_cfg]

    # Parametros editables ---------------------------------------------------
    parametros = {}
    try:
        yd = centroides["llanta_der"][1]
        yi = centroides["llanta_izq"][1]
        parametros["separacion_llantas"] = (abs(yd - yi), "distancia entre ruedas (m)")
        for m in modulos:
            if m["link"] in ("llanta_der", "llanta_izq"):
                signo = "-" if m["origen"][1] < 0 else ""
                m["origen_expr"] = (
                    f'{f(m["origen"][0])} '
                    f'${{{signo}separacion_llantas/2}} '
                    f'{f(m["origen"][2])}'
                )
                radio = m["colision"]["radio"]
        parametros["radio_llanta"] = (radio, "radio de la rueda (m)")
        parametros["altura_chasis"] = (
            float(centroides["llanta_der"][2] - radio) * -1,
            "del suelo al origen de base_link (m)")
    except KeyError:
        parametros["altura_chasis"] = (0.0, "del suelo al origen de base_link (m)")
        avisos.append("no se encontraron ambas llantas: revisar sus patrones")

    if "camara" in centroides:
        parametros["altura_camara"] = (
            float(centroides["camara"][2]), "altura de la camara sobre base_link (m)")

    # Validar antes de escribir: estos errores no se ven hasta que RViz o
    # Gazebo fallan con un mensaje que no apunta a la causa.
    for p in validar_modulos(modulos):
        avisos.append(p)

    escribir_geometria(
        os.path.join(args.salida, "urdf", "generated", "colmibot_geometria.urdf.xacro"),
        nombre_robot, modulos, avisos)
    creado = escribir_principal(
        os.path.join(args.salida, "urdf", "colmibot.urdf.xacro"),
        nombre_robot, parametros)
    escribir_soporte(args.salida, nombre_robot)

    sin_usar = sorted(set(archivos) - usados)
    print(f"\n  Eslabones generados : {len(modulos)}")
    print(f"  Masa total          : {sum(m['masa'] for m in modulos)*1000:.0f} g")
    print(f"  STL sin asignar     : {len(sin_usar)}")
    for s in sin_usar[:10]:
        print(f"      - {s}")
    if len(sin_usar) > 10:
        print(f"      ... y {len(sin_usar)-10} mas")

    if avisos:
        print("\n  REVISAR:")
        for a in avisos:
            print(f"      ! {a}")

    print("\n  urdf/generated/colmibot_geometria.urdf.xacro  (regenerado)")
    if creado:
        print("  urdf/colmibot.urdf.xacro                     (creado: editalo tu)")
    else:
        print("  urdf/colmibot.urdf.xacro                     (intacto: tus ediciones se conservan)")
        print("\n  Parametros que mide el CAD (compara con los de tu archivo):")
        for clave, (valor, _) in parametros.items():
            print(f"      {clave} = {f(valor)}")
    print(f"\n  Paquete en: {args.salida}\n")


if __name__ == "__main__":
    main()
