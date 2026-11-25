#!/usr/bin/env python3
"""Import Parcial 4 (Chapters 9-13 + TPs) questions into database.db, sync Docker DB,
export validated JSON, and generate the synchronized Obsidian question bank.

Scope strictly enforced:
- Chapter 9 (Virtual Memory) + §12.6 Swap + TP Virtual Memory (theory & Linux lab) -> topic_id=2 (memory)
- Chapter 10 (File-System Interface) -> topic_id=3 (files)
- Chapter 11 (File-System Implementation) + TP File Systems Lab -> topic_id=3 (files)
- Chapter 12 (Mass-Storage Structure, Disk Scheduling & RAID) -> topic_id=7 (io)
- Chapter 13 (I/O Systems) + TP I/O Ports -> topic_id=7 (io)

Explicitly excludes out-of-scope legacy questions (Security/Protection Ch. 14-15,
Virtualization, Distributed Systems).
"""

from __future__ import annotations

import asyncio
import difflib
import json
import re
import shutil
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path("/home/dybalux/Escritorio_Dev/image_to_text")
DB_PATH = PROJECT_ROOT / "database.db"
DOCKER_DB_PATH = PROJECT_ROOT / "data/db/database.db"
VAULT_ROOT = Path("/home/dybalux/Escritorio_Facutad/Sistemas Operativos")
JSON_PATH = VAULT_ROOT / "Sistemas Operativos.json"
OBSIDIAN_BANK_PATH = (
    VAULT_ROOT / "Examenes/Banco de Preguntas - Multiple Choice (Cuarto Parcial).md"
)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MODULES: list[tuple[str, str]] = [
    ("mod1", "🧠 Módulo 1: Memoria Virtual y Swap (Cap. 9 + TP Memoria Virtual)"),
    ("mod2", "📄 Módulo 2: Interfaz del Sistema de Archivos (Cap. 10)"),
    ("mod3", "🗂️ Módulo 3: Implementación de Sistemas de Archivos (Cap. 11 + TP11)"),
    ("mod4", "💽 Módulo 4: Almacenamiento Masivo, Discos y RAID (Cap. 12)"),
    ("mod5", "🔌 Módulo 5: Sistemas de Entrada/Salida y Puertos (Cap. 13 + TP10)"),
]


def _q(
    qid: int,
    module: str,
    topic_id: int,
    question_text: str,
    correct_text: str,
    explanation: str,
    distractors: list[str],
    trap: str | None = None,
) -> dict[str, Any]:
    """Build a normalized question entry with deterministic option ordering."""
    # Vary correct option position across questions so the answer isn't always A
    pos = (qid * 3) % 4
    opts: list[dict[str, Any]] = [
        {"text": d, "type": "incorrect", "explanation": None} for d in distractors
    ]
    opts.insert(
        pos,
        {"text": correct_text, "type": "correct", "explanation": explanation},
    )
    return {
        "id": qid,
        "module": module,
        "topic_id": topic_id,
        "question_text": question_text,
        "options": opts,
        "trap": trap,
    }


