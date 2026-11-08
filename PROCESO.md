# Colmibot: del CAD de SolidWorks al modelo en RViz

Este documento explica, en orden, todo lo que se hizo para pasar del CAD original del Colmibot a un modelo
del robot que ROS 2 puede mostrar en RViz. Para cada paso explica qué se hizo, por qué, qué programa se usó
y qué archivos salieron.

> Fecha: 2026-10-21, actualizado el 2026-11-07 (pasos 8 y 9). El paquete ya tiene las mallas reales, pero
> **todavía no se ha compilado ni abierto en ROS 2** (eso es el paso 7).
>
> **¿Quieres hacerlo tú mismo, sin scripts?** Ver [`GUIA_A_MANO.md`](GUIA_A_MANO.md): el paso a paso a mano,
> qué es cada archivo y cómo se conectan.

---

## Mapa general

Los pasos 1 a 3 preparan todo: revisar el CAD, entender los conceptos de ROS y armar el paquete. Del paso 4 en
adelante se transforman los archivos del CAD hasta llegar a RViz.

```
 Paso 1: revisar el CAD original y el BOM
 Paso 2: conceptos de ROS (URDF, xacro, frames, TF)
 Paso 3: armar el paquete robot_description (xacro, launch, RViz, script)
        │
        ▼
 CAD_Colmibot\  (ORIGINAL, no se modifica)
 ├─ CLM-EnsambleColmibot.SLDASM  + piezas .SLDPRT + subensambles
 └─ BOM.xlsx
        │                                        │
        │  Pasos 4 y 9: SolidWorks → STL         │  Paso 8: SolidWorks → masas
        │  (tools/export_stl_solidworks.ps1)     │  (tools/export_mass_solidworks.ps1)
        ▼                                        ▼
 stl_cad_actual\  (95 STL, mm, ejes del CAD)     inertia\componentes_cad.csv + inertia\masas.csv
        │                                        │
        │  Pasos 5 y 9: tools/prepare_meshes.py  │  Paso 8: tools/compute_inertial.py
        │    - ejes del CAD → ROS, mm → m        │    - pesos reales, ejes de ROS
        │    - origen en el eje de las llantas   │    - junta todo por link
        │    - grupos de color, quita la         │
        │      electrónica, cajas, sensores      │
        ▼                                        ▼
 colmibot_ws\src\robot_description\
 ├─ meshes\*.stl                             ← 8 mallas (6 del cuerpo + 2 llantas)
 ├─ urdf\generated\colmibot_meshes.xacro     ← medidas reales + lista de mallas y cajas
 └─ urdf\generated\colmibot_inertial.xacro   ← masas e inercias
        │
        │  Paso 7 (pendiente, en la VM): colcon build + ros2 launch
        ▼
 xacro → URDF → robot_state_publisher → /tf → RViz
```

Carpetas que existen hoy (2026-11-07) en `C:\Cad_colmibot2\` (antes estaban en `Downloads\CAD_Colmibot\`):

| Carpeta | Qué es | ¿Se modifica? |
|---|---|---|
| `CAD_Colmibot\` | El CAD original y el BOM | No, nunca |
| `stl_cad_actual\` | Exportación cruda del CAD actual (paso 9). Reemplazó a `stl_solidworks\`, la primera versión, que se mandó a la Papelera | No; solo se vuelve a generar si cambia el CAD |
| `colmibot_ws\` | Workspace de ROS 2: lo que se entrega y lo que va a GitHub | Sí: aquí se trabaja |

---

## Antes de empezar: ¿qué estamos haciendo y para qué?

**El objetivo:** tener una "copia virtual" del Colmibot en la computadora, que ROS 2 entienda y que se pueda
ver en 3D en un programa llamado RViz.

- **ROS 2** (*Robot Operating System*) no es un sistema operativo como Windows. Es un conjunto de programas
  y herramientas para hacer software de robots. Se instala sobre Linux (Ubuntu) y permite que muchos
  programas pequeños se comuniquen entre sí: uno lee la cámara, otro mueve los motores, otro decide hacia
  dónde ir, etc.
- **RViz** es el programa de ROS para **ver** lo que el robot "sabe": su forma, dónde están sus sensores,
  lo que miden. Es como una ventana 3D al cerebro del robot.
- Para que ROS sepa cómo es el robot (qué tamaño tiene, dónde están sus ruedas, dónde está la cámara), hay
  que **describírselo** en un archivo especial. Hacer esa descripción es todo este proyecto.

**El problema:** el robot ya estaba diseñado en **SolidWorks**, un programa de diseño 3D (CAD). Pero ROS no
puede abrir archivos de SolidWorks. Hay que "traducir" el diseño a algo que ROS entienda.

**La analogía:** imagina que tienes los planos de una casa hechos por un arquitecto (el CAD) y quieres
meter la casa en un videojuego (ROS/RViz). No puedes meter los planos directamente: tienes que sacar los
modelos 3D de cada parte, ponerlos en las medidas que usa el videojuego y decirle al juego qué partes se
mueven (las puertas) y cuáles no (las paredes).

Los pasos 1 a 3 son la preparación:

| Paso | En una frase |
|---|---|
| 1 | Ver qué hay en el diseño original y decidir qué importa |
| 2 | Aprender cómo "piensa" ROS para poder describirle el robot |
| 3 | Escribir la descripción del robot y lo necesario para mostrarlo |

---

## Paso 1. Revisar el diseño original

### 1.1 ¿Qué es un CAD y qué archivos había?

Un **CAD** (*Computer-Aided Design*, diseño asistido por computadora) es un programa para dibujar objetos en
3D con medidas exactas. SolidWorks es uno de los más usados en ingeniería.

En SolidWorks hay dos tipos principales de archivo:

- **Pieza (`.SLDPRT`)**: un solo objeto físico. Por ejemplo, una llanta, un poste o una placa.
- **Ensamble (`.SLDASM`)**: un archivo que **junta varias piezas** y dice dónde va cada una. No contiene la
  forma de las piezas; solo dice "aquí va la llanta, girada así, a tantos milímetros del centro".

> **Analogía:** las piezas son los bloques de LEGO; el ensamble es el instructivo que dice dónde va cada
> bloque. Si pierdes un bloque, el instructivo no sirve de nada. Por eso **un ensamble necesita que todas
> sus piezas estén en la misma carpeta**.

Una pieza que se repite (por ejemplo, las 2 llantas, que son idénticas) existe **una sola vez** como archivo.
El ensamble simplemente la usa dos veces, en dos lugares distintos. A cada uso se le llama **instancia**.

Un ensamble también puede contener otros ensambles más pequeños, llamados **subensambles**. Es como un
instructivo que dice "aquí va la batería ya armada", y la batería tiene su propio instructivo.

Lo que traía la carpeta `CAD_Colmibot\` (unos 91 MB en total):

| Archivo | Qué es |
|---|---|
| `CLM-EnsambleColmibot.SLDASM` | El **ensamble principal**: el robot completo |
| `CLM-EnsBat3S1P.SLDASM` | Subensamble de la **batería**: 3 pilas tipo 18650, la placa que las protege (BMS) y sus soportes |
| `CLM-LogitechC920Montaj.SLDASM` | Subensamble de la **cámara**: cuerpo, brazo y lente |
| `CLM-RasPi5.SLDASM` | Subensamble de la **Raspberry Pi 5**: la computadora del robot, con todos sus puertos y chips |
| `CLM-RasPi5_Cooler.SLDASM` | Subensamble del **ventilador** de la Raspberry Pi |
| 30 archivos `.SLDPRT` | Las **piezas** sueltas: llantas, cuerpo, placas, postes, motores, sensores, etc. |
| `BOM.xlsx` | Un Excel con la **lista de materiales** |

> **¿Qué es un BOM?** *Bill of Materials*, o lista de materiales. Es la "lista del súper" del robot: cada
> pieza, cuántas se necesitan y cómo se consigue (se imprime en 3D, se corta con láser o se compra).

### 1.2 ¿Cómo se revisó?

1. **Se contaron los archivos** por tipo, para saber de qué tamaño era el proyecto.
2. **Se abrió el BOM** y se comparó, renglón por renglón, con los nombres de los archivos. Así se confirma
   que no falte ninguna pieza.
3. **Se intentó ver por dentro el ensamble**, para saber qué piezas usa. No se pudo: SolidWorks guarda los
   ensambles en un formato propio y comprimido que solo SolidWorks (u otro CAD compatible, como Onshape)
   puede abrir. O sea, no había forma de saber si el ensamble estaba completo hasta abrirlo en un CAD
   (eso se hizo en el paso 4).
4. **Se encontraron archivos raros que empiezan con `~$`** (por ejemplo, `~$CLM-Base.SLDPRT`). No son
   piezas. SolidWorks los crea mientras alguien tiene un archivo abierto, como un letrero de "ocupado".
   Normalmente se borran solos al cerrar el programa; si alguien no lo cerró bien, se quedan. No sirven para
   nada, así que se ignoraron.

### 1.3 ¿Qué tiene el robot?

Al leer el BOM se armó esta lista. Explicada en palabras simples:

**Para moverse:**
- **2 motorreductores Pololu 37D con encoder.** Un motorreductor es un motor con engranes que lo hacen girar
  más lento pero con más fuerza. El *encoder* es un sensor que cuenta cuántas vueltas da, para saber cuánto
  avanzó el robot.
- **2 llantas de 60 mm de diámetro.** Van conectadas a los motores.
- **2 ruedas locas.** Son ruedas pequeñas que giran libremente en cualquier dirección (como las de una silla
  de oficina). No tienen motor: solo sostienen al robot para que no se caiga hacia adelante o hacia atrás.

> **¿Qué es un robot "diferencial"?** Es un robot con dos ruedas motrices, una de cada lado. Para avanzar,
> las dos giran igual. Para dar vuelta, una gira más rápido que la otra (o en sentido contrario). Así se
> mueve el Colmibot, igual que una silla de ruedas o un tanque.

**Para pensar y controlar:**
- **Raspberry Pi 5:** una computadora pequeña; aquí correría ROS 2. Lleva un ventilador.
- **ESP32:** un microcontrolador (una computadora muy simple) que controla directamente los motores y lee
  algunos sensores. Va sobre una placa de expansión, para conectar cables más fácil.
- **Cytron MDD10A:** el *driver* de motores. Recibe órdenes de la ESP32 y le da a los motores la corriente
  que necesitan (la ESP32 sola no tiene fuerza para moverlos).
- **XL4015:** un convertidor de voltaje. Ajusta el voltaje de la batería al que necesita cada componente.
- **Batería 3S:** 3 pilas 18650 en serie (unos 11 V) con un BMS, que es una placa que la protege de
  cargarse o descargarse de más.
- **2 interruptores KCD1:** los botones de encendido.

**Para "sentir" el entorno (sensores):**
- **Cámara Logitech C920:** para ver.
- **IMU BMI270:** mide aceleración y giro. Sirve para saber si el robot está girando o inclinado (como el
  sensor que hace que la pantalla del celular gire).
- **3 sensores VL53L1X:** sensores de distancia "ToF" (*Time of Flight*, tiempo de vuelo). Mandan un pulso
  de luz infrarroja y miden cuánto tarda en regresar, para saber a qué distancia hay un obstáculo. Van al
  frente: uno al centro y dos a los lados.

**Estructura (el "esqueleto"):**
- Cuerpo, soportes y postes **impresos en 3D** (plástico).
- 3 placas de **corte láser** (`CLM-Base`, `CLM-Plato` y `CLM-PisoCam`), que forman los "pisos" del robot.

**Detalles del BOM que no cuadran** (no afectan este trabajo, pero conviene corregirlos):
- Algunos nombres del BOM no coinciden con los archivos. Por ejemplo, el BOM dice `CLM-Llanta60mm` y el
  archivo se llama `CLM-Llanta60mmD`.
- Algunas cantidades son dudosas, como 2 soportes de BMS para un solo BMS.
- Faltan los tornillos, los materiales y los espesores.

La lista completa está en `soloparausointerno.md`, sección 3.

### 1.4 ¿Qué se decidió?

Para ROS, no todas las piezas son igual de importantes. La pregunta clave es: **¿esta pieza se mueve, mide
algo, o solo está ahí?** Con eso se separaron en tres tipos:

| Tipo | Piezas | Qué necesita ROS de ellas |
|---|---|---|
| **Se mueven** | Las 2 llantas | Saber dónde están y alrededor de qué eje giran, para poder dibujarlas girando |
| **Miden algo (sensores)** | Cámara, IMU y los 3 ToF | Saber **exactamente** dónde están y hacia dónde apuntan. Si el sensor de la izquierda ve un obstáculo a 20 cm, ROS necesita saber dónde está ese sensor para calcular dónde está el obstáculo |
| **Solo están ahí** | Todo lo demás (placas, cuerpo, Raspberry Pi, batería, motores, ruedas locas...) | Solo hace falta que se vean. Para ROS, todas son "el cuerpo del robot" |

Las ruedas locas sí giran en la realidad, pero como nadie las mueve ni las mide, para ROS cuentan como parte
del cuerpo.

**¿Por qué importa esta decisión?** Porque define todo lo que sigue:
- En el paso 3, cuántas "partes" tiene la descripción del robot: un cuerpo, dos llantas y cinco sensores.
- En el paso 5, cómo se agrupan los modelos 3D: las llantas por separado y el resto junto.

---

## Paso 2. Cómo "piensa" ROS: los conceptos básicos

Este paso no produce ningún archivo. Es la teoría que hace falta para entender los pasos 3 a 7. Cada
concepto viene con una analogía y con un ejemplo de nuestro robot.

### 2.1 XML: el formato de los archivos

Casi todos los archivos de la descripción del robot están en **XML**. XML es una forma de escribir
información con **etiquetas** entre `< >`, parecido a HTML (el lenguaje de las páginas web):

```xml
<llanta nombre="izquierda">
  <radio>30</radio>
