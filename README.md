# COLMIBOT — Espacio de trabajo de ROS 2

Robot móvil diferencial para la automatización de inspecciones de
mantenimiento.

**Seminario de Titulación — 001 · Otoño 2026 · ITAM**
Profesor: Sergio Hernández Sánchez

## Paquetes

| Paquete | Sistema de construcción | Contenido |
|---|---|---|
| `colmibot_teleop` | `ament_python` | Nodo de control por joystick |
| `robot_description` | `ament_cmake` | Modelo del robot para RViz y Gazebo |

El sistema de construcción de cada paquete corresponde a su contenido.
`colmibot_teleop` incluye un nodo ejecutable, por lo que emplea `ament_python`
y sus puntos de entrada. `robot_description` únicamente instala archivos
—modelo, mallas, archivos de lanzamiento—, caso en el que `ament_cmake`
resuelve la instalación con una sola instrucción `install(DIRECTORY ...)`.

## Entorno de desarrollo

| Componente | Versión |
|---|---|
| Ubuntu | 24.04 LTS |
| ROS 2 | Jazzy Jalisco |
| Gazebo | Harmonic |
| Control | Xbox Series X |

## Actividades documentadas

Cada actividad conserva su documentación en una sección propia de este
archivo.

---

# Actividad 8 — Teleoperación de Turtlesim con un control de Xbox

Este espacio de trabajo de ROS 2 permite controlar la tortuga de Turtlesim con un control de Xbox. El paquete `joy` lee los ejes y botones del dispositivo, y el nodo `joy_turtle_controller`, desarrollado por el equipo, convierte esas entradas en comandos de velocidad.

**Entorno de la actividad:** ROS 2 Jazzy Jalisco sobre Ubuntu 24.04.

**Integrantes del equipo:**

- Victor Manuel Jimenez Gonzalez · 159723
- Fernando Villalobos Betancourt · 202318

## 1. Descripción de la actividad

El archivo `turtle_joy.launch.py` inicia los tres nodos del sistema:

| Nodo | Paquete | Función |
| --- | --- | --- |
| `joy_node` | `joy` | Lee el control y publica sus ejes y botones en `/joy`. |
| `joy_turtle_controller` | `colmibot_teleop` | Recibe las entradas de `/joy` y calcula las velocidades lineal y angular. |
| `turtlesim_node` | `turtlesim` | Recibe los comandos de `/turtle1/cmd_vel` y mueve la tortuga. |

```text
joy_node ── /joy ──> joy_turtle_controller ── /turtle1/cmd_vel ──> turtlesim_node
            Joy                              Twist
```

Los mensajes de entrada son de tipo `sensor_msgs/msg/Joy`; los comandos de velocidad son de tipo `geometry_msgs/msg/Twist`.

## 2. Hardware

| Elemento | Detalle |
| --- | --- |
| Control | Xbox Series X Controller |
| Conexión utilizada | Bluetooth |
| Dispositivo observado en Linux | `/dev/input/js0` |

En las pruebas de la actividad, Ubuntu reconoció el control sin instalar controladores adicionales. Al iniciar `joy_node`, se observó el siguiente mensaje:

```text
[joy_node]: Opened joystick: Xbox Series X Controller.  deadzone: 0.100000
```

## 3. Mapeo del control

Para identificar los ejes y botones, movimos un eje o presionamos un botón a la vez y observamos los cambios en `/joy`:

```bash
ros2 topic echo /joy --field axes
ros2 topic echo /joy --field buttons
```

El siguiente mapeo corresponde al control utilizado en la actividad. Conviene comprobarlo antes de usar otro dispositivo o tipo de conexión, ya que el nodo utiliza índices fijos.

### Ejes (`axes`)

