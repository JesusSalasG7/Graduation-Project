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
    broken_symptom: str  # que probar/observar en la Etapa 1 (juego SIN la solucion) para notar la falla
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
            "En el modo Desafío del Snake, el tablero mantiene un filtro activo de "
            "valores [filter_min, filter_max] (se ve en pantalla como \"Filtro "
            "activo: [X, Y]\", y cambia solo cada 8 segundos). Cada manzana en "
            "juego tiene un valor entero al azar (food_field.apples, atributo "
            ".value: -5, 5 o 15). Hay que implementar World.count_apples_in_range() "
            "para que devuelva cuántas manzanas del tablero tienen su valor dentro "
            "del rango activo (limites inclusive), reutilizando el metodo ya "
            "existente World._apple_passes_filter(value) para decidir si cada "
            "manzana individual pasa el filtro. Este conteo alimenta dos cosas: el "
            "indicador en pantalla \"En rango: N/Total\", y un BONO DE PUNTOS "
            "AUTOMÁTICO -- cada 5 segundos, sin que el jugador tenga que comer "
            "nada, el juego debe sumar 2 puntos por cada manzana que en ESE "
            "momento esté dentro del filtro activo (N manzanas en rango -> "
            "+2*N puntos, cada 5 segundos, solo, sin comer)."
        ),
        broken_symptom=(
            "Juega un rato en Modo Desafío sin comer ninguna manzana y mira tu "
            "puntaje: cada 5 segundos, el juego debería sumarte puntos solo por "
            "tener manzanas dentro del \"Filtro activo: [X, Y]\" que se ve arriba "
            "(2 puntos por cada manzana en rango, aunque no la comas) -- es un "
            "bono automático, aparte de los puntos de comer. Fíjate si el "
            "indicador \"En rango: N/Total\" y ese aumento de puntaje cada 5 "
            "segundos realmente pasan, o si tu puntaje se queda quieto."
        ),
        signature="def count_apples_in_range(self) -> int:",
        requirements=[
            "Debe recorrer todas las manzanas de self.food_field.apples.",
            "Para cada manzana, debe usar self._apple_passes_filter(apple.value) para decidir si "
            "cuenta (no repetir la comparación de rango a mano).",
            "Debe devolver el número total de manzanas cuyo valor pasa el filtro, como int.",
            "Debe funcionar en O(n) con una sola pasada sobre la lista.",
            "No debe mutar self.food_field.apples ni ningún otro atributo de self.",
            "Debe devolver 0 si self.food_field.apples está vacía.",
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
        title="Búsqueda de un bloque 3D dentro de una matriz 3D (fuerza bruta)",
        location="src/algorithm.py -> find_3d_pattern(big_matrix, pattern_matrix)",
        statement=(
            "Busca una matriz tridimensional de enteros dentro de una matriz "
            "tridimensional más grande, desplazando la matriz más pequeña por todas "
            "las posiciones válidas de la matriz más grande. En cada posición "
            "candidata, realiza una comparación completa elemento por elemento para "
            "comprobar si hay una coincidencia exacta de todo el bloque "
            "tridimensional, pasando a la siguiente posición candidata si se "
            "encuentra un elemento que no coincide.\n\n"
            "Key Concept: Recorrido por una matriz 3D.\n"
            "Enfoque en la comprensión: Reconocimiento de patrones.\n\n"
            "(Aplicado al Cubo de Rubik: la \"matriz grande\" es el estado 3x3x3 del "
            "cubo, RubikCube.matrix, y la \"matriz patrón\" es un bloque más chico, "
            "por ejemplo 2x2x2, que se busca dentro de ese estado.)"
        ),
        broken_symptom=(
            "Toca el botón \"Buscar\" en distintos momentos (recién "
            "empezado, después de mezclar) y fíjate si realmente resalta "
            "el bloque 2x2x2 objetivo en el cubo 3D cuando ese patrón está "
            "presente, o si nunca encuentra nada."
        ),
        signature=(
            "Matrix3D = List[List[List[int]]]\n\n"
            "def find_3d_pattern(big_matrix: Matrix3D, pattern_matrix: Matrix3D) -> Dict[str, object]:"
        ),
        requirements=[
            "big_matrix y pattern_matrix son listas anidadas de 3 niveles (matriz[i][j][k]) con "
            "enteros; no asumas que son cúbicas ni que tengan un tamaño fijo.",
            "Debe devolver un diccionario con exactamente dos claves: \"found\" (True/False) y "
            "\"position\" (la tupla (x, y, z) de la primera coincidencia, recorriendo en orden "
            "x, luego y, luego z, o None si no se encontró).",
            "Si el patrón no entra en la matriz grande en algún eje, debe devolver "
            "{\"found\": False, \"position\": None} sin lanzar excepciones.",
            "Es fuerza bruta CON CORTE TEMPRANO (no hashing ni otras optimizaciones): recorre "
            "todas las posiciones de origen válidas y, en cada una, compara elemento por "
            "elemento, abandonando esa posición apenas una celda no coincide.",
            "En cuanto una posición coincida por completo, debe devolver ese resultado de "
            "inmediato, sin seguir buscando otras coincidencias.",
        ],
        examples=(
            "- Un bloque 2x2x2 extraído de la esquina (0,0,0) de un cubo de Rubik resuelto "
            "(matriz 3x3x3) debe encontrarse en (0,0,0).\n"
            "- Un patrón relleno con un valor que no existe en ninguna celda (p. ej. 99) nunca "
            "debe encontrarse.\n"
            "- Un bloque 3x3x2 extraído de un cubo recién reiniciado debe encontrarse en su "
            "posición de origen.\n"
            "- Si el patrón es más grande que la matriz grande en cualquier eje, debe devolver "
            "found=False sin lanzar excepciones."
        ),
    ),
    "Game-04": Challenge(
        game="Game-04",
        challenge_id="A04",
        title="Verificación de señal estable (palíndromo)",
        location="src/signal_check.py -> is_stable_signal(text)",
        statement=(
            "Cada transmisión interceptada es una cadena de texto. Hay que decidir si "
            "esa señal \"conserva su patrón\" al cruzar el espejo -- es decir, si se "
            "lee igual en sentido inverso, letra por letra -- o si \"se altera\" (no se "
            "lee igual). Debe implementarse en src/signal_check.py, función "
            "is_stable_signal(text: str) -> bool, sin depender de pygame ni de gale. "
            "El jugador tiene 4 segundos por ronda para responder según esta misma "
            "regla, que nunca se explica en pantalla."
        ),
        broken_symptom=(
            "Responde algunas rondas (Estable/Alterada) y fíjate qué "
            "aparece en pantalla en vez de una evaluación real de tu "
            "respuesta."
        ),
        signature="def is_stable_signal(text: str) -> bool:",
        requirements=[
            "Debe devolver un bool puro (no un valor \"truthy\" cualquiera).",
            "No debe generar efectos secundarios ni mutar nada.",
            "Cadena vacía (\"\") debe devolver True.",
            "Cadena de un solo carácter debe devolver True.",
            "Comparación carácter por carácter, incluyendo mayúsculas/minúsculas y cualquier "
            "espacio o símbolo tal cual vienen en text, sin normalizar nada.",
            "No debe usar librerías externas ni pygame/gale, es lógica pura sobre un string.",
        ],
        examples=(
            "- Estables (True): RADAR, RECONOCER, SOMETEMOS, ANILINA, ROTOR, SALAS, SOMOS, SERES.\n"
            "- Alteradas (False): CÓDIGO, PYTHON, JUEGO, SISTEMAS, VENTANA, TELÉFONO, MENSAJE, "
            "CIRCUITO."
        ),
    ),
    "Game-05": Challenge(
        game="Game-05",
        challenge_id="A05",
        title="Detección de valores repetidos en una línea del tablero",
        location="src/algorithm.py -> find_repeated(matrix)",
        statement=(
            "Detecta los valores repetidos de una línea del tablero (fila o columna), "
            "comparando cada ficha con las que le siguen. La línea se rellena "
            "inicialmente con los elementos que fue dejando el jugador con sus "
            "jugadas (sus swaps).\n\n"
            "Key Concept: Conjuntos, iteración.\n"
            "Enfoque en la comprensión: Filtrado de datos.\n\n"
            "(Aplicado a Transmutación Arcana: cada casilla del tablero 6x6 tiene un "
            "TileKind, representado como entero 0..7; cuando una Catálisis limpia una "
            "fila o columna completa, esa línea de valores es la \"matriz de una "
            "fila\" que hay que analizar.)"
        ),
        broken_symptom=(
            "Provoca una Catálisis (limpia una fila/columna completa) "
            "donde se repita algún elemento y fíjate si aparece el bono "
            "de \"Resonancia Elemental\" que debería pagar eso."
        ),
        signature="def find_repeated(matrix: List[List[int]]) -> List[int]:",
        requirements=[
            "matrix es una lista de filas, cada fila una lista de enteros; no asumas que es "
            "cuadrada ni que todas las filas midan igual (incluso puede tener una sola fila).",
            "Debe devolver una lista con los valores que aparecen 2 o más veces, cada valor una "
            "sola vez (sin importar cuántas veces más se repita), en el orden en que se detectó "
            "su repetición (el orden de su SEGUNDA aparición al recorrer la matriz fila por fila, "
            "valor por valor).",
            "El algoritmo debe usar conjuntos (seen/reported) para detectar repeticiones en una "
            "sola pasada, no una comparación O(n^2) elemento contra elemento.",
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
            "ordenadas de menor a mayor según len(word), sin mutar la lista original. "
            "Puede usarse cualquier algoritmo de ordenamiento (heapsort, quicksort, "
            "mergesort, bubble sort, etc.); no hace falta que el orden sea estable "
            "entre palabras de igual longitud. Este resultado determina el orden en "
            "que caen las palabras en la partida."
        ),
        broken_symptom=(
            "Empieza una partida nueva y fíjate si aparece la pantalla de "
            "carga con el tiempo de ordenamiento, y si las palabras caen "
            "de más cortas a más largas, o si aparecen en cualquier orden."
        ),
        signature="def sort_words_by_length(words: List[str]) -> List[str]:",
        requirements=[
            "NO debe mutar la lista words recibida (trabajar sobre una copia o construir listas "
            "nuevas).",
            "Debe devolver una lista nueva, del mismo tamaño que la de entrada, con las mismas "
            "palabras (incluyendo duplicados, sin perder ni duplicar ninguna) ordenadas "
            "ascendente según len(word).",
            "Palabras de la misma longitud pueden quedar en cualquier orden relativo entre sí "
            "(no es necesario que el ordenamiento sea estable).",
            "Debe manejar correctamente: lista vacía, una sola palabra, listas ya ordenadas, "
            "listas ordenadas al revés, y listas con muchas longitudes repetidas (el caso más "
            "común en este juego, no un caso borde).",
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
            "En 2048, cada movimiento desliza y fusiona una línea (fila o columna) del "
            "tablero, ya orientada hacia el borde al que se desliza. Hay que implementar "
            "Board._compress_and_merge(line) para que comprima los huecos, fusione cada "
            "par de fichas iguales una sola vez por turno (una línea [2,2,2,2] da [4,4], "
            "no [8,0] ni [4,2,2]), y vuelva a rellenar con ceros hasta el tamaño original, "
            "devolviendo también los puntos ganados y el desplazamiento de cada ficha para "
            "poder animarlo."
        ),
        broken_symptom=(
            "Prueba mover el tablero con las flechas -- fíjate si las "
            "fichas realmente se deslizan, se fusionan al chocar dos "
            "iguales, o si aparece una ficha nueva después de mover."
        ),
        signature=(
            "def _compress_and_merge(\n"
            "    line: List[int],\n"
            ") -> Tuple[List[int], int, bool, List[_LineShift]]:"
        ),
        requirements=[
            "Debe funcionar sobre una única línea (lista de enteros) ya orientada: el primer "
            "elemento es el más cercano al borde hacia el que se desliza.",
            "Debe comprimir los valores distintos de cero hacia el principio de la línea, "
            "sin cambiar su orden relativo.",
            "Cada ficha solo puede fusionarse UNA vez por movimiento: en [2,2,2,2] el "
            "resultado es [4,4], nunca [8,0] ni [4,2,2].",
            "Debe rellenar con ceros al final hasta recuperar el tamaño original de la línea.",
            "Debe devolver una tupla (linea_resultante, puntos_obtenidos, hubo_cambio, "
            "desplazamientos): los puntos son la suma de los valores nuevos creados por "
            "cada fusión, hubo_cambio es False si el resultado es idéntico a la entrada, y "
            "desplazamientos trae un registro por cada ficha original (indice de origen, "
            "indice de destino, valor, si se fusiono).",
            "No debe mutar la lista `line` recibida.",
        ],
        examples=(
            "line = [2, 2, 2, 4]\n"
            "- Resultado: [4, 2, 4, 0]\n"
            "- Puntos obtenidos: 4 (por la fusión 2+2)\n"
            "- hubo_cambio: True\n\n"
            "line = [2, 2, 2, 2]\n"
            "- Resultado: [4, 4, 0, 0]\n"
            "- Puntos obtenidos: 8 (dos fusiones independientes de 4 cada una)\n\n"
            "line = [4, 0, 0, 2]\n"
            "- Resultado: [4, 2, 0, 0] (se comprime pero no hay fusión; hubo_cambio: True)\n\n"
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
            "El autómata celular de este juego guarda su estado como una matriz de "
            "booleanos (viva/muerta). Hay que implementar next_generation(matrix, blocked) "
            "para que calcule la siguiente generación aplicando las reglas clásicas de "
            "Conway (B3/S23): una celda viva con 2 o 3 vecinas vivas sobrevive, una celda "
            "muerta con exactamente 3 vecinas vivas nace, y en cualquier otro caso queda "
            "(o sigue) muerta. Los vecinos son los 8 que rodean cada celda (incluidas las "
            "diagonales). Las coordenadas en `blocked` representan paredes: nunca pueden "
            "tener vida, sin importar lo que digan las reglas."
        ),
        broken_symptom=(
            "Coloca algunas células vivas y avanza una generación -- "
            "fíjate si el tablero realmente cambia según nacen/mueren "
            "células, o si se queda exactamente igual."
        ),
        signature=(
            "def next_generation(\n"
            "    matrix: List[List[bool]], blocked: Set[Coord] = frozenset()\n"
            ") -> List[List[bool]]:"
        ),
        requirements=[
            "Debe devolver una matriz NUEVA (misma cantidad de filas y columnas que "
            "matrix), sin mutar la matriz de entrada.",
            "Una celda viva con 2 o 3 vecinas vivas sobrevive a la siguiente generación.",
            "Una celda muerta con exactamente 3 vecinas vivas nace en la siguiente "
            "generación.",
            "Cualquier otra celda (viva con menos de 2 o más de 3 vecinas, o muerta con "
            "una cantidad de vecinas distinta de 3) queda muerta.",
            "Los vecinos de una celda son las 8 celdas que la rodean (arriba, abajo, "
            "izquierda, derecha y las 4 diagonales); las celdas fuera del borde de la "
            "matriz no cuentan como vecinas.",
            "Ninguna celda cuya coordenada esté en `blocked` puede tener vida en el "
            "resultado, sin importar lo que digan las reglas de nacimiento/supervivencia.",
            "Debe funcionar para matrices vacías o de cualquier tamaño rectangular (no "
            "asumir que es cuadrada).",
        ],
        examples=(
            "Con blocked vacío (juego clásico de Conway), un patrón \"parpadeante\" "
            "(blinker) de 3 celdas en línea horizontal se convierte en 3 celdas en línea "
            "vertical en la siguiente generación, y vuelve a horizontal en la generación "
            "después de esa (oscila con período 2).\n\n"
            "Una celda viva completamente aislada (sin vecinas vivas) muere en la "
            "siguiente generación (menos de 2 vecinas).\n\n"
            "Una celda muerta con exactamente 3 vecinas vivas nace, aunque esas 3 vecinas "
            "después mueran por otras reglas -- todas las celdas de la nueva generación se "
            "calculan a partir del mismo estado anterior, nunca de resultados ya "
            "actualizados.\n\n"
            "Si una coordenada está en `blocked`, debe quedar muerta en el resultado "
            "incluso si tiene exactamente 3 vecinas vivas."
        ),
    ),
}


def get_challenge(game_name: str) -> Challenge | None:
    return CHALLENGES.get(game_name)
