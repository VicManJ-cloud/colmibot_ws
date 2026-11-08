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

Modelo URDF del COLMIBOT generado a partir del ensamble de SolidWorks y
visualizable en RViz.

## Participación

Victor Manuel Jiménez González — exportación del CAD, generador, modelo URDF,
pruebas en RViz y documentación.

## Resultado obtenido

Modelo de **20 módulos** y **25 eslabones** que reproduce el robot físico:
chasis, tracción diferencial, batería, electrónica de control, Raspberry Pi 5
con su disipador, unidad inercial, tres sensores de distancia por tiempo de
vuelo y cámara. Las dos ruedas de tracción corresponden a articulaciones
móviles; los demás elementos se modelaron como uniones fijas.

Masa total estimada: **1.97 kg**.

## Herramientas y recursos empleados

| Herramienta | Versión | Función |
|---|---|---|
| SolidWorks Design Standard | 2026 SP4.1 | Exportación de la geometría del ensamble a STL |
| Python | 3.x | Lenguaje del generador |
| trimesh | 5.x | Lectura de mallas, cálculo de centroides e inercias |
| fast-simplification | — | Reducción de triángulos de las mallas visuales |
| PyYAML | 6.x | Lectura de la configuración del robot |
| RViz2 | incluida en ROS Jazzy | Visualización |

Paquetes de ROS requeridos: `robot_state_publisher`,
`joint_state_publisher_gui`, `rviz2` y `xacro`.

Recursos externos consultados:

- Archivos CAD del ensamble COLMIBOT, proporcionados por el curso.
- Hoja de datos del sensor **VL53L1X** de STMicroelectronics, que especifica un
  campo de visión típico de 27° y un alcance máximo de 4 m. Se utilizó para
  evaluar la cobertura del arreglo de sensores.
  <https://www.st.com/en/imaging-and-photonics-solutions/vl53l1x.html>
- **REP-103**, que define la convención de ejes y unidades en ROS, y
  **REP-105**, que establece los marcos de referencia de robots móviles.

## Procedimiento

El enfoque adoptado consiste en **generar el URDF a partir del CAD en lugar de
redactarlo manualmente**. Ninguna coordenada se captura a mano: todas se miden
sobre la geometría exportada. Si una pieza cambia de posición en SolidWorks,
basta reexportar y ejecutar nuevamente el generador.

```
CAD (SolidWorks)
      │  exportación a STL conservando las coordenadas del ensamble
      ▼
export_stl/  (95 archivos)
      │  tools/generar_modelo.py + tools/robot.yaml
      ▼
robot_description/  (URDF + mallas + lanzamiento + configuración de RViz)
```

### 1. Exportación desde SolidWorks

Se abre el archivo `CLM-EnsambleColmibot.SLDASM` y se utiliza la opción
**Archivo → Guardar como → STL**. Tres parámetros determinan la utilidad del
resultado:

| Parámetro | Valor | Justificación |
|---|---|---|
| Unidades | Milímetros | Corresponde a la unidad del ensamble |
| *Guardar todos los componentes en un solo archivo* | **Desactivado** | Se requiere un archivo STL por pieza para agruparlas posteriormente por módulo |
| *No trasladar datos de salida STL a espacio positivo* | **Activado** | Parámetro crítico. De no activarse, SolidWorks reubica cada pieza en su propio origen y se pierden las posiciones del ensamble, que son precisamente las que determinan el origen de cada articulación |
| Resolución | Fina | La reducción posterior de triángulos controla el peso de los archivos |

El resultado consiste en 95 archivos STL, uno por cada instancia de pieza.

**Verificación de la exportación.** Antes de continuar se comprueba que las
coordenadas se hayan conservado, midiendo la posición de ambas llantas:

```bash
python3 -c "import trimesh,glob; [print(f[-28:], trimesh.load(f,force='mesh').centroid.round(2)) for f in glob.glob('*Llanta*.STL')]"
```

Los resultados deben ser simétricos, aproximadamente x = −88.84 mm y
x = +88.84 mm. Si ambos valores se aproximan al origen, el parámetro de espacio
positivo quedó mal configurado.

### 2. Generación del paquete

```bash
python3 tools/generar_modelo.py tools/robot.yaml export_stl/ robot_description/
```

El script aplica la siguiente secuencia a cada módulo definido en `robot.yaml`:

1. **Agrupación.** Reúne los archivos STL cuyo nombre contenga los patrones
   asociados al módulo. De esta manera el módulo `base` integra 15 piezas
   —base, cuerpo, plato y doce postes— en una sola malla.
2. **Rotación y escalamiento.** El CAD emplea el eje **Y como vertical** y
   orienta el frente hacia **−Z**; ROS utiliza la convención REP-103, con
   **X al frente, Y hacia la izquierda y Z hacia arriba**. Se aplica una única
   transformación que realiza el cambio de marco y convierte milímetros a
   metros.
3. **Centrado.** Se calcula el centroide de cada módulo y se desplaza la malla
   para situarlo en el origen. El centroide se conserva porque la diferencia
   entre el del elemento hijo y el del padre constituye el origen de la
   articulación que los une.
4. **Filtrado de piezas de volumen reducido.** Se descartan los sólidos
   independientes menores al umbral configurado.
5. **Cálculo de masa e inercia** a partir del volumen y la densidad del
   material asignado.
6. **Determinación de la orientación de los sensores** a partir de su
   geometría.
7. **Reducción de triángulos** de la malla visual y generación de una
   primitiva de colisión.
8. **Escritura** del URDF en formato xacro, junto con las mallas, el archivo de
   lanzamiento y la configuración de RViz.

### 3. Compilación

```bash
cd ~/colmibot_ws
colcon build --packages-select robot_description --symlink-install
```

## Decisiones de diseño y simplificaciones

Las simplificaciones se determinaron conforme a los objetivos del proyecto: el
modelo debe **presentar una apariencia fiel al robot físico** y servir como
base para navegación y simulación. No se simplificó ningún elemento que
comprometiera alguno de esos dos propósitos.

### Agrupación por módulo funcional

Las 95 instancias se agruparon en 20 módulos. Modelar cada tornillo como un
eslabón independiente volvería ilegible el URDF y poblaría el árbol de
transformadas con marcos carentes de significado físico. El criterio de
agrupación fue funcional: los elementos que se desplazan en conjunto y no
poseen un sensor propio integran un mismo eslabón.

### Eliminación de piezas de volumen reducido

Se descartaron los sólidos independientes menores al umbral definido, que
corresponden a pines de conectores, tornillos M2, arandelas y resortes.
Resultan imperceptibles a la escala en que se observa el robot y representan
decenas de miles de triángulos. En términos concretos, se eliminaron
**1 840 piezas** del módulo de electrónica y **6 006** del módulo de la
Raspberry Pi.

El umbral se definió como un parámetro configurable
(`descartar_menores_mm3`), ajustable de forma global o por módulo; asignarle el
valor cero conserva la totalidad de la geometría.

### Colisiones mediante primitivas geométricas

La geometría visual emplea las mallas con triángulos reducidos, mientras que la
geometría de colisión utiliza **cajas y cilindros** ajustados a la envolvente de
cada módulo. Un motor de física que debe evaluar contactos contra mallas de
miles de triángulos resulta impracticable en tiempo real. Para efectos de
navegación la envolvente es suficiente, y constituye la práctica habitual en
simulación robótica.

Las ruedas emplean cilindros, orientados sobre el eje Y mediante la rotación
correspondiente.

### Ruedas vinculadas directamente a `base_link`

La cadena física del robot es chasis → soporte → motorreductor → llanta. En el
URDF, en cambio, las llantas se vinculan **directamente a `base_link`**,
mientras que soportes y motores permanecen como eslabones visuales fijos al
chasis.

La razón es funcional: los controladores de tracción diferencial requieren la
separación entre ruedas medida respecto al chasis. Encadenarlas a través de dos
eslabones intermedios convierte ese parámetro en una magnitud indirecta y
añade profundidad al árbol de transformadas sin beneficio alguno. La apariencia
visual del modelo es idéntica en ambos casos.

### Disipador modelado como elemento fijo

El ventilador de la Raspberry Pi modifica su velocidad por modulación de ancho
de pulso en función de la temperatura del procesador, pero dicho control lo
ejerce el hardware de la tarjeta y no ROS. Se modeló como un eslabón fijo: su
apariencia es la misma y se evita incorporar una articulación que ningún nodo
del sistema publicaría.

### Ruedas locas como eslabón único y fijo