RAW_QUESTIONS: list[dict[str, Any]] = [
    # =========================================================================
    # MÓDULO 1: MEMORIA VIRTUAL Y SWAP (Cap. 9 + §12.6 + TP9) -> topic_id = 2
    # =========================================================================
    _q(
        1,
        "mod1",
        2,
        "¿Qué es la memoria virtual y cuál es su principal ventaja?",
        "Es una técnica implementada por el SO que permite ejecutar procesos aunque no estén cargados completamente en memoria principal, pudiendo incluso superar el tamaño de la RAM física.",
        "La memoria virtual separa el espacio lógico del físico: solo las páginas necesarias residen en RAM, permitiendo ejecutar programas más grandes que la memoria física y aumentando el grado de multiprogramación.",
        [
            "Es una memoria caché integrada en el procesador que reemplaza a la RAM principal para eliminar los accesos a disco.",
            "Es una técnica exclusiva del programador para dividir un ejecutable en módulos manuales sin intervención del SO.",
            "Es un mecanismo que obliga a cargar el código completo del proceso en marcos contiguos antes de iniciar su ejecución.",
        ],
    ),
    _q(
        2,
        "mod1",
        2,
        "¿Cuál es la diferencia fundamental entre la carga dinámica (dynamic loading) y la memoria virtual?",
        "La carga dinámica depende del diseño explícito del programador, mientras que la memoria virtual es implementada por el SO de manera transparente para el programador.",
        "Ambas permiten ejecutar programas sin tener todo cargado en RAM, pero en la carga dinámica el programador gestiona la carga bajo demanda de rutinas; en la memoria virtual el SO y la MMU gestionan código y datos automáticamente.",
        [
            "La carga dinámica requiere hardware MMU obligatorio, mientras que la memoria virtual funciona solo por software en el compilador.",
            "La memoria virtual solo carga bibliotecas compartidas y la carga dinámica solo gestiona variables del heap.",
            "La carga dinámica permite ejecutar programas más grandes que la RAM, mientras que la memoria virtual no.",
        ],
    ),
    _q(
        3,
        "mod1",
        2,
        "En un sistema con paginación bajo demanda, ¿un fallo de página (page fault) es un error del programa?",
        "No; es una excepción/trampa normal y esperada que indica que una página legal del proceso no está aún en RAM y debe traerse desde el almacenamiento secundario.",
        "El page fault forma parte del funcionamiento normal de la memoria virtual. Solo se convierte en un error fatal (abortando el proceso) si la tabla interna del PCB determina que la referencia pertenece a una dirección ilegal.",
        [
            "Sí; siempre indica que el proceso intentó acceder a una dirección prohibida y el SO debe terminarlo inmediatamente.",
            "Sí; ocurre únicamente cuando falla físicamente un módulo de memoria RAM o se corrompe la tabla de páginas.",
            "No; significa que la dirección no estaba en la TLB pero sí se encuentra cargada en memoria principal.",
        ],
        trap="No confundir un fallo de TLB (la página SÍ está en RAM) con un fallo de página (la página está en disco), ni asumir que 'fallo' equivale a 'error fatal'.",
    ),
    _q(
        4,
        "mod1",
        2,
        "¿Qué ocurre paso a paso cuando un proceso genera un fallo de página válido y qué efecto tiene sobre la CPU?",
        "Se dispara una trampa al SO, se verifica la validez de la referencia, se busca un marco libre (o se sustituye una página), se programa la lectura desde disco generando un cambio de contexto, se actualiza la tabla de páginas y se reanuda la instrucción.",
        "Como leer una página desde disco es muy lento, el proceso se bloquea esperando la E/S y el planificador realiza un cambio de contexto para que otro proceso use la CPU hasta que llega la interrupción de disco.",
        [
            "La MMU lee directamente la página desde el disco sin avisar al SO ni realizar ningún cambio de contexto.",
            "El proceso queda en espera ocupada en la CPU hasta que el disco completa la transferencia al marco.",
            "El SO reinicia el programa desde la primera línea de main() luego de cargar todas sus páginas en RAM.",
        ],
    ),
    _q(
        5,
        "mod1",
        2,
        "Cuando Silberschatz indica que tras atender un fallo de página se 'reinicia' la instrucción/proceso de usuario, ¿qué significa exactamente?",
        "Que se reanuda la ejecución volviendo a ejecutar la instrucción que había quedado pausada por el fallo de página, no empezar el programa desde el principio.",
        "Al dispararse la trampa de page fault se guarda el estado de la CPU; una vez cargada la página y actualizado el bit de validez, la CPU re-ejecuta exactamente la instrucción interrumpida de forma transparente.",
        [
            "Que el proceso se destruye y se vuelve a lanzar desde el inicio con un nuevo PID.",
            "Que se borra toda la tabla de páginas del proceso y se recarga el binario ejecutable completo.",
            "Que se reinicia el planificador de corto plazo vaciando la cola de listos.",
        ],
    ),
    _q(
        6,
        "mod1",
        2,
        "¿Qué ventajas aporta la paginación bajo demanda (intercambiador perezoso) frente a cargar el proceso completo al inicio?",
        "Menor E/S al arranque, menor consumo de RAM física, respuesta inicial más rápida y posibilidad de alojar más procesos simultáneamente.",
        "Al cargar únicamente las páginas efectivamente referenciadas, se evita traer código de manejo de errores o funciones que quizá nunca se ejecuten durante esa corrida.",
        [
            "Elimina por completo los fallos de página y garantiza que el tiempo de acceso efectivo sea idéntico al de la caché L1.",
            "Evita tener que mantener tablas de páginas y suprime la necesidad de un espacio de intercambio en disco.",
            "Garantiza que las páginas del proceso queden siempre en marcos físicamente contiguos en la RAM.",
        ],
    ),
    _q(
        7,
        "mod1",
        2,
        "¿Cuál es el resultado de aplicar la técnica Copy-on-Write (COW) en la llamada al sistema fork()?",
        "Padre e hijo comparten inicialmente las mismas páginas físicas marcadas como solo lectura; solo se duplica una página individual en RAM si alguno intenta modificarla, acelerando enormemente fork().",
        "COW evita copiar innecesariamente todo el espacio de direcciones del padre (especialmente útil cuando el hijo invoca exec() enseguida), reduciendo tiempo de creación y consumo de RAM.",
        [
            "El hijo recibe inmediatamente una copia física completa en disco de todas las páginas del padre antes de comenzar a ejecutar.",
            "Padre e hijo comparten permanentemente todas las escrituras en memoria sin aislamiento entre procesos.",
            "Se impide que el proceso hijo pueda escribir en memoria hasta que el proceso padre finalice.",
        ],
    ),
    _q(
        8,
        "mod1",
        2,
        "Se produce un fallo de página legal pero la lista de marcos libres está vacía (toda la RAM está ocupada). ¿Cuál es la solución más comúnmente utilizada?",
        "Ejecutar un algoritmo de sustitución de páginas para elegir una página víctima en RAM, escribirla al área de intercambio si fue modificada y cargar la nueva página en ese marco.",
        "La sustitución de páginas permite continuar ejecutando procesos sin abortarlos ni suspender todo el sistema cada vez que se llena la RAM física.",
        [
            "Abortar inmediatamente el proceso que provocó el fallo de página por falta de memoria.",
            "Compactar los marcos ocupados en RAM para generar espacio contiguo libre.",
            "Ampliar automáticamente el tamaño de cada página de 4 KB a 4 MB en tiempo de ejecución.",
        ],
    ),
    _q(
        9,
        "mod1",
        2,
        "¿Qué función cumple el bit de modificación (dirty bit) durante la sustitución de páginas?",
        "Indica si la página víctima fue modificada en RAM; si está en 0 no hace falta escribirla al disco, ahorrando el 50% de las transferencias de E/S del reemplazo.",
        "Una página limpia (dirty = 0) ya tiene una copia idéntica en el disco o ejecutable, por lo que su marco puede sobrescribirse directamente con la página entrante.",
        [
            "Indica si la página pertenece al espacio lógico legal del proceso o si debe disparar un Segmentation Fault.",
            "Indica cuántas veces fue referenciada la página para calcular el algoritmo LFU.",
            "Bloquea la página en memoria para impedir que el sistema operativo pueda desalojarla.",
        ],
    ),
    _q(
        10,
        "mod1",
        2,
        "¿Qué es la Anomalía de Belady y qué algoritmo clásico de sustitución de páginas puede sufrirla?",
        "Es el fenómeno por el cual asignar más marcos físicos a un proceso provoca una mayor cantidad de fallos de página; ocurre en FIFO, pero nunca en Óptimo ni en LRU.",
        "FIFO no cumple la propiedad de inclusión de algoritmos de pila, por lo que con ciertas secuencias de referencias aumentar los marcos empeora la tasa de fallos. Óptimo y LRU son algoritmos de pila y están libres de esta anomalía.",
        [
            "Es la caída abrupta de la CPU al aumentar el tamaño de página; ocurre únicamente en el algoritmo LRU.",
            "Es el aumento de fallos de página al reducir el número de marcos; ocurre exclusivamente en el algoritmo Óptimo.",
            "Es la pérdida de traducciones en la TLB al cambiar de proceso; se resuelve con FIFO.",
        ],
        trap="Recordá: 'MÁS marcos → MÁS fallos' = Belady. FIFO SÍ la sufre; LRU y Óptimo NUNCA.",
    ),
    _q(
        11,
        "mod1",
        2,
        "¿Cómo trabaja el algoritmo de sustitución de páginas Óptimo (OPT)?",
        "Es un algoritmo teórico de referencia que reemplaza la página que no será utilizada durante el período más largo en el futuro.",
        "Garantiza la menor tasa de fallos posible para un número fijo de marcos, pero es irrealizable en la práctica porque el SO no conoce la secuencia futura de referencias.",
        [
            "Reemplaza siempre la página que lleva más tiempo sin haber sido usada en el pasado reciente.",
            "Reemplaza la página que ingresó primero a la memoria principal utilizando una cola circular.",
            "Reemplaza la página con menor cantidad de escrituras registradas en el bit dirty.",
        ],
    ),
    _q(
        12,
        "mod1",
        2,
        "¿Cuál es la principal desventaja del algoritmo FIFO frente a LRU (como en la analogía de góndolas de supermercado del TP de Memoria Virtual)?",
        "FIFO solo considera la antigüedad de ingreso e ignora la localidad de referencias, pudiendo expulsar una página muy utilizada; LRU en cambio reemplaza la que lleva más tiempo sin usarse.",
        "Al igual que un supermercado que sacaría un producto de venta diaria solo por ser el primero que se colocó en la estantería, FIFO puede desalojar páginas activas y muy referenciadas.",
        [
            "FIFO requiere hardware costoso de contadores de tiempo en cada acceso, mientras que LRU usa una simple cola.",
            "LRU sufre la Anomalía de Belady con mayor frecuencia que FIFO.",
            "FIFO solo puede aplicarse con asignación local, mientras que LRU funciona solo con asignación global.",
        ],
    ),
    _q(
        13,
        "mod1",
        2,
        "¿Cómo funciona el algoritmo de sustitución de Segunda Oportunidad (o algoritmo del Reloj)?",
        "Recorre las páginas en orden FIFO circular consultando un bit de referencia: si es 1, lo pone en 0 y avanza; si es 0, elige esa página como víctima.",
        "Es una aproximación práctica y económica a LRU usando únicamente 1 bit de referencia por hardware, evitando el alto costo de actualizar pilas o relojes en cada referencia de memoria.",
        [
            "Expulsa inmediatamente cualquier página cuyo bit de referencia esté en 1 porque ya cumplió su ciclo.",
            "Asigna un quantum de CPU a cada página y expulsa la que consumió más tiempo de procesador.",
            "Predice el próximo acceso analizando el grafo de llamadas del compilador.",
        ],
    ),
    _q(
        14,
        "mod1",
        2,
        "¿Por qué existe un número mínimo de marcos físicos que debe asignarse a cada proceso y qué determina ese mínimo?",
        "Lo determina la arquitectura de instrucciones de la CPU: un proceso necesita suficientes marcos para mantener simultáneamente todas las páginas referenciadas por una única instrucción y evitar fallos infinitos.",
        "Si una instrucción abarca dos páginas o utiliza direccionamiento indirecto sobre operandos en distintas páginas, el proceso debe contar al menos con esos marcos para poder completarla.",
        [
            "Lo determina únicamente el tamaño del bloque del sistema de archivos para evitar fragmentación externa.",
            "Debe ser siempre igual al total de páginas del ejecutable para que no ocurra ningún fallo de página.",
            "Lo fija el usuario al compilar el programa mediante el registro límite.",
        ],
    ),
    _q(
        15,
        "mod1",
        2,
        "¿Qué ventaja principal ofrece la sustitución/asignación global de marcos frente a la asignación local?",
        "Permite aprovechar mejor la RAM asignando marcos de procesos inactivos a procesos con mayor demanda, reduciendo fallos y aumentando la productividad global del sistema.",
        "En la asignación global un proceso puede tomar una víctima de cualquier marco disponible (análogo al ámbito SCS en planificación), aunque sacrifica la previsibilidad individual que da la asignación local.",
        [
            "Garantiza que el rendimiento de cada proceso sea completamente independiente de la carga de los demás procesos.",
            "Mantiene constante el conjunto residente de cada proceso durante toda su ejecución.",
            "Elimina por completo la posibilidad de hiperpaginación sin necesidad de controlar la multiprogramación.",
        ],
    ),
    _q(
        16,
        "mod1",
        2,
        "¿Por qué ciertos marcos de página en RAM —como el código residente del kernel o los búferes de E/S en uso— deben bloquearse (frame locking)?",
        "Para impedir que sean seleccionados como víctimas y desalojados a disco, lo cual corrompería transferencias DMA en curso o desestabilizaría al sistema operativo.",
        "Si un controlador DMA está transfiriendo datos hacia un búfer en RAM y ese marco fuera reemplazado y reasignado a otro proceso, los datos se escribirían en la memoria del proceso equivocado.",
        [
            "Para impedir que la CPU pueda leer esos marcos a través de la memoria caché.",
            "Para forzar a que dichos marcos se almacenen exclusivamente en el área de intercambio.",
            "Porque el hardware de paginación impide traducir direcciones virtuales del kernel.",
        ],
    ),
    _q(
        17,
        "mod1",
        2,
        "¿Qué situación debe sostenerse para que un proceso entre en hiperpaginación (thrashing)?",
        "Que el conjunto residente (páginas cargadas en RAM) sea menor que el conjunto de trabajo (páginas que necesita activamente en su localidad actual).",
        "Cuando no caben en RAM las páginas activas de la fase actual, el proceso genera fallos de página continuos y pasa más tiempo paginando contra el disco que ejecutando instrucciones útiles.",
        [
            "Que el conjunto residente sea mayor que el conjunto de trabajo y sobren marcos libres en RAM.",
            "Que la tasa de aciertos de la TLB supere el 99% durante un intervalo prolongado.",
            "Que el grado de multiprogramación disminuya hasta dejar un solo proceso en memoria.",
        ],
    ),
    _q(
        18,
        "mod1",
        2,
        "Según el laboratorio de Memoria Virtual (programa virus_gallego.c), ¿qué relación existe entre los accesos aleatorios a memoria, el principio de localidad y el conjunto de trabajo?",
        "Los accesos aleatorios rompen la localidad espacial y temporal de referencias, haciendo que el conjunto de trabajo crezca enormemente y abarque casi todas las páginas reservadas.",
        "Al no concentrarse en pocas páginas, en cuanto el volumen reservado supera la RAM disponible se dispara el thrashing en la fase de lecturas aleatorias; al cambiar a accesos secuenciales, el tiempo cae drásticamente.",
        [
            "Los accesos aleatorios fortalecen la localidad espacial y reducen el conjunto de trabajo a una sola página.",
            "El principio de localidad solo afecta al llenado inicial de memoria y no influye en las lecturas posteriores.",
            "Los accesos aleatorios eliminan la necesidad de utilizar el área de intercambio porque distribuyen la carga.",
        ],
    ),
    _q(
        19,
        "mod1",
        2,
        "¿Cuáles son los principales compromisos (trade-offs) al elegir un tamaño de página grande frente a uno pequeño?",
        "Páginas grandes reducen la tabla de páginas y mejoran la eficiencia de E/S, pero aumentan la fragmentación interna, empeoran COW y pierden resolución de localidad; páginas pequeñas invierten estos efectos.",
        "Por eso los sistemas suelen elegir un punto de equilibrio como 4 KB (4096 B) en Linux, evitando tanto tablas de páginas gigantes como desperdicio excesivo de RAM por página.",
        [
            "Páginas grandes eliminan la fragmentación interna pero introducen fragmentación externa severa.",
            "Páginas pequeñas reducen el tamaño de las tablas de páginas y optimizan la tasa de transferencia de discos HDD.",
            "El tamaño de página únicamente afecta a la segmentación y no tiene impacto sobre Copy-on-Write ni sobre la TLB.",
        ],
    ),
    _q(
        20,
        "mod1",
        2,
        "En lenguaje C (programa recorrer_matriz.c del TP de Memoria Virtual), ¿cómo se comparan el conjunto de trabajo y el rendimiento al recorrer una matriz gigante por filas vs. por columnas cuando se usa swap?",
        "Por filas aprovecha el almacenamiento contiguo (row-major), logrando un conjunto de trabajo mínimo y pocos fallos; por columnas salta entre páginas en cada paso, disparando el conjunto de trabajo y provocando thrashing severo.",
        "C almacena las matrices fila tras fila. Recorrer por columnas provoca un salto de una fila completa por acceso, expulsando páginas antes de volver a usarlas en la columna siguiente.",
        [
            "Por columnas es siempre más rápido porque C almacena las matrices contiguas por columnas (column-major).",
            "Ambos recorridos generan exactamente la misma cantidad de fallos de página porque acceden al mismo número total de elementos.",
            "Recorrer por filas aumenta la fragmentación externa en el área de intercambio.",
        ],
    ),
    _q(
        21,
        "mod1",
        2,
        "En el laboratorio de Memoria Virtual en Linux, ¿qué indica VmSwap = 0 kB en /proc/<PID>/status y cuál es el estado predominante en top cuando un proceso entra en thrashing por swap?",
        "VmSwap = 0 kB indica que el proceso no utilizó área de intercambio (todo cabe en RAM); al entrar en thrashing por swap, su estado predominante en top pasa a ser 'D' (Uninterruptible Sleep, esperando E/S de disco).",
        "Además, el comando 'free -m' permite consultar la RAM y el swap instalados en megabytes, y 'VmRSS' muestra la memoria física realmente residente en RAM.",
        [
            "VmSwap = 0 kB indica que el proceso fue desalojado por completo a disco; en thrashing su estado predominante en top es 'Z' (Zombie).",
            "VmSwap = 0 kB significa que el kernel deshabilitó la paginación; en thrashing el proceso permanece en estado 'R' al 100% de CPU.",
            "VmSwap = 0 kB muestra la memoria física residente; en thrashing el estado predominante es 'T' (Stopped).",
        ],
    ),
    _q(
        22,
        "mod1",
        2,
        "Respecto de la gestión del espacio de intercambio (Swap Space, §12.6), ¿qué ventaja tiene usar una partición cruda (raw) dedicada frente a un archivo de swap dentro del sistema de archivos?",
        "Es más rápida porque el SO gestiona directamente bloques contiguos sin atravesar las capas, directorios ni la fragmentación del sistema de archivos.",
        "El archivo de swap es más fácil de crear y redimensionar, pero agrega sobrecarga de estructura de directorios y asignación de bloques; la partición raw prioriza velocidad.",
        [
            "Permite compartir las páginas intercambiadas directamente entre usuarios mediante enlaces simbólicos.",
            "Evita cualquier desgaste en unidades SSD porque no realiza escrituras físicas en el soporte.",
            "Es más fácil de redimensionar dinámicamente en caliente sin tocar la tabla de particiones.",
        ],
    ),
    # =========================================================================
    # MÓDULO 2: INTERFAZ DEL SISTEMA DE ARCHIVOS (Cap. 10) -> topic_id = 3
    # =========================================================================
    _q(
        23,
        "mod2",
        3,
        "¿Cuál es el propósito o función principal de un sistema de archivos?",
        "Proporcionar una estructura para almacenar datos organizados como archivos, así como una colección de funciones que se pueden realizar sobre ellos.",
        "Un sistema de archivos combina estructuras de almacenamiento persistente con operaciones (crear, abrir, leer, escribir, buscar, borrar) que abstraen al usuario de los detalles físicos del disco.",
        [
            "Se encarga únicamente de agrupar sectores en particiones físicas durante la fabricación del disco.",
            "Son módulos de hardware dentro del disco rígido que encuentran espacios vacíos sin intervención del SO.",
            "Asigna exclusivamente direcciones virtuales de la RAM a los procesos en ejecución.",
        ],
    ),
    _q(
        24,
        "mod2",
        3,
        "¿Qué significa abrir un archivo (llamada al sistema open)?",
        "Relaciona un archivo con un proceso y trae a memoria principal los datos de control del archivo (metadatos / i-nodo) para agilizar operaciones posteriores.",
        "Al abrir un archivo el SO resuelve su nombre en el directorio una sola vez y registra el FCB/inodo en las tablas de archivos abiertos, devolviendo un descriptor al proceso sin cargar todavía todo el contenido del archivo.",
        [
            "Lee inmediatamente todos los datos del archivo desde el disco y los carga completos en memoria principal.",
            "Decide en qué dirección física contigua de la RAM se copiará el contenido del archivo.",
            "Permite compartir automáticamente el archivo con todos los usuarios del sistema operativo.",
        ],
        trap="Ojo: open() NO lee los bloques de datos del archivo; solo carga sus metadatos (inodo/FCB) en memoria.",
    ),
    _q(
        25,
        "mod2",
        3,
        "¿Qué significa la llamada al sistema leer un archivo (read)?",
        "Trae bytes de un archivo desde un dispositivo a memoria principal (búfer) por pedido de un proceso, desde la posición del puntero de archivo.",
        "La operación read() utiliza el descriptor devuelto por open() y el puntero actual del archivo para transferir la cantidad solicitada de bytes hacia el búfer indicado por el proceso.",
        [
            "Significa compartir los datos de un archivo abierto por el SO para que pueda ser usado por otros procesos.",
            "Significa cargar anticipadamente todos los inodos de la partición en memoria caché.",
            "Mapea obligatoriamente el archivo completo en la pila del proceso en una dirección fija.",
        ],
    ),
    _q(
        26,
        "mod2",
        3,
        "¿Cuál es el motivo principal para bloquear (proteger con lock) un archivo?",
        "Debido a que un proceso necesita realizar operaciones sobre el archivo en exclusión mutua (como escrituras), evitando inconsistencias por acceso concurrente.",
        "Los bloqueos de archivos (compartidos para lectura, exclusivos para escritura) coordinan procesos concurrentes para que no se pisen ni corrompan datos al modificar un mismo archivo.",
        [
            "Porque los archivos no pueden abrirse en ningún sistema operativo si no están previamente bloqueados.",
            "Porque los bloques que resultan de agrupar sectores de un archivo se denominan 'bloqueo'.",
            "Para impedir que dos procesos lean simultáneamente un archivo de solo lectura.",
        ],
    ),
    _q(
        27,
        "mod2",
        3,
        "¿Cuáles tipos de archivos reconoce UNIX?",
        "Regulares (ordinarios), directorios, dispositivos de carácter, dispositivos de bloque, pipes (FIFO) y enlaces simbólicos (además de sockets).",
        "En UNIX todo recurso se abstrae como archivo con un carácter de tipo (-, d, c, b, p, l, s). Los enlaces duros NO son un tipo de archivo, sino entradas de directorio.",
        [
            "Directorios, regulares, pipes, bloque y enlaces duros y simbólicos.",
            "Directorios, normales, de bloque y enlaces duros.",
            "Secuenciales, directos, aleatorios e indexados.",
        ],
        trap="¡Trampa clásica de examen! Los enlaces duros (hard links) NO son un tipo de archivo; son entradas dentro de un directorio.",
    ),
    _q(
        28,
        "mod2",
        3,
        "En UNIX/Linux, ¿qué es el número mágico (magic number) de un archivo y quién ejecuta los comandos de un archivo por lotes (script de shell)?",
        "El número mágico es una secuencia fija de bytes en la cabecera que identifica el formato real del archivo; un script de shell es ejecutado por un intérprete de comandos (shell), no directamente por la CPU.",
        "A diferencia de las extensiones de nombre (que son solo una pista), el número mágico (ej. 0x7F 'ELF', '#!') identifica el tipo real del contenido. En scripts, el kernel invoca al intérprete indicado.",
        [
            "El número mágico es la cantidad de enlaces duros en el inodo; los scripts de shell son ejecutados directamente por la ALU de la CPU sin intérprete.",
            "El número mágico es la extensión de tres letras del archivo; los scripts solo pueden ejecutarse en Windows.",
            "El número mágico es el número de partición del disco; el bootloader ejecuta directamente los scripts de usuario.",
        ],
    ),
    _q(
        29,
        "mod2",
        3,
        "¿Qué diferencia hay entre el método de acceso secuencial y el método de acceso directo (relativo)?",
        "En el secuencial los registros se recorren uno tras otro en orden tal cual fueron guardados; en el directo se calcula o especifica la posición/clave de un registro y se accede a él directamente.",
        "El acceso secuencial se adapta a cintas o reproducción de video; el acceso directo es esencial para bases de datos sobre HDD o SSD.",
        [
            "El acceso secuencial solo funciona en discos SSD y el acceso directo es exclusivo de cintas magnéticas.",
            "En el acceso directo no se permite leer el primer registro sin recorrer antes todos los bloques del volumen.",
            "En el acceso secuencial se utiliza siempre una función hash para calcular la dirección física de cada byte.",
        ],
    ),
    _q(
        30,
        "mod2",
        3,
        "¿Cómo es el método de acceso en una organización indexada?",
        "Siempre se pasa por el índice primero, ya sea para recorrer el archivo en forma secuencial o para realizar un acceso directo.",
        "El índice mantiene claves y punteros hacia los bloques de datos; consultar el índice primero permite localizar directamente cualquier bloque sin recorrer todo el archivo.",
        [
            "Permite acceder primero a los bloques de datos y luego construir el índice al cerrar el archivo.",
            "Aplica una función hash al contenido del archivo sin utilizar ninguna tabla ni índice auxiliar.",
            "Solo permite acceso secuencial desde el bloque 0 sin posibilidad de saltos directos.",
        ],
    ),
    _q(
        31,
        "mod2",
        3,
        "¿Qué es un directorio en un sistema de archivos?",
        "Es un archivo especial que contiene información/entradas sobre otros archivos y permite traducir nombres de archivo a su ubicación (ej. número de inodo o descriptor).",
        "El directorio NO almacena los datos de los archivos que 'contiene', sino una tabla de referencias (en UNIX, una lista de enlaces duros nombre → inodo). Por eso no puede haber dos nombres iguales en un mismo directorio.",
        [
            "Es una partición física independiente que guarda físicamente contiguos todos los bytes de los archivos de una carpeta.",
            "Es una estructura residente exclusivamente en RAM que desaparece cuando se apaga el equipo.",
            "Es un archivo de texto plano que contiene copias duplicadas del contenido de cada archivo del usuario.",
        ],
    ),
    _q(
        32,
        "mod2",
        3,
        "¿Qué operaciones se pueden realizar sobre una estructura de directorios?",
        "Buscar un archivo, crear archivos, borrarlos, listar el contenido del directorio, renombrar archivos y recorrer el sistema de archivos.",
        "Estas operaciones sobre el directorio manipulan las entradas nombre → ubicación (como los comandos ls, touch, rm, mv, find).",
        [
            "Únicamente leer bloques físicos de 512 bytes sin distinguir nombres de archivos.",
            "Solo operaciones aritméticas sobre los registros del archivo contenidos en RAM.",
            "Exclusivamente particionar y formatear a bajo nivel los platos del disco.",
        ],
    ),
    _q(
        33,
        "mod2",
        3,
        "¿Cómo se puede estructurar lógicamente una organización de directorios en un sistema operativo?",
        "Como una lista (nivel único o dos niveles), como un árbol, como un grafo acíclico o como un grafo general.",
        "La evolución va desde un directorio de un nivel (simple pero con colisiones) hasta árboles, grafos acíclicos (compartición sin ciclos) y grafos generales (con posibles ciclos).",
        [
            "Únicamente como un archivo de texto plano donde el único propietario permitido es el kernel.",
            "Exclusivamente como una estructura orientada a objetos donde no existen jerarquías ni rutas.",
            "Solamente como una cola FIFO circular sin subdirectorios.",
        ],
    ),
    _q(
        34,
        "mod2",
        3,
        "¿Por qué a veces resulta conveniente que los directorios se estructuren como grafos acíclicos en lugar de árboles estrictos?",
        "Para que se puedan compartir archivos o subdirectorios de forma simultánea desde distintos directorios pertenecientes a uno o varios usuarios.",
        "Un árbol impide que un mismo archivo figure en dos ramas diferentes; un grafo acíclico permite enlaces compartidos evitando al mismo tiempo los bucles infinitos de un grafo general.",
        [
            "Porque los árboles no soportan rutas absolutas ni subdirectorios anidados.",
            "Porque los grafos acíclicos permiten crear ciclos infinitos que aceleran la búsqueda con find.",
            "Porque en un árbol no se pueden asignar permisos de lectura y escritura.",
        ],
    ),
    _q(
        35,
        "mod2",
        3,
        "¿Puede un esquema de directorios en Linux tener forma de grafo general (con ciclos)?",
        "Sí, mediante el uso de enlaces simbólicos (soft links) que apuntan a directorios ancestros.",
        "Linux prohíbe a los usuarios crear enlaces duros a directorios justamente para no romper la estructura de inodos, pero sí permite enlaces simbólicos a directorios, lo que posibilita formar ciclos (grafo general).",
        [
            "Sí, mediante el uso de enlaces duros creados por el usuario hacia directorios padre.",
            "No, porque Linux prohíbe todo tipo de enlace (duro o simbólico) hacia directorios.",
            "No, porque Linux implementa un detector automático que impide crear cualquier ciclo con enlaces simbólicos.",
        ],
        trap="En una captura vieja de parcial el alumno marcó 'No, detecta ciclos' y estaba MAL. La correcta es: Sí, con enlaces simbólicos.",
    ),
    _q(
        36,
        "mod2",
        3,
        "¿Cómo se distingue en UNIX/Linux si una ruta es absoluta o relativa, y cuál es su diferencia?",
        "La ruta absoluta siempre comienza con la barra de raíz (/) especificando todo el camino desde la raíz; la relativa no comienza con / y se interpreta a partir del directorio actual de trabajo.",
        "Ejemplos: '/home/usuario/doc.txt' es absoluta (válida desde cualquier ubicación); '../doc.txt' o './a.out' son relativas al directorio actual (pwd).",
        [
            "La relativa siempre comienza con '/' y la absoluta siempre comienza con '~' (home).",
            "La absoluta comienza con './' y la relativa comienza con el nombre de la partición física.",
            "No existe diferencia en UNIX/Linux porque todos los archivos residen en un único nivel sin raíz.",
        ],
    ),
    _q(
        37,
        "mod2",
        3,
        "¿Para qué se montan los sistemas de archivos y qué ocurre en Linux si se monta un SA sobre un directorio que no está vacío?",
        "Se montan para conectarlos lógicamente bajo un único árbol y simplificar su control; en Linux (raíz única '/'), el contenido previo del punto de montaje queda temporalmente oculto ('pisado') pero no se sobrescribe ni borra.",
        "A diferencia de Windows (que asigna letras de unidad C:\\, D:\\), UNIX/Linux integra todos los volúmenes montados dentro de una única jerarquía; al desmontar reaparece el contenido original del directorio.",
        [
            "Se montan para copiar físicamente todos los archivos del disco externo dentro de la RAM; el contenido previo del directorio se borra permanentemente.",
            "Se montan únicamente para cambiar el formato físico de 512 bytes a 4 KB en caliente.",
            "Linux asigna automáticamente una nueva letra de unidad (C:, D:, E:) porque no permite montar sobre directorios.",
        ],
    ),
    _q(
        38,
        "mod2",
        3,
        "¿Cómo asigna UNIX/Linux en su forma tradicional los permisos a archivos y directorios (ACL condensada) y cómo se compara con Windows?",
        "UNIX usa 9 bits fijos registrados en el inodo (3 clases de usuario × 3 operaciones r/w/x), lo cual es una ACL condensada compacta; Windows usa por defecto listas de control de acceso (ACL) completas.",
        "La ACL condensada ocupa tamaño fijo mínimo dentro del inodo y se evalúa rapidísimo, aunque ofrece menor granularidad por usuario individual que una ACL completa (que Linux también puede habilitar opcionalmente).",
        [
            "UNIX usa por defecto matrices de acceso completas por usuario y Windows no posee control de acceso por archivo.",
            "UNIX consulta al usuario en cada ejecución sin almacenar permisos en el inodo.",
            "UNIX guarda los permisos exclusivamente en la extensión del nombre del archivo.",
        ],
    ),
    _q(
        39,
        "mod2",
        3,
        "En los permisos de un archivo GNU/Linux con esquema '-rwxr-xr--', ¿a quién corresponde cada grupo de bits en orden y qué permisos tiene el grupo?",
        "El orden es Dueño, Grupo y Otros (todos los demás); en '-rwxr-xr--' el grupo tiene permisos de lectura y ejecución (r-x).",
        "Desglose: '-' archivo regular | 'rwx' dueño (lectura, escritura, ejecución) | 'r-x' grupo (lectura y ejecución) | 'r--' otros (solo lectura).",
        [
            "El orden es Grupo, Dueño y Otros; el grupo tiene lectura, escritura y ejecución.",
            "El orden es Dueño, Grupo y Otros; el grupo tiene solo lectura.",
            "El orden es Otros, Grupo y Dueño; el grupo tiene escritura y ejecución.",
        ],
    ),
    _q(
        40,
        "mod2",
        3,
        "¿Qué archivos abre automáticamente un sistema operativo como UNIX/Linux para cada proceso al ser creado?",
        "Abre tres archivos estándar: entrada estándar (stdin, fd 0), salida estándar (stdout, fd 1) y salida de error estándar (stderr, fd 2).",
        "Estas tres entradas iniciales se cargan en la tabla de archivos abiertos por proceso, permitiendo redirecciones y tuberías (pipes) de forma uniforme.",
        [
            "UNIX no abre ningún archivo hasta que el proceso invoca explícitamente open().",
            "Abre automáticamente todos los archivos presentes en el directorio /home del usuario.",
            "Abre únicamente el ejecutable binario y el superbloque de la partición raíz.",
        ],
    ),
    # =========================================================================
    # MÓDULO 3: IMPLEMENTACIÓN DE SA + TP11 (Cap. 11 + TP11) -> topic_id = 3
    # =========================================================================
    _q(
        41,
        "mod3",
        3,
        "¿Por qué resulta conveniente diseñar e implementar un sistema de archivos dividido en capas?",
        "Porque dada la complejidad de las operaciones conviene dividir tareas en módulos independientes y reutilizar los servicios esenciales comunes entre distintos sistemas de archivos.",
        "La arquitectura estratificada reduce la duplicación de código (por ejemplo, distintos SA comparten el mismo sistema básico de archivos y controladores de dispositivo).",
        [
            "Para que el código del sistema de archivos pueda dividirse en sectores de 512 bytes y quepa en el disco.",
            "Para que cada capa sea ejecutada por un sistema operativo distinto en la misma máquina.",
            "Porque las CPU modernas impiden ejecutar código de E/S si no tiene al menos seis capas.",
        ],
    ),
    _q(
        42,
        "mod3",
        3,
        "Dentro de la arquitectura en capas de un sistema de archivos, ¿para qué sirve el sistema lógico de archivos (E/S lógica)?",
        "Gestiona los metadatos y estructuras de control del archivo (FCB/inodos, directorios, protección) y se ocupa del acceso a los registros según la visión del usuario.",
        "Es la capa superior más cercana a las aplicaciones: traduce nombres simbólicos de archivos a FCB/inodos y verifica permisos antes de delegar al módulo de organización.",
        [
            "Traduce la dirección lógica de bloque a dirección física (cilindro, superficie y sector) según la geometría del disco.",
            "Agrupa sectores consecutivos en bloques físicos y envía comandos directos a los puertos del hardware.",
            "Reemplaza al driver del dispositivo para controlar los motores del disco magnético.",
        ],
        trap="En Screenshot 14 el estudiante marcó la traducción lógica→física (eso es del Módulo de Organización). La E/S lógica gestiona metadatos/FCB y registros.",
    ),
    _q(
        43,
        "mod3",
        3,
        "¿Qué función cumple el módulo de organización de archivos (supervisor básico de E/S)?",
        "Accede a la estructura de control del archivo para traducir bloques lógicos en bloques físicos, administra el espacio libre, planifica accesos a disco y asigna búferes de E/S en memoria.",
        "Conoce el método de asignación de bloques del archivo (contigua, enlazada, indexada) y coordina la asignación de bloques libres y búferes.",
        [
            "Únicamente verifica la contraseña del usuario que abre el archivo.",
            "Convierte el nombre de un directorio en un inodo y gestiona exclusivamente enlaces simbólicos.",
            "Ejecuta las instrucciones IN y OUT directamente sobre el controlador SATA.",
        ],
    ),
    _q(
        44,
        "mod3",
        3,
        "¿Para qué sirve la capa denominada sistema básico de archivos?",
        "Se encarga de emitir comandos genéricos al driver para colocar (leer/escribir) bloques físicos de datos entre el dispositivo y los búferes/cachés de la memoria principal.",
        "Opera exclusivamente con números de bloques físicos (sin conocer nombres ni estructuras de archivos) y administra la memoria intermedia y caché de bloques.",
        [
            "Se encarga de desfragmentar automáticamente los archivos en tiempo real para eliminar la fragmentación interna.",
            "Es la capa más cercana al usuario que traduce nombres de ruta a registros lógicos.",
            "Es el circuito electrónico soldado en el disco rígido que mueve el cabezal lector.",
        ],
    ),
    _q(
        45,
        "mod3",
        3,
        "¿Qué información se guarda en un Bloque de Control de Archivo (FCB / inodo en UNIX) y qué dato importante NO se guarda en el inodo?",
        "Guarda UID, GID, tipo de archivo, permisos, marcas de tiempo, tamaño, contador de enlaces y punteros a bloques de datos; NO guarda el nombre del archivo (que reside en la entrada de directorio).",
        "Al separar el nombre (en el directorio) de los metadatos (en el inodo), un mismo archivo puede tener múltiples enlaces duros con distintos nombres compartiendo exactamente el mismo inodo.",
        [
            "Guarda únicamente el nombre completo del archivo y su ruta absoluta; los permisos se guardan en el directorio.",
            "Almacena los primeros 4 KB del contenido del archivo y el nombre del usuario que lo ejecutó por última vez.",
            "Guarda el contenido completo de la tabla de páginas del proceso que lo creó.",
        ],
    ),
    _q(
        46,
        "mod3",
        3,
        "¿Qué información contiene el bloque de control de volumen (superbloque en UNIX) y qué contiene el bloque de control de arranque (Boot Control Block)?",
        "El superbloque guarda metadatos globales del SA (tamaño del volumen, tamaño/cantidad de bloques, bloques e inodos libres); el Boot Control Block contiene la información para iniciar un SO desde esa partición.",
        "Ambas son estructuras persistentes en disco por partición; el Boot Control Block puede estar vacío si la partición no contiene un sistema operativo arrancable.",
        [
            "El superbloque guarda los archivos abiertos por cada proceso en RAM; el Boot Control Block guarda las contraseñas de usuarios.",
            "El superbloque almacena únicamente la tabla de particiones físicas; el Boot Control Block almacena el directorio /tmp.",
            "Ambos almacenan copias idénticas de todos los archivos regulares para recuperación ante cortes eléctricos.",
        ],
    ),
    _q(
        47,
        "mod3",
        3,
        "¿Cuáles son las tablas principales que utiliza un sistema de archivos tipo UNIX para administrar archivos?",
        "Tabla de i-nodos en disco, tabla global de archivos abiertos en memoria, tabla de archivos abiertos por proceso y la tabla intermedia File.",
        "La tabla de inodos vive en disco (1 por partición); en RAM el kernel coordina la tabla por proceso → tabla File (puntero de posición y modo) → tabla global de inodos activos.",
        [
            "Una tabla FAT global, una tabla de segmentos y una tabla de páginas invertida.",
            "Una tabla independiente por cada archivo existente en el disco duro.",
            "Solo utiliza una lista enlazada dentro de los bloques de datos sin tablas en memoria.",
        ],
    ),
    _q(
        48,
        "mod3",
        3,
        "¿Para qué sirve la tabla global de archivos abiertos en memoria y cuántas existen?",
        "Sirve para mantener en RAM el control y los metadatos (FCB/inodo) de los archivos abiertos por uno o más procesos (con contador de aperturas); existe una única tabla por sistema.",
        "Centraliza los archivos actualmente abiertos evitando cargar copias duplicadas del mismo inodo en memoria cuando varios procesos abren el mismo archivo.",
        [
            "Lleva el control de los archivos abiertos por cada proceso individual; hay tantas como procesos activos.",
            "Asigna direcciones virtuales de RAM a cada archivo; hay tantas tablas como archivos en el disco.",
            "Registra los archivos abiertos por cada usuario; existe una tabla por cada cuenta de usuario.",
        ],
    ),
    _q(
        49,
        "mod3",
        3,
        "¿Cuántas instancias existen de la tabla de archivos en disco y cuántas de la tabla de archivos abiertos por proceso?",
        "Hay una tabla de archivos en disco (inodos) por cada partición con sistema de archivos, y una tabla de archivos abiertos por proceso por cada proceso en ejecución.",
        "Además, la información del puntero de posición actual de lectura/escritura del proceso se mantiene asociada a la apertura del proceso (tabla por proceso / tabla File), no en el inodo del disco.",
        [
            "Hay una sola tabla de archivos en disco para toda la computadora y una sola tabla de archivos abiertos compartida sin distinción por proceso.",
            "Hay una tabla de archivos en disco por cada directorio y una tabla por proceso por cada archivo abierto.",
            "Ambas residen permanentemente en disco y se crean únicamente cuando se formatea la partición.",
        ],
    ),
    _q(
        50,
        "mod3",
        3,
        "¿Qué problema resuelve el Sistema de Archivos Virtual (VFS / SAV) en kernels como UNIX/Linux?",
        "Expone una única interfaz uniforme de llamadas al sistema (open, read, write) y traduce dinámicamente cada operación al driver del sistema de archivos real montado (ext4, FAT32, NTFS, NFS) de forma transparente.",
        "Sin VFS, las aplicaciones deberían conocer qué SA tiene cada partición e invocar funciones específicas distintas (como open_fat32() u open_ntfs()).",
        [
            "Permite crear archivos que existen únicamente en el área de swap cuando el disco está lleno.",
            "Convierte automáticamente particiones FAT32 en ext4 sin necesidad de formatear el volumen.",
            "Elimina la necesidad de usar drivers de dispositivos de bloque en el kernel.",
        ],
    ),
    _q(
        51,
        "mod3",
        3,
        "En la implementación interna de directorios (§11.3), ¿cómo gestionan las búsquedas los sistemas ext3/ext4 de Linux?",
        "Usan una lista lineal para directorios pequeños y, cuando el directorio supera cierto tamaño, construyen automáticamente un índice hash para acelerar las búsquedas.",
        "La lista lineal es simple pero O(n) (o O(log n) con búsqueda binaria si se ordena); el índice hash reduce drásticamente el tiempo de búsqueda en directorios con miles de archivos.",
        [
            "Usan siempre búsqueda secuencial sobre una lista desordenada sin importar cuántos millones de archivos haya.",
            "Guardan cada directorio dentro de la tabla global FAT cargada al inicio de la RAM.",
            "Exigen que todos los nombres de archivo tengan exactamente 8 caracteres para indexarlos por tamaño.",
        ],
    ),
    _q(
        52,
        "mod3",
        3,
        "¿Qué diferencia hay entre sector y bloque (cluster) y por qué a veces conviene que el tamaño del bloque del SA sea grande?",
        "El sector (típicamente 512 B) es la unidad física del HDD, mientras que el bloque/cluster (ej. 4 KB = 8 sectores consecutivos) es la unidad mínima de asignación del SA; bloques grandes optimizan las E/S secuenciales amortizando el acceso a disco.",
        "Basado en el principio de localidad espacial, aprovechar un solo seek + rotación para leer 4 KB mejora mucho el rendimiento, aunque bloques demasiado grandes incrementan la fragmentación interna en archivos pequeños.",
        [
            "El sector es definido por el sistema de archivos (4 KB) y el cluster es fijado en fábrica (512 B); bloques grandes eliminan la fragmentación interna.",
            "No hay diferencia entre sector y bloque; bloques grandes reducen el tiempo de giro de los platos.",
            "Bloques grandes sirven únicamente para permitir más enlaces simbólicos dentro de un directorio.",
        ],
    ),
    _q(
        53,
        "mod3",
        3,
        "¿Qué ventajas y desventajas presenta el método de asignación contigua de bloques en disco?",
        "Ventajas: excelente rendimiento para acceso secuencial y acceso directo (basta calcular inicio + desplazamiento). Desventajas: produce fragmentación externa, exige pre-asignación y dificulta el crecimiento de archivos.",
        "Al estar todos los bloques uno al lado del otro, los saltos del cabezal son mínimos, pero cuando se crean y borran archivos de distinto tamaño aparecen huecos externos difíciles de aprovechar.",
        [
            "Ventaja: no tiene fragmentación externa ni requiere conocer el tamaño inicial. Desventaja: no soporta acceso directo.",
            "Ventaja: permite crecer indefinidamente el archivo sin moverlo. Desventaja: ocupa demasiados bloques índice.",
            "Ventaja: elimina por completo la fragmentación interna. Desventaja: solo funciona en cintas magnéticas.",
        ],
    ),
    _q(
        54,
        "mod3",
        3,
        "¿Qué ventajas y desventajas presenta el método de asignación enlazada de bloques?",
        "Ventajas: soporta asignación dinámica de bloques cuando se necesita y no sufre fragmentación externa. Desventajas: solo se adapta al acceso secuencial (pésimo para acceso directo), desperdicia espacio en punteros y es frágil ante punteros corruptos.",
        "Para leer el bloque n-ésimo en asignación enlazada pura hay que leer secuencialmente desde el primer bloque siguiendo los punteros de disco uno por uno.",
        [
            "Ventaja: sus punteros se calculan con funciones hash para acceso directo instantáneo. Desventaja: produce severa fragmentación externa.",
            "Ventaja: puede enlazar bloques de distintos sistemas operativos. Desventaja: requiere pre-asignación del tamaño máximo.",
            "Ventaja: permite acceso aleatorio en O(1) sin tablas en memoria. Desventaja: no permite que el archivo crezca.",
        ],
    ),
    _q(
        55,
        "mod3",
        3,
        "¿Qué ventajas y desventajas tiene un esquema de asignación basado en FAT (File Allocation Table)?",
        "Conserva las ventajas de la asignación enlazada (sin fragmentación externa) y mejora mucho el acceso directo al recorrer la cadena en una tabla en memoria, pero la tabla global debe cargarse en RAM y se vuelve enorme en particiones grandes.",
        "FAT saca el puntero del interior de cada bloque de datos y lo concentra en una tabla indexada por número de bloque al comienzo del volumen.",
        [
            "Utiliza inodos con punteros indirectos triples, por lo que no necesita ninguna tabla global.",
            "Elimina por completo la necesidad de memoria RAM para gestionar directorios y archivos abiertos.",
            "Permite enlaces duros nativos y ACL completas con cero fragmentación interna.",
        ],
    ),
    _q(
        56,
        "mod3",
        3,
        "¿Qué ventajas y desventajas tiene la asignación indexada y cómo la mejora UNIX en su inodo (esquema combinado)?",
        "La indexada elimina la fragmentación externa y soporta crecimiento dinámico y acceso directo, pero desperdicia un bloque índice en archivos chicos; UNIX lo mejora poniendo ~12 punteros directos en el propio inodo y agregando niveles indirectos (simple, doble, triple) solo si el archivo crece.",
        "De esta forma los archivos pequeños se acceden sin bloques índice adicionales y los archivos gigantes escalan dinámicamente mediante bloques indirectos.",
        [
            "La indexada solo permite acceso secuencial; UNIX la mejora reemplazando los punteros por una tabla FAT global.",
            "La indexada exige bloques contiguos; UNIX la mejora limitando todos los archivos a un máximo de 12 bloques.",
            "La indexada no tiene ninguna desventaja; UNIX simplemente copia todos los bloques en el directorio raíz.",
        ],
    ),
    _q(
        57,
        "mod3",
        3,
        "¿Qué diferencia fundamental existe entre un enlace duro (hard link) y un enlace simbólico (soft link), y qué comando los crea en Linux?",
        "El enlace duro es otra entrada de directorio con el mismo número de inodo que el original; el simbólico es un archivo especial aparte (con su propio inodo) que almacena la ruta hacia el destino. Ambos se crean con el comando 'ln' ('ln -s' para simbólico).",
        "Por su diseño, los enlaces duros no pueden cruzar particiones ni apuntar a directorios (salvo . y .. del SO), mientras que los simbólicos sí pueden cruzar SA y apuntar a directorios o destinos inexistentes.",
        [
            "Los enlaces duros son inmutables (solo lectura) y los simbólicos son modificables; se crean con 'ls' y 'stat'.",
            "Ambos crean una copia física duplicada de los datos del archivo; se crean con el comando 'cp'.",
            "Los enlaces simbólicos comparten el mismo inodo que el archivo original y solo funcionan dentro de la misma partición.",
        ],
    ),
    _q(
        58,
        "mod3",
        3,
        "¿Qué tamaño en bytes tiene un enlace simbólico y qué sucede en el TP11 cuando se crea 'dos' (duro) y 'tres' (simbólico) a 'uno' y luego se elimina 'uno' con 'rm uno'?",
        "El enlace simbólico tiene como tamaño la longitud en bytes de la ruta que contiene; al borrar 'uno', 'dos' NO desaparece (su link count baja de 2 a 1 y conserva los datos), mientras 'tres' queda como enlace roto.",
        "El contenido de un symlink es literalmente el texto de la ruta destino. En cambio, un archivo físico solo se libera en disco cuando su contador de enlaces duros llega a 0 (y ningún proceso lo tiene abierto).",
        [
            "El enlace simbólico tiene siempre tamaño 0 bytes; al borrar 'uno' desaparecen automáticamente tanto 'dos' como 'tres'.",
            "El enlace simbólico tiene el mismo tamaño que el archivo original; al borrar 'uno', 'tres' conserva los datos y 'dos' queda roto.",
            "El enlace simbólico mide siempre 4096 bytes; al borrar 'uno' el kernel prohíbe la operación hasta borrar 'tres'.",
        ],
    ),
    _q(
        59,
        "mod3",
        3,
        "En el TP11 de Sistemas de Archivos, ¿qué contienen un directorio en FAT32 vs. en ext2, y qué representan las entradas '.' y '..' dentro de cualquier subdirectorio en Linux?",
        "En FAT32 la entrada de directorio guarda metadatos y el primer cluster, mientras en ext2 guarda esencialmente nombre y número de inodo; '.' y '..' son enlaces duros creados por el SO hacia el propio directorio y hacia su padre (creando ciclos estructurales sin symlinks).",
        "Por eso al crear dos subdirectorios 'd1' y 'd2' dentro de 'ejemplo', el contador de enlaces (Links) de 'ejemplo' aumenta de 2 a 4 (por las entradas 'd1/..' y 'd2/..').",
        [
            "En ext2 el directorio guarda todos los permisos y bloques de datos; '.' y '..' son enlaces simbólicos vacíos creados por el usuario.",
            "En FAT32 el directorio guarda números de inodo; '.' apunta siempre a la raíz '/' y '..' apunta a '/home'.",
            "En ambos sistemas las entradas '.' y '..' son archivos regulares temporales de 0 bytes.",
        ],
    ),
    _q(
        60,
        "mod3",
        3,
        "¿Cómo puede un sistema de archivos recuperarse de forma consistente después de un fallo de alimentación eléctrica?",
        "Porque el sistema de archivos guarda periódicamente en el soporte (disco) las modificaciones de metadatos/archivos (y en SA modernos registra transacciones antes de aplicarlas mediante journaling).",
        "Al sincronizar periódicamente las estructuras en disco (o aplicar un registro de transacciones / log-structured / journaling), tras un corte eléctrico se puede verificar consistencia o reproducir/deshacer operaciones incompletas.",
        [
            "Porque todos los sistemas de archivos incluyen una batería interna en el controlador que mantiene la RAM encendida.",
            "Porque cada modificación en un archivo se envía obligatoriamente a un servidor remoto antes de escribir en RAM.",
            "Porque los sistemas de archivos nunca pierden consistencia al almacenar las tablas únicamente en registros de CPU.",
        ],
    ),
    # =========================================================================
    # MÓDULO 4: ALMACENAMIENTO MASIVO, DISCOS Y RAID (Cap. 12) -> topic_id = 7
    # =========================================================================
    _q(
        61,
        "mod4",
        7,
        "En un disco magnético (HDD), ¿a qué se denomina cilindro y cuáles son los dos componentes mecánicos que dominan el tiempo de acceso?",
        "Un cilindro es el conjunto de pistas concéntricas del mismo diámetro ubicadas en todos los platos del eje; el tiempo de acceso está dominado por el tiempo de búsqueda (seek) y la latencia rotacional.",
        "Mover el brazo mecánico hasta el cilindro destino (seek time) y esperar a que el sector deseado gire debajo del cabezal (latencia rotacional) toman milisegundos, mucho más que la transferencia en sí.",
        [
            "Un cilindro es un único sector de 512 bytes; el tiempo de acceso depende únicamente de la frecuencia de reloj de la CPU.",
            "Un cilindro es la placa controladora del disco; el tiempo de acceso está dominado por el tamaño de la caché L1.",
            "Un cilindro es la partición de swap; los discos magnéticos no poseen latencia rotacional porque giran a velocidad variable nula.",
        ],
    ),
    _q(
        62,
        "mod4",
        7,
        "¿Qué diferencia hay entre el formateo de bajo nivel (físico) y el de alto nivel (lógico), y qué partes componen estrictamente un sector?",
        "El formateo físico divide el disco en sectores (compuestos por cabecera, área de datos típicamente de 512 B y cola con código de corrección de errores ECC); el formateo lógico crea e inicializa el sistema de archivos (bloques/clusters y tablas) en una partición.",
        "Aunque coloquialmente decimos 'sector de 512 bytes' refiriéndonos solo a los datos, físicamente cada sector incluye cabecera (número de sector) y cola ECC grabadas en fábrica.",
        [
            "El formateo físico instala los directorios y el superbloque; el formateo lógico graba las pistas magnéticas en fábrica.",
            "El formateo físico divide el archivo en clusters de 4 KB; el sector solo contiene datos sin metadatos ni ECC.",
            "No existe diferencia: en ambos casos el usuario define la cantidad de platos del disco rígido.",
        ],
    ),
    _q(
        63,
        "mod4",
        7,
        "¿Qué es un bloque lógico de disco y a qué se denomina almacenamiento 'raw' (crudo)?",
        "El bloque lógico es la unidad mínima direccionable del disco (abstracción de matriz unidimensional de sectores tras el formateo físico); el almacenamiento raw consiste en usar una partición sin formatear con un sistema de archivos encima.",
        "La controladora oculta la geometría física exponiendo un vector lineal de bloques lógicos. Bases de datos especializadas o particiones de swap utilizan acceso raw para máxima velocidad.",
        [
            "El bloque lógico es el nombre de un directorio en UNIX; el almacenamiento raw es un archivo comprimido sin cifrar.",
            "El bloque lógico es la dirección física en RAM de un archivo abierto; el almacenamiento raw solo existe en cintas.",
            "El almacenamiento raw impide que cualquier programa o SO pueda leer o escribir en la partición.",
        ],
    ),
    _q(
        64,
        "mod4",
        7,
        "¿Cuáles son las diferencias técnicas clave entre un disco magnético (HDD) y una unidad de estado sólido (SSD / NVMe / Flash)?",
        "El SSD no tiene partes móviles (mucho más rápido, liviano, resistente a golpes y de menor consumo/latencia, trabajando con páginas ej. 8 KB), pero tiene mayor costo/GB, menor capacidad máxima y escrituras limitadas frente al HDD.",
        "Al carecer de brazos mecánicos y platos giratorios, el SSD elimina el seek time y la latencia rotacional, aunque sus celdas Flash sufren desgaste con ciclos repetidos de escritura.",
        [
            "El SSD tiene mayor capacidad y menor costo por GB que el HDD, pero sufre alta latencia rotacional.",
            "El HDD tiene un límite estricto de ciclos de escritura y no posee partes móviles.",
            "El SSD solo permite acceso estrictamente secuencial al igual que las cintas magnéticas.",
        ],
    ),
    _q(
        65,
        "mod4",
        7,
        "Según la clasificación de conexión de almacenamiento (§12.3), ¿qué diferencia existe entre DAS (Host-attached), NAS y SAN?",
        "DAS conecta discos localmente por puertos (SATA/USB/SAS) exponiendo dispositivos; NAS opera sobre una red de datos general (Ethernet, NFS/SMB) exponiendo archivos; SAN usa una red dedicada exclusivamente a almacenamiento (FC/InfiniBand) exponiendo dispositivos/bloques.",
        "Un punto clave de cátedra: en DAS y SAN el host ve dispositivos de bloque (puede particionar y formatear); en NAS el host ve archivos compartidos como si fueran locales.",
        [
            "NAS utiliza una red exclusiva dedicada a almacenamiento exponiendo bloques crudos; SAN opera sobre Wi-Fi compartida exponiendo archivos.",
            "DAS y NAS exponen únicamente archivos y nunca permiten particionar; SAN solo admite discos ópticos.",
            "NAS y SAN son exactamente sinónimos y ambos utilizan exclusivamente cables paralelos IDE.",
        ],
        trap="Clave de parcial: NAS = red general → expone ARCHIVOS. SAN = red dedicada → expone DISPOSITIVOS (se pueden particionar y formatear).",
    ),
    _q(
        66,
        "mod4",
        7,
        "¿A qué se denomina almacenamiento terciario y qué características distinguen a los medios ópticos y las cintas magnéticas?",
        "Son medios de almacenamiento extraíbles (y bibliotecas/silos automáticos) orientados a respaldo masivo y archivo: los ópticos (CD/DVD/BR, a menudo WORM) conservan datos por mucho tiempo, y las cintas son muy baratas/confiables pero de acceso estrictamente secuencial.",
        "El almacenamiento terciario ofrece altísima capacidad a bajo costo/GB a cambio de tiempos de acceso mucho mayores que el almacenamiento secundario.",
        [
            "Son los discos que pertenecen a terceros en la nube y nunca pueden retirarse del servidor.",
            "Son las memorias caché L3 dentro del procesador destinadas a acelerar la memoria virtual.",
            "Son unidades SSD NVMe conectadas por PCIe con acceso aleatorio en nanosegundos.",
        ],
    ),
    _q(
        67,
        "mod4",
        7,
        "¿Por qué es necesario planificar las peticiones de disco y en qué medios resulta adecuado usar el algoritmo FCFS ('noop' en Linux)?",
        "Es necesario porque la CPU genera peticiones más rápido de lo que el HDD puede atenderlas y reordenarlas minimiza el tiempo de búsqueda mecánico; FCFS ('noop') es justo y resulta ideal para SSD (sin brazo mecánico) o cintas magnéticas.",
        "En un SSD no existe movimiento físico de cabezal ni latencia rotacional, por lo que reordenar peticiones por número de cilindro no aporta beneficio mecánico.",
        [
            "Es necesario para reducir la fragmentación interna de los archivos; FCFS es el algoritmo más rápido en discos HDD con alta carga.",
            "FCFS garantiza el menor movimiento total del brazo en discos magnéticos saturados.",
            "Solo se planifican discos porque ningún otro dispositivo de E/S (como red o impresora) utiliza colas.",
        ],
    ),
    _q(
        68,
        "mod4",
        7,
        "¿Cómo funciona el algoritmo de planificación de disco SSTF (Shortest Seek Time First) y qué riesgo presenta?",
        "Selecciona siempre la petición pendiente cuyo cilindro esté más cercano a la posición actual del cabezal; mejora mucho el rendimiento respecto de FCFS, pero puede provocar inanición a las peticiones en los extremos.",
        "Si llegan continuamente solicitudes cerca de los cilindros centrales, una solicitud en un extremo del disco puede quedar postergada indefinidamente (análogo a SJF en planificación de CPU).",
        [
            "Atiende las peticiones estrictamente en el orden en que llegaron a la cola, por lo que nunca causa inanición.",
            "Mueve el brazo siempre de extremo a extremo del disco en un único sentido circular.",
            "Elige primero la petición que lleva más tiempo esperando en la cola para garantizar equidad absoluta.",
        ],
    ),
    _q(
        69,
        "mod4",
        7,
        "¿Qué diferencia a LOOK y C-LOOK de SCAN y C-SCAN en la planificación de disco?",
        "SCAN y C-SCAN obligan al cabezal a viajar hasta los extremos físicos del disco aunque no haya peticiones allí; LOOK y C-LOOK invierten o retornan desde la última petición pendiente en esa dirección, y C-LOOK además brinda tiempos de espera más uniformes al servir en un solo sentido.",
        "Por esta razón SCAN y C-SCAN puros casi no se implementan en la práctica, prefiriéndose LOOK y C-LOOK (que evitan desplazamientos innecesarios y eliminan la inanición).",
        [
            "LOOK y C-LOOK sufren inanición en los extremos, mientras que SCAN y C-SCAN no la evitan.",
            "C-LOOK atiende peticiones tanto en la ida como en la vuelta, mientras que LOOK solo atiende en un sentido.",
            "SCAN y C-SCAN se utilizan únicamente en unidades SSD NVMe.",
        ],
    ),
    _q(
        70,
        "mod4",
        7,
        "¿Cómo influye el método de asignación de archivos (Cap. 11) en el rendimiento de la planificación de disco (§12.4.6)?",
        "Un archivo con asignación contigua genera peticiones en bloques adyacentes (mínimo movimiento de cabezal), mientras que un archivo fragmentado con asignación enlazada o indexada dispersa las peticiones por todo el disco, haciendo la planificación mucho más crítica.",
        "Además influyen la ubicación de metadatos (directorios e inodos) y la prioridad que el SO da a operaciones críticas como la paginación bajo demanda.",
        [
            "No influye en absoluto, porque todos los métodos de asignación colocan siempre los bloques de un archivo en el mismo cilindro.",
            "La asignación enlazada produce menos movimientos de brazo que la asignación contigua en accesos secuenciales.",
            "La asignación contigua impide utilizar algoritmos como LOOK o C-LOOK.",
        ],
    ),
    _q(
        71,
        "mod4",
        7,
        "¿Qué ventajas aportan las estructuras RAID y por qué se utiliza redundancia si reduce el espacio útil disponible?",
        "Agrupan varios discos como una sola unidad lógica para aumentar capacidad, mejorar la tasa de transferencia por paralelismo y brindar tolerancia a fallos; la redundancia es imprescindible para recuperar los datos cuando falla un disco.",
        "RAID (Redundant Array of Independent Disks) puede implementarse por hardware o software (ej. Linux MD) y utilizarse en DAS, NAS o SAN.",
        [
            "La redundancia sirve únicamente para duplicar la velocidad de escritura y nunca interviene en la recuperación de datos.",
            "RAID aumenta siempre el espacio útil por encima de la suma física de los discos gracias a compresión por hardware.",
            "RAID solo puede implementarse mediante tarjetas hardware y exclusivamente con discos HDD mecánicos.",
        ],
    ),
    _q(
        72,
        "mod4",
        7,
        "¿Cuáles son las características principales de RAID 0 (Striping) y en qué caso se justifica usarlo?",
        "Divide los datos en bandas entre 2 o más discos aprovechando el 100% del espacio y maximizando el rendimiento por paralelismo, pero NO ofrece redundancia (la pérdida de 1 disco implica pérdida total); solo conviene para datos temporales o no críticos.",
        "Al no duplicar ni calcular paridad, cualquier falla individual destruye el volumen lógico completo.",
        [
            "Aprovecha el 50% del espacio y tolera la falla de hasta la mitad de los discos.",
            "Utiliza paridad distribuida requiriendo un mínimo de 3 discos para tolerar 1 fallo.",
            "Es el nivel recomendado para bases de datos críticas porque ofrece máxima tolerancia a fallos.",
        ],
    ),
    _q(
        73,
        "mod4",
        7,
        "¿Cómo se comparan RAID 1 (Mirroring) y RAID 1+0 (RAID 10) en cuanto a mínimo de discos, espacio efectivo y características?",
        "RAID 1 espeja datos (mínimo 2 discos, espacio útil 1/n = 50% con 2 discos, alta redundancia); RAID 1+0 combina espejado + striping (mínimo 4 discos en HW, 50% útil, suma redundancia de RAID 1 y rendimiento de RAID 0; por software con Linux MD puede armarse desde 2 discos).",
        "RAID 10 ofrece un excelente equilibrio de rendimiento y tolerancia a fallos a costa de sacrificar la mitad de la capacidad bruta.",
        [
            "RAID 1 aprovecha el 100% del espacio en disco y RAID 1+0 no provee redundancia.",
            "RAID 1+0 requiere como mínimo 3 discos y utiliza paridad distribuida XOR.",
            "RAID 1 solo puede configurarse por software y no tolera la caída de ningún disco.",
        ],
    ),
    _q(
        74,
        "mod4",
        7,
        "¿Cómo funciona RAID 5 (Paridad distribuida) respecto a cantidad mínima de discos, espacio efectivo y tolerancia a fallos?",
        "Combina striping con un bloque de paridad distribuido rotativamente entre todos los discos: requiere un mínimo de 3 discos, ofrece un espacio efectivo de N-1 discos (≥ 66,7%) y tolera la pérdida de 1 disco cualquiera.",
        "Distribuir la paridad entre todos los discos evita el cuello de botella que sufriría un único disco de paridad dedicado (como en RAID 4).",
        [
            "Requiere mínimo 2 discos, aprovecha el 50% del espacio y tolera la falla simultánea de todos menos un disco.",
            "Concentra toda la paridad en un único disco dedicado, lo que permite aprovechar el 100% de los discos de datos.",
            "Requiere mínimo 4 discos y no permite recuperar datos si falla el disco que contiene el superbloque.",
        ],
    ),
    # =========================================================================
    # MÓDULO 5: SISTEMAS DE E/S Y PUERTOS (Cap. 13 + TP10) -> topic_id = 7
    # =========================================================================
    _q(
        75,
        "mod5",
        7,
        "¿Cuál es la función de los drivers o controladores de dispositivos (software) y en qué se diferencian de la placa controladora?",
        "El driver es el módulo de software del kernel responsable de iniciar y procesar la finalización de las solicitudes de E/S ofreciendo una interfaz uniforme; la placa controladora es el circuito electrónico (hardware) que opera directamente al periférico.",
        "Esta distinción es clave en cátedra: el driver abstrae los detalles específicos de la placa controladora para que el resto del SO sea independiente del hardware.",
        [
            "Los drivers son dispositivos físicos que controlan a otros dispositivos como la DMA.",
            "El driver se encarga de asignar bloques de disco a los archivos del usuario y la placa controladora planifica la CPU.",
            "No existe diferencia: ambos términos se refieren exclusivamente a los cables del bus de datos.",
        ],
    ),
    _q(
        76,
        "mod5",
        7,
        "Según el TP de Puertos de Entrada/Salida, ¿qué son los puertos de E/S, dónde se encuentran físicamente y cuáles son los tres tipos básicos de registros?",
        "Son registros de memoria ubicados físicamente EN EL DISPOSITIVO de E/S (placa controladora) a través de los cuales la CPU intercambia mensajes; los básicos son control, estado y datos.",
        "Cada puerto posee una dirección (por ejemplo 0x320 control, 0x321 estado y 0x322 datos para el controlador de disco) que la CPU selecciona para comandar el periférico.",
        [
            "Son celdas reservadas dentro de la memoria RAM principal donde el compilador guarda variables globales.",
            "Son archivos regulares del directorio /home que almacenan la velocidad de transferencia de cada disco.",
            "Son registros internos de la ALU de la CPU que se utilizan únicamente para saltos incondicionales.",
        ],
    ),
    _q(
        77,
        "mod5",
        7,
        "¿Qué diferencia existe entre la E/S mapeada en memoria y la E/S dedicada (directa), y qué restricción tienen las instrucciones IN/OUT en x86 según el TP10?",
        "La E/S mapeada usa las mismas instrucciones que la RAM (ej. MOV) compartiendo su espacio de direcciones; la E/S dedicada usa instrucciones especiales (IN/OUT) en un espacio separado y en x86 no admite direccionamiento inmediato del dato (exige cargar primero en registros como AL y DX).",
        "En el TP10 se ve que para E/S mapeada alcanza con 'MOV 0x322, 0d500', mientras que con E/S dedicada hay que cargar AL y DX antes de ejecutar 'OUT dx, al'.",
        [
            "La E/S mapeada utiliza las instrucciones IN/OUT y la E/S dedicada utiliza la instrucción MOV con direccionamiento inmediato.",
            "En la E/S mapeada en memoria los registros del dispositivo están físicamente fabricados dentro de los módulos de RAM.",
            "La E/S dedicada no requiere privilegios de kernel, mientras que la E/S mapeada solo existe en discos ópticos.",
        ],
    ),
    _q(
        78,
        "mod5",
        7,
        "¿Qué dispositivo de una PC x86 utiliza simultáneamente E/S dedicada y E/S mapeada en memoria?",
        "La tarjeta gráfica (controladora de video): usa puertos de E/S dedicada (ej. 0x3D0–0x3DF) para registros de control y E/S mapeada en memoria para transferir grandes volúmenes de píxeles al framebuffer.",
        "Combinar ambos mecanismos permite configuración simple por puertos y transferencia masiva de alta velocidad mediante operaciones estándar de memoria.",
        [
            "El teclado PS/2, que mapea todo un framebuffer de gigabytes en memoria principal.",
            "El temporizador del sistema (timer), que requiere transferir bloques de video por DMA.",
            "Ningún dispositivo puede utilizar ambos mecanismos simultáneamente en arquitectura x86.",
        ],
    ),
    _q(
        79,
        "mod5",
        7,
        "En el ejemplo de lectura del sector 500 del TP de Puertos de E/S, ¿qué ocurriría si invirtiéramos el orden de las dos primeras instrucciones (escribir primero en el puerto de control 0x320 y luego el sector 500 en el puerto de datos 0x322)?",
        "El disco iniciaría inmediatamente la lectura usando el valor anterior/basura presente en el registro de datos 0x322 antes de recibir el 500, leyendo un sector erróneo o corrompiendo la operación.",
        "El bit de inicio en el registro de control dispara la acción del hardware; todos los parámetros previos (como el número de sector) deben estar cargados antes de activar la orden.",
        [
            "No ocurriría ningún problema porque la controladora siempre espera a que termine todo el programa antes de leer el registro de control.",
            "La CPU detectaría automáticamente la inversión y reordenaría los puertos de E/S.",
            "El disco escribiría el número 500 dentro del sector 0 en lugar de realizar una lectura.",
        ],
    ),
    _q(
        80,
        "mod5",
        7,
        "En el código assembler del TP10 ('CONTROLAR: MOV al, 0x321 / SUB al, 0b0000_0001 / JNZ CONTROLAR'), ¿cómo se llama este método de E/S y qué tipo de instrucción es JNZ?",
        "Se llama E/S programada (sondeo o polling / espera activa), y JNZ ('Jump if Not Zero') es una instrucción de salto condicional que evalúa la bandera de cero (ZF).",
        "Mientras el bit de estado listo no sea 1, la resta no da cero (ZF = 0) y JNZ vuelve a CONTROLAR, manteniendo a la CPU girando en vacío hasta que el dispositivo termine.",
        [
            "Se llama E/S por DMA, y JNZ es un salto incondicional que siempre vuelve al inicio del programa.",
            "Se llama E/S dirigida por interrupciones, y JNZ bloquea el proceso en estado S sin consumir CPU.",
            "Se llama spooling, y JNZ es una instrucción privilegiada exclusiva para escribir en discos SATA.",
        ],
    ),
    _q(
        81,
        "mod5",
        7,
        "¿Cuál es la principal desventaja de la E/S programada (sondeo/polling) frente a la E/S por interrupciones, y en qué caso particular puede justificarse el sondeo?",
        "En dispositivos lentos el sondeo desperdicia el 100% de la CPU esperando (mientras las interrupciones la liberan para otros procesos); el sondeo solo se justifica en dispositivos ultrarrápidos donde la espera es menor que el costo de atender una interrupción.",
        "Por ejemplo, esperar nanosegundos puede costar menos ciclos que guardar contexto, saltar a una rutina de interrupción y restaurar contexto.",
        [
            "El sondeo impide leer registros de estado; las interrupciones solo sirven para discos de gran capacidad.",
            "Las interrupciones consumen 100% de la CPU en espera activa, mientras que el sondeo bloquea al proceso sin usar CPU.",
            "El sondeo se justifica especialmente en impresoras y cintas magnéticas por su alta velocidad mecánica.",
        ],
    ),
    _q(
        82,
        "mod5",
        7,
        "¿Cómo funciona la E/S mediante DMA (Acceso Directo a Memoria), qué es el 'robo de ciclos' y cuándo se justifica utilizarla?",
        "La CPU configura al controlador DMA y este transfiere bloques enteros directo entre dispositivo y RAM tomando el bus temporalmente ('robo de ciclos'), emitiendo una sola interrupción al finalizar; se justifica en transferencias grandes de datos (discos, red).",
        "DMA evita interrumpir a la CPU por cada byte transferido, liberándola casi por completo durante transferencias masivas.",
        [
            "En DMA la CPU copia manualmente cada byte en un bucle rápido; el robo de ciclos ocurre cuando un proceso roba quantum de otro.",
            "DMA se justifica únicamente para transferencias de 1 byte desde el teclado sin generar interrupciones.",
            "El robo de ciclos consiste en desactivar las interrupciones del reloj mientras se ejecuta un programa de usuario.",
        ],
    ),
    _q(
        83,
        "mod5",
        7,
        "¿Por qué las operaciones de E/S deben ejecutarse en modo privilegiado (modo kernel)?",
        "Porque los dispositivos de E/S son recursos compartidos/públicos del sistema que deben ser controlados y protegidos exclusivamente por el SO para evitar accesos no autorizados o corrupción de datos.",
        "Los procesos de usuario siempre solicitan E/S mediante llamadas al sistema (syscalls) que el kernel valida antes de acceder a los puertos o controladores.",
        [
            "Porque las instrucciones de lectura de RAM solo funcionan en modo usuario y las de disco solo en modo protegido.",
            "Para evitar que los procesos de usuario puedan utilizar memoria caché.",
            "Porque los drivers de dispositivo están escritos exclusivamente en lenguaje de alto nivel fuera del kernel.",
        ],
    ),
    _q(
        84,
        "mod5",
        7,
        "¿Qué diferencia existe entre dispositivos orientados a bloque vs. a carácter, y entre dispositivos compartibles vs. dedicados?",
        "Los de bloque transfieren bloques direccionables de tamaño fijo (ej. HDD/SSD) y los de carácter flujos de bytes sin direccionamiento (ej. teclado/puerto serie); los compartibles atienden múltiples procesos concurrentes (disco) y los dedicados exigen exclusión mutua (impresora, cinta).",
        "La categorización permite al subsistema de E/S ofrecer interfaces y políticas adecuadas a cada clase de periférico.",
        [
            "Los de carácter siempre usan acceso aleatorio por cilindro y los de bloque solo permiten lectura secuencial.",
            "Los dispositivos dedicados son aquellos que pueden mezclar salidas de varios procesos al mismo tiempo.",
            "Los discos magnéticos son dispositivos dedicados de carácter y las impresoras son compartibles de bloque.",
        ],
    ),
    _q(
        85,
        "mod5",
        7,
        "¿Para qué sirve la llamada al sistema ioctl() en UNIX/Linux y cuáles son sus tres parámetros?",
        "Actúa como 'válvula de escape' para enviar comandos de control específicos de un dispositivo que no encajan en read/write; recibe (1) descriptor de archivo fd, (2) código de comando/request y (3) puntero a argumentos/estructura de datos.",
        "Permite configurar parámetros particulares del hardware (como velocidad en baudios de un puerto serie, expulsar una bandeja o consultar geometría de disco) sin crear decenas de syscalls nuevas.",
        [
            "Sirve únicamente para leer bloques de 4 KB desde particiones ext4; recibe ruta, tamaño y permisos.",
            "Sirve para desactivar las interrupciones del procesador; recibe PID, señal y prioridad.",
            "Sirve para crear enlaces simbólicos entre dispositivos; recibe origen, destino y número de inodo.",
        ],
    ),
    _q(
        86,
        "mod5",
        7,
        "¿Es lo mismo E/S asíncrona que E/S no bloqueante (§13.3.4)? ¿Cómo se diferencian de la E/S bloqueante (síncrona)?",
        "No son lo mismo: la bloqueante suspende al proceso hasta completar la E/S; la no bloqueante retorna de inmediato con los bytes disponibles en ese instante (aunque sean 0); la asíncrona lanza la operación completa en segundo plano mientras el proceso sigue corriendo y le avisa al finalizar.",
        "Esta distinción fue destacada expresamente en las diapositivas de cátedra: no bloqueante = 'dame lo que haya ya'; asíncrona = 'iniciá toda la transferencia y avisame cuando termine'.",
        [
            "Sí, asíncrona y no bloqueante son exactamente sinónimos y ambas suspenden al proceso hasta completar la transferencia.",
            "La E/S bloqueante permite que el proceso siga ejecutando instrucciones mientras el kernel lee el disco.",
            "La E/S asíncrona solo existe en dispositivos orientados a carácter y nunca notifica su finalización.",
        ],
    ),
    _q(
        87,
        "mod5",
        7,
        "¿Para qué se utiliza el buffering en el subsistema de E/S y cuál es su diferencia fundamental respecto del caching?",
        "El buffering adapta diferencias de velocidad y de tamaño de transferencia y preserva la semántica de copia (puede contener la única copia de datos en tránsito); el caching mantiene una copia adicional en memoria rápida de datos que ya existen en otro soporte para acelerar futuros accesos.",
        "La caché se apoya en el principio de localidad y retiene los datos tras una lectura; un búfer suele descartar los datos una vez entregados al consumidor.",
        [
            "El búfer se almacena siempre en disco y la caché siempre en registros de puertos de E/S.",
            "No hay diferencia: ambos eliminan los datos inmediatamente después de la primera lectura.",
            "El caching sirve únicamente para garantizar semántica de copia en escrituras de red.",
        ],
    ),
    _q(
        88,
        "mod5",
        7,
        "¿Para qué sirve la técnica de spooling (§13.4.4) y cómo debe responder el subsistema de E/S ante errores transitorios vs. permanentes (§13.4.5)?",
        "El spooling encola en disco las salidas concurrentes destinadas a dispositivos dedicados (como impresoras) para enviarlas de a una sin mezclarlas; ante errores transitorios el SO reintenta recuperarse, y ante errores permanentes aísla el fallo e informa códigos de error a la aplicación sin derribar el sistema.",
        "Solo fallos críticos (como perder acceso al área de swap o al disco raíz) resultan irrecuperables para el SO.",
        [
            "El spooling permite que dos documentos se impriman intercalados línea por línea; ante cualquier error transitorio de E/S el SO reinicia la máquina.",
            "El spooling reemplaza a la memoria virtual cuando no hay swap; los errores permanentes nunca se informan a las aplicaciones.",
            "El spooling acelera exclusivamente los accesos aleatorios a bases de datos mediante tablas hash.",
        ],
    ),
]


