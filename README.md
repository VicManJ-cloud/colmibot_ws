# Teleoperación de Turtlesim con un control de Xbox

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
