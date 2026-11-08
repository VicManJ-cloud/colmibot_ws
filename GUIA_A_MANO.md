# Guía: construir el modelo del Colmibot a mano, paso a paso

Esta guía explica cómo pasar del diseño del robot en SolidWorks a un modelo que se ve y se mueve en ROS 2,
**sin usar ningún script**: solo SolidWorks, un editor de texto y la máquina virtual con ROS.

- **Para quién es:** para cualquier integrante del equipo, aunque nunca haya usado ROS. Los términos
  técnicos se explican la primera vez que aparecen.
- **Qué se obtiene al final:** el robot en 3D en RViz, con colores, con sus llantas girando y con los
  puntos de referencia de cada sensor, más los datos de masa para simular la física.
- **Cuánto tarda:** la primera vez, una tarde completa (4–6 horas). Las siguientes, mucho menos.
- **Documentos hermanos:**
  - [`PROCESO.md`](PROCESO.md): la bitácora. Cuenta **qué se hizo y por qué**, con los problemas que hubo.
  - [`README.md`](README.md): la presentación del proyecto.
  - Esta guía: **cómo hacerlo uno mismo**, desde cero.

> **Sobre los scripts.** En la carpeta `tools/` hay programas que hacen automáticamente casi todo lo que
> aquí se hace a mano. Al final (Anexo C) hay una tabla que dice qué paso de esta guía reemplaza cada
> uno. Hacerlo a mano al menos una vez sirve para entender qué hacen y para revisar que sus resultados
> sean correctos.

---

## Índice