</llanta>
```

Cada cosa se abre con `<algo>` y se cierra con `</algo>`. Lo que está entre `<!--` y `-->` es un
**comentario**: una nota para las personas que la computadora ignora.

### 2.2 URDF: la descripción del robot

**URDF** (*Unified Robot Description Format*) es el formato estándar de ROS para describir un robot. Es un
archivo XML que describe al robot como un **conjunto de partes unidas entre sí**.

> **Analogía:** piensa en un esqueleto. Los **huesos** son partes rígidas; las **articulaciones** (codo,
> rodilla) los unen y dicen cómo se pueden mover. En URDF, los huesos se llaman **links** y las
> articulaciones se llaman **joints**.

**Link (parte rígida).** Cualquier parte que no se deforma: el cuerpo del robot, una llanta, un sensor. Un
link puede tener tres descripciones:

| Descripción | Para qué sirve | En nuestro robot |
|---|---|---|
| `visual` | Cómo **se ve** en RViz | Los modelos 3D reales del CAD |
| `collision` | Su forma **simplificada** para detectar choques en simulación | Una caja y cilindros |
| `inertial` | Su **masa** y cómo se distribuye, para simular física | Valores aproximados |

¿Por qué tener una forma para ver y otra para chocar? Porque calcular choques con un modelo de cientos de
miles de triángulos es lentísimo. Para choques basta una caja del mismo tamaño.

**Joint (unión).** Une dos links: un **padre** y un **hijo**. Dice dos cosas:
1. **Dónde está el hijo respecto al padre:** "la llanta izquierda está 87 mm a la izquierda del centro del
   cuerpo".
2. **Cómo se puede mover el hijo:**

| Tipo de joint | Movimiento | Ejemplo en el robot |
|---|---|---|
| `fixed` (fijo) | No se mueve | La cámara atornillada al cuerpo |
| `continuous` (continuo) | Gira sin límite, vueltas y vueltas | Las llantas |
| `revolute` (giratorio con límite) | Gira, pero solo cierto ángulo | No se usa (sería un brazo, una puerta) |
| `prismatic` (deslizante) | Se desliza en línea recta | No se usa (sería un elevador) |

Así se ve el joint real de la llanta izquierda de nuestro robot, con cada línea explicada:

```xml
<joint name="wheel_left_joint" type="continuous">   <!-- unión llamada "wheel_left_joint", gira sin límite -->
  <parent link="base_link"/>                         <!-- el padre: el cuerpo del robot -->
  <child link="wheel_left_link"/>                    <!-- el hijo: la llanta izquierda -->
  <origin xyz="0 0.08705 0" rpy="0 0 0"/>            <!-- posición: 0.08705 m (87 mm) a la izquierda, sin girar -->
  <axis xyz="0 1 0"/>                                <!-- gira alrededor del eje Y (el eje que va de lado a lado) -->
</joint>
```

En `origin`, **xyz** es la posición (adelante, izquierda, arriba) y **rpy** es la rotación (*roll, pitch,
yaw*: alabeo, cabeceo y giro, como en un avión).

### 2.3 xacro: URDF con atajos

Escribir un URDF a mano es repetitivo. Por ejemplo, la llanta izquierda y la derecha son iguales, salvo que
una va a la izquierda y la otra a la derecha. **xacro** (*XML macros*) es una forma de escribir URDF con
atajos. Después, un programa llamado `xacro` lo convierte en URDF normal.

> **Analogía:** xacro es como una plantilla de Word con campos para rellenar. Escribes la carta una vez y
> la plantilla genera una para cada destinatario.

Los atajos que se usan:

**a) Variables (`property`).** Se guarda una medida con nombre y se usa donde haga falta:

```xml
<xacro:property name="wheel_radius" value="0.030"/>   <!-- radio de la llanta: 0.030 m = 30 mm -->
...
<cylinder radius="${wheel_radius}" .../>               <!-- aquí se usa: ${...} se reemplaza por 0.030 -->
```

Si la llanta cambia de tamaño, se cambia el número en **un solo lugar**.

**b) Incluir otros archivos (`include`).** Un archivo puede "pegar" el contenido de otro. Así se separan
las medidas, los colores y el modelo en archivos distintos, más fáciles de leer.

**c) Macros (`macro`).** Un bloque con "huecos" que se rellenan cada vez que se usa. En nuestro robot hay
una macro `drive_wheel` (rueda motriz) que se usa dos veces:

```xml
<xacro:drive_wheel side="left"  ... />   <!-- genera la llanta izquierda -->
<xacro:drive_wheel side="right" ... />   <!-- genera la llanta derecha -->
```

**d) Condiciones (`if` / `unless`).** "Si pasa esto, pon esto; si no, pon lo otro". Lo usamos para que el
mismo archivo pueda dibujar el robot con figuras simples o con los modelos 3D reales.

**Detalle importante:** si una variable se define dos veces, **vale la última**. Con eso funciona el paso 5:
primero se cargan las medidas estimadas y después las reales, que "pisan" a las estimadas.

### 2.4 Frames: puntos de referencia

Un **frame** (marco de referencia) es un punto con tres ejes (X, Y, Z) pegado a algo. Sirve para decir dónde
está cada cosa **respecto a otra**.

> **Analogía:** si das indicaciones como "la tienda está 2 cuadras adelante y 1 a la izquierda **de la
> escuela**", la escuela es tu frame de referencia. Sin decir "de dónde", las distancias no significan nada.

En nuestro robot, cada link tiene su frame. Los más importantes:

| Frame | Dónde está | Para qué |
|---|---|---|
| `base_footprint` | En el **piso**, justo debajo del centro entre las dos llantas | Es "la posición del robot" en el mapa |
| `base_link` | En el **centro entre las dos llantas, a la altura de su eje** (30 mm sobre el piso) | Es el frame principal: todo lo demás se mide desde aquí |
| `wheel_left_link`, `wheel_right_link` | En el centro de cada llanta | Para girarlas |
| `camera_link`, `imu_link`, `tof_..._link` | En cada sensor | Para saber desde dónde mide cada uno |

¿Por qué `base_link` está entre las llantas? Porque en un robot diferencial ese es el punto sobre el que
gira cuando una rueda va hacia adelante y la otra hacia atrás: el robot da vueltas "en su lugar" alrededor
de ese punto.

### 2.5 TF: el sistema que sabe dónde está todo

**TF** (*Transform*, transformación) es la parte de ROS que **guarda cómo se relacionan todos los frames**
y lo mantiene actualizado mientras las cosas se mueven.

> **Analogía:** es como un árbol genealógico con direcciones. Cada frame sabe dónde está respecto a su
> "papá". TF puede responder preguntas como "¿dónde está el sensor izquierdo respecto al piso?" sumando el
> camino: sensor → cuerpo → piso.

**Ejemplo práctico:** el ToF izquierdo dice "hay algo a 20 cm frente a mí". Con TF, ROS sabe que ese sensor
está 8 cm adelante y 5 cm a la izquierda del centro del robot, y girado 30° hacia la izquierda. Con eso
calcula dónde está el obstáculo **respecto al robot**. Sin TF, el dato "20 cm" no sirve.

**La cámara es especial.** Por costumbre, las cámaras usan otros ejes: Z hacia adelante (hacia donde mira),
X hacia la derecha y Y hacia abajo. Por eso hay un frame extra, `camera_optical_frame`, girado respecto a
`camera_link` para seguir esa costumbre.

### 2.6 La regla de ejes de ROS (REP-103)

Para que todos los robots y programas se entiendan, ROS tiene una regla oficial (el documento **REP-103**):

- **X** apunta hacia **adelante**
- **Y** apunta hacia la **izquierda**
- **Z** apunta hacia **arriba**
- Las distancias van en **metros** y los ángulos en **radianes** (180° = 3.1416 radianes).

En RViz cada eje tiene un color fijo: **X rojo, Y verde, Z azul**. Truco para recordarlo: RGB = XYZ.

**El problema con nuestro CAD:** SolidWorks no sigue esa regla. En el diseño del Colmibot:

| | ROS | Nuestro CAD |
|---|---|---|
| Arriba | +Z | +Y |
| Adelante | +X | −Z |
| Unidades | metros | milímetros |

Si metiéramos los modelos 3D tal cual, el robot aparecería **acostado de lado** y **mil veces más grande**
(ROS leería 200 mm como 200 metros). Por eso hay que rotarlos y escalarlos; lo hace el script del paso 5.

### 2.7 Modelos 3D en STL

Un archivo **STL** guarda la **superficie** de un objeto 3D como miles de triángulos pegados.

> **Analogía:** es como cubrir un objeto con papel en forma de triángulos. Con pocos triángulos se ve
> "cuadrado" (como un videojuego viejo); con muchos se ve liso, pero el archivo pesa más.

Lo que **no** guarda un STL:
- **Colores:** por eso los colores se ponen aparte, en el URDF.
- **Unidades:** solo guarda números. Hay que saber si están en milímetros o en metros (los nuestros, en mm).

Hay dos versiones: **ASCII** (texto que se puede leer, pero muy pesado) y **binario** (pesa unas 5 veces
menos). Se usó binario.

### 2.8 Nodos, tópicos y launch: cómo se organiza ROS

- **Nodo:** un programa de ROS que hace una tarea. Por ejemplo, uno publica la forma del robot y otro dibuja.
- **Tópico:** un "canal" por donde los nodos se mandan mensajes. Un nodo **publica** en el tópico y otros
  lo **escuchan**. Los tópicos tienen nombres como `/tf` o `/joint_states`.

> **Analogía:** los tópicos son como canales de radio. Un nodo transmite en el canal `/tf` y cualquier
> nodo que sintonice ese canal recibe los mensajes.

- **Launch file:** un archivo que **arranca varios nodos a la vez** con una sola orden, en lugar de abrir
  una terminal por cada uno.

### 2.9 Paquete y workspace

- **Paquete:** la unidad básica de ROS. Es una carpeta con archivos relacionados y dos archivos que la
  identifican: `package.xml` (nombre y de qué depende) y `CMakeLists.txt` (cómo se instala). El nuestro se
  llama `robot_description`, que es el nombre que se acostumbra para el paquete con el modelo del robot.
- **Workspace (espacio de trabajo):** la carpeta donde viven los paquetes. Tiene una subcarpeta `src/`
  (*source*, código fuente) con los paquetes adentro. El nuestro es `colmibot_ws` (*ws* = workspace).
- **Compilar (`colcon build`):** en ROS 2, `colcon` es el programa que prepara los paquetes para usarse. Crea
  tres carpetas: `build/`, `install/` y `log/`. No se suben a Git porque se pueden volver a generar en
  cualquier momento.
- **`source install/setup.bash`:** un comando que le dice a la terminal "aquí están mis paquetes". Hay que
  correrlo en **cada terminal nueva**; si no, ROS no encuentra el paquete.

---

## Paso 3. Escribir la descripción del robot: el paquete `robot_description`

Con los conceptos del paso 2, este paso es escribir los archivos que describen al Colmibot y los que lo
muestran en RViz.

### 3.1 Por qué se hizo antes de tener los modelos 3D

Cuando se escribió el paquete, todavía no había forma de sacar los modelos 3D del CAD (nadie tenía
SolidWorks; eso se resolvió en el paso 4). Para no quedarse esperando, el paquete se hizo con **dos modos**:

| Modo | Cómo se ve el robot | Para qué sirve |
|---|---|---|
| `use_meshes:=false` (sin modelos) | Con **figuras simples**: una caja para el cuerpo, cilindros para las llantas y esferas para las ruedas locas, con medidas estimadas | Probar que todo funciona (que RViz abre, que las llantas giran, que los sensores están) **sin necesitar los modelos 3D** |
| `use_meshes:=true` (con modelos) | Con los **modelos 3D reales** del CAD y las medidas reales | El resultado final |

*Mesh* significa "malla": así se le dice en inglés a un modelo 3D de triángulos.

**Ventaja:** cuando por fin llegaron los modelos 3D, no hubo que reescribir nada. Solo se corrió el script
del paso 5, que agrega los modelos y las medidas reales.

#### Estructura y geometría: las dos cosas que ROS necesita

¿Cómo se pudo describir el robot sin poder abrir el CAD? Porque ROS necesita saber **dos cosas distintas**,
y cada una sale de un lugar distinto:

1. **La estructura:** qué partes tiene el robot y cómo se conectan. Por ejemplo, "hay un cuerpo, dos
   llantas que giran y cinco sensores pegados al cuerpo". Son los **links y joints** del URDF.
2. **La geometría:** qué forma tiene cada parte y dónde está exactamente. Por ejemplo, "la llanta mide
   60 mm y está a 87 mm del centro". Son las **mallas STL** y las **medidas**.

La estructura se pudo escribir **sin abrir el CAD**; la geometría **no**:

| Archivo original | ¿Se puede leer sin un CAD? | Qué aportó |
|---|---|---|
| `BOM.xlsx` | ✅ Sí, es un Excel normal | La lista de componentes → **la estructura** |
| Nombres de los `.SLDPRT` / `.SLDASM` | ✅ Sí, son solo nombres | Confirmar que no faltara ninguna pieza del BOM |
| **Contenido** de los `.SLDPRT` / `.SLDASM` | ❌ No (formato propio de SolidWorks, paso 1.2) | Nada, hasta que se abrió en SolidWorks → **la geometría** (pasos 4 y 5) |

> **Analogía:** el árbol de links es como el **organigrama** de una empresa (quién depende de quién) y las
> medidas son la **dirección de la oficina** de cada persona. El organigrama se puede escribir el primer
> día; las direcciones se llenan cuando ya se sabe en qué piso está cada quien. O, como una maqueta:
> primero se arma con cajas de cartón (modo `use_meshes:=false`) y luego se cambian por los muebles reales.

#### De la regla del paso 1.4 al árbol de links

El árbol del robot (paso 3.5) sale **directamente** de la pregunta del paso 1.4: *¿la pieza se mueve, mide
algo o solo está ahí?*

| Respuesta | Componentes | En el URDF se vuelve... |
|---|---|---|
| **Se mueve** | Las 2 llantas | Un link propio con un joint **`continuous`** (gira sin límite, alrededor del eje Y) |
| **Mide algo** | Cámara, IMU y los 3 ToF | Un link propio, **sin forma**, con un joint **`fixed`**: no se mueve, pero ROS necesita saber dónde está y hacia dónde apunta |
| **Solo está ahí** | Placas, cuerpo, Raspberry Pi, batería, motores, ruedas locas... | **Ningún link nuevo:** todo se dibuja dentro de `base_link` |

Por eso el CAD tiene más de 40 piezas, pero el URDF solo tiene **11 links**: `base_footprint`, `base_link`,
2 llantas y 7 frames de sensores (contando `camera_optical_frame`). Para armar ese árbol solo hacía falta
saber **qué hay**, y eso lo dice el BOM.

#### Las tres secciones de un link

Un link puede tener hasta tres secciones. `base_link` y las llantas tienen las tres:

| Sección | Para qué sirve | Qué usa el Colmibot |
|---|---|---|
| `<visual>` | Lo que **se ve** en RViz | Figuras simples **o** las mallas STL, según `use_meshes` |
| `<collision>` | La forma "para chocar" (simulación y planeación de rutas) | **Siempre** figuras simples: son mucho más ligeras que una malla de 11 MB |
| `<inertial>` | Masa e inercia, para simular física (por ejemplo en Gazebo) | Fórmulas de caja y de cilindro (paso 3.7) con masas estimadas |

En RViz **solo importa `<visual>`**. Las otras dos quedaron listas para cuando se simule el robot. Los links
de los sensores no tienen ninguna de las tres: son solo un punto con sus ejes.

#### Los números van aparte

Todas las posiciones (los `x y z` de cada joint) son **variables**, no números escritos directamente en el
árbol. Primero se llenaron con estimaciones en `colmibot_params.xacro` (paso 3.6); después el script del
paso 5 escribió las reales en `generated/colmibot_meshes.xacro`, **con los mismos nombres**. Como ese archivo
se pega después, sus valores reemplazan a los estimados. Gracias a esa separación, al llegar el CAD la
estructura no cambió en nada: solo cambiaron los números.

| Pregunta | De dónde salió | Dónde está escrita |
|---|---|---|
| ¿Qué partes tiene? | BOM + la regla del paso 1.4 | Los `<link>` de `colmibot.urdf.xacro` (3.5) |
| ¿Cuáles se mueven y cómo? | Es un robot diferencial: solo giran sus 2 llantas | `type="continuous"` y `axis 0 1 0` en `macros.xacro` (3.7) |
| ¿Dónde está cada cosa? | Primero estimado, luego medido del CAD | `colmibot_params.xacro` (3.6) → reemplazado por `generated/colmibot_meshes.xacro` (5.9) |
| ¿Cómo se ve? | Figuras simples, luego las mallas STL | `<visual>`, según `use_meshes` |

### 3.2 Los archivos del paquete y cómo se conectan

```
colmibot_ws/                        ← el workspace
├─ README.md                        ← documentación para entregar
├─ PROCESO.md                       ← este documento
├─ .gitignore                       ← lo que Git no debe subir
├─ soloparausointerno.md            ← notas del equipo (no se sube)
└─ src/
   └─ robot_description/            ← el paquete
      ├─ package.xml                ← "credencial" del paquete
      ├─ CMakeLists.txt             ← instrucciones de instalación
      ├─ launch/
      │  └─ display.launch.py       ← arranca todo con una orden
      ├─ rviz/
      │  └─ display.rviz            ← cómo se configura la vista de RViz
      ├─ urdf/                      ← la descripción del robot
      │  ├─ colmibot.urdf.xacro     ← el archivo principal: partes y uniones
      │  ├─ colmibot_params.xacro   ← todas las medidas (estimadas)
      │  ├─ macros.xacro            ← plantillas: llanta, sensor, inercias
      │  ├─ materials.xacro         ← colores
      │  └─ generated/
      │     └─ colmibot_meshes.xacro← medidas reales (lo crea el script)
      ├─ meshes/                    ← modelos 3D (los crea el script)
      └─ tools/
         └─ prepare_meshes.py       ← el script del paso 5
