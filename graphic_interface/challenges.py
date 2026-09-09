"""Catalogo de desafios por juego: enunciado que se le presenta al participante
en la Etapa 1 de la sesion guiada.

Cada uno de los 7 juegos tiene un desafio algoritmico central (una funcion
en `src/algorithm.py`, `src/world.py`, `logic2048.py`, etc.) que el
participante debe completar en base a su propio prompt (ver
challenge_solver.py). Este modulo guarda, para cada juego, el enunciado
completo tal como se le presenta.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Challenge:
    game: str  # nombre de la carpeta, ej. "Game-01"
    challenge_id: str  # identificador corto del desafio, ej. "A01"
    title: str  # titulo descriptivo del desafio
    location: str  # archivo/funcion donde se resuelve
    statement: str  # enunciado del desafio tal como se le presenta al participante
    signature: str  # firma exacta de la funcion/metodo a implementar
    requirements: list[str]  # lista de requisitos exactos que debe cumplir la solucion
    examples: str  # ejemplos/casos de prueba concretos, formateados como bloque de texto


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
            "alimenta el indicador en pantalla \"En rango: N/Total\" y el bono "
            "periodico de puntos del modo Desafio."
        ),
        signature="def count_apples_in_range(self) -> int:",
        requirements=[
            "Debe recorrer todas las manzanas de self.food_field.apples.",
            "Para cada manzana, debe usar self._apple_passes_filter(apple.value) para decidir si "
            "cuenta (no repetir la comparacion de rango a mano).",
            "Debe devolver el numero total de manzanas cuyo valor pasa el filtro, como int.",
            "Debe funcionar en O(n) con una sola pasada sobre la lista.",
            "No debe mutar self.food_field.apples ni ningun otro atributo de self.",
            "Debe devolver 0 si self.food_field.apples esta vacia.",
        ],
        examples=(
            "valores = [-5, +5, +15, +5, -5, +15]\n"
            "- rango [0, 10]   -> 2 (los dos +5)\n"
            "- rango [-5, 5]   -> 4 (los dos -5 y los dos +5)\n"
            "- rango [-5, 15]  -> 6 (todas)\n"
            "- rango [10, 20]  -> 2 (los dos +15)"
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
        signature=(
            "Matrix3D = List[List[List[int]]]\n\n"
            "def find_3d_pattern(big_matrix: Matrix3D, pattern_matrix: Matrix3D) -> Dict[str, object]:"
        ),
        requirements=[
            "big_matrix y pattern_matrix son listas anidadas de 3 niveles (matriz[i][j][k]) con "
            "enteros; no asumas que son cubicas ni que tengan un tamano fijo.",
            "Debe devolver un diccionario con exactamente dos claves: \"found\" (True/False) y "
            "\"position\" (la tupla (x, y, z) de la primera coincidencia, recorriendo en orden "
            "x, luego y, luego z, o None si no se encontro).",
            "Si el patron no entra en la matriz grande en algun eje, debe devolver "
            "{\"found\": False, \"position\": None} sin lanzar excepciones.",
            "Es fuerza bruta CON CORTE TEMPRANO (no hashing ni otras optimizaciones): recorre "
            "todas las posiciones de origen validas y, en cada una, compara elemento por "
            "elemento, abandonando esa posicion apenas una celda no coincide.",
            "En cuanto una posicion coincida por completo, debe devolver ese resultado de "
            "inmediato, sin seguir buscando otras coincidencias.",
        ],
        examples=(
            "- Un bloque 2x2x2 extraido de la esquina (0,0,0) de un cubo de Rubik resuelto "
            "(matriz 3x3x3) debe encontrarse en (0,0,0).\n"
            "- Un patron relleno con un valor que no existe en ninguna celda (p. ej. 99) nunca "
            "debe encontrarse.\n"
            "- Un bloque 3x3x2 extraido de un cubo recien reiniciado debe encontrarse en su "
            "posicion de origen.\n"
            "- Si el patron es mas grande que la matriz grande en cualquier eje, debe devolver "
            "found=False sin lanzar excepciones."
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
        signature="def is_stable_signal(text: str) -> bool:",
        requirements=[
            "Debe devolver un bool puro (no un valor \"truthy\" cualquiera).",
            "No debe generar efectos secundarios ni mutar nada.",
            "Cadena vacia (\"\") debe devolver True.",
            "Cadena de un solo caracter debe devolver True.",
            "Comparacion caracter por caracter, incluyendo mayusculas/minusculas y cualquier "
            "espacio o simbolo tal cual vienen en text, sin normalizar nada.",
            "No debe usar librerias externas ni pygame/gale, es logica pura sobre un string.",
        ],
        examples=(
            "- Estables (True): RADAR, RECONOCER, SOMETEMOS, ANILINA, ROTOR, SALAS, SOMOS, SERES.\n"
            "- Alteradas (False): CODIGO, PYTHON, JUEGO, SISTEMAS, VENTANA, TELEFONO, MENSAJE, "
            "CIRCUITO."
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
        signature="def find_repeated(matrix: List[List[int]]) -> List[int]:",
        requirements=[
            "matrix es una lista de filas, cada fila una lista de enteros; no asumas que es "
            "cuadrada ni que todas las filas midan igual (incluso puede tener una sola fila).",
            "Debe devolver una lista con los valores que aparecen 2 o mas veces, cada valor una "
            "sola vez (sin importar cuantas veces mas se repita), en el orden en que se detecto "
            "su repeticion (el orden de su SEGUNDA aparicion al recorrer la matriz fila por fila, "
            "valor por valor).",
            "El algoritmo debe usar conjuntos (seen/reported) para detectar repeticiones en una "
            "sola pasada, no una comparacion O(n^2) elemento contra elemento.",
        ],
        examples=(
            "find_repeated([[1, 2, 2, 3], [3, 1, 4]]) debe devolver [2, 3, 1] (en ese orden "
            "exacto: 2 se repite primero al recorrer, luego 3, luego 1; el 4 nunca se repite y "
            "no aparece)."
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
        signature="def sort_words_by_length(words: List[str]) -> List[str]:",
        requirements=[
            "NO debe mutar la lista words recibida (trabajar sobre una copia o construir listas "
            "nuevas).",
            "Debe devolver una lista nueva, del mismo tamano que la de entrada, con las mismas "
            "palabras (incluyendo duplicados, sin perder ni duplicar ninguna) ordenadas "
            "ascendente segun len(word).",
            "Palabras de la misma longitud pueden quedar en cualquier orden relativo entre si "
            "(no es necesario que el ordenamiento sea estable).",
            "Debe manejar correctamente: lista vacia, una sola palabra, listas ya ordenadas, "
            "listas ordenadas al reves, y listas con muchas longitudes repetidas (el caso mas "
            "comun en este juego, no un caso borde).",
            "Debe implementar un algoritmo de ordenamiento real (mergesort, heapsort o "
            "quicksort recomendados), sin depender de sorted() ni list.sort() de Python.",
            "No debe lanzar excepciones para ninguna entrada valida (lista de strings).",
        ],
        examples=(
            "El resultado debe ser equivalente, en cuanto a orden por longitud, a "
            "sorted(words, key=len) (mismas longitudes en el mismo orden ascendente), aunque el "
            "orden interno entre palabras de igual longitud puede diferir."
        ),
    ),
    "Game-02": Challenge(
        game="Game-02",
        challenge_id="A02",
        title="Compresión y fusión de una línea del tablero",
        location="logic2048.py -> Board._compress_and_merge(line)",
        statement=(
            "En 2048, cada movimiento desliza y fusiona una linea (fila o columna) del "
            "tablero, ya orientada hacia el borde al que se desliza. Hay que implementar "
            "Board._compress_and_merge(line) para que comprima los huecos, fusione cada "
            "par de fichas iguales una sola vez por turno (una linea [2,2,2,2] da [4,4], "
            "no [8,0] ni [4,2,2]), y vuelva a rellenar con ceros hasta el tamano original, "
            "devolviendo tambien los puntos ganados y el desplazamiento de cada ficha para "
            "poder animarlo."
        ),
        signature=(
            "def _compress_and_merge(\n"
            "    line: List[int],\n"
            ") -> Tuple[List[int], int, bool, List[_LineShift]]:"
        ),
        requirements=[
            "Debe funcionar sobre una unica linea (lista de enteros) ya orientada: el primer "
            "elemento es el mas cercano al borde hacia el que se desliza.",
            "Debe comprimir los valores distintos de cero hacia el principio de la linea, "
            "sin cambiar su orden relativo.",
            "Cada ficha solo puede fusionarse UNA vez por movimiento: en [2,2,2,2] el "
            "resultado es [4,4], nunca [8,0] ni [4,2,2].",
            "Debe rellenar con ceros al final hasta recuperar el tamano original de la linea.",
            "Debe devolver una tupla (linea_resultante, puntos_obtenidos, hubo_cambio, "
            "desplazamientos): los puntos son la suma de los valores nuevos creados por "
            "cada fusion, hubo_cambio es False si el resultado es identico a la entrada, y "
            "desplazamientos trae un registro por cada ficha original (indice de origen, "
            "indice de destino, valor, si se fusiono).",
            "No debe mutar la lista `line` recibida.",
        ],
        examples=(
            "line = [2, 2, 2, 4]\n"
            "- Resultado: [4, 2, 4, 0]\n"
            "- Puntos obtenidos: 4 (por la fusion 2+2)\n"
            "- hubo_cambio: True\n\n"
            "line = [2, 2, 2, 2]\n"
            "- Resultado: [4, 4, 0, 0]\n"
            "- Puntos obtenidos: 8 (dos fusiones independientes de 4 cada una)\n\n"
            "line = [4, 0, 0, 2]\n"
            "- Resultado: [4, 2, 0, 0] (se comprime pero no hay fusion; hubo_cambio: True)\n\n"
            "line = [8, 4, 2, 0]\n"
            "- Resultado: [8, 4, 2, 0] (ya estaba compacta; hubo_cambio: False)"
        ),
    ),
    "Game-07": Challenge(
        game="Game-07",
        challenge_id="A07",
        title="Reglas del Juego de la Vida (Conway)",
        location="src/board.py -> next_generation(matrix, blocked)",
        statement=(
            "El automata celular de este juego guarda su estado como una matriz de "
            "booleanos (viva/muerta). Hay que implementar next_generation(matrix, blocked) "
            "para que calcule la siguiente generacion aplicando las reglas clasicas de "
            "Conway (B3/S23): una celda viva con 2 o 3 vecinas vivas sobrevive, una celda "
            "muerta con exactamente 3 vecinas vivas nace, y en cualquier otro caso queda "
            "(o sigue) muerta. Los vecinos son los 8 que rodean cada celda (incluidas las "
            "diagonales). Las coordenadas en `blocked` representan paredes: nunca pueden "
            "tener vida, sin importar lo que digan las reglas."
        ),
        signature=(
            "def next_generation(\n"
            "    matrix: List[List[bool]], blocked: Set[Coord] = frozenset()\n"
            ") -> List[List[bool]]:"
        ),
        requirements=[
            "Debe devolver una matriz NUEVA (misma cantidad de filas y columnas que "
            "matrix), sin mutar la matriz de entrada.",
            "Una celda viva con 2 o 3 vecinas vivas sobrevive a la siguiente generacion.",
            "Una celda muerta con exactamente 3 vecinas vivas nace en la siguiente "
            "generacion.",
            "Cualquier otra celda (viva con menos de 2 o mas de 3 vecinas, o muerta con "
            "una cantidad de vecinas distinta de 3) queda muerta.",
            "Los vecinos de una celda son las 8 celdas que la rodean (arriba, abajo, "
            "izquierda, derecha y las 4 diagonales); las celdas fuera del borde de la "
            "matriz no cuentan como vecinas.",
            "Ninguna celda cuya coordenada este en `blocked` puede tener vida en el "
            "resultado, sin importar lo que digan las reglas de nacimiento/supervivencia.",
            "Debe funcionar para matrices vacias o de cualquier tamano rectangular (no "
            "asumir que es cuadrada).",
        ],
        examples=(
            "Con blocked vacio (juego clasico de Conway), un patron \"parpadeante\" "
            "(blinker) de 3 celdas en linea horizontal se convierte en 3 celdas en linea "
            "vertical en la siguiente generacion, y vuelve a horizontal en la generacion "
            "despues de esa (oscila con periodo 2).\n\n"
            "Una celda viva completamente aislada (sin vecinas vivas) muere en la "
            "siguiente generacion (menos de 2 vecinas).\n\n"
            "Una celda muerta con exactamente 3 vecinas vivas nace, aunque esas 3 vecinas "
            "despues mueran por otras reglas -- todas las celdas de la nueva generacion se "
            "calculan a partir del mismo estado anterior, nunca de resultados ya "
            "actualizados.\n\n"
            "Si una coordenada esta en `blocked`, debe quedar muerta en el resultado "
            "incluso si tiene exactamente 3 vecinas vivas."
        ),
    ),
}


def get_challenge(game_name: str) -> Challenge | None:
    return CHALLENGES.get(game_name)