Son elementos pasivos que no reciben consignas de control. Para efectos de
visualización y navegación basta con representar su presencia geométrica.

### Marcos de referencia de los sensores

Cada sensor de distancia y la cámara cuentan con un marco de referencia propio,
adicional a su eslabón visual:

- Los sensores de tiempo de vuelo incorporan el marco `tof_N_frame`, con el eje
  X orientado en la dirección de medición.
- La cámara incorpora el marco `camara_optical_frame`, con la convención óptica
  establecida en REP-103 —Z hacia el frente, X hacia la derecha, Y hacia
  abajo—, que es la que esperan los nodos de procesamiento de imagen.

### Incorporación de `base_footprint`

Se agregó el marco de referencia estándar para robots móviles, correspondiente
a la proyección del robot sobre el plano del piso. Es el marco que requiere
Nav2 y el que se emplea como *Fixed Frame* en RViz.

## Estructura del paquete `robot_description`

```
robot_description/
├── CMakeLists.txt
├── package.xml
├── tools/
│   ├── generar_modelo.py          # genera el contenido a partir de las STL
│   └── robot.yaml                 # diseño: módulos, jerarquía, juntas, materiales
├── urdf/
│   ├── colmibot.urdf.xacro        # ARCHIVO PRINCIPAL — edición manual
│   └── generated/
│       └── colmibot_geometria.urdf.xacro   # GENERADO — no editar
├── meshes/                        # una malla por módulo, expresada en metros
├── launch/
│   └── display.launch.py
└── rviz/
    └── colmibot.rviz
```

### Distinción entre archivos generados y editables

Esta separación responde a una decisión deliberada:

- **`urdf/generated/colmibot_geometria.urdf.xacro`** contiene los eslabones y
  articulaciones medidos sobre el CAD. Se **sobrescribe por completo** en cada
  ejecución del generador, por lo que no debe editarse manualmente.
- **`urdf/colmibot.urdf.xacro`** constituye el archivo principal: define los
  parámetros del modelo e incorpora al anterior. El generador **nunca lo
  modifica**. En él se incorporan los ajustes del equipo, los sensores
  adicionales y los complementos de Gazebo.

De esta forma el CAD puede reexportarse cuantas veces sea necesario sin perder
el trabajo realizado manualmente.

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
deslizante para manipular las articulaciones.

### Regeneración a partir del CAD

Procedimiento necesario únicamente cuando el ensamble sufre modificaciones.
Requiere reexportar previamente los archivos STL.

```bash
pip install trimesh fast-simplification pyyaml
python3 src/robot_description/tools/generar_modelo.py \
        src/robot_description/tools/robot.yaml \
        <carpeta_con_los_archivos_STL> \
        src/robot_description
```

## Modificación del modelo

Los parámetros ajustables se encuentran al inicio de
`urdf/colmibot.urdf.xacro`:

```xml
<xacro:property name="separacion_llantas" value="0.177679195"/>
<xacro:property name="radio_llanta"       value="0.0299977789"/>
<xacro:property name="altura_chasis"      value="0.0432855681"/>
<xacro:property name="altura_camara"      value="0.130448889"/>
```

Se emplea **xacro** en lugar de URDF simple porque este último es XML sin
variables: modificar el radio de una rueda obligaría a editar el valor en
diversos puntos del archivo y a mantener la consistencia manualmente. Xacro
incorpora propiedades con nombre y expresiones aritméticas —por ejemplo
`${separacion_llantas/2}`—, que se expanden antes de que ROS procese el
archivo. El archivo de lanzamiento procesa el xacro en tiempo de ejecución, de
modo que no se requiere una conversión manual previa.

A manera de ejemplo, al modificar `radio_llanta` de `0.03` a `0.04` y volver a
ejecutar el lanzamiento, las ruedas aumentan de tamaño y el chasis se eleva,
puesto que la altura del robot se calcula a partir de ese valor.

La opción `--symlink-install` permite que baste con reiniciar el lanzamiento,
sin necesidad de recompilar.

## Problemas encontrados y soluciones implementadas

### 1. Incompatibilidad del exportador oficial de SolidWorks a URDF

El complemento `sw_urdf_exporter` admite hasta la versión **SolidWorks 2021**,
mientras que el equipo trabaja con la versión **2026 SP4.1**. En consecuencia,
el complemento no aparece en el menú correspondiente.