```

Qué pasa cuando se ejecuta, en orden:

```
1. Se corre el launch (display.launch.py)
2. El launch le pide a xacro que convierta colmibot.urdf.xacro en URDF:
      colmibot.urdf.xacro
        ├─ pega colmibot_params.xacro         → medidas estimadas
        ├─ pega materials.xacro               → colores
        ├─ pega macros.xacro                  → plantillas
        └─ si use_meshes=true, pega generated/colmibot_meshes.xacro
                                               → medidas reales (pisan a las estimadas)
                                               → usa los modelos de meshes/
3. El URDF resultante se le pasa a robot_state_publisher, que calcula dónde está cada frame
4. RViz lo dibuja
```

Ahora, cada archivo en detalle.

### 3.3 `package.xml`: la credencial del paquete

Es un XML con los datos del paquete:
- **Nombre:** `robot_description`.
- **Descripción:** "Modelo URDF/xacro del robot móvil diferencial Colmibot y su visualización en RViz".
- **Responsable:** todavía dice `todo@todo.com`; **hay que poner el correo real**.
- **Licencia:** MIT (una licencia abierta que permite usar el código libremente).
- **Dependencias:** los otros paquetes de ROS que necesita para funcionar:

| Dependencia | Para qué |
|---|---|
| `xacro` | Convertir los `.xacro` en URDF |
| `robot_state_publisher` | Publicar la forma del robot y la posición de cada frame |
| `joint_state_publisher` y `joint_state_publisher_gui` | Decir en qué ángulo están las llantas (con o sin ventana de controles) |
| `rviz2` | Dibujar el robot |
| `launch`, `launch_ros` | Que funcione el archivo launch |

Con estas dependencias anotadas, el comando `rosdep` puede instalar todo lo que falte de una vez.

### 3.4 `CMakeLists.txt`: instrucciones de instalación

Le dice a `colcon` qué hacer con el paquete al compilar. Nuestro paquete **no tiene programas que compilar**
(no hay código en C++), así que solo dice: "copia las carpetas `launch`, `meshes`, `rviz` y `urdf` a la
carpeta de instalación", que es donde ROS las busca.

**Consecuencia práctica:** ROS usa la **copia** instalada, no los archivos originales. Si se cambia un
archivo (un color, una medida o un modelo 3D), **hay que volver a correr `colcon build`** para que el cambio
se vea.

### 3.5 `colmibot.urdf.xacro`: el archivo principal

Es el "esqueleto" del robot. Se lee de arriba abajo:

**1. Recibe la opción `use_meshes`.** Por defecto es `true` (modelos 3D reales; antes era `false`, ver paso 10).

**2. Pega los demás archivos:** medidas, colores y plantillas. Si `use_meshes` es `true`, también pega el
archivo con las medidas reales.

**3. Crea `base_footprint`.** Un frame vacío (sin forma) en el piso. Es el punto que, más adelante, un
sistema de navegación usaría como "aquí está el robot".

**4. Une `base_footprint` con `base_link`.** Con un joint **fijo** que sube 30 mm, exactamente el radio de la
llanta. Así `base_link` queda a la altura del eje de las llantas, porque las llantas tocan el piso.

**5. Le da forma al cuerpo (`base_link`):**
- **Con modelos 3D:** pone los 7 modelos del cuerpo (electrónica, batería, piezas impresas, etc.), cada uno
  con su color.
- **Sin modelos:** pone una caja (el cuerpo) y dos esferas (las ruedas locas, una adelante y una atrás).
- **Para choques**, en los dos modos usa la caja y las esferas, porque son mucho más ligeras.
- Su **masa** se estima en 1.2 kg.

**6. Crea las 2 llantas** con la plantilla `drive_wheel` (explicada en 3.7).

**7. Crea los frames de los sensores** con la plantilla `sensor_frame`:
- `camera_link`: la cámara.
- `camera_optical_frame`: colgado de la cámara y girado para seguir la costumbre de las cámaras (paso 2.5).
- `imu_link`: la IMU.
- `tof_left_link`: el ToF izquierdo, girado 30° hacia la izquierda.
- `tof_center_link`: el ToF central, mirando derecho al frente.
- `tof_right_link`: el ToF derecho, girado 30° hacia la derecha.

El resultado es este árbol (cada línea es "papá → hijo"):

```
base_footprint                    (en el piso)
└─ base_link                      (cuerpo, a la altura del eje de las llantas)
   ├─ wheel_left_link             (llanta izquierda: gira)
   ├─ wheel_right_link            (llanta derecha: gira)
   ├─ camera_link                 (cámara)
   │  └─ camera_optical_frame     (cámara, con los ejes "de cámara")
   ├─ imu_link                    (IMU)
   ├─ tof_left_link               (ToF izquierdo)
   ├─ tof_center_link             (ToF central)
   └─ tof_right_link              (ToF derecho)
