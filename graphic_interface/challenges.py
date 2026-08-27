"""Catalogo de desafios por juego: enunciado + prompt de IA para resolverlos.

Cada juego (Game-01, Game-03, ...) tiene un desafio algoritmico central
(una funcion en `src/algorithm.py`, `src/world.py`, etc.) que el
participante debe completar. Este modulo guarda, para cada juego, el
enunciado tal como se le presenta al participante y un prompt ya
redactado para pedirle la solucion a una IA (Claude, ChatGPT, etc.),
de forma que quede registrado en la interfaz grafica a cual juego
pertenece cada prompt.

No incluye Game-02 ni Game-07: todavia no tienen un desafio definido
(carpetas sin implementacion, ver discover_games()).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Challenge:
    game: str  # nombre de la carpeta, ej. "Game-01"
    challenge_id: str  # identificador corto del desafio, ej. "A01"
    title: str  # titulo descriptivo del desafio
    location: str  # archivo/funcion donde se resuelve
    statement: str  # enunciado del desafio tal como se le presenta al participante
    prompt: str  # prompt listo para pedirle la solucion a una IA


CHALLENGES: dict[str, Challenge] = {
    "Game-01": Challenge(
        game="Game-01",
        challenge_id="A01",
        title="Conteo de manzanas en rango",
        location="src/world.py -> World.count_apples_in_range()",
        statement=(
            "En el modo Desafio del Snake, el tablero mantiene un filtro activo de "
            "valores [filter_min, filter_max]. Cada manzana en juego tiene un valor "
            "entero (food_field.apples, atributo .value). Hay que implementar "
            "World.count_apples_in_range() para que devuelva cuantas manzanas del "
            "tablero tienen su valor dentro del rango activo (limites inclusive), "
            "reutilizando el metodo ya existente World._apple_passes_filter(value) "
            "para decidir si cada manzana individual pasa el filtro. Este conteo "
            "alimenta el HUD \"En rango: N/Total\" y el bono periodico de puntos "
            "del modo Desafio."
        ),
        prompt=(
            "Actua como un ingeniero de software Python experto. Necesito que "
            "implementes un unico metodo dentro de una clase ya existente.\n\n"
            "Contexto:\n"
            "- Proyecto: un juego de Snake en Python (Pygame), archivo `src/world.py`, clase `World`.\n"
            "- La clase ya tiene un atributo `self.food_field.apples`: una lista de objetos `Apple`, "
            "cada uno con un atributo entero `.value`.\n"
            "- La clase ya tiene un rango activo definido por `self.filter_min` y `self.filter_max` (enteros).\n"
            "- Ya existe, y NO debes reimplementar, el metodo:\n"
            "  def _apple_passes_filter(self, value: int) -> bool:\n"
            "      return self.filter_min <= value <= self.filter_max\n\n"
            "Tarea: implementa el cuerpo de:\n"
            "  def count_apples_in_range(self) -> int:\n\n"
            "Requisitos exactos:\n"
            "1. Debe recorrer todas las manzanas de `self.food_field.apples`.\n"
            "2. Para cada manzana, debe usar `self._apple_passes_filter(apple.value)` para decidir si "
            "cuenta (no repitas la comparacion de rango a mano).\n"
            "3. Debe devolver el numero total de manzanas cuyo valor pasa el filtro, como `int`.\n"
            "4. Debe funcionar en O(n) con una sola pasada sobre la lista.\n"
            "5. No debe mutar `self.food_field.apples` ni ningun otro atributo de `self`.\n"
            "6. Debe devolver 0 si `self.food_field.apples` esta vacia.\n\n"
            "Verifica tu solucion mentalmente con este ejemplo antes de responder:\n"
            "valores = [-5, +5, +15, +5, -5, +15]\n"
            "- rango [0, 10]   -> 2 (los dos +5)\n"
            "- rango [-5, 5]   -> 4 (los dos -5 y los dos +5)\n"
            "- rango [-5, 15]  -> 6 (todas)\n"
            "- rango [10, 20]  -> 2 (los dos +15)\n\n"
            "Devuelveme solo el cuerpo del metodo (codigo Python), sin explicaciones adicionales, "
            "sin cambiar la firma ni agregar imports."
        ),
    ),
    "Game-03": Challenge(
        game="Game-03",
        challenge_id="A03",
        title="Busqueda de un bloque 3D dentro de una matriz 3D (fuerza bruta)",
        location="src/algorithm.py -> find_3d_pattern(big_matrix, pattern_matrix)",
        statement=(
            "Busca una matriz tridimensional de enteros dentro de una matriz "
            "tridimensional mas grande, desplazando la matriz mas pequena por todas "
            "las posiciones validas de la matriz mas grande. En cada posicion "
            "candidata, realiza una comparacion completa elemento por elemento para "
            "comprobar si hay una coincidencia exacta de todo el bloque "
            "tridimensional, pasando a la siguiente posicion candidata si se "
            "encuentra un elemento que no coincide.\n\n"
            "Key Concept: Recorrido por una matriz 3D.\n"
            "Enfoque en la comprension: Reconocimiento de patrones.\n\n"
            "(Aplicado al Cubo de Rubik: la \"matriz grande\" es el estado 3x3x3 del "
            "cubo, RubikCube.matrix, y la \"matriz patron\" es un bloque mas chico, "
            "por ejemplo 2x2x2, que se busca dentro de ese estado.)"
        ),
        prompt=(
            "Actua como un ingeniero de software Python experto en algoritmos. Necesito que "
            "implementes una funcion pura (sin dependencias de pygame ni de ningun framework grafico).\n\n"
            "Archivo: `src/algorithm.py`. Firma exacta a implementar:\n\n"
            "from typing import Dict, List, Optional, Tuple\n"
            "Matrix3D = List[List[List[int]]]\n\n"
            "def find_3d_pattern(big_matrix: Matrix3D, pattern_matrix: Matrix3D) -> Dict[str, object]:\n"
            "    ...\n\n"
            "Enunciado del desafio (copialo tal cual, es el criterio de evaluacion):\n"
            "\"Busca una matriz tridimensional de enteros dentro de una matriz tridimensional mas "
            "grande, desplazando la matriz mas pequena por todas las posiciones validas de la matriz "
            "mas grande. En cada posicion candidata, realiza una comparacion completa elemento por "
            "elemento para comprobar si hay una coincidencia exacta de todo el bloque tridimensional, "
            "pasando a la siguiente posicion candidata si se encuentra un elemento que no coincide.\"\n"
            "Key Concept: recorrido por una matriz 3D. Enfoque en la comprension: reconocimiento de patrones.\n\n"
            "Especificacion de entrada/salida:\n"
            "- `big_matrix` y `pattern_matrix` son listas anidadas de 3 niveles (matriz[i][j][k]), con "
            "enteros. No asumas que son cubicas ni que tengan un tamano fijo.\n"
            "- Debes devolver un diccionario con exactamente dos claves:\n"
            "  - \"found\": True si el patron aparece completo en algun lugar de big_matrix, False si no.\n"
            "  - \"position\": la tupla (x, y, z) de la esquina donde empieza la coincidencia (la primera "
            "que encuentres, recorriendo en orden x, luego y, luego z), o None si no se encontro.\n\n"
            "Algoritmo requerido (fuerza bruta con corte temprano, no optimizaciones tipo hashing):\n"
            "1. Calcula las dimensiones (profundidad, filas, columnas) de ambas matrices.\n"
            "2. Si el patron no entra en la matriz grande en algun eje, devuelve inmediatamente "
            "{\"found\": False, \"position\": None}.\n"
            "3. Recorre todas las posiciones de origen (x, y, z) donde el patron, apoyado ahi, cae "
            "completamente dentro de la matriz grande.\n"
            "4. Para cada posicion candidata, compara el bloque completo elemento por elemento contra "
            "el patron. En cuanto una celda no coincida, abandona esa posicion sin seguir comparando "
            "(corte temprano) y pasa a la siguiente posicion candidata.\n"
            "5. En cuanto una posicion coincida por completo, devuelve {\"found\": True, \"position\": "
            "(x, y, z)} inmediatamente, sin seguir buscando.\n"
            "6. Si se agotan todas las posiciones sin coincidencia, devuelve "
            "{\"found\": False, \"position\": None}.\n\n"
            "Casos de prueba que tu solucion debe cumplir:\n"
            "- Un bloque 2x2x2 extraido de la esquina (0,0,0) de un cubo de Rubik resuelto (matriz "
            "3x3x3) debe encontrarse en (0,0,0).\n"
            "- Un patron relleno con un valor que no existe en ninguna celda (p. ej. 99) nunca debe "
            "encontrarse.\n"
            "- Un bloque 3x3x2 extraido de un cubo recien reiniciado debe encontrarse en su posicion "
            "de origen.\n"
            "- Si el patron es mas grande que la matriz grande en cualquier eje, debe devolver "
            "found=False sin lanzar excepciones.\n\n"
            "Devuelveme el codigo Python completo de `find_3d_pattern` (puedes usar una funcion "
            "auxiliar interna para la comparacion de bloque si lo consideras mas claro), sin "
            "dependencias externas, con nombres de variables descriptivos, y sin cambiar la firma "
            "de la funcion."
        ),
    ),
    "Game-04": Challenge(
        game="Game-04",
        challenge_id="A04",
        title="Verificacion de senal estable (palindromo)",
        location="src/signal_check.py -> is_stable_signal(text)",
        statement=(
            "Cada transmision interceptada es una cadena de texto. Hay que decidir si "
            "esa senal \"conserva su patron\" al cruzar el espejo -- es decir, si se "
            "lee igual en sentido inverso, letra por letra -- o si \"se altera\" (no se "
            "lee igual). Debe implementarse en src/signal_check.py, funcion "
            "is_stable_signal(text: str) -> bool, sin depender de pygame ni de gale. "
            "El jugador tiene 4 segundos por ronda para responder segun esta misma "
            "regla, que nunca se explica en pantalla."
        ),
        prompt=(
            "Actua como un ingeniero de software Python experto. Necesito que implementes una "
            "unica funcion pura.\n\n"
            "Archivo: `src/signal_check.py`. Firma exacta a implementar (no la cambies):\n\n"
            "def is_stable_signal(text: str) -> bool:\n"
            "    ...\n\n"
            "Enunciado: la funcion debe determinar si `text` \"conserva su patron\" al cruzar el "
            "espejo, es decir, si se lee exactamente igual en sentido inverso (comparando caracter "
            "por caracter, incluyendo mayusculas/minusculas y cualquier espacio o simbolo tal cual "
            "vienen en `text`, sin normalizar nada). Si se lee igual invertida, es una senal estable "
            "(True); si no, esta alterada (False).\n\n"
            "Requisitos exactos:\n"
            "1. Debe devolver un `bool` puro (no un valor \"truthy\" cualquiera).\n"
            "2. No debe generar efectos secundarios ni mutar nada (los strings de Python ya son "
            "inmutables).\n"
            "3. Cadena vacia (\"\") debe devolver True.\n"
            "4. Cadena de un solo caracter debe devolver True.\n"
            "5. No debe usar librerias externas ni pygame/gale, es logica pura sobre un string.\n\n"
            "Casos de prueba que tu solucion debe cumplir:\n"
            "- Estables (True): \"RADAR\", \"RECONOCER\", \"SOMETEMOS\", \"ANILINA\", \"ROTOR\", "
            "\"SALAS\", \"SOMOS\", \"SERES\".\n"
            "- Alteradas (False): \"CODIGO\", \"PYTHON\", \"JUEGO\", \"SISTEMAS\", \"VENTANA\", "
            "\"TELEFONO\", \"MENSAJE\", \"CIRCUITO\".\n\n"
            "Devuelveme solo el codigo Python de la funcion `is_stable_signal`, simple, legible y en "
            "una sola pasada (comparar la cadena contra su version invertida es suficiente), sin "
            "explicaciones adicionales."
        ),
    ),
    "Game-05": Challenge(
        game="Game-05",
        challenge_id="A05",
        title="Deteccion de valores repetidos en una linea del tablero",
        location="src/algorithm.py -> find_repeated(matrix)",
        statement=(
            "Detecta los valores repetidos de una linea del tablero (fila o columna), "
            "comparando cada ficha con las que le siguen. La linea se rellena "
            "inicialmente con los elementos que fue dejando el jugador con sus "
            "jugadas (sus swaps).\n\n"
            "Key Concept: Conjuntos, iteracion.\n"
            "Enfoque en la comprension: Filtrado de datos.\n\n"
            "(Aplicado a Transmutacion Arcana: cada casilla del tablero 6x6 tiene un "
            "TileKind, representado como entero 0..7; cuando una Catalisis limpia una "
            "fila o columna completa, esa linea de valores es la \"matriz de una "
            "fila\" que hay que analizar.)"
        ),
        prompt=(
            "Actua como un ingeniero de software Python experto en algoritmos. Necesito que "
            "implementes una funcion pura (sin pygame).\n\n"
            "Archivo: `src/algorithm.py`. Firma exacta a implementar:\n\n"
            "from typing import List\n\n"
            "def find_repeated(matrix: List[List[int]]) -> List[int]:\n"
            "    ...\n\n"
            "Enunciado del desafio (copialo tal cual, es el criterio de evaluacion):\n"
            "\"Detecta los valores repetidos de una linea del tablero (fila o columna), comparando "
            "cada ficha con las que le siguen. La linea se rellena inicialmente con los elementos "
            "que fue dejando el jugador con sus jugadas (sus swaps).\"\n"
            "Key Concept: conjuntos, iteracion. Enfoque en la comprension: filtrado de datos.\n\n"
            "Especificacion de entrada/salida:\n"
            "- `matrix` es una lista de filas, cada fila una lista de enteros. No asumas que es "
            "cuadrada ni que todas las filas midan igual; incluso puede tener una sola fila.\n"
            "- Debe devolver una lista con los valores que aparecen 2 o mas veces en `matrix`, cada "
            "valor una sola vez (sin importar cuantas veces mas se repita), en el orden en que se "
            "detecto su repeticion (el orden de su SEGUNDA aparicion al recorrer la matriz fila por "
            "fila, valor por valor).\n\n"
            "Algoritmo requerido (usa conjuntos, es el \"Key Concept\" del enunciado, no una "
            "comparacion O(n^2) elemento contra elemento):\n"
            "1. Usa un conjunto `seen` para los valores ya vistos una vez, y otro conjunto `reported` "
            "para los valores ya agregados al resultado (asi uno que se repite 3+ veces no aparece "
            "mas de una vez en el resultado).\n"
            "2. Recorre la matriz fila por fila y, dentro de cada fila, valor por valor.\n"
            "3. Si el valor no esta en `seen`, agregalo a `seen` (primera aparicion, no hagas nada mas).\n"
            "4. Si el valor ya esta en `seen` y no esta en `reported`, agregalo tanto a `reported` "
            "como a la lista de resultado (es una repeticion nueva).\n"
            "5. Al terminar, devuelve la lista de resultado.\n\n"
            "Caso de prueba que tu solucion debe cumplir exactamente:\n"
            "find_repeated([[1, 2, 2, 3], [3, 1, 4]]) debe devolver [2, 3, 1] (en ese orden exacto: "
            "2 se repite primero al recorrer, luego 3, luego 1; el 4 nunca se repite y no aparece).\n\n"
            "Devuelveme solo el codigo Python de la funcion `find_repeated`, sin explicaciones "
            "adicionales, sin cambiar la firma."
        ),
    ),
    "Game-06": Challenge(
        game="Game-06",
        challenge_id="A06",
        title="Ordenamiento de palabras por longitud",
        location="src/algorithms/sort_task.py -> sort_words_by_length(words)",
        statement=(
            "PlayState genera un lote de palabras reales antes de cada partida. Hay "
            "que implementar sort_words_by_length(words) para que reciba esa lista y "
            "devuelva una lista NUEVA con las mismas palabras (incluyendo duplicados), "
            "ordenadas de menor a mayor segun len(word), sin mutar la lista original. "
            "Puede usarse cualquier algoritmo de ordenamiento (heapsort, quicksort, "
            "mergesort, bubble sort, etc.); no hace falta que el orden sea estable "
            "entre palabras de igual longitud. Este resultado determina el orden en "
            "que caen las palabras en la partida."
        ),
        prompt=(
            "Actua como un ingeniero de software Python experto en algoritmos de ordenamiento. "
            "Necesito que implementes una unica funcion pura.\n\n"
            "Archivo: `src/algorithms/sort_task.py`. Firma exacta a implementar (no la cambies):\n\n"
            "from typing import List\n\n"
            "def sort_words_by_length(words: List[str]) -> List[str]:\n"
            "    ...\n\n"
            "Enunciado: recibe una lista de palabras (`words`) y debe devolver una lista NUEVA con "
            "esas mismas palabras (incluyendo duplicados, mismo tamano de lista) ordenadas de forma "
            "ascendente segun `len(word)`.\n\n"
            "Requisitos exactos:\n"
            "1. NO debe mutar la lista `words` recibida (trabaja sobre una copia o construye listas "
            "nuevas).\n"
            "2. Debe devolver una lista nueva, del mismo tamano que la de entrada, con las mismas "
            "palabras (sin perder ni duplicar ninguna).\n"
            "3. Palabras de la misma longitud pueden quedar en cualquier orden relativo entre si (no "
            "es necesario que el ordenamiento sea estable).\n"
            "4. Debe manejar correctamente: lista vacia, una sola palabra, listas ya ordenadas, "
            "listas ordenadas al reves, y listas con muchas longitudes repetidas (este es el caso "
            "mas comun en este juego, no un caso borde).\n"
            "5. No hace falta optimizar para listas enormes (como mucho ~500 palabras), pero "
            "implementa un algoritmo de ordenamiento real (mergesort, heapsort o quicksort "
            "recomendados) en vez de depender de `sorted()`/`list.sort()` de Python, ya que el "
            "objetivo del ejercicio es demostrar el algoritmo.\n"
            "6. No debe lanzar excepciones para ninguna entrada valida (lista de strings).\n\n"
            "Verificacion: el resultado de tu funcion debe ser equivalente, en cuanto a orden por "
            "longitud, a `sorted(words, key=len)` (mismas longitudes en el mismo orden ascendente), "
            "aunque el orden interno entre palabras de igual longitud puede diferir.\n\n"
            "Devuelveme el codigo Python completo (la funcion principal y las funciones auxiliares "
            "que necesites para implementar el algoritmo de ordenamiento elegido), con nombres "
            "descriptivos, sin depender de `sorted()` ni `list.sort()`, y sin cambiar la firma de "
            "`sort_words_by_length`."
        ),
    ),
}


def get_challenge(game_name: str) -> Challenge | None:
    return CHALLENGES.get(game_name)