**Solución.** Se optó por exportar únicamente la geometría en formato STL y
desarrollar un generador que deduce la estructura del URDF a partir de
mediciones sobre esa geometría. El resultado superó al que habría producido el
exportador: el modelo queda parametrizado y es reproducible mediante un solo
comando.

### 2. Discrepancia entre los ejes del CAD y los de ROS

SolidWorks entregó el ensamble con el eje **Y como vertical**, mientras que ROS
emplea **Z hacia arriba y X al frente**, conforme a REP-103. Con la convención
incorrecta, el eje de giro de las ruedas queda sobre X cuando un robot
diferencial lo requiere sobre Y, lo que invalida tanto la odometría como la
navegación.

**Solución.** El generador aplica la rotación a las mallas y a los centroides
antes de escribir el modelo, de manera que el URDF resultante no contiene
rotaciones correctivas.

### 3. Valores de masa desproporcionados en los módulos con varias tarjetas

El módulo de electrónica reportó una masa de **2 275 g**. La causa fue que, al
no tratarse de mallas cerradas, la masa se aproximaba mediante **una caja
envolvente global** que, al contener cinco tarjetas separadas entre sí,
incorporaba también el espacio vacío intermedio y lo consideraba material
macizo.

**Solución.** Se modificó el cálculo para emplear **una caja envolvente por
cada componente independiente**, sumando las contribuciones y trasladando cada
tensor de inercia al centroide del módulo mediante el teorema de ejes
paralelos. La masa del módulo descendió a 172 g, y la del robot completo pasó
de 4 186 g a 1 973 g.

### 4. Sesgo en los ángulos de los sensores de distancia

La orientación de los sensores se dedujo inicialmente mediante análisis de
componentes principales sobre los vértices de cada malla. El procedimiento
arrojó ángulos de −8.1°, +21.9° y +51.9°: correctamente espaciados 30° entre
sí, pero desplazados respecto al eje longitudinal del robot.

La causa resultó ser el **conector de perfil elevado de la tarjeta**, que
desplaza la dispersión de los vértices y, con ello, inclina el eje principal.
Al reproducir la geometría en una simulación se obtuvo un sesgo constante de
7.8° y el mismo índice de confianza reducido (0.42) que reportaba el script.

**Solución.** Se adoptó como método principal la identificación de la **cara
plana de mayor área** de la tarjeta, cuya normal corresponde a la dirección de
medición sin sesgo alguno. Los ángulos corregidos resultaron **−30°, 0° y
+30°**, simétricos respecto al eje del robot. Considerando un campo de visión
de 27° por sensor, los conos de medición quedan prácticamente contiguos.

### 5. Inercias de magnitud reducida escritas como cero

El formato numérico empleaba seis posiciones decimales fijas. La inercia de la
unidad inercial equivale a 1.26 × 10⁻⁸ kg·m², valor que con dicho formato se
escribía literalmente como `0` en el archivo XML. El defecto afectaba a la
unidad inercial, los tres sensores de distancia y los interruptores. Una
inercia nula provoca que Gazebo rechace el eslabón correspondiente, y el error
no se habría manifestado sino hasta la etapa de simulación.

**Solución.** Se modificó el formato para emplear cifras significativas.
Adicionalmente se incorporó una **validación automática** en el generador, que
revisa masas, inercias, geometrías de colisión y orígenes, y reporta cualquier
valor inválido antes de escribir los archivos.

### 6. Piezas excluidas del modelo

Los interruptores `CLM-KCD1` no coincidían con ningún patrón definido en el
archivo de configuración. El generador los reportó en su listado de archivos
STL sin asignar.

**Solución.** Se incorporó el módulo correspondiente. El reporte de piezas sin
asignar quedó establecido como verificación de rutina: un valor distinto de
cero indica geometría faltante.

### 7. Imposibilidad de ejecutar MeshLab

La aplicación fallaba con el mensaje `GLEW initialization failed`, atribuible al
controlador gráfico del equipo.

**Solución.** Ejecutarla mediante `LIBGL_ALWAYS_SOFTWARE=1 meshlab`.
Posteriormente dejó de ser necesaria, dado que la totalidad de las mediciones
se automatizó con la biblioteca trimesh.

### 8. Falla de `colcon build` al crear enlaces simbólicos

