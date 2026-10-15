#!/usr/bin/env python3
"""Deduplicate and import Parcial 3 exam questions into database.db and export JSON."""

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

# Raw questions definition
RAW_QUESTIONS = [
    {
        "id": 1,
        "question_text": "¿Cuál de las condiciones necesarias para que haya abrazo mortal no se puede eliminar de un sistema?",
        "topic_id": 5,
        "options": [
            {
                "text": "Exclusión mutua",
                "type": "correct",
                "explanation": "Los recursos intrínsecamente no compartibles (como impresoras o unidades de cinta) requieren acceso exclusivo para no corromper datos; no se puede suprimir la exclusión mutua de estos dispositivos.",
            },
            {
                "text": "Inanición",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Retención y espera",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Espera circular",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 2,
        "question_text": "¿Por qué algunos desarrolladores de SOs de propósito general prefieren ignorar el problema de abrazo mortal?",
        "topic_id": 5,
        "options": [
            {
                "text": "Porque sostienen que los abrazos mortales no son frecuentes y dejan que se resuelva a nivel de aplicación en coordinación con el usuario.",
                "type": "correct",
                "explanation": "Conocido como el algoritmo del avestruz. El costo en overhead de los algoritmos de prevención o detección continua no se justifica dada la baja probabilidad de ocurrencia en SOs de propósito general.",
            },
            {
                "text": "Es muy costoso implementar algoritmos de detección, o demás soluciones.",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Porque hay miles de procesos y no podemos saber de antemano la cantidad de recursos que necesitarán.",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Impedir alguna de las cuatro condiciones puede llevarnos a problemas en términos de concurrencia.",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 3,
        "question_text": "¿Qué indica un ciclo en un grafo de asignación de recursos?",
        "topic_id": 5,
        "options": [
            {
                "text": "Que puede haber abrazo mortal",
                "type": "correct",
                "explanation": "Si los recursos tienen múltiples instancias, la existencia de un ciclo es condición necesaria pero NO suficiente; puede haber ciclo sin que exista interbloqueo.",
            },
            {
                "text": "Que se produjo un abrazo mortal",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Que no hay abrazo mortal",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Que el sistema está en un estado seguro",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 4,
        "question_text": "¿Qué indica un ciclo en un grafo de asignación de recursos con sólo una instancia de cada tipo de recurso?",
        "topic_id": 5,
        "options": [
            {
                "text": "Que se produjo un abrazo mortal",
                "type": "correct",
                "explanation": "Si cada tipo de recurso cuenta con una única instancia, un ciclo en el grafo de asignación de recursos es condición necesaria Y suficiente para la existencia de abrazo mortal.",
            },
            {
                "text": "Que puede haber abrazo mortal",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Que no hay abrazo mortal",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Que el sistema está en un estado seguro",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 5,
        "question_text": "¿Cuál de las siguientes NO ES condición necesaria para que haya abrazo mortal?",
        "topic_id": 5,
        "options": [
            {
                "text": "Inanición",
                "type": "correct",
                "explanation": "Las 4 condiciones necesarias de Coffman son exclusión mutua, retención y espera, no apropiación y espera circular. La inanición (starvation) es un problema de equidad de planificación, no una condición de deadlock.",
            },
            {
                "text": "Exclusión mutua",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Retención y espera",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Espera circular",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 6,
        "question_text": "¿Qué método se sugiere en el tp de semáforos para determinar el tamaño de un semáforo en memoria?",
        "topic_id": 6,
        "options": [
            {
                "text": "Usando sizeof(mutex);",
                "type": "correct",
                "explanation": "El operador `sizeof` en C devuelve la cantidad exacta de bytes que ocupa en memoria el tipo de dato abstracto del semáforo (`sem_t` o `pthread_mutex_t`).",
            },
            {
                "text": "Examinar el código fuente de la librería.",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Comparar las direcciones de memoria asignadas a los semáforos",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Mostrarlo con printf",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 7,
        "question_text": "¿Qué representan los vértices del grafo de asignación de recursos?",
        "topic_id": 5,
        "options": [
            {
                "text": "Procesos o recursos",
                "type": "correct",
                "explanation": "El grafo de asignación de recursos (RAG) es un grafo dirigido cuyos vértices están divididos en dos conjuntos disjuntos: procesos (P) y tipos de recursos (R).",
            },
            {
                "text": "Asignaciones",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Procesos",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Recursos",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 8,
        "question_text": "¿Puede un programa que tenga condiciones de carrera andar bien?",
        "topic_id": 6,
        "options": [
            {
                "text": "Sí, puede que jamás falle",
                "type": "correct",
                "explanation": "Las condiciones de carrera dependen del entrelazado de instrucciones en el tiempo; en un entorno particular o con cierta velocidad de CPU el fallo puede no manifestarse jamás, lo que hace a estos bugs no deterministas y difíciles de detectar.",
            },
            {
                "text": "Sí, mientras no haya exclusión mutua andará bien",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "No, porque las condiciones de carrera son errores o incoherencias",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "No, porque tendrá incoherencias",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 9,
        "question_text": "¿Qué característica tiene la función sem_trywait?",
        "topic_id": 6,
        "options": [
            {
                "text": "No es bloqueante",
                "type": "correct",
                "explanation": "`sem_trywait()` intenta bloquear el semáforo si está disponible (>0); si el valor es 0, en vez de suspender el proceso/hilo retorna de inmediato devolviendo -1 y seteando `errno = EAGAIN`.",
            },
            {
                "text": "Tiene mucho overhead",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "La función no existe",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Es sincrónica",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 10,
        "question_text": "¿Cuál es el problema de usar espera activa u ocupada?",
        "topic_id": 6,
        "options": [
            {
                "text": "Que hace uso intensivo de la CPU",
                "type": "correct",
                "explanation": "El proceso ejecuta continuamente un ciclo condicional (spin-lock) consumiendo ciclos de procesamiento en el procesador que podrían ser utilizados por otros procesos productivos.",
            },
            {
                "text": "Que demora más que un bloqueo",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "No hay desventaja con este tipo de espera",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Que el proceso va a la cola de listos",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 11,
        "question_text": "¿Qué significa que un proceso libere la CPU de manera voluntaria?",
        "topic_id": 4,
        "options": [
            {
                "text": "Que tiene que esperar la ejecución de una operación de entrada/salida.",
                "type": "correct",
                "explanation": "La liberación voluntaria ocurre cuando el proceso invoca una llamada al sistema bloqueante (como lectura/escritura de E/S o wait), pasando por sí mismo del estado Ejecución al estado Espera/Bloqueado.",
            },
            {
                "text": "Que ejecuta sus instrucciones sin que sea interrumpido por otro proceso.",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Que no existe un temporizador que permita quitarlo de la CPU.",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Que permite que un planificador apropiativo no tenga que elegirlo de una cola de listos.",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 12,
        "question_text": "¿Cómo resuelven algunos SOs los problemas introducidos por la planificación apropiativa en el kernel?",
        "topic_id": 4,
        "options": [
            {
                "text": "No desalojan procesos mientras las estructuras de datos del SO estén en estado incoherente",
                "type": "correct",
                "explanation": "Para evitar inconsistencias y condiciones de carrera dentro del kernel, el SO desactiva la apropiación o deshabilita interrupciones durante la actualización de estructuras de datos compartidas.",
            },
            {
                "text": "Evitando o impidiendo la utilización de instrucciones atómicas en el SO",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Haciendo que los semáforos bloqueen los procesos internos que presentan incoherencias en su PCB",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "No permiten que más de un proceso del kernel entre a su sección crítica al mismo tiempo",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 13,
        "question_text": "¿En cuál de las siguientes circunstancias no interviene el planificador de corto plazo?",
        "topic_id": 4,
        "options": [
            {
                "text": "Al crear un proceso nuevo",
                "type": "correct",
                "explanation": "La creación y admisión de nuevos procesos a la memoria/sistema es responsabilidad del planificador de largo plazo (o mediano plazo). El de corto plazo (CPU scheduler) se encarga de asignar la CPU a procesos que ya están listos.",
            },
            {
                "text": "Al cambiar un proceso de estado de ejecución a espera",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Al cambiar un proceso de estado de espera a listo o preparado",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Al finalizar un proceso",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 14,
        "question_text": "¿A qué se llama función de selección en la planificación de CPU?",
        "topic_id": 4,
        "options": [
            {
                "text": "Al algoritmo de planificación",
                "type": "correct",
                "explanation": "La función de selección determina qué proceso de la cola de listos es elegido para recibir la CPU (por ejemplo FCFS, Round Robin, SJF, etc.).",
            },
            {
                "text": "A una solución por SW al problema de la sección crítica",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "A un algoritmo de recuperación de abrazo mortal",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Al despachador",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 15,
        "question_text": "¿Qué significa que un proceso ingresó a la sección crítica?",
        "topic_id": 6,
        "options": [
            {
                "text": "Ejecutó instrucciones que modifican valores de recursos compartidos de uso exclusivo.",
                "type": "correct",
                "explanation": "La sección crítica es la porción de código en la que el proceso manipula estructuras de datos, variables o recursos compartidos que requieren exclusión mutua.",
            },
            {
                "text": "Pudo hacerlo porque ningún otro proceso estaba intentando acceder a la misma.",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Accedió a instrucciones privilegiadas a donde solamente se pueden acceder en modo kernel.",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Ejecutó instrucciones que permite el acceso a variables de recursos de uso exclusivo de solo lectura.",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 16,
        "question_text": "¿Qué problema tiene el algoritmo FCFS?",
        "topic_id": 4,
        "options": [
            {
                "text": "El tiempo medio de espera es con frecuencia bastante largo",
                "type": "correct",
                "explanation": "Debido al efecto convoy, si un proceso largo llega primero, los procesos cortos sufren tiempos de espera desproporcionadamente elevados.",
            },
            {
                "text": "Es poco apropiado para los sistemas por lotes",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "El código del algoritmo es altamente complejo aunque breve",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Presenta anomalías en su implementación para multiprocesamiento",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 17,
        "question_text": "¿Qué se puede decir de la latencia de despacho?",
        "topic_id": 4,
        "options": [
            {
                "text": "Debe ser mínima",
                "type": "correct",
                "explanation": "La latencia de despacho es el tiempo consumido por el despachador en detener un proceso y arrancar otro (cambio de contexto, cambio a modo usuario, etc.); al ser tiempo ocioso del sistema, debe ser lo más pequeña posible.",
            },
            {
                "text": "Es característica exclusiva de los planificadores no apropiativos",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Es el tiempo que transcurre entre la finalización de un proceso y la selección del siguiente",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Sólo se considera en entornos de multiprocesamiento",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 18,
        "question_text": "¿Cómo se inicializa un semáforo en C (POSIX)?",
        "topic_id": 6,
        "options": [
            {
                "text": "Ninguna de las opciones",
                "type": "correct",
                "explanation": "Se inicializa mediante la función de biblioteca `sem_init(&sem, pshared, value)` para semáforos no nombrados o `sem_open()` para nombrados.",
            },
            {
                "text": "Usando sem_signal las veces que sea necesario",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Debe inicializarse al declararlo",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Usando la LS sem_t",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 19,
        "question_text": "¿Cómo traduce las direcciones paginadas en un sistema con hashing (dispersión)?",
        "topic_id": 2,
        "options": [
            {
                "text": "Se convierte con una función, el enorme número de página en un número pequeño y se traduce",
                "type": "correct",
                "explanation": "En sistemas con espacios de direcciones grandes (>32 bits), el número de página virtual se pasa por una función hash que mapea a una tabla de dispersión, encadenando colisiones.",
            },
            {
                "text": "Se calcula con una tabla (tabla hash) y se mueve la página a Memoria Principal, para traducirla",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Se traduce una dirección virtual con un circuito especial (circuito hash)",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Se aplica teoría de árboles para recorrerlo en un tiempo mínimo y se calcula la dirección",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 20,
        "question_text": "¿Cuáles son las desventajas del enfoque Predicción (evitación) con manejo para encontrar al menos un camino seguro?",
        "topic_id": 5,
        "options": [
            {
                "text": "Deben conocerse las demandas futuras de recursos y los procesos pueden bloquearse por largo tiempo.",
                "type": "correct",
                "explanation": "Requiere que cada proceso declare de antemano su reclamo máximo de recursos y el sistema puede mantener procesos bloqueados innecesariamente por precaución para no abandonar el estado seguro.",
            },
            {
                "text": "Se deben solicitar todos los recursos de antemano y verificar constantemente la disponibilidad de éstos",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Deben ejecutar algoritmos de comprobación que demandan grandes recursos",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Se deben conocer los puntos de comprobación de antemano.",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 21,
        "question_text": "¿Para qué sirven los pipes de UNIX?",
        "topic_id": 1,
        "options": [
            {
                "text": "Sirven para la comunicación y sincronización de procesos",
                "type": "correct",
                "explanation": "Los pipes (tuberías) son canales unidireccionales de comunicación entre procesos relacionados que brindan sincronización implícita mediante bloqueo en read/write.",
            },
            {
                "text": "Sirven para la comunicación de procesos y entre el SO y los procesos",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Sirve para la sincronización de procesos e hilos en momentos de concurrencia",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Sirven para que el SO avise a los procesos sobre la ocurrencia de un evento.",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 22,
        "question_text": "¿A qué se denomina estado seguro de un sistema en prevención/evitación de Deadlocks?",
        "topic_id": 5,
        "options": [
            {
                "text": "Al hecho de que existe al menos una secuencia de ejecución, donde todos los procesos terminan.",
                "type": "correct",
                "explanation": "Un estado es seguro si existe una secuencia segura de asignación <P1, P2, ..., Pn> tal que para cada Pi, los recursos que aún necesita puedan ser satisfechos con los recursos disponibles más los ya asignados a los procesos anteriores.",
            },
            {
                "text": "Es el estado al cual se puede llegar luego de que los procesos controlen de que tienen todos los recursos",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Aquel estado hipotético del sistema, donde los recursos alcanzan para todos los procesos.",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Es un sistema que se ha garantizado la no existencia de deadlock, gracias a una buena planificación.",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 23,
        "question_text": "¿Cómo puede ayudar un SO a la organización lógica de los programas?",
        "topic_id": 2,
        "options": [
            {
                "text": "Soportando la segmentación, como mecanismo de división y asignación de espacio en Memoria Principal",
                "type": "correct",
                "explanation": "La segmentación organiza la memoria según la visión del programador, dividiendo el espacio lógico en segmentos variables que corresponden a funciones, objetos, pilas o arrays.",
            },
            {
                "text": "Haciendo que el programador divida las partes de su programa, según el esquema de sus segmentos",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Ayudando al compilador para que divida como corresponda las partes de un programa",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Usando los registros del procesador para asignarle los marcos en la Memoria Principal",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 28,
        "question_text": "¿Si ya existen las tablas de páginas por proceso, para qué sirve la tabla de marcos de páginas (invertida)?",
        "topic_id": 2,
        "options": [
            {
                "text": "Las tablas de páginas ven el aspecto lógico de los procesos, la tabla de marco de página ve el aspecto físico",
                "type": "correct",
                "explanation": "Las tablas de páginas tradicionales son locales a cada proceso y mapean páginas lógicas; la tabla invertida es global y tiene una sola entrada por cada marco físico real en RAM, indexada por el marco físico.",
            },
            {
                "text": "Las tablas de páginas son de los procesos. La tabla de marco de página controla el espacio que ocupa el SO",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Las páginas invertidas, sirven para verificar que la dirección haya sido bien calculada (se invierte el proceso)",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Las tablas de marcos (una por proceso), sirve para agilizar las traducciones. Más rápidas que las otras tablas",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 29,
        "question_text": "¿Qué diferencia fundamental hay entre la paginación y la segmentación?",
        "topic_id": 2,
        "options": [
            {
                "text": "La paginación optimiza espacio en la RAM, la segmentación contempla las estructuras de programación",
                "type": "correct",
                "explanation": "La paginación divide la memoria física y lógica en bloques de tamaño fijo sin fragmentación externa y de forma invisible al usuario; la segmentación refleja la estructura lógica del programa con bloques de tamaño variable definidos por el programador.",
            },
            {
                "text": "Es en los tamaños, la paginación es más chica. Los segmentos son muchos más grandes",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Ninguna diferencia, sólo que hay sistemas operativos que reconocen uno u otra técnica",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "La paginación es más precisa, porque todas las páginas tienen el mismo tamaño. La segmentación no.",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 32,
        "question_text": """Sean papel y lápiz 2 semáforos inicializados en 1, y considerando el siguiente fragmento de código:
sem_wait(papel); printf("HIJO: tengo el papel\\n");
sem_wait(lapiz); printf("HIJO: tengo el lápiz\\n");
printf("Tengo lápiz y papel, ahora escribo\\n");
sem_post(papel);
sem_post(lapiz);
¿Es posible que 2 procesos que ejecuten éste código entren en abrazo mortal?""",
        "topic_id": 5,
        "options": [
            {
                "text": "Sería posible, pero sólo si el segundo proceso tuviera invertidas las líneas 1 y 2.",
                "type": "correct",
                "explanation": "Si ambos procesos solicitan los recursos en el mismo orden (primero papel y luego lápiz), se rompe la condición de espera circular y no puede haber deadlock. Se requiere que otro proceso solicite primero lápiz y luego papel para generar el ciclo.",
            },
            {
                "text": "No es posible, porque no hay suficientes recursos para entrar en abrazo mortal.",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Sí es posible, depende de la cantidad de veces que se ejecute.",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "No es posible, porque el orden de las líneas 6 y 7 no coincide con 1 y 2.",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 33,
        "question_text": "¿Qué tamaño tiene típicamente una página de memoria en arquitecturas estándar de GNU/Linux?",
        "topic_id": 2,
        "options": [
            {
                "text": "Tiene 4096 Bytes",
                "type": "correct",
                "explanation": "En la gran mayoría de las arquitecturas x86 y x86_64, el tamaño de página base soportado por la MMU y configurado en el kernel Linux es de 4096 Bytes (4 KiB).",
            },
            {
                "text": "Tiene 4096 KBytes",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Tiene 100 Bytes",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Tiene 128 KBytes",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
    {
        "id": 34,
        "question_text": "¿Qué son las señales en UNIX / Linux?",
        "topic_id": 1,
        "options": [
            {
                "text": "Una señal es un mecanismo de software que informa un proceso de la ocurrencia de eventos asíncronos",
                "type": "correct",
                "explanation": "Son interrupciones por software enviadas a un proceso por el sistema operativo u otro proceso para notificar la ocurrencia de un evento (e.g. SIGINT, SIGSEGV, SIGTERM).",
            },
            {
                "text": "Una señal es la forma que tienen los procesos de avisar la ocurrencia de un evento a un usuario",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Una señal es la transmisión de información que el SO le hace a los procesos",
                "type": "incorrect",
                "explanation": None,
            },
            {
                "text": "Una señal es la forma en que los procesos logran ejecutar otro proceso, para atender un evento.",
                "type": "incorrect",
                "explanation": None,
            },
        ],
    },
]

TOPIC_MAP = {
    1: "Procesos",
    2: "Administración de Memoria",
    3: "Sistemas de Archivos",
    4: "Planificación de CPU",
    5: "Deadlock",
    6: "Sincronización",
    7: "Entrada/Salida",
    8: "Seguridad",
    9: "Otros",
}


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[¿?¡!.,:;\"\'\(\)\[\]\{\}\/\\\\\-_\n\r\t]", " ", text)
    accents = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n"}
    for k, v in accents.items():
        text = text.replace(k, v)
    return " ".join(text.split())


async def main() -> None:
    db_path = "/home/dybalux/Escritorio_Dev/image_to_text/database.db"
    json_path = (
        "/home/dybalux/Escritorio_Facutad/Sistemas Operativos/Sistemas Operativos.json"
    )

    print("=================================================================")
    print("PARCIAL 3 QUESTION DEDUPLICATION AND IMPORT TOOL")
    print("=================================================================")

    # 1. Connect to SQLite to read existing questions
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    existing_rows = cursor.execute(
        "SELECT id, exam_id, topic_id, question_text FROM questions"
    ).fetchall()
    initial_q_count = len(existing_rows)
    initial_a_count = cursor.execute("SELECT count(*) FROM answers").fetchone()[0]

    print("Initial DB state:")
    print(f"  Questions: {initial_q_count}")
    print(f"  Answers:   {initial_a_count}")

    # 2. Check duplicates
    duplicates = []
    unique_to_insert = []

    print("\n--- Deduplication Check (threshold > 0.85) ---")
    for q in RAW_QUESTIONS:
        q_norm = normalize(q["question_text"])
        best_sim = 0.0
        best_match = None

        for ex_id, ex_exam, ex_topic, ex_text in existing_rows:
            ex_norm = normalize(ex_text)
            sim = difflib.SequenceMatcher(None, q_norm, ex_norm).ratio()
            if sim > best_sim:
                best_sim = sim
                best_match = (ex_id, ex_exam, ex_topic, ex_text)

        if best_sim > 0.85:
            duplicates.append((q, best_sim, best_match))
            print(
                f"  [DUPLICATE] Q{q['id']}: '{q['question_text'][:50]}...' matches DB Q{best_match[0]} (sim: {best_sim:.3f})"
            )
        else:
            unique_to_insert.append((q, best_sim, best_match))
            print(
                f"  [UNIQUE]    Q{q['id']}: '{q['question_text'][:50]}...' (max sim: {best_sim:.3f} with DB Q{best_match[0] if best_match else 'None'})"
            )

    print("\nDeduplication results:")
    print(f"  Total evaluated: {len(RAW_QUESTIONS)}")
    print(f"  Duplicates found: {len(duplicates)}")
    print(f"  Unique to insert: {len(unique_to_insert)}")

    # 3. Insert unique questions into database
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
    inserted_questions = 0
    inserted_answers = 0

    print("\n--- Inserting unique questions ---")
    for q, sim, match in unique_to_insert:
        q_uuid = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO questions (
                exam_id, image_id, question_text, extracted_text,
                confidence_score, order_in_exam, is_corrected,
                correction_notes, has_code_in_answers, created_at,
                updated_at, uuid, topic_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,  # exam_id = 1
                None,  # image_id
                q["question_text"],  # question_text
                q["question_text"],  # extracted_text
                1.0,  # confidence_score = 1.0
                None,  # order_in_exam
                1,  # is_corrected = 1
                None,  # correction_notes
                0,  # has_code_in_answers
                now_str,  # created_at
                now_str,  # updated_at
                q_uuid,  # uuid
                q["topic_id"],  # topic_id
            ),
        )
        new_qid = cursor.lastrowid
        inserted_questions += 1

        for idx, opt in enumerate(q["options"], start=1):
            a_uuid = str(uuid.uuid4())
            cursor.execute(
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
                    0,  # is_common_misconception
                    opt["explanation"],
                    idx,  # display_order (1 to 4)
                    now_str,
                    now_str,
                    a_uuid,
                ),
            )
            inserted_answers += 1

    conn.commit()
    print(f"Committed {inserted_questions} questions and {inserted_answers} answers.")

    # 4. Verify SQLite Integrity
    print("\n--- Verifying Database Integrity ---")
    cursor.execute("PRAGMA foreign_key_check;")
    fk_errors = cursor.fetchall()
    if fk_errors:
        print(f"ERROR: Foreign key errors detected: {fk_errors}")
        sys.exit(1)
    else:
        print("  PRAGMA foreign_key_check: OK (0 errors)")

    cursor.execute("PRAGMA integrity_check;")
    integrity = cursor.fetchall()
    print(f"  PRAGMA integrity_check: {integrity[0][0]}")

    final_q_count = cursor.execute("SELECT count(*) FROM questions").fetchone()[0]
    final_a_count = cursor.execute("SELECT count(*) FROM answers").fetchone()[0]

    print("\nFinal DB counts:")
    print(
        f"  Questions: {final_q_count} (was {initial_q_count}, +{final_q_count - initial_q_count})"
    )
    print(
        f"  Answers:   {final_a_count} (was {initial_a_count}, +{final_a_count - initial_a_count})"
    )

    # Topic breakdown
    print("\n--- Topic Breakdown (Final DB) ---")
    topic_dist = cursor.execute(
        """
        SELECT t.id, t.name, count(q.id)
        FROM topics t
        LEFT JOIN questions q ON q.topic_id = t.id
        GROUP BY t.id, t.name
        ORDER BY t.id
        """
    ).fetchall()
    for tid, tname, count in topic_dist:
        print(f"  Topic {tid} ({tname}): {count} questions")

    conn.close()

    # Also update docker db copy to stay in sync
    docker_db_path = "/home/dybalux/Escritorio_Dev/image_to_text/data/db/database.db"
    shutil.copy2(db_path, docker_db_path)
    print(f"\nSynced updated database to {docker_db_path}")

    # 5. Export to JSON using JsonIOService
    print("\n--- Exporting to JSON via JsonIOService ---")
    from app.db.session import AsyncSessionLocal
    from app.schemas.json_io import ExportFileSchema
    from app.services.json_io_service import JsonIOService

    async with AsyncSessionLocal() as session:
        service = JsonIOService(session)
        export_data = await service.export_full_db()
        dumped = export_data.model_dump(mode="json")

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(dumped, f, indent=2)
            f.write("\n")

        print(f"Wrote {len(dumped['questions'])} questions to {json_path}")

        # Validate exported JSON against Pydantic schema
        validated = ExportFileSchema.model_validate(dumped)
        print(
            f"Export validation successful: {len(validated.questions)} questions validated."
        )


if __name__ == "__main__":
    asyncio.run(main())