| Índice | Control | Valor en reposo | Valores observados |
| --- | --- | --- | --- |
| 0 | Stick izquierdo, horizontal | `0.0` | `+1.0` a la izquierda; `-1.0` a la derecha |
| 1 | Stick izquierdo, vertical | `0.0` | `+1.0` arriba; `-1.0` abajo |
| 2 | Stick derecho, horizontal | `0.0` | `+1.0` a la izquierda; `-1.0` a la derecha |
| 3 | Stick derecho, vertical | `0.0` | `+1.0` arriba; `-1.0` abajo |
| 4 | Gatillo derecho (RT) | `1.0` | De `1.0` sin presionar a `-1.0` completamente presionado |
| 5 | Gatillo izquierdo (LT) | `1.0` | De `1.0` sin presionar a `-1.0` completamente presionado |
| 6 | Cruz direccional, horizontal | `0.0` | `-1.0`, `0.0` o `1.0` |
| 7 | Cruz direccional, vertical | `0.0` | `-1.0`, `0.0` o `1.0` |

### Botones (`buttons`)

| Índice | Botón |
| --- | --- |
| 0 | A |
| 1 | B |
| 3 | X |
| 4 | Y |
| 6 | LB |
| 7 | RB |

En el mapeo observado, los índices 2 y 5 no corresponden a botones físicos.

### Observaciones del mapeo

- **Gatillos:** su rango puede convertirse a valores entre 0 y 1 mediante `(1 - valor) / 2`. No se utilizan para mover la tortuga en esta actividad.
- **Cruz direccional:** sus entradas aparecen como ejes, pero solo toman tres valores. No ofrece el control proporcional de los sticks.
- **Verificación con `jstest`:** utilizamos `jstest /dev/input/js0` para revisar el dispositivo fuera de ROS. Como su interfaz de lectura puede producir un mapeo distinto del que entrega `joy_node`, la referencia para configurar el nodo son los mensajes de `/joy`.

## 4. Decisiones de diseño

### Leer el dispositivo con `joy_node`

Usamos el paquete `joy` para leer el control, normalizar los ejes y aplicar una zona muerta. Esto permitió concentrar el desarrollo en la conversión de entradas a movimiento.

### Desarrollar un nodo de control propio

Aunque `teleop_twist_joy` permite convertir entradas de un control en comandos de velocidad, en esta actividad desarrollamos `joy_turtle_controller` para definir y probar la asignación de botones, los modos de velocidad y la función de parada.

### Dirigir la tortuga con el stick izquierdo

El eje vertical determina `linear.x` y el horizontal determina `angular.z`. Se conservan los signos observados: arriba produce avance y la izquierda produce un giro antihorario. Ambos ejes pueden combinarse para avanzar o retroceder mientras la tortuga gira.

### Habilitar el movimiento con RB

La tortuga solo recibe velocidades de movimiento mientras RB permanece presionado. Cuando el nodo recibe un mensaje con RB liberado, publica un `Twist` con velocidades en cero. B también publica un comando de parada y tiene prioridad sobre los demás botones.

### Definir los modos de velocidad

La velocidad es proporcional a la inclinación del stick. El nodo aplica las siguientes expresiones:

```text
linear.x  = axes[1] × 2.0 × factor
angular.z = axes[0] × 2.0 × factor
```

| Modo | Condición, manteniendo RB presionado | Factor | Máximo lineal | Máximo angular |
| --- | --- | --- | --- | --- |
| Normal | Sin A ni LB | `1.0` | `2.0` unidades/s | `2.0` rad/s |
| Turbo | LB presionado, sin A | `2.0` | `4.0` unidades/s | `4.0` rad/s |
| Preciso | A presionado | `0.4` | `0.8` unidades/s | `0.8` rad/s |

Si A y LB se presionan al mismo tiempo, se aplica el modo preciso.

### Configurar la lectura del control

El archivo launch configura los siguientes parámetros de `joy_node`:

| Parámetro | Valor | Función |
| --- | --- | --- |
| `deadzone` | `0.1` | Ignora pequeñas variaciones cerca del centro del stick. |
| `autorepeat_rate` | `20.0` | Republica el estado del control a 20 Hz, aunque no cambie. |

La republicación permite que el nodo siga enviando velocidades mientras el stick permanece inclinado. Durante las pruebas, sin mensajes nuevos, Turtlesim dejaba de recibir comandos y la tortuga se detenía después de un tiempo.

## 5. Guía de controles