```

Los sensores son links **sin forma** (no se dibujan): solo son puntos de referencia. Su forma ya aparece
dentro del modelo de electrónica o de la cámara.

### 3.6 `colmibot_params.xacro`: las medidas

Aquí están **todas las medidas** del robot juntas, en metros. Cuando se escribió, no se podía abrir el CAD,
así que muchas eran **estimaciones** (marcadas con `[CAD]` en el archivo). Después, el script del paso 5
midió las reales directamente de los modelos 3D:

| Medida | Estimada al principio | Real (medida en el paso 5) |
|---|---|---|
| Radio de llanta | 30 mm | 30.0 mm ✅ |
| Ancho de llanta | 26 mm | 12.0 mm |
| Distancia entre llantas | 190 mm | 174.1 mm |
| Cuerpo (largo × ancho × alto) | 220 × 160 × 100 mm | 200 × 200 × 167 mm |
| Cámara (adelante del eje, arriba del eje) | 90 mm, 140 mm | 53 mm, 121 mm |
| ToF central (adelante, arriba) | 115 mm, 20 mm | 93 mm, 59 mm |
| Ángulo de los ToF laterales | 30° | **No se pudo medir automáticamente: sigue en 30°** |

¿Por qué se dejan las estimadas si ya hay reales? Porque el modo sin modelos (`use_meshes:=false`) las sigue
usando. En el modo con modelos, las reales las reemplazan (por la regla de "vale la última" del paso 2.3).

Las **masas** (1.2 kg el cuerpo y 0.05 kg cada llanta) también son estimadas. Para RViz no importan; solo
importarían en una simulación de física.

### 3.7 `macros.xacro`: las plantillas

**Plantilla `drive_wheel` (rueda motriz).** Recibe de qué lado va (`left` o `right`) y su posición. Crea:
- **El link de la llanta** (`wheel_left_link` o `wheel_right_link`):
  - *Forma visible:* con modelos, el archivo `meshes/wheel_left.stl` (o `wheel_right.stl`); sin modelos, un
    cilindro. Detalle: en URDF los cilindros nacen "parados" (sobre Z), así que se giran 90° para que queden
    "acostados" como llanta.
  - *Forma para choques:* siempre el cilindro.
  - *Masa e inercia:* las de un cilindro de 0.05 kg.
- **El joint** (`wheel_left_joint` o `wheel_right_joint`): tipo `continuous`, que gira alrededor del eje Y.
  Por eso, al mover el control deslizante en RViz, la llanta gira como debe.

**Plantilla `sensor_frame`.** Recibe el nombre, el padre, la posición y, si hace falta, los ángulos. Crea un
link vacío y un joint fijo. Se usa para los 6 frames de sensores.

**Plantillas `box_inertia` y `wheel_inertia`.** La **inercia** describe qué tan difícil es hacer girar un
objeto, según cómo está repartida su masa. Estas plantillas aplican las fórmulas de física de una caja y de
un cilindro. RViz no las usa, pero un URDF sin inercias falla si después se quiere simular el robot (por
ejemplo, en Gazebo).

### 3.8 `materials.xacro`: los colores

Como los STL no guardan colores, aquí se define un color por grupo de piezas. Los colores se escriben como
**RGBA**: cuánto rojo, verde y azul (de 0 a 1), y la opacidad (1 = sólido).

| Grupo | Color actual | Ejemplo en RGBA |
|---|---|---|
| Piezas impresas en 3D | gris oscuro | `0.15 0.15 0.15 1` |
| Placas de corte láser | color madera | `0.85 0.70 0.50 1` |
| Electrónica | verde de circuito | `0.05 0.45 0.20 1` |
| Batería | azul | `0.20 0.35 0.80 1` |
| Motores | gris metálico | `0.70 0.70 0.72 1` |
| Ruedas locas | gris | `0.55 0.55 0.58 1` |
| Cámara y llantas | casi negro | `0.08 0.08 0.08 1` |

Los nombres de los colores son **los mismos** que los grupos de modelos 3D del paso 5 (`electronica`,
`bateria`, ...). Así cada modelo se pinta con su color. Son provisionales: lo ideal es igualarlos al robot
físico.

### 3.9 `display.launch.py`: arrancar todo con una orden

Es un archivo en **Python** que arranca los nodos necesarios. Sin él habría que abrir 4 terminales y
escribir 4 comandos largos.

Los nodos que arranca:

| Nodo | Qué hace, en simple | Canal (tópico) donde publica |
|---|---|---|
| `robot_state_publisher` | Recibe la descripción del robot y, con los ángulos de las llantas, calcula dónde está cada parte | `/robot_description` (la descripción) y `/tf` (las posiciones) |
| `joint_state_publisher_gui` | Abre una ventanita con **controles deslizantes** (*sliders*), uno por llanta, para girarlas a mano | `/joint_states` (los ángulos) |
| `joint_state_publisher` | Lo mismo, pero sin ventana (deja las llantas en 0°) | `/joint_states` |
| `rviz2` | Abre RViz y dibuja el robot | — |

Antes de arrancarlos, el launch corre `xacro` para convertir el `.xacro` en URDF.

**Cómo fluye la información cuando mueves un slider:**

```
Mueves el slider de la llanta izquierda
   → joint_state_publisher_gui publica "llanta izquierda = 45°" en /joint_states
   → robot_state_publisher lo escucha y recalcula dónde está la llanta
   → publica la nueva posición en /tf
   → RViz la escucha y dibuja la llanta girada