0. [La idea en una página](#0-la-idea-en-una-página)
1. [Qué programas se usan y para qué](#1-qué-programas-se-usan-y-para-qué)
2. [Cinco conceptos que hay que entender antes](#2-cinco-conceptos-que-hay-que-entender-antes)
3. [Los archivos del paquete: qué es cada uno y cómo se conectan](#3-los-archivos-del-paquete-qué-es-cada-uno-y-cómo-se-conectan)
4. [Fase 1 — Preparar una copia de trabajo del CAD](#fase-1--preparar-una-copia-de-trabajo-del-cad)
5. [Fase 2 — Revisar el robot y decidir qué se dibuja](#fase-2--revisar-el-robot-y-decidir-qué-se-dibuja)
6. [Fase 3 — Crear los sistemas de coordenadas en SolidWorks](#fase-3--crear-los-sistemas-de-coordenadas-en-solidworks)
7. [Fase 4 — Medir y anotar](#fase-4--medir-y-anotar)
8. [Fase 5 — Masas, centro de masa e inercia](#fase-5--masas-centro-de-masa-e-inercia)
9. [Fase 6 — Exportar los modelos 3D (STL) por grupos](#fase-6--exportar-los-modelos-3d-stl-por-grupos)
10. [Fase 7 — Escribir los archivos del paquete](#fase-7--escribir-los-archivos-del-paquete)
11. [Fase 8 — Probar en la máquina virtual](#fase-8--probar-en-la-máquina-virtual)
12. [Fase 9 — Cuando algo cambia en el diseño](#fase-9--cuando-algo-cambia-en-el-diseño)
13. [Anexos: hojas para llenar, equivalencias, problemas comunes](#anexos)

---

## 0. La idea en una página

El robot ya existe **dibujado** en SolidWorks. ROS no puede leer archivos de SolidWorks: necesita que se le
**describa** el robot en un formato propio. Esa descripción tiene dos partes:

| Parte | Qué dice | Ejemplo | Dónde vive |
|---|---|---|---|
| **Estructura** | De qué partes está hecho el robot, cómo se unen, cuáles se mueven, dónde está cada cosa y cuánto pesa | "Hay dos llantas que giran sobre un eje, a 87 mm del centro" | Archivos de texto `.xacro` |
| **Forma** | Cómo se ve cada parte | El dibujo 3D de la llanta | Archivos de modelo 3D `.stl` |

Todo el trabajo consiste en **sacar esas dos cosas del CAD** y ponerlas en una carpeta con un formato que
ROS entiende (un **paquete**).

```
 SolidWorks (CAD_Colmibot)                               Editor de texto
 ┌───────────────────────────┐                          ┌───────────────────────────┐
 │ Fase 3: sistemas de       │                          │ Fase 7: escribir los      │
 │         coordenadas       │                          │         archivos .xacro   │
 │ Fase 4: medir  ───────────┼── hoja de medidas ──────▶│  (estructura, medidas,    │
 │ Fase 5: masas  ───────────┼── hoja de masas ────────▶│   masas, colores)         │
 │ Fase 6: exportar STL ─────┼── archivos .stl ───┐     └─────────────┬─────────────┘
 └───────────────────────────┘                    │                   │
                                                  ▼                   ▼
                                   ┌─────────────────────────────────────────────┐
                                   │ Carpeta del paquete robot_description        │
                                   └──────────────────────┬──────────────────────┘
                                                          │ Fase 8: copiar a la VM
                                                          ▼
                                   Máquina virtual (Ubuntu + ROS 2): compilar y abrir RViz
```

---

## 1. Qué programas se usan y para qué

| Programa | Dónde corre | Para qué se usa en esta guía | Qué hay que saber hacer |
|---|---|---|---|
| **SolidWorks** | Windows | Ver el robot, crear puntos de referencia, medir, sacar masas y exportar los STL | Abrir un ensamble, seleccionar piezas en el árbol, usar *Medir* y *Propiedades físicas* |
| **Editor de texto** (recomendado: **VS Code**; sirve el Bloc de notas) | Windows | Escribir los archivos `.xacro`, `.py`, `.xml` | Abrir, editar y guardar archivos. VS Code colorea el texto y avisa errores |
| **Visor 3D de Windows** (viene con Windows) | Windows | Revisar que cada STL exportado salió bien | Abrir un archivo con doble clic |
| **Báscula de cocina** (en gramos) | — | Pesar las piezas reales | Pesar cada pieza o el robot completo |
| **VirtualBox** + **Ubuntu 24.04** | Windows (la VM es una computadora "simulada") | Tener Linux, que es donde corre ROS 2 | Encender la VM y abrir una terminal |
| **ROS 2 Jazzy** | Dentro de la VM | Leer la descripción del robot y mostrarla | Copiar y pegar los comandos de la Fase 8 |
| **RViz2** | Dentro de la VM (viene con ROS) | Ver el robot en 3D | Girar la vista con el mouse, activar y desactivar paneles |

> **Idioma de SolidWorks.** Los menús de esta guía están en español. Si tu SolidWorks está en inglés:
> *Herramientas = Tools*, *Evaluar = Evaluate*, *Medir = Measure*, *Propiedades físicas = Mass
> Properties*, *Insertar → Geometría de referencia = Insert → Reference Geometry*, *Sistema de coordenadas
> = Coordinate System*, *Suprimir = Suppress*, *Ocultar/Mostrar = Hide/Show*, *Aislar = Isolate*.

---

## 2. Cinco conceptos que hay que entender antes

### 2.1 Link y joint: las piezas y las uniones

ROS ve a un robot como un **esqueleto**:

- Un **link** (eslabón) es una **parte rígida**: algo que se mueve como un solo bloque.
- Un **joint** (articulación) es la **unión entre dos links**: dice dónde está uno respecto al otro y si se
  puede mover (girar, deslizar) o si está fijo.

La regla de oro: **solo se separa en links lo que se mueve por separado** (o lo que necesita un punto de
referencia propio). Todo lo que va atornillado junto es **un solo link**, aunque sean 50 piezas.

En el Colmibot:

```
base_footprint  (un punto en el piso, debajo del robot)
   └─ base_link  (TODO el cuerpo: placas, postes, motores, batería, electrónica...)
        ├─ wheel_left_link    ← gira (joint "continuous")
        ├─ wheel_right_link   ← gira (joint "continuous")
        ├─ camera_link → camera_optical_frame   ← fijos (solo son puntos de referencia)
        ├─ imu_link                              ← fijo
        └─ tof_left_link / tof_center_link / tof_right_link   ← fijos
```

Los motores **no** son links aparte: van atornillados al cuerpo. Lo que gira es la llanta.

### 2.2 Frame: un punto con tres flechas

Un **frame** (marco de referencia) es un punto en el espacio con tres flechas perpendiculares (ejes X, Y, Z).
Cada link tiene el suyo. Los de los sensores son importantes porque dicen **desde dónde y hacia dónde
mide** cada sensor: la flecha X de un ToF apunta hacia donde mide la distancia.

### 2.3 La regla de ejes de ROS (REP-103)

Todos los robots de ROS siguen la misma regla. Hay que respetarla siempre:

| Eje | Apunta hacia | Color en RViz |
|---|---|---|
| **X** | **Adelante** del robot (en el Colmibot, hacia los ToF) | Rojo |
| **Y** | **Izquierda** del robot | Verde |
| **Z** | **Arriba** | Azul |

Truco para recordarlo: con la mano derecha, el índice hacia adelante (X), el dedo medio a la izquierda (Y) y
el pulgar hacia arriba (Z).

**El CAD del Colmibot usa otros ejes:** en SolidWorks, arriba es **+Y** y adelante es **−Z**. Por eso en la
Fase 3 se crea un sistema de coordenadas nuevo con los ejes de ROS. Sin eso, el robot saldría acostado o de
lado.

### 2.4 Unidades: metros, kilogramos y radianes

ROS **siempre** usa:

| Magnitud | Unidad de ROS | Conversión |
|---|---|---|
| Distancia | **metros** | 87 mm = 0.087 m (dividir entre 1000) |
| Masa | **kilogramos** | 205 g = 0.205 kg (dividir entre 1000) |
| Ángulo | **radianes** | radianes = grados × 3.1416 ÷ 180. Por ejemplo, 30° = 0.5236 y 6.1° = 0.1064 |
| Inercia | **kg·m²** | SolidWorks puede mostrarla directamente en estas unidades (Fase 5) |

Error más común de todo el proyecto: escribir milímetros donde van metros. El robot sale **1000 veces más
grande**.

### 2.5 STL y xacro: los dos tipos de archivo

- **STL**: un modelo 3D hecho solo de triángulos. No tiene colores, ni unidades, ni nombres: solo forma.
  Por eso hay que cuidar en qué unidad y en qué ejes se exporta.
- **URDF**: el formato de ROS para describir robots. Es un archivo de texto con etiquetas `<...>` (formato
  **XML**, el mismo estilo que HTML).
- **xacro**: un URDF con atajos. Permite poner **variables** (escribir `0.087` una vez y usarlo en varios
  lugares), **plantillas** (escribir la llanta una vez y usarla dos veces) y **dividir** el robot en varios
  archivos. ROS convierte el xacro en URDF justo antes de usarlo.

Ejemplo mínimo de cómo se ve un link y un joint:

```xml
<link name="wheel_left_link">            <!-- una parte rígida llamada así -->
  <visual> ... </visual>                 <!-- cómo se ve -->
  <collision> ... </collision>           <!-- su forma para choques (simplificada) -->
  <inertial> ... </inertial>             <!-- cuánto pesa y cómo está repartido el peso -->
</link>

<joint name="wheel_left_joint" type="continuous">   <!-- gira sin límite -->
  <parent link="base_link"/>                       <!-- unido a... -->
  <child link="wheel_left_link"/>                  <!-- ...este -->
  <origin xyz="0 0.087 0" rpy="0 0 0"/>            <!-- dónde: 87 mm a la izquierda del centro -->
  <axis xyz="0 1 0"/>                              <!-- gira alrededor del eje Y -->
</joint>
```

`xyz` es la posición en metros; `rpy` son los giros en radianes (*roll* alrededor de X, *pitch*
alrededor de Y, *yaw* alrededor de Z).

---

## 3. Los archivos del paquete: qué es cada uno y cómo se conectan

### 3.0 Dónde está cada cosa en la computadora

Todo el proyecto vive en `C:\Cad_colmibot2\`, en tres carpetas:

| Carpeta | Qué es | ¿Va a GitHub? | ¿Se modifica? |
|---|---|---|---|
| `CAD_Colmibot\` | El diseño original de SolidWorks y el BOM | No (pesa ~90 MB y es de SolidWorks) | **Nunca.** Para trabajar se hace una copia (Fase 1) |
| `stl_cad_actual\` | Los 95 STL "crudos" exportados del CAD actual, uno por pieza | No (~60 MB; se regeneran desde el CAD) | Solo se vuelve a exportar si cambia el CAD |
| `colmibot_ws\` | El workspace de ROS 2: el paquete, la documentación y los scripts | **Sí: este es el repositorio** | Aquí se trabaja |

En el camino a mano (esta guía) aparece una cuarta carpeta, `CAD_Colmibot_ROS\`: la copia de trabajo del CAD
con los sistemas de coordenadas y la configuración "ROS" (Fase 1).

### 3.1 El árbol de carpetas

```
colmibot_ws/                          ← "workspace": la carpeta de trabajo de ROS (= el repositorio)
├── README.md                         ← presentación del proyecto (lo que ve el profesor)
├── PROCESO.md                        ← bitácora: qué se hizo y por qué
├── GUIA_A_MANO.md                    ← esta guía
├── .gitignore                        ← lo que Git no sube (carpetas de compilación, notas internas)
└── src/                              ← ROS busca los paquetes aquí
    └── robot_description/            ← NUESTRO PAQUETE
        ├── package.xml               ← la "credencial" del paquete
        ├── CMakeLists.txt            ← instrucciones de instalación
        ├── launch/
        │   └── display.launch.py     ← arranca todo con una orden
        ├── rviz/
        │   └── display.rviz          ← vista guardada de RViz
        ├── meshes/                   ← los modelos 3D (STL)
        │   ├── impreso_3d.stl, placas_laser.stl, motores.stl, ...
        │   └── wheel_left.stl, wheel_right.stl
        ├── urdf/                     ← la descripción del robot
        │   ├── colmibot.urdf.xacro   ← ARCHIVO PRINCIPAL: el esqueleto
        │   ├── colmibot_params.xacro ← medidas aproximadas (para el modo sin modelos 3D)
        │   ├── materials.xacro       ← colores
        │   ├── macros.xacro          ← plantillas (llanta, frame de sensor)
        │   └── generated/
        │       ├── colmibot_meshes.xacro    ← medidas reales del CAD + lista de STL
        │       └── colmibot_inertial.xacro  ← masas e inercias del CAD
        ├── inertia/                  ← (solo para los scripts) datos de masas
        │   ├── componentes_cad.csv   ←   generado: forma y masa del CAD de cada pieza
        │   ├── masas.csv             ←   SE LLENA A MANO: pesos reales
        │   └── masas_usadas.csv      ←   generado: reporte de qué masa se usó y de dónde salió
        └── tools/                    ← (solo para los scripts; ver Anexo C)
            ├── export_stl_solidworks.ps1, export_mass_solidworks.ps1   (Windows + SolidWorks)
            └── prepare_meshes.py, compute_inertial.py                   (Python, cualquier sistema)
```

La carpeta `generated/` se llama así porque normalmente la **escriben los scripts**. A mano, se escriben
esos mismos dos archivos con los números que se midieron. **Se mantienen los mismos nombres** para que el
resto del paquete funcione igual, venga el número de un script o de una medición.

### 3.2 Para qué sirve cada archivo y quién lo escribe

| Archivo | En palabras simples | Se escribe | Cuándo cambia |
|---|---|---|---|
| `package.xml` | "Este paquete se llama así, lo hizo tal equipo y necesita estos otros programas de ROS" | A mano, una vez | Casi nunca (solo poner el correo real) |
| `CMakeLists.txt` | "Al instalar el paquete, copia estas carpetas" | A mano, una vez | Si se agrega una carpeta nueva que ROS deba ver |
| `colmibot.urdf.xacro` | El esqueleto: qué links y joints hay y en qué orden | A mano, una vez | Si se agrega un sensor o una parte móvil |
| `colmibot_params.xacro` | Medidas **aproximadas** para dibujar el robot con cajas y cilindros | A mano, una vez | Rara vez |
| `materials.xacro` | La "paleta de colores" | A mano | Cuando se quiere cambiar un color |
| `macros.xacro` | Plantillas: "así se hace una llanta", "así se hace un frame de sensor" | A mano, una vez | Casi nunca |
| `generated/colmibot_meshes.xacro` | Medidas **reales** del CAD (llantas, sensores) y la lista de STL con su color | A mano (Fase 7) **o** script | Cada vez que cambia el CAD |
| `generated/colmibot_inertial.xacro` | Masa, centro de masa e inercia de cada link | A mano (Fase 7) **o** script | Cuando cambia el CAD o se pesan piezas |
| `meshes/*.stl` | La forma de cada grupo de piezas | Exportados de SolidWorks (Fase 6) | Cada vez que cambia el CAD |
| `display.launch.py` | "Arranca estos 3 programas y pásales el robot" | A mano, una vez | Casi nunca |
| `display.rviz` | Qué muestra RViz al abrir y desde qué ángulo | Se guarda desde RViz | Cuando se quiere otra vista |

### 3.3 Cómo se conectan entre sí

**a) Los archivos de descripción se "incluyen" unos en otros.** El archivo principal no tiene todo adentro:
va trayendo a los demás, como capítulos de un libro. El orden importa: **si una medida aparece dos veces,
gana la última que se leyó.** Así, la medida real del CAD (`colmibot_meshes.xacro`) reemplaza a la
aproximada (`colmibot_params.xacro`).

```
colmibot.urdf.xacro  (el principal)
 │
 ├─ 1. incluye colmibot_params.xacro      → medidas aproximadas (wheel_radius = 0.030, ...)
 ├─ 2. incluye materials.xacro            → colores (impreso_3d = gris oscuro, ...)
 ├─ 3. incluye macros.xacro               → plantillas drive_wheel y sensor_frame
 ├─ 4. incluye generated/colmibot_inertial.xacro  → plantillas base_inertial, wheel_left_inertial, ...
 └─ 5. SI use_meshes:=true, incluye generated/colmibot_meshes.xacro
          → REEMPLAZA las medidas del paso 1 por las reales
          → define body_meshes: la lista de STL del cuerpo con su color
               └─ cada STL apunta a meshes/<grupo>.stl
```

**b) El color de cada STL se busca por nombre.** En `colmibot_meshes.xacro`, cada STL dice
`<material name="motores"/>`, y ese nombre tiene que existir en `materials.xacro`. Si no coincide letra por
letra, la pieza sale sin color o con error.

**c) Al arrancar, los programas de ROS se pasan la información así:**

```
display.launch.py
 ├─ corre "xacro" sobre colmibot.urdf.xacro  → produce el URDF completo (un solo texto)
 │
 ├─ robot_state_publisher  ← recibe ese URDF
 │     publica /robot_description (el modelo) y /tf (dónde está cada frame)
 │
 ├─ joint_state_publisher_gui  ← ventanita con barras deslizantes
 │     publica /joint_states (cuánto ha girado cada llanta)
 │     └─▶ robot_state_publisher lo usa para mover las llantas en /tf
 │
 └─ rviz2 -d display.rviz  ← abre RViz con la vista guardada
       dibuja /robot_description en la posición que dice /tf
       └─ las mallas las busca con "package://robot_description/meshes/..."
```

Un **tópico** (como `/tf`) es un "canal de radio" por donde un programa de ROS le manda datos a otro.

### 3.4 Anatomía de cada archivo

#### `package.xml`

```xml
<?xml version="1.0"?>
<package format="3">
  <name>robot_description</name>                 <!-- DEBE llamarse igual que la carpeta -->
  <version>0.1.0</version>
  <description>Modelo URDF/xacro del Colmibot.</description>
  <maintainer email="correo@real.com">Equipo Colmibot</maintainer>   <!-- poner un correo real -->
  <license>MIT</license>

  <buildtool_depend>ament_cmake</buildtool_depend>   <!-- cómo se compila -->

  <!-- Programas de ROS que este paquete necesita para funcionar -->
  <exec_depend>xacro</exec_depend>
  <exec_depend>robot_state_publisher</exec_depend>
  <exec_depend>joint_state_publisher</exec_depend>
  <exec_depend>joint_state_publisher_gui</exec_depend>
  <exec_depend>rviz2</exec_depend>
  <exec_depend>launch</exec_depend>
  <exec_depend>launch_ros</exec_depend>

  <export><build_type>ament_cmake</build_type></export>
</package>
```

#### `CMakeLists.txt`

```cmake
cmake_minimum_required(VERSION 3.8)
project(robot_description)                 # mismo nombre que en package.xml
find_package(ament_cmake REQUIRED)

# Copiar estas carpetas a la instalación. Si una carpeta no está aquí, ROS no la encuentra.
install(DIRECTORY launch meshes rviz urdf
        DESTINATION share/${PROJECT_NAME})

ament_package()
```

> **Importante:** ROS **no** lee los archivos de `src/`: lee una **copia** que se hace al compilar
> (`colcon build`). Si cambias algo y no recompilas, ROS sigue usando la versión vieja.

#### `materials.xacro`: los colores

```xml
<robot xmlns:xacro="http://www.ros.org/wiki/xacro">
  <!-- rgba = rojo, verde, azul, opacidad; cada uno de 0 a 1 -->
  <material name="impreso_3d"><color rgba="0.15 0.15 0.15 1.0"/></material>
  <material name="placas_laser"><color rgba="0.85 0.70 0.50 1.0"/></material>
  <material name="electronica"><color rgba="0.05 0.45 0.20 1.0"/></material>
  <material name="motores"><color rgba="0.70 0.70 0.72 1.0"/></material>
  <material name="ruedas_locas"><color rgba="0.55 0.55 0.58 1.0"/></material>
  <material name="camara"><color rgba="0.08 0.08 0.08 1.0"/></material>
  <material name="rueda"><color rgba="0.10 0.10 0.10 1.0"/></material>
</robot>
```

Para sacar un color de una foto: cualquier selector de color da valores de 0 a 255; se dividen entre 255.
Por ejemplo, un madera (217, 178, 128) queda como `0.85 0.70 0.50`.

#### `colmibot_params.xacro`: las medidas aproximadas

Son **variables** (`xacro:property`): un nombre y un valor. Sirven para el modo `use_meshes:=false`, que
dibuja el robot con figuras simples. Así se puede probar todo aunque todavía no haya STL.

```xml
<robot xmlns:xacro="http://www.ros.org/wiki/xacro">
  <xacro:property name="wheel_radius" value="0.030"/>   <!-- metros -->
  <xacro:property name="wheel_width"  value="0.012"/>
  <xacro:property name="wheel_left_y" value="0.087"/>
  ...
  <xacro:property name="caster_radius" value="0.012"/>  <!-- ruedas locas -->
  <xacro:property name="caster_x"      value="0.080"/>
  ...
  <xacro:property name="tof_side_yaw"  value="0.5236"/> <!-- 30 grados -->
  <xacro:property name="camera_pitch"  value="0.1064"/> <!-- 6.1 grados hacia abajo -->
</robot>
```

Se usan escribiéndolas entre `${ }`: `<origin xyz="0 ${wheel_left_y} 0"/>`.

#### `macros.xacro`: las plantillas

Una **macro** es una plantilla con huecos. Se escribe una vez y se usa varias veces cambiando los huecos.

- `drive_wheel` (hueco: `side` = left o right, y la posición): crea el link de la llanta, con su malla o un
  cilindro, su forma de choque, su inercia, y el joint que gira sobre Y.
- `sensor_frame` (huecos: nombre, padre, posición y giros): crea un link vacío (solo un frame) unido con un
  joint fijo.

```xml
<xacro:macro name="sensor_frame" params="name parent x y z roll:=0 pitch:=0 yaw:=0">
  <link name="${name}"/>
  <joint name="${name}_joint" type="fixed">
    <parent link="${parent}"/>
    <child link="${name}"/>
    <origin xyz="${x} ${y} ${z}" rpy="${roll} ${pitch} ${yaw}"/>
  </joint>
</xacro:macro>
```

#### `colmibot.urdf.xacro`: el esqueleto

Lee todo lo anterior y arma el árbol de la sección 2.1. En resumen:

```xml
<robot name="colmibot" xmlns:xacro="http://www.ros.org/wiki/xacro">
  <xacro:arg name="use_meshes" default="true"/>          <!-- opción al arrancar -->
  <!-- incluye params, materials, macros, inertial, y (si use_meshes) meshes: ver 3.3 -->

  <link name="base_footprint"/>                           <!-- punto en el piso -->
  <joint name="base_joint" type="fixed">                  <!-- base_link 30 mm arriba del piso -->
    <parent link="base_footprint"/><child link="base_link"/>
    <origin xyz="0 0 ${wheel_radius}"/>
  </joint>

  <link name="base_link">
    <!-- visual: con use_meshes, la lista body_meshes; sin él, una caja y dos esferas -->
    <!-- collision: siempre una caja y dos esferas (más ligero para simular) -->
    <xacro:base_inertial/>                               <!-- masa de TODO el cuerpo -->
  </link>

  <xacro:drive_wheel side="left"  x="${wheel_left_x}"  y="${wheel_left_y}"  z="${wheel_left_z}"  .../>
  <xacro:drive_wheel side="right" x="${wheel_right_x}" y="${wheel_right_y}" z="${wheel_right_z}" .../>

  <xacro:sensor_frame name="camera_link" parent="base_link"
                      x="${camera_x}" y="${camera_y}" z="${camera_z}" pitch="${camera_pitch}"/>
  <xacro:sensor_frame name="camera_optical_frame" parent="camera_link"
                      x="0" y="0" z="0" roll="${-pi/2}" yaw="${-pi/2}"/>
  <xacro:sensor_frame name="imu_link" parent="base_link" x="${imu_x}" y="${imu_y}" z="${imu_z}"/>
  <xacro:sensor_frame name="tof_left_link"   ... yaw="${tof_side_yaw}"/>
  <xacro:sensor_frame name="tof_center_link" .../>
  <xacro:sensor_frame name="tof_right_link"  ... yaw="${-tof_side_yaw}"/>
</robot>
```

`camera_optical_frame` existe porque las cámaras en ROS usan otra convención: **Z hacia donde mira**, X a
la derecha y Y hacia abajo. Ese frame es el mismo punto que `camera_link`, solo que girado.

#### `generated/colmibot_meshes.xacro`: medidas reales y lista de STL

Tiene dos partes: **variables con las medidas reales** (sustituyen a las de `colmibot_params.xacro`) y la
macro **`body_meshes`**, que es la lista de STL del cuerpo con su color.

```xml
<robot xmlns:xacro="http://www.ros.org/wiki/xacro">
  <!-- Medidas reales (de la hoja de medidas, Anexo A), en metros -->
  <xacro:property name="wheel_radius" value="0.03000"/>
  <xacro:property name="wheel_width"  value="0.01200"/>
  <xacro:property name="wheel_left_x" value="0.0"/> <xacro:property name="wheel_left_y" value="0.08705"/> <xacro:property name="wheel_left_z" value="0.0"/>
  ... (llanta derecha, tamaño del cuerpo, cámara, IMU, 3 ToF)

  <xacro:macro name="body_meshes">
    <!-- Un bloque <visual> por cada STL del cuerpo. Los STL ya vienen en la posición correcta,
         por eso el origin es 0 0 0. -->
    <visual>
      <origin xyz="0 0 0" rpy="0 0 0"/>
      <geometry><mesh filename="package://robot_description/meshes/impreso_3d.stl"/></geometry>
      <material name="impreso_3d"/>
    </visual>
    ... (uno por cada grupo de la Fase 6)

    <!-- Una pieza que se dibuja como caja: el origin es el CENTRO de la caja, size es su tamaño -->
    <visual>
      <origin xyz="0.00968 -0.04597 0.05252" rpy="0 0 0"/>
      <geometry><box size="0.07183 0.05418 0.02026"/></geometry>
      <material name="electronica"/>
    </visual>
  </xacro:macro>
</robot>
```

`package://robot_description/meshes/...` significa "dentro de la carpeta instalada del paquete
`robot_description`". Así funciona en cualquier computadora, sin importar dónde esté la carpeta.

#### `generated/colmibot_inertial.xacro`: masas e inercias

Tres macros, una por cada link que pesa. El esqueleto las usa con `<xacro:base_inertial/>` y la plantilla de
la llanta con `wheel_left_inertial` / `wheel_right_inertial`.

```xml
<robot xmlns:xacro="http://www.ros.org/wiki/xacro">
  <xacro:macro name="base_inertial">
    <inertial>
      <origin xyz="CMx CMy CMz" rpy="0 0 0"/>   <!-- centro de masa, en metros, desde base_link -->
      <mass value="M"/>                          <!-- kg -->
      <inertia ixx="..." ixy="..." ixz="..." iyy="..." iyz="..." izz="..."/>   <!-- kg·m² -->
    </inertial>
  </xacro:macro>
  <xacro:macro name="wheel_left_inertial">  ... (igual, medido desde el centro de la llanta) </xacro:macro>
  <xacro:macro name="wheel_right_inertial"> ... </xacro:macro>
</robot>
```

#### `display.launch.py`

Es un programa de Python que **declara** qué arrancar. Tiene opciones que se pueden cambiar al lanzarlo:

| Opción | Valor por defecto | Qué hace |
|---|---|---|
| `use_meshes` | `true` | `true` = con los STL; `false` = con cajas y cilindros |
| `gui` | `true` | Abrir la ventanita con barras para girar las llantas |
| `rviz` | `true` | Abrir RViz |

Ejemplo: `ros2 launch robot_description display.launch.py use_meshes:=true`.

#### `display.rviz`

Es la vista guardada de RViz. Lo más importante que guarda es el ***Fixed Frame* = `base_footprint`**: la
cuadrícula de RViz se dibuja en ese frame, o sea, en el piso. Se crea así: se abre RViz, se acomoda la
vista y se usa *File → Save Config As*.

---

## Fase 1 — Preparar una copia de trabajo del CAD

En las Fases 3 a 6 se agregan cosas al ensamble (puntos, sistemas de coordenadas, una configuración). Para
**no tocar el diseño original**:

1. Copiar la carpeta `CAD_Colmibot` completa y llamar a la copia **`CAD_Colmibot_ROS`**.
2. Trabajar **siempre** en la copia. Abrir `CAD_Colmibot_ROS\CLM-EnsambleColmibot.SLDASM`.
3. Revisar que abra sin errores: el árbol de la izquierda (*FeatureManager*) no debe tener piezas con
   signo de interrogación o en rojo.

> Si el diseño original cambia, se vuelve a copiar y se repiten las fases (ver Fase 9).

---

## Fase 2 — Revisar el robot y decidir qué se dibuja

### 2.1 Conocer las piezas

Abrir `BOM.xlsx` (la lista de materiales) junto al ensamble. Cada pieza tiene un tipo: **Comercial** (se
compra), **3D** (impresa) o **CorteLaser**.

Cuidado con dos detalles del CAD actual:

- **`CLM-Body` está oculto** en el ensamble (para ver adentro mientras se diseña). En el árbol aparece con
  el ícono más claro. Hay que **mostrarlo** (clic derecho → *Mostrar componentes*), porque SolidWorks **no
  exporta lo que está oculto**.
- `CLM-HolderVoltageRegulator.SLDPRT` está en la carpeta pero **no se usa** (no está en el ensamble ni en el
  BOM).

### 2.2 Decidir qué pasa con cada pieza

Cada pieza tiene uno de tres destinos. Esta es la decisión del equipo (2026-11-07):

| Destino | Piezas | Por qué |
|---|---|---|
| **Se dibuja** | Estructura (`CLM-Base`, `CLM-Body`, `CLM-Plato`, `CLM-PisoCam`, `CLM-BaseCam`, 12 postes, 2 brackets, 4 separadores, holders, `CLM-ShieldESP32`, carcasa de la Pi `CLM-PI5_Case*`), llantas, motores, ruedas locas, sensores (3 ToF, IMU, cámara) e interruptores KCD1 | Forman la figura del robot o son sensores |
| **Se quita** (no se dibuja) | `CLM-Cytron_MDD10A`, `CLM-BMS_3S_25A`, 3× `CLM-18650Battery`, `CLM-RasPi5`, `CLM-RasPi5_Cooler` | Quedan escondidas dentro del cuerpo o tapadas por la carcasa. La Pi y su cooler son, además, 42 piezas pesadas de dibujar |
| **Se dibuja como caja** | `CLM-ESP32_Wroom_30pins` + `CLM-ExpansionBoardESP32` (una caja), `CLM-StepUp_XL4015` (otra caja) | Están a la vista en el piso de arriba; una caja del mismo tamaño basta |

**Quitar una pieza del dibujo no le quita su peso**: su masa se cuenta igual en la Fase 5.

### 2.3 Decidir los grupos de color

Cada grupo será **un STL** y **un color**. El nombre del grupo es el nombre del archivo y el del material en
`materials.xacro`.

| Grupo (= nombre del STL y del color) | Piezas |
|---|---|
| `impreso_3d` | `CLM-Body`, brackets, separadores, postes, holders (18650, BMS, 3TOF), `CLM-ShieldESP32`, `CLM-PI5_CaseBase`, `CLM-PI5_CaseTop`, `CLM-BaseCam` |
| `placas_laser` | `CLM-Base`, `CLM-Plato`, `CLM-PisoCam` |
| `motores` | 2× `Motorreductor 37D con encoder` |
| `ruedas_locas` | 2× `CLM-RuedaLoca` |
| `camara` | `CLM-LogitechC920Montaj` (cámara, lente y brazo) |
| `electronica` | 3× `CLM-VL53L1XV2` (ToF), `CLM-IMU_BMI270`, 2× `CLM-KCD1` |
| `wheel_left` | `CLM-Llanta60mmD` de la **izquierda** (sola) |
| `wheel_right` | `CLM-Llanta60mmD` de la **derecha** (sola) |

Las llantas van solas porque **giran**: son su propio link y necesitan su propio STL, centrado en su eje.

> **Ojo con "BaseCam".** `CLM-BaseCam` es impresa (grupo `impreso_3d`). `CLM-Base` y `CLM-PisoCam` son de
> corte láser. Los nombres se parecen; hay que fijarse bien.

---

## Fase 3 — Crear los sistemas de coordenadas en SolidWorks

Un **sistema de coordenadas** en SolidWorks es exactamente un frame (sección 2.2): un punto con tres ejes.
Se van a crear tres:

| Nombre | Dónde va el origen | Para qué |
|---|---|---|
| **`ROS`** | En el centro del eje de las llantas | Es `base_link`. Todo se mide y se exporta respecto a él |
| **`LLANTA_IZQ`** | En el centro de la llanta izquierda | Exportar la llanta centrada en su eje y medir su inercia |
| **`LLANTA_DER`** | En el centro de la llanta derecha | Igual, para la derecha |

**Los tres llevan los ejes de ROS:** X adelante (hacia los ToF), Y a la izquierda, Z arriba.

### 3.1 Puntos en el centro de cada llanta

1. **Insertar → Geometría de referencia → Punto**.
2. Elegir el tipo **"Centro de arco"** y hacer clic en una **arista circular** de la llanta izquierda que
   esté en su eje: el borde del agujero central o el borde del rin. **No** en la banda de rodadura si tiene
   dibujo, porque no es un círculo perfecto.
3. Aceptar (✓). Renombrar el punto (clic lento sobre el nombre en el árbol) como **`P_LLANTA_IZQ`**.

   El borde que elijas está en una cara de la llanta, no en su centro a lo ancho. Para que el punto quede
   **a la mitad del ancho**, hay dos opciones: elegir una arista circular que esté a la mitad, o crear un
   punto en cada cara de la llanta y luego su punto medio, como en 3.2.
4. Repetir con la llanta derecha: **`P_LLANTA_DER`**.

### 3.2 Punto medio entre las llantas (el origen de `base_link`)

1. **Insertar → Croquis 3D**. Dibujar una **línea** de `P_LLANTA_IZQ` a `P_LLANTA_DER` (que los extremos se
   "peguen" a los puntos: aparece un ícono de coincidencia). Cerrar el croquis.
2. **Insertar → Geometría de referencia → Punto**, tipo **"Distancia a lo largo de la curva"**, seleccionar
   la línea, elegir **porcentaje = 50 %**. Renombrar: **`P_ORIGEN_ROS`**.

### 3.3 El sistema de coordenadas `ROS`

1. **Insertar → Geometría de referencia → Sistema de coordenadas**.
2. **Origen:** `P_ORIGEN_ROS`.
3. **Eje X:** una arista o un eje que apunte **hacia el frente** (hacia los ToF). En este CAD, el frente es
   la dirección −Z del ensamble: sirve cualquier arista recta que vaya de atrás hacia adelante, por ejemplo
   un borde lateral recto de un bracket de motor. Si la flecha sale hacia atrás, usar el botón **"Invertir
   dirección"**.
4. **Eje Z:** una arista vertical, por ejemplo un poste. Debe apuntar **hacia arriba**; invertir si no.
5. SolidWorks deduce el eje Y. **Comprobar** que la flecha Y apunte a la **izquierda** del robot (viendo el
   robot desde atrás, hacia los ToF).
6. Aceptar. Renombrar como **`ROS`**.

### 3.4 Los sistemas de las llantas

Igual que 3.3, pero con origen en `P_LLANTA_IZQ` (o `P_LLANTA_DER`) y **los mismos ejes** que `ROS`.
Nombres: **`LLANTA_IZQ`** y **`LLANTA_DER`**.

### 3.5 Comprobar

Con **Herramientas → Evaluar → Medir** (ver Fase 4):

- `P_LLANTA_IZQ` respecto a `ROS` debe dar algo como **X ≈ 0, Y ≈ +87 mm, Z ≈ 0**. La derecha, Y ≈ −87 mm.
  Si Y sale negativa en la izquierda, el eje Y quedó al revés: revisar X o Z.
- El punto más bajo de una llanta debe estar en **Z ≈ −30 mm** (el radio): el piso está 30 mm abajo del
  origen.

---

## Fase 4 — Medir y anotar

Todo lo que se mide aquí se anota en la **hoja de medidas (Anexo A)**, en **milímetros** como salen de
SolidWorks. Al final se pasa a metros dividiendo entre 1000.

### 4.1 Cómo usar *Medir* respecto al sistema `ROS`

1. **Herramientas → Evaluar → Medir** (ícono de regla).
2. En la ventanita de *Medir*, abrir el menú de **sistema de coordenadas** (ícono de ejes con flecha) y
   elegir **`ROS`**. A partir de ahí, todas las coordenadas que muestre son respecto a `base_link`.
3. Hacer clic en un **punto** (un vértice o un punto de referencia): muestra **X, Y, Z** de ese punto.
4. Hacer clic en **dos cosas** (dos caras, dos puntos...): muestra la distancia, el ángulo, y **dX, dY,
   dZ**.

> Para medir el **centro** de algo (el centro de un sensor), lo más limpio es crear antes un punto de
> referencia ahí: *Punto → "Centro de cara"* sobre la cara del sensor. Luego se mide ese punto.

### 4.2 Qué medir

| Qué | Cómo | Dónde se usa |
|---|---|---|
| **Radio de la llanta** | Medir el diámetro del borde exterior y dividir entre 2 | `wheel_radius` |
| **Ancho de la llanta** | Distancia entre sus dos caras planas | `wheel_width` |
| **Posición de cada llanta** | Coordenadas de `P_LLANTA_IZQ` y `P_LLANTA_DER` respecto a `ROS` | `wheel_left_x/y/z`, `wheel_right_x/y/z` |
| **Piso** | Punto más bajo de una llanta y de una rueda loca: las dos Z deben ser iguales (≈ −30 mm) | Revisión: el robot no cojea |
| **Tamaño total del cuerpo** (sin llantas) | Medir de la cara más adelantada a la más atrasada (largo), izquierda-derecha (ancho) y piso-techo (alto); y la Z del centro | `chassis_length`, `chassis_width`, `chassis_height`, `chassis_z` (caja de choque) |
| **Centro de cada sensor** | Punto "Centro de cara" sobre la cara frontal del ToF, el chip de la IMU y el lente de la cámara | `tof_*_x/y/z`, `imu_x/y/z`, `camera_x/y/z` |
| **Ángulo de los ToF laterales** | *Medir* entre la cara frontal del ToF central y la de un lateral | `tof_side_yaw` (en el CAD actual: **30°**) |
| **Inclinación de la cámara** | *Medir* entre la cara del lente y un plano vertical del ensamble (por ejemplo, el *Plano frontal*) | `camera_pitch` (en el CAD actual: **6.1° hacia abajo**) |
| **Cajas de la electrónica** | Ver 4.3 | Las `<box>` de `body_meshes` |

**Signos de los ángulos** (regla de la mano derecha alrededor de cada eje):

- `yaw` positivo = girar hacia la **izquierda** visto desde arriba. El ToF izquierdo lleva `+tof_side_yaw` y
  el derecho `−tof_side_yaw`.
- `pitch` positivo = **inclinar la nariz hacia abajo**. La cámara, que mira 6.1° hacia abajo, lleva
  `camera_pitch = +0.1064`.

### 4.3 Medir una caja (ESP32 y XL4015)

Para dibujar una pieza como caja hacen falta su **centro** y su **tamaño** en los ejes de `ROS`:

1. Ocultar todo menos la pieza (clic derecho sobre ella → **Aislar**).
2. Con *Medir* (en `ROS`), anotar la **X más chica y la más grande** (la cara más atrasada y la más
   adelantada), lo mismo en **Y** y en **Z**.
3. **Tamaño** = máximo − mínimo en cada eje. **Centro** = (máximo + mínimo) ÷ 2 en cada eje.
4. La caja de la ESP32 debe abarcar **la ESP32 y su tarjeta de expansión juntas**.
5. Salir de *Aislar*.

---

## Fase 5 — Masas, centro de masa e inercia

### 5.1 ¿Para qué sirve esto?

**RViz no lo necesita**: solo dibuja. Lo usa un **simulador de física** (Gazebo): con la masa y cómo está
repartida, decide si el robot se ladea al frenar, cuánto le cuesta acelerar o girar, etc.

- **Masa**: cuánto pesa (kg).
- **Centro de masa**: el punto donde "se concentra" el peso. Si está muy alto o muy hacia un lado, el robot
  se vuelca con más facilidad.
- **Inercia** (tensor de inercia, 6 números): qué tanto le cuesta girar alrededor de cada eje. No hay que
  entender la fórmula: SolidWorks la calcula.

En el URDF va **una masa, un centro y una inercia por link**: uno para `base_link` (todo el cuerpo,
**incluidas las piezas que no se dibujan**) y uno para cada llanta.

### 5.2 Primero: corregir los materiales del CAD

SolidWorks calcula la masa como **volumen × densidad del material**. En el CAD actual **los materiales son
de relleno** y dan masas muy equivocadas:

| En el CAD | Problema | Qué hacer |
|---|---|---|
| Piezas impresas con "Acrílico" | El BOM dice impresas en 3D | Material **PLA** (o el que usen) |
| `CLM-Base` y `CLM-BaseCam` con "EPDM" (hule) | Material equivocado | Material real (MDF, acrílico o PLA, según el BOM) |
| Electrónica con "Aluminio 6061" macizo | Una placa no es aluminio macizo | **Anular la masa** con el peso real (5.3) |
| Motores y celdas 18650 con "Acero 1020" macizo | Sale 462 g por motor y 128 g por celda | **Anular la masa** con el peso real |
| Raspberry Pi y cooler sin material | Sale 18 g la Pi | **Anular la masa** |
| `CLM-ESP32_Wroom_30pins` y `CLM-PI5_CaseTop` | Son superficies sin volumen: masa 0 | **Anular la masa** |

Cambiar el material: abrir la pieza → en su árbol, clic derecho en **Material** → **Editar material** →
elegir → *Aplicar*.

> **Piezas impresas:** no son macizas, tienen relleno (*infill*). Una pieza al 20 % pesa mucho menos que
> el PLA macizo. Lo más exacto es **pesarla** y anular su masa (5.3).

### 5.3 Poner el peso real a una pieza

1. Abrir la pieza (o seleccionarla en el ensamble).
2. **Herramientas → Evaluar → Propiedades físicas → Anular propiedades físicas**.
3. Activar **"Anular masa"** y escribir el peso real.
4. Aceptar. SolidWorks reparte ese peso en la misma forma de la pieza: el centro de masa sigue en su lugar.

Anotar cada peso, y de dónde salió (báscula, hoja de datos...), en la **hoja de masas (Anexo B)**.

**Si solo se pesa el robot completo:** pesar el robot, comparar con la masa total que da SolidWorks (5.4) y
anular la masa de las piezas comerciales más pesadas (motores, celdas, Pi) hasta que el total coincida. Es
una aproximación, pero mucho mejor que los materiales de relleno.

### 5.4 Medir `base_link`

> **Antes de empezar:** las masas se miden con **todas** las piezas, incluidas las que no se dibujan. Hacerlo
> en la configuración **normal** del ensamble, **no** en la configuración "ROS" de la Fase 6 (ahí hay
> piezas suprimidas, y una pieza suprimida no cuenta).

1. En el árbol del ensamble, seleccionar **todas las piezas menos las dos llantas** (`Ctrl+A` y luego
   `Ctrl+clic` sobre cada `CLM-Llanta60mmD` para quitarlas).
2. **Herramientas → Evaluar → Propiedades físicas**.
3. En **Opciones**: *Usar configuración personalizada* → unidades **kilogramos** y **metros**. Más decimales:
   6 o más.
4. **"Informar valores de coordenadas relativos a"** → **`ROS`**.
5. Revisar que esté marcada la opción de **incluir componentes ocultos**, si aparece.
6. Copiar a la hoja (Anexo B):
   - **Masa** (kg).
   - **Centro de masa**: X, Y, Z (m).
   - El bloque **"Momentos de inercia: (kilogramos × metros²) tomados en el centro de masa y alineados con el
     sistema de coordenadas resultante"**: **Lxx, Lxy, Lxz, Lyy, Lyz, Lzz**.

### 5.5 Medir cada llanta

Igual que 5.4, seleccionando **solo** la llanta izquierda y con *relativo a* = **`LLANTA_IZQ`**. Luego la
derecha con `LLANTA_DER`.

### 5.6 ⚠️ El signo de los productos de inercia

SolidWorks y ROS usan **convenciones distintas** para los tres números "cruzados" (Lxy, Lxz, Lyz):

| En el URDF | Se escribe |
|---|---|
| `ixx`, `iyy`, `izz` | Lxx, Lyy, Lzz **tal cual** |
| `ixy`, `ixz`, `iyz` | **−Lxy, −Lxz, −Lyz** (con el **signo cambiado**) |

Esto se verificó en el proyecto comparando con la inercia calculada directo de las mallas. En este robot
los números cruzados son chicos y el error casi no se nota, pero **en otro robot puede importar mucho**.

---

## Fase 6 — Exportar los modelos 3D (STL) por grupos

### 6.1 Configuración "ROS" sin la electrónica que se quita

Una **configuración** es una "versión" del ensamble dentro del mismo archivo; por ejemplo, una con piezas
suprimidas. Se cambia de una a otra sin perder nada.

1. Pestaña **ConfigurationManager** (arriba del árbol, el ícono de varias hojas) → clic derecho en el nombre
   del ensamble → **Agregar configuración**. Nombre: **`ROS`**.
2. Con `ROS` activa, en el árbol, clic derecho → **Suprimir** en: `CLM-Cytron_MDD10A`, `CLM-BMS_3S_25A`, las
   3 `CLM-18650Battery` (dentro de `CLM-EnsBat3S1P`), `CLM-RasPi5` y `CLM-RasPi5_Cooler`.
3. **Suprimir** también la ESP32, su tarjeta de expansión y el XL4015: se dibujarán como cajas (Fase 4.3).
4. **Mostrar** `CLM-Body` si sigue oculto.

*Suprimir* es más fuerte que *ocultar*: la pieza deja de existir en esa configuración. Por eso **las masas
se miden en la configuración normal** (Fase 5).

### 6.2 Opciones de exportación

**Archivo → Guardar como** → Tipo: **STL (\*.stl)** → botón **Opciones…**:

| Opción | Valor | Por qué |
|---|---|---|
| Formato de salida | **Binario** | Pesa ~5 veces menos que ASCII |
| Unidad | **Metros** | ROS usa metros: así no hay que convertir nada |
| Resolución | **Personalizada**: desviación ≈ 0.2 mm, ángulo 10° | Equilibrio entre suavidad y peso del archivo. Si RViz va lento, subir la desviación |
| **No convertir los datos de salida de STL a espacio positivo** | ✅ **Marcada** | **La más importante.** Si no, SolidWorks mueve la pieza para que todo sea positivo y queda fuera de lugar |
| Guardar todos los componentes de un ensamblaje en un único archivo | ✅ **Marcada** | Aquí sí: se exporta **un grupo a la vez**, y cada grupo debe salir como un solo archivo |
| **Sistema de coordenadas de salida** | **`ROS`** (para las llantas, `LLANTA_IZQ` / `LLANTA_DER`) | Así el STL sale **ya en los ejes de ROS** y con el origen en `base_link` |

### 6.3 Exportar cada grupo

Para **cada grupo** de la tabla de la Fase 2.3:

1. Seleccionar en el árbol todas las piezas del grupo (`Ctrl+clic`).
2. Clic derecho → **Aislar**: se oculta todo lo demás. SolidWorks no exporta lo oculto.
3. **Archivo → Guardar como → STL**, con las opciones de 6.2. **Nombre del archivo = nombre del grupo**
   (`impreso_3d.stl`, `motores.stl`...). Sistema de salida: **`ROS`**.
4. **Salir de Aislar** y pasar al siguiente grupo.

**Las llantas**, una por una: aislar solo la llanta izquierda y exportarla como `wheel_left.stl` con
sistema de salida **`LLANTA_IZQ`**. Luego la derecha como `wheel_right.stl` con **`LLANTA_DER`**.

> **¿Por qué la llanta con su propio sistema?** En el URDF, el *joint* dice dónde está la llanta y la
> malla solo dice su forma. Si la malla de la llanta trajera también su posición, la llanta se movería **dos
> veces** y aparecería lejos del robot (este error ya pasó en el proyecto: ver `PROCESO.md`, paso 5.5).

### 6.4 Revisar los STL

Abrir cada `.stl` con doble clic (**Visor 3D** de Windows):

- ¿Está la pieza completa? ¿Faltan piezas del grupo?
- Las del cuerpo **no** deben estar centradas en el visor: van en su lugar dentro del robot.
- Las llantas **sí** deben verse centradas.
- Tamaño de archivo: si alguno pasa de ~5 MB, exportarlo con una desviación mayor.

Copiar los STL a `src/robot_description/meshes/` y **borrar los que ya no se usen**.

---

## Fase 7 — Escribir los archivos del paquete

Si el paquete **ya existe** (como ahora), solo se actualizan los dos archivos de `urdf/generated/`. Si se
empieza **de cero**, se crean todos con las plantillas de la sección 3.4, en este orden, probando en
cada paso:

| Orden | Archivo | Prueba |
|---|---|---|
| 1 | `package.xml`, `CMakeLists.txt` | `colcon build` termina sin error |
| 2 | `colmibot_params.xacro`, `materials.xacro`, `macros.xacro` y un `colmibot.urdf.xacro` con **solo** `base_link` (una caja) | RViz muestra una caja |
| 3 | Agregar las dos llantas | Las barras deslizantes las hacen girar |
| 4 | Agregar los frames de sensores | Aparecen los ejes de cada sensor |
| 5 | `generated/colmibot_inertial.xacro` | `colcon build` y RViz siguen funcionando |
| 6 | `generated/colmibot_meshes.xacro` + STL | `use_meshes:=true` muestra el robot real |

> **Consejo:** agregar **una cosa a la vez** y probar. Si se escribe todo de golpe y algo falla, no se sabe
> qué fue.

### 7.1 `generated/colmibot_meshes.xacro` a mano

1. Pasar a **metros** cada medida de la hoja (Anexo A) y escribirla como `xacro:property` (sección 3.4).
2. En `body_meshes`, un bloque `<visual>` por cada STL del cuerpo, con `origin 0 0 0` (los STL ya vienen
   en su lugar) y su `material`.
3. Un bloque `<visual>` con `<box>` por cada caja (Fase 4.3): `origin` = centro y `size` = tamaño, en
   metros.

### 7.2 `generated/colmibot_inertial.xacro` a mano

Con los datos de la hoja de masas (Anexo B):

| En el archivo | `base_inertial` | `wheel_left_inertial` / `wheel_right_inertial` |
|---|---|---|
| `<origin xyz>` | Centro de masa medido respecto a `ROS` | Centro de masa medido respecto a `LLANTA_IZQ` / `LLANTA_DER` (casi 0 0 0) |
| `<mass value>` | Masa (kg) | Masa (kg) |
| `ixx`, `iyy`, `izz` | Lxx, Lyy, Lzz | Lxx, Lyy, Lzz |
| `ixy`, `ixz`, `iyz` | **−Lxy, −Lxz, −Lyz** | **−Lxy, −Lxz, −Lyz** |

### 7.3 Revisar antes de copiar a la VM

- Todas las etiquetas que se abren se cierran (`<visual>` … `</visual>`). VS Code ayuda a verlo.
- Todos los números en **metros, kg y radianes**, con **punto decimal** (no coma).
- Cada `material name` existe en `materials.xacro`.
- Cada `meshes/xxx.stl` mencionado existe en la carpeta `meshes/`.

---

## Fase 8 — Probar en la máquina virtual

### 8.1 Pasar la carpeta a la VM

La forma más cómoda para probar seguido es una **carpeta compartida de VirtualBox**: en la configuración de
la VM, *Carpetas compartidas* → agregar `colmibot_ws` → marcar *Automontar*. Aparece dentro de Ubuntu (en
`/media/sf_colmibot_ws`) y se copia a la carpeta personal:

```bash
cp -r /media/sf_colmibot_ws ~/colmibot_ws
```

Otras formas: GitHub (`git clone`) o una memoria USB. Ver `PROCESO.md`, paso 7.2.

### 8.2 Instalar lo que haga falta (una sola vez)

```bash
sudo apt update
sudo apt install ros-jazzy-xacro ros-jazzy-robot-state-publisher \
                 ros-jazzy-joint-state-publisher-gui ros-jazzy-rviz2
```

### 8.3 Compilar y abrir

```bash
source /opt/ros/jazzy/setup.bash          # activar ROS en esta terminal
cd ~/colmibot_ws
colcon build --packages-select robot_description   # "instalar" el paquete
source install/setup.bash                 # que la terminal encuentre el paquete (en CADA terminal nueva)
ros2 launch robot_description display.launch.py use_meshes:=true
```

**Si algo falla, probar primero sin modelos:** `use_meshes:=false`. Si así funciona, el problema está en
los STL o en `colmibot_meshes.xacro`.

**Ver el URDF final** (sirve para encontrar errores): `xacro src/robot_description/urdf/colmibot.urdf.xacro
use_meshes:=true > /tmp/colmibot.urdf` y luego `check_urdf /tmp/colmibot.urdf` (viene en el paquete
`liburdfdom-tools`). Muestra el árbol de links y si hay errores.

### 8.4 Lista de revisión

| Revisar | Cómo | Si está mal |
|---|---|---|
| El robot está parado sobre sus llantas | A simple vista | Ejes del sistema `ROS` (Fase 3.3) |
| El frente (ToF) apunta a la flecha **roja** de `base_link` | Mirar los ejes en el centro | Eje X del sistema `ROS` invertido |
| Las llantas y ruedas locas **tocan la cuadrícula** | Vista de lado | *Fixed Frame* debe ser `base_footprint`; revisar `wheel_radius` |
| Las llantas **giran sobre su eje** con las barras | Mover cada barra | La llanta no se exportó con su propio sistema (Fase 6.3) |
| Las llantas no están "lejos" del robot | A simple vista | Igual que arriba |
| Los ejes de cada sensor están **sobre** el sensor | Panel *TF* → *Show Names* | Medidas de la Fase 4 o paso a metros |
| ToF laterales a ±30° hacia afuera; cámara un poco hacia abajo | Flecha roja de cada frame | Signos de la Fase 4.2 |
| Las cajas verdes están sobre la placa, junto a la carcasa de la Pi | A simple vista | Centro y tamaño de la Fase 4.3 |
| Colores parecidos al robot real | A simple vista | `materials.xacro` |

### 8.5 Mensajes de error comunes

| Mensaje | Causa | Solución |
|---|---|---|
| `Package 'robot_description' not found` | Falta `source install/setup.bash` en esa terminal | Correrlo |
| `ros2: command not found` | Falta activar ROS | `source /opt/ros/jazzy/setup.bash` |
| Error de xacro con un número de línea | Etiqueta mal cerrada, variable mal escrita o una coma en vez de punto | Ir a esa línea del archivo |
| `Could not load resource [package://...stl]` | El STL no está en `meshes/` o el nombre no coincide (ojo con mayúsculas: Linux las distingue) | Revisar nombre y carpeta, y recompilar |
| El robot mide metros de largo | Se exportó en mm o se escribieron mm | Exportar en metros (Fase 6.2) |
| Cambié algo y no se nota | ROS usa la copia instalada | `colcon build` otra vez y relanzar |

---

## Fase 9 — Cuando algo cambia en el diseño

| Qué cambió en el CAD | Fases que hay que repetir |
|---|---|
| Se movió una pieza que **no** es sensor ni llanta | 6 (solo su grupo), 5 (masas) |
| Se movió o giró un **sensor** | 4 (su posición/ángulo), 7.1 |
| Cambiaron las **llantas** o su posición | 3 (sistemas), 4, 5, 6, 7 — prácticamente todo, porque el origen depende de ellas |
| Se agregó una pieza nueva | 2 (decidir su destino y grupo), 6 (su grupo), 5 |
| Se pesaron piezas | 5.3, 5.4, 5.5 y 7.2 |
| Solo un color | `materials.xacro` |

Antes de repetir: volver a copiar `CAD_Colmibot` a `CAD_Colmibot_ROS` (Fase 1) y rehacer los sistemas de
coordenadas y la configuración `ROS`. O, si el equipo lo acepta, crearlos directamente en el CAD original
para no repetirlos cada vez.

---

## Anexos

### Anexo A — Hoja de medidas

Llenar en **mm y grados** desde SolidWorks (respecto al sistema `ROS`); después pasar a **m y rad**. La
columna "Valor actual" es la del paquete hoy (2026-11-07), para comparar.

| Medida | Variable | mm / grados | m / rad | Valor actual (m / rad) |
|---|---|---|---|---|
| Radio de la llanta | `wheel_radius` | | | 0.03000 |
| Ancho de la llanta | `wheel_width` | | | 0.01200 |
| Llanta izquierda X, Y, Z | `wheel_left_x/y/z` | | | 0, 0.08705, 0 |
| Llanta derecha X, Y, Z | `wheel_right_x/y/z` | | | 0, −0.08705, 0 |
| Cuerpo: largo, ancho, alto | `chassis_length/width/height` | | | 0.200, 0.200, 0.167 |
| Cuerpo: Z del centro | `chassis_z` | | | 0.0536 |
| Cámara X, Y, Z | `camera_x/y/z` | | | 0.0529, 0.0000, 0.1214 |
| Cámara: inclinación | `camera_pitch` | | | 0.1064 (6.1°) |
| IMU X, Y, Z | `imu_x/y/z` | | | 0.0595, 0.0006, 0.0386 |
| ToF izquierdo X, Y, Z | `tof_left_x/y/z` | | | 0.0792, 0.0492, 0.0590 |
| ToF central X, Y, Z | `tof_center_x/y/z` | | | 0.0928, 0.0016, 0.0590 |
| ToF derecho X, Y, Z | `tof_right_x/y/z` | | | 0.0825, −0.0450, 0.0590 |
| ToF laterales: ángulo | `tof_side_yaw` | | | 0.5236 (30°) |
| Caja ESP32: centro / tamaño | (en `body_meshes`) | | | (0.0097, −0.0460, 0.0525) / (0.0718, 0.0542, 0.0203) |
| Caja XL4015: centro / tamaño | (en `body_meshes`) | | | (−0.0685, −0.0100, 0.0477) / (0.0389, 0.0673, 0.0159) |
| Piso: Z más baja de llanta / de rueda loca | (revisión) | | | −0.030 / −0.030 |

> Las posiciones de los sensores que dan los scripts son el centro de la **caja que envuelve** al sensor.
> El método a mano (centro de la cara frontal) es un poco distinto: puede variar 1–5 mm. Las dos sirven
> para RViz; la de la cara frontal es más fiel a desde dónde mide el sensor.

### Anexo B — Hoja de masas

**Pesos de las piezas** (para la Fase 5.3):

| Pieza | Cantidad | Peso c/u (g) | Fuente (báscula / hoja de datos) | Masa en el CAD hoy (g, materiales de relleno) |
|---|---|---|---|---|
| Motorreductor 37D con encoder | 2 | | | 461.7 |
| CLM-18650Battery | 3 | | | 127.5 |
| Logitech C920 (sin brazo) | 1 | | | 127.0 |
| CLM-PisoCam | 1 | | | 95.7 |
| CLM-Body | 1 | | | 84.5 |
| CLM-Plato | 1 | | | 82.3 |
| CLM-Base | 1 | | | 71.9 |
| CLM-RuedaLoca | 2 | | | 61.2 |
| Logitech C920 brazo | 1 | | | 53.8 |
| CLM-Cytron_MDD10A | 1 | | | 36.7 |
| CLM-StepUp_XL4015 | 1 | | | 34.6 |
| CLM-ExpansionBoardESP32 | 1 | | | 24.8 |
| CLM-BaseCam | 1 | | | 24.5 |
| CLM-Llanta60mmD | 2 | | | 19.4 |
| CLM-RasPi5 | 1 | | | 18.1 |
| CLM-PI5_CaseBase / CaseTop | 1 / 1 | | | 16.8 / 0 |
| CLM-HolderBMS | 2 | | | 16.4 |
| CLM-ShieldESP32 | 1 | | | 13.4 |
| CLM-Holder3TOF | 1 | | | 13.4 |
| CLM-BracketsPololu37D | 2 | | | 13.0 |
| CLM-Holder18650 | 1 | | | 11.0 |
| CLM-ESP32_Wroom_30pins | 1 | | | 0 (sin volumen) |
| CLM-BMS_3S_25A | 1 | | | 8.3 |
| CLM-RasPi5_Cooler | 1 | | | 7.8 |
| CLM-KCD1 | 2 | | | 5.5 |
| Postes M3x50 / M3x40 / M3x15 | 4 / 4 / 4 | | | 3.0 / 2.4 / 0.9 |
| CLM-IMU_BMI270 | 1 | | | 3.0 |
| CLM-VL53L1XV2 | 3 | | | 1.5 |
| Lente C920 | 1 | | | 0.9 |
| CLM-Separador_Rue_Loca | 4 | | | 0.3 |
| **Robot completo** | 1 | | | **2296** |

**Resultados de SolidWorks** (para la Fase 7.2):

| | Masa (kg) | CM x, y, z (m) | Lxx | Lyy | Lzz | Lxy | Lxz | Lyz |
|---|---|---|---|---|---|---|---|---|
| `base_link` (todo menos llantas, relativo a `ROS`) | | | | | | | | |
| Llanta izquierda (relativo a `LLANTA_IZQ`) | | | | | | | | |
| Llanta derecha (relativo a `LLANTA_DER`) | | | | | | | | |

Recordatorio: en el URDF, `ixy = −Lxy`, `ixz = −Lxz`, `iyz = −Lyz` (Fase 5.6).

### Anexo C — Qué paso reemplaza cada script

| Script (carpeta `tools/`) | Qué hace | Reemplaza a | Diferencia con el método a mano |
|---|---|---|---|
| `export_stl_solidworks.ps1` | Exporta **todas** las piezas, cada una en su archivo, en los ejes del CAD, sin tocar el ensamble | Fase 6 (parte de exportar) | No crea la configuración "ROS" ni exporta por grupos: eso lo decide después `prepare_meshes.py` |
| `prepare_meshes.py` | Gira los ejes, pasa a metros, pone el origen entre las llantas, agrupa por color, quita la electrónica, hace las cajas, encuentra los sensores y escribe `colmibot_meshes.xacro` | Fases 3, 4, 6.3 y 7.1 | Hace con cálculos lo que a mano hacen los sistemas de coordenadas. Las reglas de qué quitar y qué agrupar están al principio del archivo (`GROUP_RULES`, `EXCLUDE_RULES`, `BOX_RULES`) |
| `export_mass_solidworks.ps1` | Saca masa, centro de masa e inercia de cada pieza (con el signo ya corregido) | Fase 5.4 (la lectura) | Lo guarda pieza por pieza en `inertia/componentes_cad.csv`, para poder cambiar pesos sin volver a abrir SolidWorks |
| `compute_inertial.py` | Aplica los pesos de `inertia/masas.csv`, junta todo por link y escribe `colmibot_inertial.xacro` | Fases 5.3, 5.4, 5.5 y 7.2 | Los pesos reales se escriben en un CSV en vez de en SolidWorks. Si solo hay peso total, escala **solo las piezas sin peso**, no todas |

Cómo se corren y qué imprimen: `PROCESO.md`, pasos 5, 8 y 9.

### Anexo D — Errores reales que ya pasaron en este proyecto

| Qué pasó | Por qué | Cómo se evita |
|---|---|---|
| La exportación de Onshape no dejaba cada pieza en su lugar | Limitación de Onshape | Usar SolidWorks (Fase 6) |
| Las llantas aparecían desplazadas | La malla de la llanta traía su posición **y** el joint también | Exportar la llanta con su propio sistema de coordenadas (Fase 6.3) |
| Faltaba el cuerpo en la exportación | `CLM-Body` está **oculto** en el ensamble | Mostrarlo antes de exportar (Fase 2.1) |
| Las masas del CAD eran absurdas (motor de 462 g) | Materiales de relleno | Corregir materiales o anular masas (Fase 5.2) |
| Los productos de inercia tenían el signo al revés | SolidWorks y ROS usan convenciones distintas | Cambiar el signo de Lxy, Lxz y Lyz (Fase 5.6) |
| La cámara no estaba inclinada en el modelo | No se había medido su ángulo | Medir ángulos, no solo posiciones (Fase 4.2) |
| Piezas que se llaman casi igual (`CLM-Base` y `CLM-BaseCam`; `CLM-HolderBMS` y `CLM-BMS_3S_25A`) | Nombres parecidos | Revisar dos veces al seleccionar y al agrupar |

### Anexo E — Glosario mínimo

| Término | Significado |
|---|---|
| **CAD** | Programa de diseño 3D con medidas exactas (SolidWorks) |
| **Ensamble / pieza** | Archivo que junta piezas (`.SLDASM`) / archivo de un objeto (`.SLDPRT`) |
| **Configuración** | "Versión" de un ensamble dentro del mismo archivo (por ejemplo, con piezas suprimidas) |
| **Suprimir / ocultar / aislar** | Quitar la pieza de esa configuración / no dibujarla / ocultar todo lo demás |
| **Sistema de coordenadas** | Un punto con tres ejes. En ROS se llama *frame* |
| **Link / joint** | Parte rígida / unión entre dos partes |
| **base_link** | Frame principal del robot (centro del eje de las llantas) |
| **base_footprint** | Frame en el piso, 30 mm debajo de `base_link` |
| **STL** | Modelo 3D hecho de triángulos |
| **URDF / xacro** | Descripción del robot en texto / URDF con variables y plantillas |
| **Macro** | Plantilla de xacro con huecos |
| **Paquete / workspace** | Carpeta con archivos de ROS / carpeta que contiene paquetes |
| **colcon build** | Instala los paquetes del workspace para que ROS los use |
| **Tópico** | Canal por donde los programas de ROS se mandan datos |
| **TF** | El sistema de ROS que sabe dónde está cada frame |
| **RViz** | Visor 3D de ROS |
| **Centro de masa** | Punto donde se concentra el peso |
| **Tensor de inercia** | Seis números que dicen qué tanto cuesta hacer girar algo alrededor de cada eje |
| **Radián** | Unidad de ángulo de ROS: 180° = 3.1416 rad |