| Entrada | Función |
| --- | --- |
| **Stick izquierdo, eje vertical** | Arriba avanza; abajo retrocede. |
| **Stick izquierdo, eje horizontal** | Izquierda gira en sentido antihorario; derecha, en sentido horario. |
| **RB** | Habilita el movimiento mientras se mantiene presionado. |
| **RB + LB** | Activa el modo turbo: duplica las velocidades del modo normal. |
| **RB + A** | Activa el modo preciso: reduce las velocidades al 40 % del modo normal. |
| **B** | Detiene la tortuga, independientemente del estado de los demás botones. |
| **X, Y, stick derecho, gatillos y cruz direccional** | Sin función asignada en esta actividad. |

En cada mensaje recibido, el nodo evalúa primero B, después RB y, por último, el modo de velocidad.

## 6. Estructura del repositorio

```text
colmibot_xbox_controller_ws/
├── README.md
└── src/
    └── colmibot_teleop/
        ├── LICENSE
        ├── package.xml
        ├── setup.py
        ├── setup.cfg
        ├── resource/
        │   └── colmibot_teleop
        ├── colmibot_teleop/
        │   ├── __init__.py
        │   └── joy_turtle_controller.py
        ├── launch/
        │   └── turtle_joy.launch.py
        └── test/
```

## 7. Instalación y ejecución

Los siguientes comandos suponen que ROS 2 Jazzy ya está instalado. Ejecuta los comandos de compilación y lanzamiento desde la raíz de este repositorio, donde se encuentra `src/`.

### Instalar dependencias

```bash
sudo apt update
sudo apt install ros-jazzy-joy ros-jazzy-turtlesim ros-jazzy-rqt-graph python3-colcon-common-extensions

# Opcional: probar el control fuera de ROS
sudo apt install joystick
```

### Verificar el control

Empareja y conecta el control por Bluetooth antes de iniciar el archivo launch.

```bash
# Comprobar si Linux detecta un dispositivo de joystick
ls /dev/input/js*

# Si instalaste joystick, revisar ejes y botones (salir con Ctrl+C)
jstest /dev/input/js0
```

Si el dispositivo tiene otro índice, sustituye `/dev/input/js0` por la ruta correspondiente.

### Compilar el espacio de trabajo

```bash
# Desde la raíz del repositorio
source /opt/ros/jazzy/setup.bash
colcon build
source install/setup.bash

# Comprobar que se instalaron el ejecutable y el archivo launch
ls install/colmibot_teleop/lib/colmibot_teleop/
ls install/colmibot_teleop/share/colmibot_teleop/launch/
```

### Iniciar la actividad

Desde la raíz del repositorio, ejecuta:

```bash
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch colmibot_teleop turtle_joy.launch.py
```

Con la ventana de Turtlesim abierta, mantén RB presionado y mueve el stick izquierdo. Para detener la tortuga, suelta RB o presiona B. Para cerrar los nodos, usa `Ctrl+C` en la terminal del lanzamiento.

### Comprobar los nodos y tópicos

Abre otra terminal en la raíz del repositorio y carga el entorno:

```bash
source /opt/ros/jazzy/setup.bash
source install/setup.bash

# Listar los nodos y los tópicos con sus tipos de mensaje
ros2 node list
ros2 topic list -t

# Consultar publicadores, suscriptores y conexiones del controlador
ros2 topic info /joy
ros2 topic info /turtle1/cmd_vel
ros2 node info /joy_turtle_controller

# Visualizar el grafo de nodos
ros2 run rqt_graph rqt_graph
```

Para observar los mensajes o medir su frecuencia, ejecuta cada comando por separado y detenlo con `Ctrl+C` antes de continuar:

```bash
# Entradas del control
ros2 topic echo /joy

# Velocidades enviadas a Turtlesim
ros2 topic echo /turtle1/cmd_vel

# Frecuencia de publicación del estado del control
ros2 topic hz /joy
```

También puedes observar ambos tópicos en terminales separadas para comparar las entradas con las velocidades generadas. En `rqt_graph`, actualiza el grafo para revisar la conexión entre los tres nodos.

## 8. Problemas encontrados y soluciones

### El archivo launch no aparecía