```

**Opciones del launch** (se escriben al final del comando, como `use_meshes:=true`):

| Opción | Valor por defecto | Qué cambia |
|---|---|---|
| `use_meshes` | `true` | `true` = usar los modelos 3D reales |
| `gui` | `true` | `false` = no abrir la ventana de sliders |
| `rviz` | `true` | `false` = no abrir RViz (por ejemplo, si solo se quiere publicar el modelo) |
| `model` | `colmibot.urdf.xacro` | Usar otro archivo de descripción |
| `rviz_config` | `display.rviz` | Usar otra configuración de vista |

Ejemplo:

```bash
ros2 launch robot_description display.launch.py use_meshes:=true
#   ros2 launch  = "arranca un launch"
#   robot_description = de este paquete
#   display.launch.py = este archivo
#   use_meshes:=true = con los modelos 3D reales
```

### 3.10 `display.rviz`: la vista guardada de RViz

RViz abre vacío por defecto y habría que agregarle todo a mano cada vez. Este archivo guarda una
configuración lista:

| Elemento | Qué muestra |
|---|---|
| **Fixed Frame: `base_footprint`** | El punto de referencia de toda la escena: el piso bajo el robot |
| **Grid** | Una cuadrícula en el piso de 20 × 20 cuadros de 5 cm (1 m × 1 m en total), para tener noción del tamaño |
| **RobotModel** | El robot, dibujado a partir de la descripción |
| **TF** | Los ejes de cada frame (rojo, verde y azul), para revisar que cada sensor esté en su lugar y apunte bien |
| **Vista Orbit** | La cámara de RViz gira alrededor del robot con el mouse: clic izquierdo gira, rueda hace zoom, Shift + clic mueve |

**Ojo:** este archivo se escribió a mano y todavía no se ha probado en RViz2. Si al abrir da un error, se
arma la vista a mano en RViz (**Add → RobotModel**, **Add → TF**, **Add → Grid**, y en *Fixed Frame* escribir
`base_footprint`) y se guarda encima con **File → Save Config As**.

### 3.11 Los archivos sueltos del workspace

| Archivo | Qué es |
|---|---|
| `README.md` | La documentación que se entrega: cómo se hizo, cómo se usa y qué problemas hubo. **Está desactualizada:** todavía cuenta la ruta de Onshape y no la de SolidWorks (paso 4) |
| `PROCESO.md` | Este documento |
| `.gitignore` | La lista de lo que Git **no** debe subir al repositorio: las carpetas que crea `colcon` (`build/`, `install/`, `log/`), archivos temporales de Python, los archivos `~$` de SolidWorks y las notas internas |
| `soloparausointerno.md` | Las notas del equipo: estado del proyecto, decisiones y guías detalladas. No se sube |

---

## Paso 4. Sacar los modelos 3D del CAD (exportar a STL)

### 4.0 ¿Qué se necesita y por qué es difícil?

ROS no puede abrir archivos de SolidWorks, pero sí puede abrir **STL** (modelos 3D hechos de triángulos,
paso 2.7). Entonces hay que **exportar**, es decir, "guardar como" STL. Hay dos condiciones:

1. **Un STL por pieza, incluyendo las repetidas.** Si el robot tiene 2 llantas, tiene que haber 2 archivos
   de llanta, no uno. Igual con los 3 sensores ToF.
2. **Cada STL tiene que conservar su posición dentro del robot.** La llanta izquierda tiene que quedar a la
   izquierda y la derecha a la derecha.

¿Por qué la segunda condición? Recuerda que una pieza (`.SLDPRT`) no sabe dónde va: eso lo sabe el
ensamble. Si se exporta la pieza sola, sale en el centro de la pantalla, en la posición en que se dibujó.
Hay que exportar **desde el ensamble**, para que cada pieza salga ya acomodada.

> **Analogía:** es como tomarle foto a cada bloque de LEGO del modelo armado. Si sacas el bloque y lo
> fotografías sobre la mesa, pierdes dónde iba. Hay que "fotografiarlo" en su lugar.

**¿Qué son las "coordenadas"?** Son tres números (X, Y, Z) que dicen dónde está un punto respecto al
origen (el punto 0, 0, 0). En el CAD del Colmibot, el origen está en el centro del robot. Cada vértice de
cada triángulo de un STL tiene sus coordenadas. Si los números de la llanta izquierda son negativos en X y
los de la derecha positivos, quedaron en su lugar.

### 4.1 Primer intento: Onshape (no funcionó)

Como nadie tenía SolidWorks instalado, se probó **Onshape**: un CAD gratuito que funciona en el navegador y
puede abrir archivos de SolidWorks.

**Lo que se hizo:**

1. **Se comprimió la carpeta del CAD en un `.zip`.** Onshape necesita recibir el ensamble con todas sus
   piezas juntas. Si se suben los archivos sueltos, no los traduce.
2. **Primer error:** al subir el zip, Onshape dijo *"Root assembly file not found"* ("no encuentro el
   ensamble principal"). La causa: el zip **tiene que llamarse igual que el ensamble principal**. Se
   renombró a `CLM-EnsambleColmibot.zip` y funcionó.
3. **Onshape abrió el robot completo** (46 piezas colocadas). Solo falló un detalle sin importancia: las
   letras impresas sobre la placa ESP32.
4. **Se descubrieron los ejes del CAD.** Viendo el robot en Onshape con sus ejes de referencia, se confirmó
   que en este diseño **arriba es +Y** y **adelante es −Z** (el lado donde están los sensores ToF). Este dato
   es clave para el paso 5.
5. **El problema:** al exportar el ensamble, Onshape solo ofrece *"Export unique parts"*, que guarda **una
   sola vez cada pieza distinta**. Como las 2 llantas son la misma pieza, saldría 1 llanta; de los 3 ToF,
   saldría 1. No cumplía la primera condición.

**La alternativa en Onshape** era exportar 14 veces, ocultando y mostrando grupos de piezas cada vez (por
ejemplo: dejar visible solo la llanta izquierda y exportar; luego solo la derecha; etc.). Era lento y fácil
equivocarse. Entonces se consiguió e instaló **SolidWorks**.

### 4.2 Exportación con SolidWorks (lo que funcionó)

**Paso a paso:**

1. Se abrió `CLM-EnsambleColmibot.SLDASM` en SolidWorks. Como todas las piezas estaban en la misma
   carpeta, abrió completo, sin piezas faltantes.
2. **Archivo → Guardar como** → en "Tipo" se eligió **STL (\*.stl)**.
3. Se dio clic en **Opciones…** y se configuró así:

| Opción | Valor elegido | Qué significa y por qué |
|---|---|---|
| Formato | **Binario** | El STL binario pesa unas 5 veces menos que el de texto (ASCII), y ROS lee los dos |
| Unidad | **Milímetros** | Las medidas del diseño están en mm. El script del paso 5 las pasa a metros |
| Resolución | Personalizada: desviación 0.16 mm, ángulo 10° | Qué tan fino se dibujan las curvas. **Desviación**: cuánto se puede separar un triángulo de la superficie real (0.16 mm es muy poco). **Ángulo**: cuánto puede "doblarse" la superficie entre un triángulo y el siguiente. Menos = más liso, pero más pesado |
| **No convertir los datos de salida de STL a espacio positivo** | ✅ **Marcada** | **La más importante.** Si se deja sin marcar, SolidWorks "empuja" cada pieza para que todas sus coordenadas sean positivas, o sea, la mueve de su lugar. Todas las piezas quedarían amontonadas en una esquina |
| Guardar todos los componentes de un ensamblaje en un único archivo | ⬜ **Desmarcada** | Si se marca, todo el robot sale en un solo STL. Así no se podrían separar las llantas (que giran) del resto, ni pintar cada grupo de un color |
| Sistema de coordenadas de salida | **Predeterminado** | Usa el origen y los ejes del ensamble, que son los que ya conocemos (arriba = +Y, adelante = −Z) |

> **Analogía para "espacio positivo":** imagina que el robot está dibujado sobre una hoja con el centro en
> (0, 0). La llanta izquierda está en −87 mm. Si "conviertes a espacio positivo", es como si a cada pieza le
> sumaras lo necesario para que nada quede en negativo: la llanta izquierda se mueve a 0, la derecha
> también... y quedan una encima de la otra.

4. Se guardó. SolidWorks creó **95 archivos STL**, uno por cada pieza de cada instancia, con nombres como:

```
CLM-EnsambleColmibot - CLM-Llanta60mmD-1.STL      ← llanta, instancia 1
CLM-EnsambleColmibot - CLM-Llanta60mmD-2.STL      ← llanta, instancia 2
CLM-EnsambleColmibot - CLM-RasPi5-1 ... BROADCOM_1.STEP-1.STL   ← un chip de la Raspberry Pi
```

¿Por qué 95 y no 46? Porque SolidWorks también separa las piezas de adentro de los subensambles. Solo la
Raspberry Pi 5 sale en unas 40 piezas (cada puerto USB, cada conector, cada chip).

5. Por error se guardaron en la carpeta del CAD original. Se movieron a una carpeta nueva,
   `stl_solidworks\`, para no mezclar el diseño original con lo exportado.

### 4.3 Cómo se comprobó que la exportación salió bien

Para cada STL importante se calculó su **caja envolvente** (*bounding box*): la caja más pequeña que
contiene a la pieza. Se describe con su esquina mínima y su esquina máxima en X, Y y Z. Con eso se sabe
dónde está la pieza y cuánto mide.

| Pieza | Caja envolvente (mm) | Qué nos dice |
|---|---|---|
| Llanta 1 | X: −93 a −81 · Y: −13.5 a 46.5 · Z: −30 a 30 | Está en un lado (X negativo). Mide 12 mm de ancho (93 − 81) y 60 mm de alto y de largo: es una llanta de 60 mm ✅ |
| Llanta 2 | X: +81 a +93 · (lo demás igual) | Está **del otro lado**: las posiciones se conservaron ✅ |
| 3 sensores ToF | Z: entre −99 y −72 · Y: 63 a 88 | Están en Z negativo (= adelante) y en Y positivo (= arriba): los ejes son los que se esperaban ✅ |
| Cuerpo | X: −94.6 a 94.6 · Z: −100 a 100 | Centrado en el origen y de unos 20 cm de largo ✅ |

Además había coordenadas negativas, prueba de que la opción de "espacio positivo" funcionó.

---

## Paso 5. Preparar los modelos para ROS: el script `prepare_meshes.py`

### 5.0 ¿Qué es un script y por qué hace falta?

Un **script** es un programa pequeño que hace una tarea automática. Este está escrito en **Python**, un
lenguaje de programación muy usado. Se escribió especialmente para este proyecto.

Los 95 STL de SolidWorks todavía **no sirven tal cual** para ROS:

| Problema | Qué hace el script |
|---|---|
| Están en milímetros; ROS usa metros | Los convierte a metros |
| Están "acostados": en el CAD, arriba es Y; en ROS, arriba es Z | Los gira |
| El origen está en el centro del CAD; ROS lo quiere entre las llantas | Mueve todo para que el origen quede entre las llantas |
| Las llantas tienen que girar sobre su propio centro | Guarda cada llanta en su archivo, centrada |
| 95 archivos son muchos para manejar y colorear | Los junta en 7 grupos por tipo |
| Hay que saber las medidas reales (radio, separación, posición de sensores) | Las mide y escribe un archivo con ellas |

Hacerlo a mano sería larguísimo y fácil equivocarse. El script lo hace en segundos y se puede repetir
cuantas veces haga falta. Solo usa lo que ya trae Python, así que no hay que instalar nada extra.

### 5.1 Cómo se corrió

> **Nota (2026-11-07):** así se corrió la primera vez. Hoy las carpetas están en `C:\Cad_colmibot2\` y la
> entrada es `stl_cad_actual\`: el comando vigente está en el paso 9.2.

En Windows, en una terminal:

```
cd C:\Users\victo\Downloads\CAD_Colmibot\colmibot_ws\src\robot_description
python tools\prepare_meshes.py ..\..\..\stl_solidworks --units mm --up=y --forward=-z --grid 0.2
```

Cada parte del comando:

| Parte | Qué significa |
|---|---|
| `cd ...` | "Change directory": entrar a la carpeta del paquete |
| `python tools\prepare_meshes.py` | Ejecutar el script con Python |
| `..\..\..\stl_solidworks` | Dónde están los STL. `..` significa "subir una carpeta"; tres veces lleva a `CAD_Colmibot\` y de ahí a `stl_solidworks` |
| `--units mm` | Los STL están en milímetros |
| `--up=y` | En el CAD, "arriba" es el eje +Y |
| `--forward=-z` | En el CAD, "adelante" es el eje −Z |
| `--grid 0.2` | Simplificar los modelos con una cuadrícula de 0.2 mm (explicado en 5.6) |

### 5.2 Etapa 1: leer los archivos

El script abre cada uno de los 95 STL y lee sus triángulos. Cada triángulo son 3 puntos, y cada punto son 3
números (X, Y, Z). Por ejemplo, la llanta tiene 23 132 triángulos. Si un archivo estuviera vacío, avisa y
lo salta.

### 5.3 Etapa 2: girar y escalar (de "ejes del CAD" a "ejes de ROS")

Hay que transformar cada punto para que siga la regla de ROS (paso 2.6). La conversión es:

| Eje en ROS | Significado | Sale del eje del CAD... |
|---|---|---|
| X | adelante | −Z (lo que en el CAD es "adelante") |
| Y | izquierda | −X |
| Z | arriba | +Y (lo que en el CAD es "arriba") |

> **Analogía:** es como tomar el robot, que en el CAD está "acostado", y pararlo sobre sus llantas, con el
> frente apuntando hacia donde ROS espera.

¿Cómo sabe el script cuál es la izquierda? Por una regla de la geometría: si sabes dónde es arriba y dónde
es adelante, la izquierda queda determinada (con la "regla de la mano derecha"). Por eso solo hay que darle
`--up` y `--forward`.

Al mismo tiempo, multiplica cada número por 0.001 para pasar de milímetros a metros (87 mm → 0.087 m).

### 5.4 Etapa 3: clasificar cada pieza por su nombre

El script lee el **nombre de cada archivo** y decide a qué grupo pertenece. Para eso usa una lista de reglas
con palabras clave. Las reglas se revisan en orden y **gana la primera que coincide**:

| Grupo | Si el nombre contiene... | Ejemplo |
|---|---|---|
| `rueda` (llantas) | llanta, wheel | `CLM-Llanta60mmD-1` |
| `camara` | c920, logitech | `Logitech_C920Glass-1` |
| `placas_laser` | base (pero no basecam), plato, pisocam | `CLM-Plato-1` |
| `impreso_3d` | body, bracket, separador, poste, holder, shield, pi5case, basecam | `CLM-PosteM3x40-2` |
| `bateria` | 18650, battery | `CLM-18650Battery-3` |
| `motores` | motorreductor, 37d, motor (excepto si dice "cooler") | `Motorreductor 37D con encoder-1` |
| `ruedas_locas` | ruedaloca | `CLM-RuedaLoca-2` |
| `electronica` | esp32, cytron, raspi, cooler, vl53, imu, kcd1, bms, xl4015... | `CLM-Cytron_MDD10A-1` |
| `otros` | lo que no coincidió con nada | (quedó vacío: se clasificó todo) |

Antes de comparar, el nombre se pasa a minúsculas y se le quitan espacios y símbolos. Así
`CLM-Llanta60mmD-1` se vuelve `clmllanta60mmd1`, y ya no importa cómo esté escrito.

> **Las reglas se escriben como "expresiones regulares"** (*regex*): una forma compacta de describir
> patrones de texto. Por ejemplo, `llanta|wheel` significa "contiene llanta **o** wheel".

**Un error que se encontró y se corrigió:** el ventilador de la Raspberry Pi trae una pieza llamada
`MotorHouse` (la carcasa del motorcito del ventilador). Como su nombre contiene "motor", caía en el grupo de
los motores del robot. Se cambió la regla para que "motor" no cuente si el nombre también dice "cooler"
(ventilador), y ahora va con la electrónica.

### 5.5 Etapa 4: encontrar las llantas y poner el origen entre ellas

1. **Toma las piezas del grupo `rueda`** y las separa en izquierda y derecha según su posición en Y (en ROS,
   Y positivo = izquierda).
2. **Mide cada llanta** con su caja envolvente: **radio de 30.0 mm, ancho de 12.0 mm**, y la distancia entre
   sus centros: **174.1 mm**.
3. **Hace dos comprobaciones de seguridad:**
   - El lado más delgado de la llanta debe quedar sobre Y (las llantas giran de lado a lado). Si no, avisa
     que `--up` o `--forward` están mal.
   - Si las dos llantas quedaron en el mismo lugar, se detiene con un error: significa que la exportación
     perdió las posiciones (por ejemplo, si se olvidó la casilla de "espacio positivo").
4. **Calcula el punto medio entre las dos llantas** y **mueve todas las piezas** para que ese punto sea el
   nuevo origen (0, 0, 0). Ese punto es `base_link` (paso 2.4).

> **Corrección (2026-10-23):** la primera versión del script tenía un error. Las llantas se guardaban
> **16.4 mm más arriba** de su eje, porque el script trabajaba con una copia de las llantas que no recibía
> el movimiento al nuevo origen. En RViz se habrían visto flotando y girando chuecas. Se corrigió el script,
> se volvió a correr y solo cambiaron `wheel_left.stl` y `wheel_right.stl`. Ahora cada llanta queda centrada
> en su propio frame (de −30 a +30 mm). Las medidas y los demás modelos salieron idénticos.

### 5.6 Etapa 5: guardar los modelos finales

**Las llantas, cada una en su archivo y centrada en su eje.** Se guardan `wheel_left.stl` y
`wheel_right.stl` movidas para que el centro de cada llanta quede en (0, 0, 0). La posición real
(87 mm a cada lado) la pone el joint del URDF.

> **¿Por qué centradas?** RViz gira cada modelo alrededor del origen de su archivo. Si la llanta estuviera
> a 87 mm del origen, al girarla daría vueltas alrededor del centro del robot, como una piedra amarrada a
> una cuerda, en lugar de girar sobre su eje.

**El resto, juntado por grupo.** Todas las piezas de un mismo grupo se juntan en un solo STL. Así quedan 7
archivos en lugar de 93. Es más fácil de manejar, RViz lo carga más rápido y cada grupo se pinta de un color.

| Archivo | Cuántos STL junta |
|---|---|
| `electronica.stl` | 53 (la mayoría son piezas de la Raspberry Pi) |
| `impreso_3d.stl` | 27 |
| `bateria.stl` | 3 |
| `camara.stl` | 3 |
| `placas_laser.stl` | 3 |
| `motores.stl` | 2 |
| `ruedas_locas.stl` | 2 |

**Simplificación con `--grid 0.2`.** El primer resultado tenía un problema: `electronica.stl` pesaba
**48 MB** y tenía casi un millón de triángulos, por el detalle de la Raspberry Pi. Eso hace lento a RViz y
está cerca del límite de GitHub (avisa en 50 MB y rechaza archivos de más de 100 MB).

La opción `--grid 0.2` simplifica el modelo así:

1. Imagina una cuadrícula 3D de cubitos de 0.2 mm.
2. Cada punto se "jala" a la esquina de cubito más cercana.
3. Los puntos que estaban muy cerca terminan en el mismo lugar y se fusionan.
4. Los triángulos que quedan aplastados (dos de sus puntos se fusionaron) desaparecen, y los repetidos se
   quitan.

> **Analogía:** es como bajar la resolución de una foto. Si los pixeles son lo bastante chicos, no se nota
> la diferencia, pero el archivo pesa mucho menos.

Resultado: `electronica.stl` bajó de 958 699 triángulos (48 MB) a 228 421 (**11 MB**), y a 0.2 mm no se
nota la diferencia a simple vista.

Modelos finales en `meshes\`:

| Archivo | Tamaño | Color en RViz |
|---|---|---|
| `electronica.stl` | 11.4 MB | verde |
| `impreso_3d.stl` | 2.0 MB | gris oscuro |
| `ruedas_locas.stl` | 1.0 MB | gris |
| `motores.stl` | 1.0 MB | gris metálico |
| `wheel_left.stl` | 0.7 MB | casi negro |
| `wheel_right.stl` | 0.7 MB | casi negro |
| `bateria.stl` | 0.6 MB | azul |
| `placas_laser.stl` | 0.6 MB | color madera |
| `camara.stl` | 0.2 MB | casi negro |

### 5.7 Etapa 6: revisar el tamaño y el piso

- **Mide el robot completo:** 200 mm de largo, 200 mm de ancho y 167 mm de alto.
- **Revisa que el robot "pise" bien:** el punto más bajo de todo el robot debería estar a la altura del piso
  de las llantas (30 mm debajo del eje), con un margen de ±3 mm. Si no, es señal de que el robot quedó al
  revés o de que las ruedas locas no tocan el piso en el diseño. **No hubo aviso:** todo bien.

### 5.8 Etapa 7: encontrar los sensores

Para cada sensor busca sus piezas por nombre y calcula el **centro de su caja envolvente**. Ese centro es
donde va el frame del sensor:

| Sensor | Se busca por | Posición encontrada (respecto a `base_link`) |
|---|---|---|
| Cámara | `c920glass`, `glass` (el lente) | 53 mm adelante, 121 mm arriba, centrada |
| IMU | `bmi270`, `imu` | 59 mm adelante, 39 mm arriba, centrada |
| 3 ToF | `vl53` | Se separan en izquierdo, central y derecho según su posición. Quedan entre 79 y 93 mm adelante, 59 mm arriba; los laterales a unos 45–49 mm de cada lado |

**Lo que el script no puede saber:** hacia dónde **apuntan** los ToF laterales. Con la caja envolvente se
sabe dónde está un sensor, pero no hacia dónde mira. Por eso el ángulo sigue en 30° (una estimación). Para
que quede exacto habría que medirlo en SolidWorks.

### 5.9 Etapa 8: escribir el archivo de medidas reales

Por último, el script escribe `urdf/generated/colmibot_meshes.xacro`, con dos cosas:

1. **Las medidas reales**, como variables de xacro, con los mismos nombres que en `colmibot_params.xacro`.
   Por ejemplo:
   ```xml
   <xacro:property name="wheel_left_y" value="0.08705"/>   <!-- llanta izquierda a 87.05 mm del centro -->
   <xacro:property name="camera_z" value="0.12140"/>       <!-- cámara 121.4 mm arriba del eje -->
   ```
   Como este archivo se carga después, estas medidas reemplazan a las estimadas (paso 2.3).
2. **Una plantilla `body_meshes`** que pone los 7 modelos del cuerpo, cada uno con su color.

La primera línea del archivo avisa que **no se edita a mano**. Si algo cambia (por ejemplo, se modifica el
diseño), se exporta otra vez y se vuelve a correr el script.

### 5.10 Resumen de lo que imprimió el script

```
Llantas: radio=30.0 mm  ancho=12.0 mm  separacion=174.1 mm
Robot: largo=200 mm  ancho=200 mm  alto=167 mm
Sensores:
  camera: OK
  imu: OK
  tof_left/center/right: OK (3 STL)