El espacio de trabajo se encontraba en una partición con sistema de archivos
**exFAT**, compartida con Windows. Dicho sistema no admite enlaces simbólicos,
que son precisamente el mecanismo que utiliza la opción `--symlink-install`.

**Solución.** Trasladar el espacio de trabajo a `~/colmibot_ws`, ubicado en una
partición ext4. Cabe señalar que exFAT tampoco conserva los permisos de Unix ni
distingue mayúsculas de minúsculas, lo que habría ocasionado problemas con el
control de versiones y con las rutas de las mallas.

### 9. Ausencia de paquetes de ROS

El archivo de lanzamiento fallaba con el mensaje
`file not found: 'xacro'`.

**Solución.** Instalar `ros-jazzy-xacro` y `ros-jazzy-joint-state-publisher-gui`
de manera independiente.

### 10. Modelo situado por debajo del plano del piso

En RViz la retícula atravesaba las llantas por su punto medio, en lugar de
quedar por debajo de ellas. La retícula representa el plano del suelo —z = 0 en
el marco `base_footprint`—, de modo que las ruedas deben apoyarse sobre ella.

El origen del problema estaba en el cálculo del parámetro `altura_chasis`. La
fórmula medía la distancia del piso al **origen absoluto del CAD**, pero
`base_link` no se ubica en ese punto, sino en el centroide del chasis, 29.8 mm
por encima. Esa diferencia correspondía exactamente al desplazamiento
observado.

El indicio determinante fue que la retícula atravesara el **centro** de la
rueda y no cualquier otra altura, lo que implicaba que el error equivalía
precisamente a la altura del centroide.

**Solución.** Medir la distancia del piso al centroide del chasis, que es la
ubicación real de `base_link`:

```python
# versión anterior
float(centroides["llanta_der"][2] - radio) * -1
# versión corregida
float(centroides["base"][2] - (centroides["llanta_der"][2] - radio))
```

El valor pasó de 13.5 mm a 43.29 mm. Dado que el archivo principal no se
sobrescribe durante la regeneración, fue necesario actualizar la propiedad
manualmente a partir del reporte que emite el generador.

Conviene destacar que este defecto no lo detectó la validación automática, sino
la revisión visual. El generador verifica masas, inercias y dimensiones, pero
carece de criterio para determinar que un robot debe encontrarse apoyado sobre
el piso.

## Medidas obtenidas del CAD

La totalidad de los valores fue medida por el generador; ninguno se capturó
manualmente:

| Parámetro | Valor |
|---|---|
| Separación entre ruedas | 177.68 mm |
| Radio de rueda | 30.00 mm |
| Altura del origen de `base_link` sobre el piso | 43.29 mm |
| Altura de la cámara sobre `base_link` | 130.45 mm |
| Orientación de los sensores de distancia | −30°, 0°, +30° |
| Masa total estimada | 1.97 kg |

## Limitaciones conocidas

**Las masas constituyen estimaciones y no mediciones.** Se calculan
multiplicando el volumen de cada malla por la densidad del material asignado.
En los casos en que el modelo CAD no conforma un sólido cerrado, el cálculo
recurre a cajas envolventes, procedimiento que **sobreestima** el valor real.

El caso más evidente son los **motorreductores, con 369.8 g cada uno**. El
generador detectó que su malla no está cerrada, es decir, que su superficie
presenta discontinuidades y no delimita un volumen definido. Sin un volumen
determinado no es posible calcular la masa a partir de la densidad, por lo que
el script recurre a la caja envolvente, cuyo volumen sí es conocido. Esa
aproximación arroja invariablemente un valor por exceso, puesto que la caja
incorpora todo el espacio vacío que rodea al cuerpo del motor y lo considera
macizo.

Para efectos de visualización en RViz esta limitación no tiene consecuencias;
para simulación dinámica sí las tiene. El archivo `robot.yaml` contempla la
opción `masa_g`, destinada a declarar masas medidas:

```yaml
  motor_der:
    # masa_g: 215        # pendiente: determinar mediante pesaje o ficha técnica
```

Al declararse, el tensor de inercia se reescala conservando su forma.

**Trabajo pendiente.** El curso publicó una versión actualizada de los archivos
CAD con materiales y pesos asignados. Dicha información se incorporará al
modelo durante los ajustes finales del robot físico.

---

# Actividad 10 — Integración en Gazebo

*(en desarrollo)*