Al ejecutar el proyecto aparecía el mensaje `file 'turtle_joy.launch.py' was not found in the share directory`. El archivo existía en el código fuente, pero faltaba incluirlo en `data_files` dentro de `setup.py`.

La solución fue registrar `launch/turtle_joy.launch.py` para su instalación en `share/colmibot_teleop/launch`. Los archivos launch se instalan como datos del paquete.

### No se encontraba el ejecutable del nodo

El lanzamiento mostraba el error `libexec directory does not exist`. El bloque `entry_points` de `setup.py` estaba vacío, por lo que no se generaba el ejecutable del controlador.

La solución fue registrar el punto de entrada en `console_scripts`:

```python
'joy_turtle_controller.py = colmibot_teleop.joy_turtle_controller:main'
```

Después de modificar la configuración de instalación, es necesario volver a ejecutar `colcon build` y cargar `install/setup.bash`.

## 9. Evidencia en video

*Enlace:* [Video de la actividad](https://drive.google.com/file/d/1BlDcLYgs7mdx93NZxwTFr-G7-gZ0Tuow/view?usp=drive_link)

---

# Actividad 9 — Representación virtual del robot

Modelo URDF del COLMIBOT construido a partir del ensamble de SolidWorks y
visualizable en RViz.

Esta sección resume el trabajo. El detalle completo está en dos documentos del
repositorio:

- **[`GUIA_A_MANO.md`](GUIA_A_MANO.md)** — el procedimiento definitivo, en ocho
  fases, tal como debe reproducirse.
- **[`PROCESO.md`](PROCESO.md)** — la bitácora de todo lo que se intentó,
  incluidos los caminos que no funcionaron y por qué.

## Participación

Victor Manuel Jiménez González — exportación del CAD, construcción del modelo,
pruebas en RViz y documentación.

## Resultado obtenido

Modelo que reproduce el robot físico con esta estructura de eslabones:

```
base_footprint                    (en el piso)
└─ base_link                      (cuerpo, a la altura del eje de las llantas)
   ├─ wheel_left_link             (llanta izquierda, gira)
   ├─ wheel_right_link            (llanta derecha, gira)
   ├─ camera_link
   │  └─ camera_optical_frame     (convención óptica de REP-103)
   ├─ imu_link
   ├─ tof_left_link
   ├─ tof_center_link
   └─ tof_right_link
```

La geometría se reparte en **ocho mallas**: seis que integran el cuerpo y dos
para las llantas, que son las únicas piezas móviles. Las masas y los tensores
de inercia provienen de las propiedades físicas del CAD, con los materiales ya
asignados.

El paquete admite dos modos de visualización, seleccionables al lanzarlo:

| Modo | Geometría | Para qué sirve |
|---|---|---|
| `use_meshes:=true` *(predeterminado)* | Las mallas reales del CAD | El resultado final |
| `use_meshes:=false` | Figuras primitivas con medidas estimadas | Verificar la estructura sin depender de las mallas |

## Herramientas y recursos empleados

| Herramienta | Función |
|---|---|
| SolidWorks Design Standard 2026 | Crear sistemas de coordenadas, medir, obtener masas y exportar las mallas |
| Ubuntu 24.04 + ROS 2 Jazzy | Entorno de ejecución |
| RViz2 | Visualización |
| Editor de texto | Redacción de los archivos `.xacro` |
| Báscula de cocina | Contrastar las masas del CAD con las reales |

Recursos externos consultados:

- Archivos CAD del ensamble COLMIBOT y su lista de materiales, proporcionados
  por el curso.
- **REP-103**, que define la convención de ejes y unidades en ROS, y
  **REP-105**, que establece los marcos de referencia de robots móviles.
- Hoja de datos del sensor **VL53L1X** de STMicroelectronics: campo de visión
  típico de 27° y alcance máximo de 4 m.
  <https://www.st.com/en/imaging-and-photonics-solutions/vl53l1x.html>

## Procedimiento

El método consiste en **extraer del CAD las dos cosas que ROS necesita** —la
estructura y la forma— y expresarlas en los formatos que ROS entiende. El
trabajo se organiza en ocho fases, detalladas en `GUIA_A_MANO.md`:

| Fase | Qué se hace | Qué produce |
|---|---|---|
| 1 | Preparar una copia de trabajo del CAD | Copia intacta del original |
| 2 | Decidir qué pieza se dibuja, cuál se omite y cuál se sustituye por una caja | Criterio de agrupación |
| 3 | Crear en SolidWorks los sistemas de coordenadas con la convención de ROS | Marco `ROS` y el de cada llanta |
| 4 | Medir cada posición respecto a ese marco | Hoja de medidas |
| 5 | Obtener masa, centro de masa e inercia con las propiedades físicas | Hoja de masas |
| 6 | Exportar las mallas agrupadas por color | Ocho archivos STL |
| 7 | Escribir los archivos `.xacro` del paquete | Modelo completo |
| 8 | Compilar y abrir en RViz | Verificación |

Tres parámetros de la exportación a STL determinan si el resultado sirve:

| Parámetro | Valor | Justificación |
|---|---|---|
| Formato | Binario | Pesa alrededor de cinco veces menos que el ASCII y ROS lee ambos |
| Unidades | Milímetros | Corresponde a la unidad del ensamble; la conversión a metros ocurre después |
| *No convertir los datos de salida a espacio positivo* | **Activado** | Parámetro crítico. De no activarse, SolidWorks desplaza cada pieza para que ninguna coordenada sea negativa, con lo que todas quedan amontonadas y se pierde su posición dentro del ensamble |

## Decisiones de diseño y simplificaciones

Las simplificaciones se eligieron conforme a los objetivos del proyecto: el
modelo debe **presentar una apariencia fiel al robot físico** y servir como
base para navegación y simulación.

### Qué se dibuja y qué no

Cada pieza del CAD recibió uno de tres destinos:

| Destino | Piezas | Criterio |
|---|---|---|
| **Se dibuja** | Estructura, llantas, motores, ruedas locas, sensores e interruptores | Forman la silueta del robot o son sensores |
| **Se omite** | Driver Cytron, BMS, celdas 18650, Raspberry Pi y su disipador | Quedan ocultas dentro del cuerpo o tras la carcasa. La Raspberry y su disipador suman además 42 piezas de alto costo de dibujado |
| **Se sustituye por una caja** | ESP32 con su placa de expansión, y el convertidor XL4015 | Están a la vista en el piso superior, y una caja de sus mismas dimensiones basta |

Omitir una pieza del dibujo **no elimina su masa**: se contabiliza igual al
calcular las inercias.

### Agrupación por método de fabricación

Las mallas se agruparon según cómo se fabrica cada pieza, criterio que además
define su color:

| Grupo | Contenido |
|---|---|
| `impreso_3d` | Cuerpo, soportes, separadores, postes, carcasa de la Raspberry Pi |
| `placas_laser` | Las tres placas de corte láser que forman los pisos |
| `motores` | Los dos motorreductores |
| `ruedas_locas` | Las dos ruedas locas |
| `camara` | Cámara, lente y brazo |
| `electronica` | Los tres sensores de distancia, la unidad inercial y los interruptores |
| `wheel_left` / `wheel_right` | Cada llanta por separado |

Las llantas van solas porque **giran**: cada una es su propio eslabón y
necesita su malla centrada en su eje.

### Eslabones de sensor sin geometría

Los sensores existen en el modelo como marcos de referencia sin forma visible.
Su apariencia ya está contenida en la malla del grupo `electronica` o en la de
la cámara; lo que ROS necesita de ellos es **dónde están y hacia dónde
apuntan**, para interpretar sus mediciones.

### Colisiones mediante primitivas geométricas

La geometría visual usa las mallas; la de colisión usa cajas y cilindros. Un
motor de física que debe evaluar contactos contra mallas de miles de triángulos
resulta impracticable en tiempo real, y para navegación la envolvente es
suficiente.

### Incorporación de `base_footprint`

`base_link` se sitúa en el punto medio entre las dos llantas, a la altura de su
eje, porque es el punto sobre el que gira un robot diferencial cuando una rueda
avanza y la otra retrocede. Debajo se agregó `base_footprint`, la proyección
sobre el piso, que es el marco que requiere Nav2 y el que se usa como *Fixed
Frame* en RViz.

## Estructura del paquete `robot_description`

```
robot_description/
├── CMakeLists.txt
├── package.xml
├── inertia/                       # masas y propiedades extraídas del CAD
│   ├── componentes_cad.csv
│   ├── masas.csv
│   └── masas_usadas.csv
├── tools/
│   ├── export_stl_solidworks.ps1  # exportación de mallas
│   ├── export_mass_solidworks.ps1 # exportación de masas
│   ├── prepare_meshes.py          # cambio de ejes, escala y agrupación
│   └── compute_inertial.py        # tensores de inercia por eslabón
├── urdf/
│   ├── colmibot.urdf.xacro        # archivo principal: eslabones y uniones
│   ├── colmibot_params.xacro      # medidas
│   ├── macros.xacro               # plantillas de rueda, sensor e inercias
│   ├── materials.xacro            # colores por grupo
│   └── generated/
│       ├── colmibot_meshes.xacro  # medidas reales y lista de mallas
│       └── colmibot_inertial.xacro# masas e inercias
├── meshes/                        # ocho mallas, en metros
├── launch/
│   └── display.launch.py
└── rviz/
    └── display.rviz
```

Los archivos bajo `generated/` contienen lo medido del CAD y se reescriben al
regenerar; los demás se editan a mano.

## Instrucciones de ejecución

```bash
sudo apt install ros-jazzy-robot-state-publisher ros-jazzy-joint-state-publisher-gui \
                 ros-jazzy-rviz2 ros-jazzy-xacro

source /opt/ros/jazzy/setup.bash
cd ~/colmibot_ws
colcon build --packages-select robot_description --symlink-install
source install/setup.bash
ros2 launch robot_description display.launch.py
```

Se abren dos ventanas: RViz con el modelo cargado y la interfaz de control
deslizante para girar las llantas.

Opciones disponibles al lanzar:

| Opción | Valor predeterminado | Efecto |
|---|---|---|
| `use_meshes` | `true` | `false` dibuja el robot con figuras primitivas |
| `gui` | `true` | `false` omite la ventana de controles deslizantes |
| `rviz` | `true` | `false` no abre RViz |

## Modificación del modelo

Las medidas están reunidas en `urdf/colmibot_params.xacro` como propiedades con
nombre. Se emplea **xacro** en lugar de URDF simple porque este último es XML
sin variables: cambiar el radio de una rueda obligaría a editar el valor en
varios puntos y mantener la consistencia manualmente. Xacro permite escribir
`${wheel_radius}` y que una sola definición gobierne todos los usos.

La opción `--symlink-install` permite que baste con reiniciar el lanzamiento
tras editar un `.xacro`, sin recompilar.

## Problemas encontrados y soluciones implementadas

### 1. Una primera versión del modelo quedó descartada

Antes del procedimiento actual se construyó una versión preliminar mediante un
generador automático que deducía la estructura del URDF midiendo las mallas
exportadas. Funcionaba y llegó a visualizarse en RViz, pero presentaba dos
inconvenientes: las masas eran estimaciones calculadas por volumen y densidad,
no valores reales, y la agrupación en veinte módulos resultaba innecesariamente
pesada.

**Solución.** Se rehízo el modelo con el procedimiento de `GUIA_A_MANO.md`, que
toma las masas directamente de las propiedades físicas del CAD y agrupa la
geometría por método de fabricación, con ocho mallas en lugar de veinte
módulos. La bitácora de la versión preliminar se conserva en `PROCESO.md`.

### 2. El exportador oficial de SolidWorks a URDF no es compatible

El complemento `sw_urdf_exporter` admite hasta la versión SolidWorks 2021,
mientras que el equipo trabaja con la 2026. No aparece en el menú de
complementos.

**Solución.** Se exportó únicamente la geometría y se construyeron a mano los
archivos de descripción, apoyándose en los sistemas de coordenadas creados en
el propio CAD.

### 3. Onshape no permite exportar piezas repetidas

Antes de disponer de SolidWorks se recurrió a Onshape, que abrió el ensamble
completo sin problema. Sin embargo, su exportación ofrece únicamente *Export
unique parts*, que guarda una sola vez cada pieza distinta: de las dos llantas
habría salido una, y de los tres sensores de distancia, uno.

**Solución.** Se consiguió SolidWorks, que exporta cada instancia por separado.

### 4. Discrepancia entre los ejes del CAD y los de ROS

El ensamble emplea el eje Y como vertical y orienta el frente hacia −Z, con
medidas en milímetros. ROS utiliza la convención REP-103: X al frente, Y hacia
la izquierda, Z hacia arriba, y metros. Sin corregirlo, el robot aparecería
acostado y mil veces más grande.

**Solución.** Se creó en SolidWorks un sistema de coordenadas con la
orientación de ROS, y todas las mediciones se tomaron respecto a él. La
conversión de unidades se aplica al preparar las mallas.

### 5. El ángulo de los sensores laterales no pudo medirse automáticamente

La orientación de los sensores de distancia no se deduce de forma fiable a
partir de la geometría exportada.

**Solución.** Se tomó directamente del CAD, donde los dos sensores laterales
están girados 30° respecto al central. Con un campo de visión de 27° por
sensor, los conos de medición quedan prácticamente contiguos.

### 6. El modelo se mostraba completamente negro en RViz

Al abrir el modelo con las mallas activadas, todas las piezas aparecían negras
pese a que `materials.xacro` define diez colores distintos.

Se verificó que las definiciones llegaran al URDF expandido, que cada bloque
`<visual>` referenciara su material, que el enlace de la carpeta de instalación
apuntara al archivo correcto y que las normales de las mallas fueran
consistentes. Todo resultó correcto.

**Solución.** El archivo `.xacro` se procesa al arrancar el lanzamiento, de modo
que una modificación no afecta a una ventana ya abierta. Bastó cerrar RViz y
volver a lanzar.

### 7. Falla de `colcon build` al crear enlaces simbólicos

El espacio de trabajo se encontraba en una partición exFAT compartida con
Windows, sistema que no admite enlaces simbólicos, que es el mecanismo que
emplea `--symlink-install`.

**Solución.** Trasladar el espacio de trabajo a una partición ext4. exFAT
tampoco conserva los permisos de Unix ni distingue mayúsculas, lo que habría
ocasionado problemas con el control de versiones.

### 8. Error de compilación por entorno sin inicializar

`colcon build` fallaba con `ModuleNotFoundError: No module named 'ament_package'`.
CMake localizaba los archivos de ROS porque residen en una ruta fija, pero el
intérprete de Python carecía de la ruta correspondiente.

**Solución.** Ejecutar `source /opt/ros/jazzy/setup.bash` antes de compilar, y
eliminar la caché de la compilación fallida.

### 9. Ausencia de paquetes de ROS

El archivo de lanzamiento fallaba con `file not found: 'xacro'`.

**Solución.** Instalar `ros-jazzy-xacro` y `ros-jazzy-joint-state-publisher-gui`
por separado, en lugar del metapaquete completo.

## Medidas obtenidas del CAD

| Parámetro | Valor |
|---|---|
| Radio de llanta | 30.0 mm |
| Ancho de llanta | 12.0 mm |
| Separación entre llantas | 174.1 mm |
| Envolvente del cuerpo | 200 × 200 × 167 mm |
| Cámara, respecto al eje de las llantas | 53 mm al frente, 121 mm de altura |
| Sensor de distancia central | 93 mm al frente, 59 mm de altura |
| Orientación de los sensores laterales | 30° |

## Limitaciones conocidas

**Los colores son provisionales.** Se eligieron para distinguir los grupos de
piezas, no para reproducir el acabado del robot físico. Varios valores quedan
por debajo de 0.2 en la escala de luminosidad, lo que en RViz los aproxima al
negro y dificulta distinguir unas piezas de otras.

**Las masas provienen del CAD, no de un pesaje.** Son considerablemente más
confiables que una estimación por volumen y densidad, pero dependen de que los
materiales asignados en el ensamble correspondan a los reales. Contrastarlas
con una báscula queda pendiente para los ajustes finales del robot físico.

---

# Actividad 10 — Integración en Gazebo

*(en desarrollo)*