Escrito: ...\urdf\generated\colmibot_meshes.xacro
```

Todo salió como se esperaba: dos llantas de 60 mm, un robot de 20 × 20 cm, los 5 sensores encontrados y
ninguna pieza sin clasificar.

---

## Paso 6. Limpiar la carpeta

Durante el trabajo se acumularon archivos que ya no hacían falta. Antes de borrar algo se **comparó** su
contenido, para no perder nada importante. Todo se mandó a la **Papelera de reciclaje**, así que se puede
recuperar si hiciera falta.

| Se borró | Por qué ya no hacía falta |
|---|---|
| `CAD_Colmibot - copia\` (91 MB) | Era una copia de respaldo del diseño. Se comparó archivo por archivo con el original: era idéntica, solo que le faltaba el BOM |
| `CLM-EnsambleColmibot.zip` y `CAD_Colmibot_onshape.zip` (89 MB cada uno) | Eran iguales entre sí y solo servían para subir el diseño a Onshape, que ya no se usa. Si algún día hicieran falta, se rehacen comprimiendo la carpeta original |
| 7 capturas de pantalla | Se tomaron para revisar opciones de Onshape y SolidWorks en el momento |

**Lo que quedó** en `Downloads\CAD_Colmibot\`, en el orden en que se usa:

| Carpeta | Qué es | Regla |
|---|---|---|
| `CAD_Colmibot\` | El diseño original de SolidWorks y el BOM | **No se toca nunca** |
| `stl_solidworks\` | Los 95 STL exportados (paso 4) | Se conserva para poder volver a correr el script sin abrir SolidWorks (por ejemplo, para cambiar la simplificación) |
| `colmibot_ws\` | El workspace de ROS 2 con el paquete terminado | Aquí se sigue trabajando y es lo que se entrega |

**Actualización (2026-11-07):** todo se movió a `C:\Cad_colmibot2\`. `stl_solidworks\` se mandó a la Papelera
porque la reemplaza `stl_cad_actual\`, exportada del CAD actual (paso 9). Con ella se fueron
`stl_solidworks\modulos\`, `agrupar.py` y `medir_stl.py`: un intento de agrupar en 19 grupos que no se usó.

Dentro de `CAD_Colmibot\` pueden seguir apareciendo archivos `~$...`: son los letreros de "ocupado" de
SolidWorks (paso 1.2). Desaparecen al cerrar SolidWorks.

---

## Paso 7. Probarlo en ROS 2 (pendiente)

Hasta aquí todo se hizo en Windows. ROS 2 corre en Linux, así que la prueba final se hace en la **máquina
virtual**.

### 7.1 ¿Qué es la máquina virtual?

Una **máquina virtual (VM)** es una computadora "simulada" dentro de tu computadora. Con el programa
**VirtualBox** se crea una ventana que funciona como otra computadora completa, con su propio sistema
operativo. En nuestro caso, la VM tiene **Ubuntu 24.04** (una versión de Linux) con **ROS 2 Jazzy**
instalado. *Jazzy* es el nombre de la versión de ROS 2 que corresponde a Ubuntu 24.04.

### 7.2 Pasar el workspace a la VM

La carpeta `colmibot_ws` tiene que llegar a la carpeta personal de la VM (`~/colmibot_ws`; en Linux, `~`
significa "mi carpeta personal"). Hay tres formas:

| Forma | Cómo |
|---|---|
| **Repositorio de Git (la recomendada)** | Se sube a GitHub desde Windows y se descarga en la VM con `git clone`. Además deja el historial de quién hizo qué, que el profesor revisa |
| Carpeta compartida de VirtualBox | En la configuración de la VM: *Carpetas compartidas* → agregar `colmibot_ws`. Aparece dentro de Ubuntu y se copia a `~` |
| USB | Copiar la carpeta a una memoria y conectarla a la VM (menú *Dispositivos → USB*) |

### 7.3 Instalar lo que haga falta

Si en la VM falta alguno de los paquetes de ROS que usa el nuestro (paso 3.3), se instalan con:

```bash
sudo apt update
sudo apt install ros-jazzy-xacro ros-jazzy-robot-state-publisher \
                 ros-jazzy-joint-state-publisher-gui ros-jazzy-rviz2
```

- `sudo` = ejecutar como administrador (pide la contraseña de Ubuntu).
- `apt` = el instalador de programas de Ubuntu.
- La `\` al final de una línea significa "el comando sigue en la siguiente línea".

### 7.4 Compilar y abrir

En una terminal de Ubuntu:

```bash
source /opt/ros/jazzy/setup.bash
cd ~/colmibot_ws
colcon build --packages-select robot_description
source install/setup.bash
ros2 launch robot_description display.launch.py use_meshes:=true
```

Línea por línea:

| Comando | Qué hace |
|---|---|
| `source /opt/ros/jazzy/setup.bash` | "Activa" ROS 2 en esta terminal. Muchas VMs ya lo hacen solas al abrir la terminal |
| `cd ~/colmibot_ws` | Entra al workspace |
| `colcon build --packages-select robot_description` | Compila (instala) **solo** nuestro paquete. Al final debe decir `Finished <<< robot_description` y `Summary: 1 package finished` |
| `source install/setup.bash` | Le dice a la terminal dónde quedó nuestro paquete. **Hay que repetirlo en cada terminal nueva** |
| `ros2 launch ... use_meshes:=true` | Arranca todo (paso 3.9) con los modelos 3D reales |

No hace falta volver a correr el script: los modelos y las medidas ya están dentro del paquete.

### 7.5 Qué se debe ver

Se abren dos ventanas:

1. **RViz**, con el Colmibot en 3D sobre la cuadrícula, a colores y con los ejes de cada frame.
2. **Joint State Publisher**, una ventanita con dos controles deslizantes: `wheel_left_joint` y
   `wheel_right_joint`.

**Lista de revisión:**

| Revisar | Cómo | Si está mal |
|---|---|---|
| El robot está **parado** sobre sus llantas, no de lado ni de cabeza | A simple vista | Los ejes del script están mal: volver a correrlo con otro `--up` / `--forward` |
| El **frente** del robot (donde están los ToF) apunta hacia la **flecha roja** (X) de `base_link` | Mirar los ejes en el centro del robot | Igual que arriba: revisar `--forward` |
| Las llantas **tocan la cuadrícula** (el piso) | Ver el robot de lado | Revisar la altura de `base_footprint` |
| Las llantas **giran sobre su eje** al mover los sliders | Mover cada slider | Revisar el eje del joint en `macros.xacro` |
| Los ejes de la cámara, la IMU y los 3 ToF están **sobre cada sensor** | En el panel *TF* de RViz, activar *Show Names* | Revisar los nombres de las piezas en el script (paso 5.8) |
| Los ToF laterales **apuntan hacia afuera** (unos 30°) | Ver la flecha roja de `tof_left_link` y `tof_right_link` | Ajustar `tof_side_yaw` en `colmibot_params.xacro` |
| Los colores se parecen al robot real | A simple vista | Ajustar `materials.xacro` |

También se puede probar el modo sin modelos (`use_meshes:=false`), que debe mostrar el robot hecho de una
caja, cilindros y esferas.

### 7.6 Problemas comunes y cómo resolverlos

| Mensaje o síntoma | Causa probable | Solución |
|---|---|---|
| `Package 'robot_description' not found` | No se hizo `source install/setup.bash` en esta terminal | Correrlo (desde `~/colmibot_ws`) |
| `ros2: command not found` | ROS 2 no está activado en esta terminal | `source /opt/ros/jazzy/setup.bash` |
| `executable 'joint_state_publisher_gui' not found` (o algo parecido con `xacro`) | Falta instalar ese paquete de ROS | Ver el paso 7.3 |
| RViz abre pero el robot no aparece, o sale en rojo con *"No transform"* | La vista no está usando el frame correcto | En RViz, *Fixed Frame* = `base_footprint` |
| Se ve el robot de cajas aunque se puso `use_meshes:=true` | Se escribió mal la opción, o no se recompiló | Revisar que diga `use_meshes:=true` y repetir `colcon build` |
| Cambié un color o una medida y no se nota | ROS usa la copia instalada (paso 3.4) | `colcon build` otra vez y relanzar |
| RViz marca error al abrir `display.rviz` | El archivo se escribió a mano y no se ha probado | Armar la vista a mano y guardarla encima (paso 3.10) |
| RViz va muy lento | La VM tiene poca memoria o no tiene aceleración 3D | En VirtualBox: más memoria de video y activar *aceleración 3D*. O volver a correr el script con `--grid 0.5` |

Cualquier problema real que salga hay que anotarlo en el `README.md`, en la sección de problemas: el
profesor lo pide.

---

## Paso 8. Masas, centro de masa e inercia (para simular la física)

### 8.1 ¿Para qué?

RViz solo **dibuja** el robot: no le importa cuánto pesa. Un simulador de física (Gazebo) sí lo necesita:
con la masa y su reparto decide si el robot se vuelca al frenar, cuánto le cuesta girar, etc. En el URDF eso
va en la sección `<inertial>` de cada link (paso 3.1): **masa**, **centro de masa** y **tensor de inercia**.

Lo que se ve (`<visual>`) y la física (`<inertial>`) son **independientes**. Por eso se pueden quitar de las
mallas la Raspberry Pi, el cooler o el XL4015 y su masa **sigue contando** en `base_link`. Para la física no
hace falta la forma de cada pieza, solo **un centro de masa y una inercia por link** (aquí, 3 links con masa:
`base_link` y las dos llantas).

### 8.2 De dónde salen los datos

Los STL no sirven: no tienen masa. Los datos salen del **CAD de `CAD_Colmibot`**, leído con SolidWorks por un
script (`tools/export_mass_solidworks.ps1`):

```powershell
powershell -ExecutionPolicy Bypass -File tools\export_mass_solidworks.ps1 `
    -Assembly C:\Cad_colmibot2\CAD_Colmibot\CLM-EnsambleColmibot.SLDASM
```

Escribe `inertia/componentes_cad.csv`: **55 componentes**, uno por cada instancia de un archivo de
`CAD_Colmibot` (los 12 postes son 12 filas porque cada uno está en otro lugar). Las 42 piezas que no tienen
archivo propio (vienen del STEP importado de la Raspberry Pi y su cooler) se suman a su subensamble. De cada
componente guarda: material, volumen, masa, centro de masa, inercia y caja envolvente.

**Este CSV es la información que se conserva** aunque las piezas se quiten de las mallas visuales.

### 8.3 Cuidado: los materiales del CAD son de relleno

El volumen y la forma del CAD son buenos, pero **los materiales no**:

| En el CAD | Problema |
|---|---|
| Electrónica (ESP32, Cytron, XL4015, ToF, IMU, cámara) = aluminio 6061 | Una placa no es aluminio macizo |
| Motores 37D y baterías 18650 = acero AISI 1020 macizo | Salen 462 g por motor y 128 g por batería: demasiado |
| Raspberry Pi y cooler = sin material (1000 kg/m³) | 18 g para la Pi: muy poco |
| `CLM-Base` y `CLM-BaseCam` = hule EPDM; `CLM-Body` = acrílico (el BOM dice impreso 3D) | Material equivocado |
| `CLM-ESP32_Wroom_30pins` y `CLM-PI5_CaseTop` | Sin volumen (superficies): se tratan como caja |

Por eso la masa del CAD (2.3 kg) es solo un punto de partida. Lo que sí vale es **dónde** está cada pieza
y **qué forma** tiene.

### 8.4 Poner los pesos reales: `inertia/masas.csv`

Es el único archivo que se edita a mano. Trae una fila por pieza del BOM (masa **por unidad**, en gramos),
una por subensamble y una `TOTAL`. Se llena lo que se tenga; lo vacío se queda con el CAD:

| Qué se sabe | Qué se llena | Qué hace el script |
|---|---|---|
| El peso de una pieza (báscula o hoja de datos) | `masa_g` de esa pieza (ej. `Motorreductor 37D con encoder` = 205) | Usa ese peso en cada instancia |
| El peso de un subensamble completo | `masa_g` del subensamble (ej. `CLM-EnsBat3S1P` = 160) | Lo reparte entre sus piezas según el CAD |
| Solo el peso del robot completo | `masa_g` de `TOTAL` | Escala las piezas sin dato para que sumen eso |

La columna `fuente` es para anotar de dónde salió cada número (báscula, hoja de datos…). Después:

```
python tools/compute_inertial.py
```

Gira todo a los ejes de ROS (igual que `prepare_meshes.py`), pone el origen entre las llantas y junta los
componentes por link con el **teorema de ejes paralelos**. Escribe:

- `urdf/generated/colmibot_inertial.xacro`: las macros `base_inertial`, `wheel_left_inertial` y
  `wheel_right_inertial`, que ya usan `colmibot.urdf.xacro` y `macros.xacro`.
- `inertia/masas_usadas.csv`: la masa de cada componente y de dónde salió (`real`, `subensamble`, `cad`,
  `cad_escalada`). Sirve para revisar.

**Ojo con el signo:** SolidWorks da los productos de inercia (Lxy, Lxz, Lyz) con la convención contraria al
URDF. `export_mass_solidworks.ps1` les cambia el signo antes de girar los ejes; se comprobó contra la inercia
calculada directo de las mallas (2026-11-07).

**Comprobación:** los centros de la cámara, la IMU y los ToF que da este cálculo coinciden con los de
`prepare_meshes.py` (paso 5.8) con 1–3 mm de diferencia, así que los ejes son los mismos.

### 8.5 Revisión del CAD actual: piso y hacia dónde apunta cada sensor

Se leyó la rotación exacta de cada componente en el ensamble de `CAD_Colmibot` (2026-11-07):

| Qué | En el CAD | En el URDF |
|---|---|---|
| Piso | Las 2 llantas y las 2 ruedas locas tocan el mismo plano, 30 mm bajo el eje | `base_footprint` está 30 mm bajo `base_link`: el piso de RViz queda bajo las llantas si *Fixed Frame* = `base_footprint`. Con *Fixed Frame* = `base_link` la rejilla se ve a media llanta (no es error del modelo) |
| ToF central | Horizontal, apunta al frente (0°) | ✅ igual |
| ToF laterales | Horizontales, giradas **exactamente 30°** hacia afuera | ✅ `tof_side_yaw` = 30° (ya no es estimado) |
| Cámara C920 | Al frente, **inclinada 6.1° hacia abajo** (todo el `CLM-LogitechC920Montaj`) | Se agregó `camera_pitch` = 0.1064 rad |
| IMU BMI270 | Plana (horizontal) | Frame sin giro. Falta confirmar con la serigrafía de la placa hacia dónde apuntan sus ejes X/Y |

---

## Paso 9. Mallas nuevas desde el CAD actual, sin la electrónica

### 9.1 Exportar el CAD actual (sin tocarlo)

Los STL de `stl_solidworks\` eran la **primera versión** (2026-10-27). El CAD de `CAD_Colmibot` es más nuevo,
así que se exportó otra vez, ahora con un script que hace lo mismo que el paso 4.2 con las mismas opciones:

```powershell
powershell -ExecutionPolicy Bypass -File tools\export_stl_solidworks.ps1 `
    -Assembly C:\Cad_colmibot2\CAD_Colmibot\CLM-EnsambleColmibot.SLDASM `
    -OutDir C:\Cad_colmibot2\stl_cad_actual -IncluirOcultas
```

- **No modifica el CAD:** abre el ensamble, exporta y lo cierra sin guardar. Las opciones de STL de SolidWorks
  se cambian solo mientras exporta y después se dejan como estaban.
- **`-IncluirOcultas`:** en el CAD, `CLM-Body` está **oculto** (para ver adentro mientras se diseña) y
  SolidWorks no exporta piezas ocultas. Sin esta opción salen 94 STL en vez de 95 y falta el cuerpo.

Resultado: `C:\Cad_colmibot2\stl_cad_actual\` con 95 STL. `stl_solidworks\` después se mandó a la Papelera (paso 6).

### 9.2 Qué se quita y qué se vuelve caja

Se decidió en `tools/prepare_meshes.py`, con dos listas al principio del archivo (no en SolidWorks):

| Lista | Piezas | Por qué |
|---|---|---|
| `EXCLUDE_RULES` (no se dibujan) | Cytron MDD10A, BMS, 3 celdas 18650 | Quedan escondidas dentro del cuerpo |
| | Raspberry Pi 5 + cooler | Las tapa su carcasa (`CLM-PI5_Case*`, que se queda) |
| `BOX_RULES` (caja verde de su mismo tamaño) | ESP32 + Expansion Board | Están en el piso de arriba, a la vista |
| | XL4015 | Ídem |

Todo lo demás se queda: estructura (impresa y de corte láser, **incluido `CLM-ShieldESP32`**, que es impreso),
llantas, motores, ruedas locas, sensores (ToF, IMU, cámara) y los interruptores KCD1.
`CLM-HolderVoltageRegulator.SLDPRT` está en la carpeta del CAD pero **no se usa** (no está en el ensamble ni en el BOM).

```
python tools/prepare_meshes.py C:\Cad_colmibot2\stl_cad_actual --units mm --up=y --forward=-z --grid 0.2
```

Para dibujar todo como antes: agregar `--all-parts`.

**Resultado:** de 95 STL se quitan 50 (47 sin dibujar y 3 que se vuelven cajas) y quedan 45. Las mallas pasaron de **18 MB a 7.9 MB**. Ya no
existe `bateria.stl` (se borró). Las medidas (llantas, sensores, piso) quedaron iguales a la primera versión.

**La masa de lo que se quitó sigue contando** en la física: está en `inertia/componentes_cad.csv` (paso 8).

---

## Paso 10. Primera prueba en RViz: el robot salía como una caja (2026-11-08)

**Problema:** al correr `ros2 launch robot_description display.launch.py` (sin opciones), RViz mostró una caja
negra con dos cilindros y unos ejes de colores, sin la cámara ni la forma redonda del robot.

**Causa:** no era un error. La opción `use_meshes` estaba en `false` por defecto, así que salía el modo de
**figuras simples** (caja + cilindros + esferas; la cámara y los sensores son solo ejes, sin dibujo).

**Revisión de las mallas:** las 8 STL de `meshes/` son válidas, están en metros y tienen el tamaño correcto
(cuerpo de 20 × 19 cm, llantas de 6 cm, cámara arriba). Una vista previa hecha directo desde los STL muestra el
robot real: cuerpo redondo, placas de láser, cámara Logitech arriba, llantas.

**Cambio:** `use_meshes` ahora es `true` por defecto, en `display.launch.py` y en `colmibot.urdf.xacro`. Así,
`ros2 launch robot_description display.launch.py` ya muestra el robot real. Para las figuras simples:
`use_meshes:=false`.

**Ojo:** después del cambio hay que volver a correr `colcon build` y `source install/setup.bash`.

---

## Pendientes

| Pendiente | Quién (reparto sugerido) |
|---|---|
| Probar en la VM con ROS 2 Jazzy (paso 7) | C |
| Pesar los componentes (o el robot completo), llenar `inertia/masas.csv` y correr `compute_inertial.py` (paso 8) | Todos |
| ~~Medir el ángulo real de los ToF laterales~~ (30°, del CAD: paso 8.5). Falta ajustar colores | B |
| Confirmar los ejes X/Y de la IMU con la serigrafía de la placa | B |
| ~~Volver a exportar los STL desde `CAD_Colmibot`~~ (hecho: paso 9). Revisar en RViz que las cajas de la ESP32 y del XL4015 se vean bien | C |
| Actualizar el README: cambiar la ruta de Onshape por la de SolidWorks | D |
| Crear el repositorio de GitHub; **cada integrante sube su parte con su cuenta** | Todos |
| Video de ≤ 3 min, integrantes y problemas reales en el README | D |

---

## Guía para hacerlo todo desde cero, paso a paso

Esta sección resume todo el documento como una lista de tareas, en orden, para quien quiera repetir el
proceso completo. Respeta lo que ya se hizo, con dos mejoras: **probar en ROS antes de tener las mallas**
y **crear el repositorio de GitHub desde el principio**.

### Fase 0. Preparar las herramientas (una sola vez)

| Qué | Dónde | Para qué |
|---|---|---|
| **SolidWorks** | Windows | Abrir el CAD y exportar los STL |
| **Python 3** | Windows | Correr `prepare_meshes.py`. No necesita librerías extra, solo Python normal |
| **Git** + cuenta de **GitHub** (una por integrante) | Windows y VM | Historial y entrega |
| **VirtualBox + Ubuntu 24.04 + ROS 2 Jazzy** | VM | Compilar y ver el robot |
| Paquetes de ROS | Terminal de Ubuntu | `sudo apt install ros-jazzy-xacro ros-jazzy-robot-state-publisher ros-jazzy-joint-state-publisher-gui ros-jazzy-rviz2` |

Para revisar que Python está instalado, en PowerShell: `python --version`.

### Fase 1. Entender el robot (sin abrir el CAD)

1. Abrir `CAD_Colmibot\BOM.xlsx` y hacer la lista de componentes.
2. Comparar el BOM con los nombres de los `.SLDPRT` y anotar los que no coinciden.
3. **Clasificar cada componente** con la pregunta: *¿se mueve, mide algo o solo está ahí?* (paso 1.4).
4. Dibujar el árbol en papel: `base_footprint → base_link → llantas + sensores`.

**Lo que sale:** la estructura del robot. No hace falta el CAD, porque el BOM ya dice qué partes tiene.
Referencia: pasos 1 y 2.

### Fase 2. Crear el repositorio (al inicio, no al final)

El profesor revisa quién hizo qué. Si el repositorio existe desde el inicio, cada fase queda registrada con
el nombre de quien la hizo.

```powershell
cd C:\Cad_colmibot2\colmibot_ws
git init
git add .
git commit -m "Estructura inicial del workspace"
```

Después se crea el repositorio en github.com y se conecta con `git remote add origin <url>` y
`git push -u origin main`. Cada integrante sube **su** parte desde **su** cuenta.

### Fase 3. Escribir el paquete con figuras simples

Dentro de `colmibot_ws\src\robot_description\`, en este orden, porque cada archivo usa al anterior:

| # | Archivo | Qué contiene |
|---|---|---|
| 1 | `package.xml` | Nombre del paquete y de qué depende (paso 3.3) |
| 2 | `CMakeLists.txt` | Qué carpetas se instalan: `urdf`, `meshes`, `launch`, `rviz` (paso 3.4) |
| 3 | `urdf/colmibot_params.xacro` | Medidas **estimadas**. El radio de 0.030 m sale del BOM; las demás son aproximadas (paso 3.6) |
| 4 | `urdf/materials.xacro` | Colores (paso 3.8) |
| 5 | `urdf/macros.xacro` | Plantillas: `drive_wheel`, `sensor_frame` y las inercias (paso 3.7) |
| 6 | `urdf/colmibot.urdf.xacro` | El árbol: links y joints usando las plantillas (paso 3.5) |
| 7 | `launch/display.launch.py` | Arranca robot_state_publisher, los sliders y RViz (paso 3.9) |
| 8 | `rviz/display.rviz` | Vista guardada de RViz (paso 3.10) |

**Prueba intermedia (no se hizo en su momento, pero conviene):** pasar el workspace a la VM y probar
**solo con figuras simples**:

```bash
source /opt/ros/jazzy/setup.bash
cd ~/colmibot_ws
colcon build --packages-select robot_description
source install/setup.bash
ros2 launch robot_description display.launch.py use_meshes:=false
```

Se debe ver una caja con 2 cilindros y 2 esferas, y las llantas deben girar con los sliders. Si esto falla,
el problema está en la **estructura**, no en las mallas, y es mucho más fácil de arreglar en este punto.

### Fase 4. Exportar los STL desde SolidWorks

1. Abrir `CAD_Colmibot\CLM-EnsambleColmibot.SLDASM` y revisar que no aparezcan piezas faltantes.
2. **Archivo → Guardar como → Tipo: STL → Opciones…**
   - Binario · Milímetros · Resolución personalizada: 0.16 mm / 10°
   - ✅ **"No convertir los datos de salida de STL a espacio positivo"** (la más importante)
   - ⬜ "Guardar todos los componentes de un ensamblaje en un único archivo" (desmarcada)
   - Sistema de coordenadas: Predeterminado
3. Guardar en una carpeta **nueva** y vacía (hoy: `C:\Cad_colmibot2\stl_cad_actual\`), no dentro del CAD.
4. Comprobar que salgan **95 archivos**, con las 2 llantas y los 3 ToF por separado. Si salen 94, falta
   `CLM-Body`: está oculto en el ensamble y hay que mostrarlo antes.

Atajo: `tools\export_stl_solidworks.ps1 ... -IncluirOcultas` hace todo esto (paso 9.1). Referencia: paso 4.2.

### Fase 5. Convertir los STL para ROS (en Windows)

```powershell
cd C:\Cad_colmibot2\colmibot_ws\src\robot_description
python tools\prepare_meshes.py C:\Cad_colmibot2\stl_cad_actual --units mm --up=y --forward=-z --grid 0.2
```

Revisar al final:

- Que haya **8 STL** en `meshes\` (6 grupos del cuerpo + 2 llantas) y que la lista de "Se quitan de las
  mallas" sea la esperada (paso 9.2).
- Que exista `urdf\generated\colmibot_meshes.xacro`.
- Que el radio de la llanta salga en **0.030** y las llantas en unos **±0.087 m** a los lados.

Guardar en Git: `git add .` y `git commit -m "Mallas y medidas reales del CAD"`. Referencia: paso 5.

### Fase 6. Probar el robot completo en la VM

1. Pasar los cambios a la VM (con Git: `git pull` dentro de `~/colmibot_ws`).
2. Compilar y abrir:

   ```bash
   cd ~/colmibot_ws
   colcon build --packages-select robot_description
   source install/setup.bash
   ros2 launch robot_description display.launch.py use_meshes:=true
   ```

3. Revisar la lista del paso 7.5: el robot parado, el frente (los ToF) hacia la flecha roja, las llantas
   tocando el piso y girando con los sliders, y los frames de los sensores en su lugar.
4. **Anotar cada error** que salga y cómo se resolvió: el profesor lo pide en el README.

### Fase 7. Ajustes finos

- Medir el ángulo real de los ToF laterales y cambiar `tof_side_yaw` en `colmibot_params.xacro`.
- Ajustar los colores en `materials.xacro`.
- Después de cada cambio: `colcon build` y volver a lanzar (paso 3.4).

### Fase 8. Entrega

1. **README.md**: integrantes, cómo correrlo, problemas reales y cómo se resolvieron. Cambiar la parte de
   Onshape por SolidWorks.
2. **Video de ≤ 3 min**: RViz con el robot, las llantas girando y los frames de los sensores.
3. Último `git push`, revisando que cada integrante tenga commits propios.

### Resumen del orden

```
0 Herramientas → 1 BOM y estructura → 2 Repositorio → 3 Paquete con figuras → prueba en VM (false)
  → 4 Exportar STL → 5 Script → 6 Prueba en VM (true) → 7 Ajustes → 8 README + video + push