def normalize_text(text: str) -> str:
    """Normalize text for duplicate checking."""
    text = text.lower().strip()
    text = re.sub(r"[¿?¡!.,;:()\[\]\"'\-]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def render_obsidian_bank(questions: list[dict[str, Any]]) -> str:
    """Render the synchronized Obsidian interactive Multiple Choice bank."""
    letters = ["A", "B", "C", "D"]
    lines: list[str] = [
        "# Banco de Preguntas - Multiple Choice (Cuarto Parcial)",
        "",
        "> **Materia**: Sistemas Operativos (UTN FRT)  ",
        "> **Origen**: Preguntas reales de parciales/cátedra filtradas al alcance actual + ejercicios de TPs, sincronizadas con `Sistemas Operativos.json` y la app de práctica (`Parcial 4`).  ",
        "> **Temas Evaluados**: Memoria Virtual y Swap (Cap. 9 + §12.6 + TP9), Interfaz del Sistema de Archivos (Cap. 10), Implementación de Sistemas de Archivos (Cap. 11 + TP11), Almacenamiento Masivo, Planificación de Disco y RAID (Cap. 12), Sistemas de E/S y Puertos (Cap. 13 + TP10).  ",
        "> **Modo de Estudio**: Cada pregunta es una tarjeta interactiva con spoiler desplegable. Respondé mentalmente antes de abrir la justificación.",
        "",
        "> [!TIP] Blueprint de Evaluación para Simulacros (configurado en la app para Parcial 4)",
        "> - **Memoria Virtual y Swap (`memory` — Cap. 9 + TP9)**: 25% (2–3 preguntas en simulacro de 10)",
        "> - **Sistemas de Archivos (`files` — Caps. 10–11 + TP11)**: 45% (4–5 preguntas en simulacro de 10)",
        "> - **Almacenamiento Masivo y E/S (`io` — Caps. 12–13 + TP10)**: 30% (3 preguntas en simulacro de 10)",
        "",
        "> [!NOTE] Alcance Estricto",
        "> Las preguntas históricas sobre **Seguridad y Protección (Caps. 14–15)**, **Virtualización** y **Sistemas Distribuidos** fueron excluidas deliberadamente para ajustarse al temario exacto del Cuarto Parcial (Capítulos 9 al 13).",
        "",
        "---",
        "",
    ]

    by_module: dict[str, list[dict[str, Any]]] = {key: [] for key, _ in MODULES}
    for q in questions:
        by_module[q["module"]].append(q)

    for mod_key, mod_title in MODULES:
        mod_qs = by_module[mod_key]
        lines.append(f"## {mod_title} ({len(mod_qs)} preguntas)")
        lines.append("")
        for q in mod_qs:
            lines.append(f"### Pregunta {q['id']}")
            lines.append(f"**{q['question_text']}**")
            lines.append("")
            correct_letter = ""
            correct_text = ""
            correct_expl = ""
            for idx, opt in enumerate(q["options"]):
                letter = letters[idx]
                lines.append(f"- [ ] {letter}) {opt['text']}")
                if opt["type"] == "correct":
                    correct_letter = letter
                    correct_text = opt["text"]
                    correct_expl = opt["explanation"] or ""
            lines.append("")
            lines.append("<details>")
            lines.append(
                "<summary><b>🔍 Ver Respuesta Correcta y Justificación</b></summary>"
            )
            lines.append("")
            lines.append(f"**Respuesta Correcta: {correct_letter}) {correct_text}**")
            lines.append("")
            lines.append("**Justificación Técnica**:  ")
            lines.append(correct_expl)
            if q.get("trap"):
                lines.append("")
                lines.append("> [!WARNING] Trampa de Examen")
                lines.append(f"> {q['trap']}")
            lines.append("</details>")
            lines.append("")
            lines.append("---")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


async def main() -> None:
    print("=" * 65)
    print("IMPORT PARCIAL 4 QUESTIONS (CAPS 9-13 + TPs) & SYNC OBSIDIAN")
    print("=" * 65)

    # 1. Self-check: ensure internal uniqueness and 4 options (1 correct) per question
    seen_norm: dict[str, int] = {}
    for q in RAW_QUESTIONS:
        assert len(q["options"]) == 4, f"Q{q['id']} must have 4 options"
        correct_opts = [o for o in q["options"] if o["type"] == "correct"]
        assert len(correct_opts) == 1, f"Q{q['id']} must have exactly 1 correct option"
        assert correct_opts[0]["explanation"], f"Q{q['id']} missing explanation"
        norm = normalize_text(q["question_text"])
        if norm in seen_norm:
            raise ValueError(
                f"Duplicate internal question Q{q['id']} vs Q{seen_norm[norm]}"
            )
        seen_norm[norm] = q["id"]

    # 2. Backup database.db before modifying
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DB_PATH.with_name(f"{DB_PATH.name}.bak_parcial4_{ts}")
    shutil.copy2(DB_PATH, backup_path)
    print(f"Created DB backup: {backup_path}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    # Locate or verify Parcial 4 exam row (partial_number = 4)
    exam_row = cur.execute(
        "SELECT id, partial_number, exam_date FROM exams WHERE partial_number = 4 ORDER BY id LIMIT 1"
    ).fetchone()
    if exam_row is None:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
        cur.execute(
            """
            INSERT INTO exams (partial_number, exam_date, topic_tags, created_at, updated_at, uuid, subject_id)
            VALUES (4, NULL, 'memoria-virtual,sistemas-de-archivos,almacenamiento-masivo,entrada-salida', ?, ?, ?, 1)
            """,
            (now_str, now_str, str(uuid.uuid4())),
        )
        exam_id = int(cur.lastrowid)
        print(f"Created new Exam row for Parcial 4: exam_id={exam_id}")
    else:
        exam_id = int(exam_row[0])
        print(
            f"Found existing Exam row for Parcial 4: exam_id={exam_id} (date={exam_row[2]})"
        )

    # Update topic_tags on Parcial 4 exam for clarity
    cur.execute(
        "UPDATE exams SET topic_tags = ? WHERE id = ?",
        (
            "memoria-virtual,sistemas-de-archivos,almacenamiento-masivo,entrada-salida",
            exam_id,
        ),
    )

    initial_q_count = cur.execute("SELECT count(*) FROM questions").fetchone()[0]
    initial_a_count = cur.execute("SELECT count(*) FROM answers").fetchone()[0]

    # Check existing questions in exam_id=4 for idempotent re-runs
    existing_in_exam4 = [
        (r[0], normalize_text(r[1]))
        for r in cur.execute(
            "SELECT id, question_text FROM questions WHERE exam_id = ?", (exam_id,)
        ).fetchall()
    ]
    existing_in_other = [
        (r[0], r[1], normalize_text(r[2]))
        for r in cur.execute(
            "SELECT id, exam_id, question_text FROM questions WHERE exam_id != ?",
            (exam_id,),
        ).fetchall()
    ]

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
    inserted_questions = 0
    inserted_answers = 0
    skipped_duplicates = 0

    for q in RAW_QUESTIONS:
        norm_new = normalize_text(q["question_text"])

        # Skip if already present in exam 4
        if any(
            difflib.SequenceMatcher(None, norm_new, ex_norm).ratio() >= 0.90
            for _, ex_norm in existing_in_exam4
        ):
            skipped_duplicates += 1
            continue

        # Warn (do not block) if similar to another exam
        for ex_id, ex_exam, ex_norm in existing_in_other:
            ratio = difflib.SequenceMatcher(None, norm_new, ex_norm).ratio()
            if ratio >= 0.85:
                print(
                    f"  [NOTE] Q{q['id']} resembles exam {ex_exam} Q{ex_id} (sim={ratio:.2f})"
                )

        q_uuid = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO questions (
                exam_id, image_id, question_text, extracted_text,
                confidence_score, order_in_exam, is_corrected,
                correction_notes, has_code_in_answers, created_at,
                updated_at, uuid, topic_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                exam_id,
                None,
                q["question_text"],
                q["question_text"],
                1.0,
                None,
                1,
                None,
                0,
                now_str,
                now_str,
                q_uuid,
                q["topic_id"],
            ),
        )
        new_qid = cur.lastrowid
        inserted_questions += 1

        for idx, opt in enumerate(q["options"], start=1):
            cur.execute(
                """
                INSERT INTO answers (
                    question_id, answer_text, answer_type,
                    is_common_misconception, explanation,
                    display_order, created_at, updated_at, uuid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_qid,
                    opt["text"],
                    opt["type"],
                    0,
                    opt["explanation"],
                    idx,
                    now_str,
                    now_str,
                    str(uuid.uuid4()),
                ),
            )
            inserted_answers += 1

    # Verify SQLite Integrity BEFORE committing
    fk_errors = cur.execute("PRAGMA foreign_key_check;").fetchall()
    if fk_errors:
        conn.rollback()
        raise RuntimeError(f"Foreign key errors detected: {fk_errors}")

    integrity = cur.execute("PRAGMA integrity_check;").fetchone()[0]
    if integrity != "ok":
        conn.rollback()
        raise RuntimeError(f"Integrity check failed: {integrity}")

    conn.commit()

    final_q_count = cur.execute("SELECT count(*) FROM questions").fetchone()[0]
    final_a_count = cur.execute("SELECT count(*) FROM answers").fetchone()[0]

    print(
        f"Inserted: {inserted_questions} questions, {inserted_answers} answers "
        f"(skipped duplicates: {skipped_duplicates})"
    )
    print(f"PRAGMA foreign_key_check: OK | PRAGMA integrity_check: {integrity}")
    print(
        f"Total DB counts -> Questions: {final_q_count} (was {initial_q_count}), "
        f"Answers: {final_a_count} (was {initial_a_count})"
    )

    print("\nBreakdown by Exam:")
    for row in cur.execute(
        """
        SELECT e.id, e.partial_number, count(q.id)
        FROM exams e LEFT JOIN questions q ON q.exam_id = e.id
        GROUP BY e.id, e.partial_number ORDER BY e.id
        """
    ).fetchall():
        print(f"  Exam {row[0]} (Parcial {row[1]}): {row[2]} questions")

    print(f"\nTopic Breakdown for Parcial 4 (exam_id={exam_id}):")
    for row in cur.execute(
        """
        SELECT t.id, t.slug, t.name, count(q.id)
        FROM questions q JOIN topics t ON q.topic_id = t.id
        WHERE q.exam_id = ?
        GROUP BY t.id, t.slug, t.name ORDER BY t.id
        """,
        (exam_id,),
    ).fetchall():
        print(f"  Topic {row[0]} ({row[1]} - {row[2]}): {row[3]} questions")

    conn.close()

    # 3. Sync Docker DB copy
    shutil.copy2(DB_PATH, DOCKER_DB_PATH)
    print(f"\nSynced DB to {DOCKER_DB_PATH}")

    # 4. Export full JSON via JsonIOService and validate against ExportFileSchema
    from app.db.session import AsyncSessionLocal
    from app.schemas.json_io import ExportFileSchema
    from app.services.json_io_service import JsonIOService

    async with AsyncSessionLocal() as session:
        service = JsonIOService(session)
        export_data = await service.export_full_db()
        dumped = export_data.model_dump(mode="json")

        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(dumped, f, indent=2, ensure_ascii=False)
            f.write("\n")

        validated = ExportFileSchema.model_validate(dumped)
        print(
            f"Exported & validated {len(validated.questions)} questions to {JSON_PATH}"
        )

    # 5. Render synchronized Obsidian Question Bank
    md_content = render_obsidian_bank(RAW_QUESTIONS)
    OBSIDIAN_BANK_PATH.parent.mkdir(parents=True, exist_ok=True)
    OBSIDIAN_BANK_PATH.write_text(md_content, encoding="utf-8")
    print(
        f"Wrote Obsidian question bank ({len(RAW_QUESTIONS)} questions) to {OBSIDIAN_BANK_PATH}"
    )


if __name__ == "__main__":
    asyncio.run(main())