```

**Estado al 2026-10-23:** ya están hechas las fases 1, 3, 4 y 5. Faltan la 2, la prueba de la fase 3 en la
VM, la 6, la 7 y la 8.

---

## De `CAD_Colmibot` a `colmibot_ws`, a mano

Esta sección explica cómo se pasa de una carpeta a la otra **sin depender del script**, para entender qué
hace cada parte. Hay **tres transformaciones**, y solo la tercera la hizo un programa:

```
CAD_Colmibot\                       colmibot_ws\src\robot_description\
─────────────                       ──────────────────────────────────
BOM.xlsx ───────── (A) a mano ────► urdf\*.xacro, launch, rviz, package.xml   ← texto
.SLDASM ── (B) SolidWorks ─► STL ── (C) script o a mano ─► meshes\*.stl + medidas
```

### (A) La estructura: crear el paquete y escribir los archivos

Es 100 % manual: son archivos de texto que se escriben con cualquier editor (VS Code, el Bloc de notas...).

**1. Crear las carpetas.** En la VM, ROS crea el esqueleto:

```bash
mkdir -p ~/colmibot_ws/src
cd ~/colmibot_ws/src
ros2 pkg create robot_description --build-type ament_cmake
cd robot_description
mkdir urdf launch rviz meshes
```

`ros2 pkg create` hace un `package.xml` y un `CMakeLists.txt` básicos. Luego solo hay que agregar las
dependencias (paso 3.3) y la línea `install(DIRECTORY launch meshes rviz urdf ...)` (paso 3.4). También se
puede hacer en Windows creando las carpetas a mano.

**2. Llevar cada dato del CAD a un archivo:**

| Lo que se sabe del CAD / BOM | A qué archivo va | Cómo se escribe |
|---|---|---|
| "Tiene 2 llantas que giran" | `colmibot.urdf.xacro` + `macros.xacro` | Un `<link>` por llanta y un `<joint type="continuous">` con `axis 0 1 0` |
| "Tiene cámara, IMU y 3 ToF" | `colmibot.urdf.xacro` | Un `<link>` vacío por sensor con un `<joint type="fixed">` |
| "Todo lo demás es el cuerpo" | `colmibot.urdf.xacro` | Va dentro de `base_link` |
| "La llanta mide 60 mm" (BOM) | `colmibot_params.xacro` | `wheel_radius = 0.030` (en **metros**) |
| Dónde está cada cosa | `colmibot_params.xacro` | `x y z` en metros, medidos desde el centro entre las llantas (ver C5) |
| De qué color es cada grupo | `materials.xacro` | `rgba` de 0 a 1 |
| Qué programas arrancar | `launch/display.launch.py` | robot_state_publisher + sliders + RViz |

**Consejo:** empezar con **un solo link** (`base_link` con una caja), compilar y abrirlo en RViz. Luego
agregar una llanta, probar otra vez, y así. Si se escribe todo de golpe y algo falla, no se sabe qué fue.

### (B) La geometría: SolidWorks → STL

Ya es manual: **Guardar como → STL**, con las opciones del paso 4.2.

### (C) Dejar los STL listos para ROS: lo que hace el script

El script hace **cinco cosas**. Las cinco se pueden hacer en SolidWorks **antes de exportar**, y así no hace
falta el script:

| # | Problema | Qué hace el script | Cómo hacerlo a mano en SolidWorks |
|---|---|---|---|
| C1 | El CAD usa otros ejes (arriba = +Y, adelante = −Z) y ROS usa X adelante, Y izquierda, Z arriba | Gira todos los triángulos (5.3) | Crear un **sistema de coordenadas** nuevo en el ensamble (*Insertar → Geometría de referencia → Sistema de coordenadas*) con X hacia los ToF, Y a la izquierda y Z arriba. Al exportar, elegirlo en **"Sistema de coordenadas de salida"** |
| C2 | El CAD está en mm y ROS en metros | Multiplica por 0.001 (5.3) | En las opciones del STL elegir unidad **metros** (o dejar mm y convertir después) |
| C3 | El origen tiene que estar entre las dos llantas, a la altura de su eje | Busca las llantas y mueve todo (5.5) | Poner el origen del sistema de coordenadas de C1 en el **punto medio entre los centros de las llantas**: primero se crea un *punto de referencia* ahí y luego el sistema de coordenadas sobre ese punto |
| C4 | 95 piezas son demasiadas; se quieren 7 grupos de colores + 2 llantas | Junta las piezas por nombre (5.4, 5.6) | **Ocultar** todo menos un grupo (por ejemplo, la electrónica) y exportar con ✅ "un único archivo". Repetir por cada grupo. **Cada llanta** se exporta sola, con **su propio** sistema de coordenadas en su centro, porque gira alrededor de su eje |
| C5 | Saber dónde están los sensores | Calcula el centro de cada sensor (5.8) | **Herramientas → Evaluar → Medir**: medir del sistema de coordenadas de C1 al centro de cada sensor y anotar X, Y y Z en `colmibot_params.xacro` |

En C4, lo de las llantas es justo donde estaba el error que se corrigió el 2026-10-23 (paso 5.5). Cada malla
de llanta tiene que quedar **centrada en su propio eje**: el joint dice dónde está la llanta y la malla solo
dice su forma. Si la malla no está centrada, la llanta se desplaza dos veces.

A mano son unas 9 exportaciones y varias mediciones: es lento y fácil equivocarse, y por eso se escribió el
script. Pero así se entiende lo que hace: **el script es solo una calculadora de estos cinco pasos.**

**Para practicar:** hacer C5 con un sensor (por ejemplo, el ToF central) y comparar la medida con la de
`urdf/generated/colmibot_meshes.xacro` (`tof_center_x/y/z`). Es la forma más rápida de comprobar que se
entendió.

### Una tercera opción: SW2URDF

Ahora que hay SolidWorks, existe el complemento **SW2URDF** (*SolidWorks to URDF Exporter*). Se le indica
qué piezas forman cada link y dónde va cada joint, y genera las mallas y un URDF. **No se probó.** Además,
genera un paquete con el formato de ROS 1, que hay que adaptar a ROS 2, y no da los xacro ordenados que ya
tiene el paquete. Sirve para comparar resultados, no para reemplazar lo que hay.

### Resumen

| Transformación | Herramienta | ¿Se puede a mano? |
|---|---|---|
| (A) BOM → estructura en xacro | Editor de texto | ✅ Siempre fue manual |
| (B) .SLDASM → STL | SolidWorks | ✅ Ya se hizo a mano |
| (C) STL → mallas y medidas para ROS | `prepare_meshes.py` | ✅ Con sistemas de coordenadas, ocultar/exportar y *Medir* en SolidWorks |

---

## Glosario de programas

| Programa | Para qué se usó |
|---|---|
| **SolidWorks** | CAD original; exportar las STL en su posición |
| **Onshape** | Primer intento de exportación; sirvió para confirmar los ejes |
| **Python 3.12** | Correr `prepare_meshes.py` en Windows |
| **xacro** | Convertir los `.xacro` en URDF |
| **colcon** | Compilar e instalar el paquete en ROS 2 |
| **robot_state_publisher** | Publicar el modelo y la posición de cada frame (TF) |
| **joint_state_publisher_gui** | Sliders para mover las llantas |
| **RViz2** | Ver el robot en 3D |
| **VirtualBox + Ubuntu 24.04** | Máquina virtual donde corre ROS 2 Jazzy |
| **Git / GitHub** | Historial y entrega (pendiente) |

---

## Glosario de términos

| Término | Qué significa | Dónde se explica |
|---|---|---|
| **base_footprint** | Frame en el piso, debajo del centro entre las llantas | 2.4 |
| **base_link** | Frame principal del robot, entre las dos llantas a la altura de su eje | 2.4 |
| **BOM** | Lista de materiales del robot | 1.1 |
| **Caja envolvente** (*bounding box*) | La caja más pequeña que contiene a una pieza; dice dónde está y cuánto mide | 4.3 |
| **CAD** | Programa de diseño 3D con medidas exactas (SolidWorks, Onshape) | 1.1 |
| **colcon build** | Comando que compila e instala los paquetes de un workspace | 2.9 |
| **Coordenadas** | Los tres números (X, Y, Z) que dicen dónde está un punto | 4.0 |
| **Ensamble / pieza / instancia** | Archivo que junta piezas / un objeto / cada uso de una pieza dentro del ensamble | 1.1 |
| **Exportar** | Guardar un archivo en otro formato (aquí, de SolidWorks a STL) | 4.0 |
| **Frame** | Punto de referencia con sus tres ejes | 2.4 |
| **Joint** | Unión entre dos links; dice dónde está el hijo y cómo se mueve | 2.2 |
| **Launch file** | Archivo que arranca varios nodos con una sola orden | 2.8 |
| **Link** | Parte rígida del robot | 2.2 |
| **Malla** (*mesh*) | Modelo 3D hecho de triángulos (un STL) | 2.7 |
| **Nodo** | Un programa de ROS que hace una tarea | 2.8 |
| **Paquete / workspace** | Carpeta con archivos de ROS relacionados / carpeta que contiene los paquetes | 2.9 |
| **REP-103** | Regla de ROS: X adelante, Y izquierda, Z arriba; metros y radianes | 2.6 |
| **RGBA** | Forma de escribir un color: rojo, verde, azul y opacidad, de 0 a 1 | 3.8 |
| **Robot diferencial** | Robot con dos ruedas motrices que gira cambiando la velocidad de cada una | 1.3 |
| **Script** | Programa pequeño que hace una tarea automática | 5.0 |
| **source** | Comando que "activa" ROS o un workspace en la terminal actual | 2.9, 7.4 |
| **STL** | Formato de archivo de modelos 3D hechos de triángulos | 2.7 |
| **TF** | Sistema de ROS que sabe dónde está cada frame respecto a los demás | 2.5 |
| **ToF** | Sensor de distancia que mide el tiempo que tarda la luz en ir y volver | 1.3 |
| **Tópico** | Canal por donde los nodos se mandan mensajes | 2.8 |
| **URDF** | Archivo XML que describe al robot (links y joints) | 2.2 |
| **VM** (máquina virtual) | Computadora simulada dentro de otra | 7.1 |
| **xacro** | URDF con variables, plantillas y condiciones | 2.3 |
| **XML** | Formato de texto con etiquetas `<...>` | 2.1 |
