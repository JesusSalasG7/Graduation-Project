"""Banco estatico de preguntas de seleccion multiple sobre el ENUNCIADO de
cada desafio (Etapa 1 de la sesion guiada).

A diferencia de las preguntas sobre la solucion (que dependen del codigo que
genera cada participante y por eso se generan dinamicamente, ver
challenge_solver.py), el enunciado es el mismo para todos los participantes,
asi que estas preguntas estan escritas a mano una sola vez por juego -- 7
preguntas de dificultad moderada, verificadas contra el enunciado real de
challenges.py.
"""

from quiz import QuizQuestion

STATEMENT_QUESTIONS: dict[str, list[QuizQuestion]] = {
    "Game-01": [
        QuizQuestion(
            "¿Qué representa exactamente el valor que debe devolver count_apples_in_range()?",
            [
                "La suma de los valores de las manzanas dentro del rango",
                "La cantidad de manzanas cuyo valor está dentro del rango activo (límites inclusive)",
                "La cantidad total de manzanas en el tablero, sin importar el filtro",
                "El valor máximo entre las manzanas que pasan el filtro",
            ],
            1,
        ),
        QuizQuestion(
            "Según el enunciado, los límites del rango [filter_min, filter_max] son...",
            [
                "Exclusivos (no cuentan los extremos)",
                "Solo el mínimo es inclusivo",
                "Inclusive en ambos extremos",
                "Solo el máximo es inclusivo",
            ],
            2,
        ),
        QuizQuestion(
            "¿Qué método ya existente debe reutilizarse para decidir si una manzana individual pasa el filtro?",
            ["count_apples_in_range()", "_apple_passes_filter(value)", "food_field.apples()", "_update_range_bonus()"],
            1,
        ),
        QuizQuestion(
            "Con valores = [-5, +5, +15, +5, -5, +15], ¿cuál es el resultado esperado para el rango [-5, 5]?",
            ["2", "4", "6", "0"],
            1,
        ),
        QuizQuestion(
            "¿Qué complejidad temporal se pide para la solución?",
            [
                "O(n²), comparando cada manzana con todas las demás",
                "O(log n), usando búsqueda binaria",
                "O(n), con una sola pasada sobre la lista",
                "O(1), sin importar la cantidad de manzanas",
            ],
            2,
        ),
        QuizQuestion(
            "Si self.food_field.apples está vacía, ¿qué debe devolver la función?",
            ["None", "Una excepción (ValueError)", "0", "-1"],
            2,
        ),
        QuizQuestion(
            "¿Qué partes del juego consumen el resultado de count_apples_in_range(), según el enunciado?",
            [
                "Solo el sistema de puntuación final",
                "El HUD \"En rango: N/Total\" y el bono periódico de puntos del modo Desafío",
                "La generación aleatoria de nuevas manzanas",
                "El sistema de colisiones de la serpiente",
            ],
            1,
        ),
    ],
    "Game-04": [
        QuizQuestion(
            "¿Cuándo se considera que una señal \"conserva su patrón\" (es estable)?",
            [
                "Cuando tiene un número par de caracteres",
                "Cuando se lee exactamente igual en sentido inverso, carácter por carácter",
                "Cuando todas sus letras son mayúsculas",
                "Cuando no contiene espacios ni símbolos",
            ],
            1,
        ),
        QuizQuestion(
            "¿Qué debe devolver is_stable_signal(\"\") (cadena vacía)?",
            ["False", "None", "True", "Lanza una excepción"],
            2,
        ),
        QuizQuestion(
            "¿La comparación debe normalizar mayúsculas/minúsculas o espacios antes de comparar?",
            [
                "Sí, todo se pasa a mayúsculas primero",
                "Sí, se eliminan los espacios",
                "No, se compara carácter por carácter tal cual viene el texto",
                "Solo se normalizan los acentos",
            ],
            2,
        ),
        QuizQuestion(
            "¿Cuál de estas palabras es estable (True) según los casos de prueba dados?",
            ["PYTHON", "CIRCUITO", "ANILINA", "VENTANA"],
            2,
        ),
        QuizQuestion(
            "¿Qué tipo de dato exacto debe devolver la función?",
            ["Un entero (0 o 1)", "Un string (\"True\"/\"False\")", "Un bool puro", "Cualquier valor \"truthy\""],
            2,
        ),
        QuizQuestion(
            "¿Cuánto tiempo tiene el jugador para responder en cada ronda, según el enunciado?",
            ["2 segundos", "4 segundos", "10 segundos", "No hay límite de tiempo"],
            1,
        ),
        QuizQuestion(
            "¿Qué característica particular tiene la regla de verificación dentro del juego?",
            [
                "Se explica en una pantalla de instrucciones antes de cada ronda",
                "Cambia aleatoriamente en cada partida",
                "Nunca se explica en pantalla; el jugador debe inferirla jugando",
                "Se muestra como pista después de fallar una vez",
            ],
            2,
        ),
    ],
    "Game-05": [
        QuizQuestion(
            "¿Qué debe devolver find_repeated(matrix)?",
            [
                "Todos los valores de la matriz, sin repetir",
                "Los valores que aparecen 2 o más veces, cada uno una sola vez",
                "La cantidad total de valores repetidos",
                "Solo el valor que más se repite",
            ],
            1,
        ),
        QuizQuestion(
            "Según el enunciado, ¿en qué orden deben aparecer los valores repetidos en el resultado?",
            [
                "De mayor a menor valor",
                "En el orden de su primera aparición",
                "En el orden en que se detectó su repetición (su segunda aparición)",
                "En orden alfabético/numérico ascendente",
            ],
            2,
        ),
        QuizQuestion(
            "¿Qué estructura de datos es el \"Key Concept\" para resolver esto en una sola pasada?",
            [
                "Una lista ordenada con búsqueda binaria",
                "Un diccionario de conteo con sort() al final",
                "Conjuntos (sets) para marcar valores ya vistos y ya reportados",
                "Una matriz auxiliar del mismo tamaño",
            ],
            2,
        ),
        QuizQuestion(
            "Con find_repeated([[1, 2, 2, 3], [3, 1, 4]]), ¿cuál es el resultado exacto esperado?",
            ["[1, 2, 3]", "[2, 3, 1]", "[2, 3]", "[1, 2, 2, 3, 3, 1]"],
            1,
        ),
        QuizQuestion(
            "Si un valor aparece 3 o más veces en la matriz, ¿cuántas veces debe aparecer en el resultado?",
            ["Tantas veces como se repita", "Dos veces", "Una sola vez", "Ninguna, se descartan"],
            2,
        ),
        QuizQuestion(
            "¿La matriz de entrada debe asumirse cuadrada (mismo número de filas y columnas)?",
            [
                "Sí, siempre es cuadrada",
                "No, ni siquiera se asume que todas las filas midan igual",
                "Sí, pero solo en Transmutación Arcana",
                "No se puede saber sin ejecutar el código",
            ],
            1,
        ),
        QuizQuestion(
            "En el juego real, ¿qué evento del tablero genera la \"línea\" que se analiza con este algoritmo?",
            [
                "El movimiento aleatorio de fichas al iniciar la partida",
                "La Regla de Catálisis, que limpia una fila o columna completa",
                "El cálculo del daño del hechizo",
                "La generación de nuevas fichas al caer por gravedad",
            ],
            1,
        ),
    ],
    "Game-06": [
        QuizQuestion(
            "¿Según qué criterio deben ordenarse las palabras?",
            [
                "Orden alfabético",
                "La longitud de cada palabra (len(word)), ascendente",
                "La frecuencia de uso de la palabra",
                "El orden en que fueron generadas, invertido",
            ],
            1,
        ),
        QuizQuestion(
            "¿Qué debe pasar con la lista `words` original que recibe la función?",
            [
                "Se ordena \"in place\" para ahorrar memoria",
                "No debe mutarse; hay que trabajar sobre una copia o construir listas nuevas",
                "Se vacía y se rellena con el resultado ordenado",
                "Se convierte en un set para eliminar duplicados",
            ],
            1,
        ),
        QuizQuestion(
            "Si dos palabras tienen la misma longitud, ¿en qué orden relativo deben quedar entre sí?",
            [
                "Deben mantener el orden original (ordenamiento estable) obligatoriamente",
                "Alfabético entre ellas",
                "Puede ser cualquiera; no es necesario que el ordenamiento sea estable",
                "Deben quedar en orden inverso al original",
            ],
            2,
        ),
        QuizQuestion(
            "¿Qué está explícitamente prohibido usar para implementar el ordenamiento?",
            ["Recursión", "sorted() o list.sort() de Python", "Funciones auxiliares", "Comparar por len(word)"],
            1,
        ),
        QuizQuestion(
            "¿Cuál de estos casos aclara el enunciado que NO es un caso borde, sino el más común en el juego?",
            [
                "Lista vacía",
                "Una sola palabra",
                "Listas con muchas longitudes repetidas",
                "Listas ya ordenadas al revés",
            ],
            2,
        ),
        QuizQuestion(
            "Si la función recibe una lista con palabras duplicadas, ¿cómo debe ser la lista resultado?",
            [
                "Puede tener menos elementos si hay duplicados de longitud",
                "Del mismo tamaño, con las mismas palabras (incluyendo duplicados)",
                "Siempre debe eliminar los duplicados",
                "Debe agrupar los duplicados en una sublista",
            ],
            1,
        ),
        QuizQuestion(
            "¿Qué algoritmos se recomiendan explícitamente en el enunciado para esta tarea?",
            ["Bubble sort únicamente", "Búsqueda binaria y bubble sort", "Mergesort, heapsort o quicksort", "Counting sort obligatoriamente"],
            2,
        ),
    ],
    "Game-03": [
        QuizQuestion(
            "¿Cuál es la estrategia general que debe usar find_3d_pattern?",
            [
                "Ordenar ambas matrices y compararlas directamente",
                "Deslizar la matriz patrón por todas las posiciones válidas de la matriz grande y comparar elemento por elemento",
                "Usar una tabla hash de todos los bloques posibles",
                "Convertir las matrices 3D en strings y usar búsqueda de substrings",
            ],
            1,
        ),
        QuizQuestion(
            "¿Qué debe devolver la función exactamente?",
            [
                "Solo un booleano indicando si se encontró o no",
                "Un diccionario con \"found\" (bool) y \"position\" (tupla o None)",
                "La lista de todas las posiciones donde coincide el patrón",
                "El número de coincidencias encontradas",
            ],
            1,
        ),
        QuizQuestion(
            "Si el patrón no entra en la matriz grande en algún eje (es más grande), ¿qué debe pasar?",
            [
                "Debe lanzar una excepción ValueError",
                "Debe devolver found=False sin lanzar excepciones",
                "Debe recortar el patrón para que quepa",
                "Debe devolver found=True con position=None",
            ],
            1,
        ),
        QuizQuestion(
            "¿Qué significa \"corte temprano\" en el algoritmo pedido?",
            [
                "Detener todo el programa apenas se encuentra un error",
                "Abandonar una posición candidata en cuanto una celda no coincide, sin seguir comparando el resto del bloque",
                "Limitar la búsqueda a las primeras 10 posiciones",
                "Cortar la matriz grande por la mitad antes de buscar",
            ],
            1,
        ),
        QuizQuestion(
            "Si el patrón coincide en más de una posición de la matriz grande, ¿cuál debe devolver la función?",
            [
                "Todas las posiciones donde coincide",
                "La última posición encontrada",
                "La primera posición encontrada, recorriendo en orden x, luego y, luego z; deja de buscar ahí",
                "La posición más cercana al centro de la matriz",
            ],
            2,
        ),
        QuizQuestion(
            "Un patrón relleno completamente con el valor 99 (que no existe en ninguna celda del cubo), ¿qué resultado debe dar?",
            [
                "Se encuentra en (0,0,0) por defecto",
                "Nunca debe encontrarse (found=False)",
                "Lanza una excepción porque 99 es inválido",
                "Depende de si el cubo está resuelto o no",
            ],
            1,
        ),
        QuizQuestion(
            "¿Qué optimización NO debe usarse, ya que el enunciado pide explícitamente fuerza bruta?",
            [
                "Corte temprano al comparar un bloque",
                "Recorrer solo posiciones donde el patrón cabe completo",
                "Hashing de bloques u otras optimizaciones para evitar la comparación elemento por elemento",
                "Calcular las dimensiones de ambas matrices antes de buscar",
            ],
            2,
        ),
    ],
    "Game-02": [
        QuizQuestion(
            "¿Qué debe hacer _compress_and_merge con los huecos (ceros) de la línea?",
            [
                "Dejarlos en su posición original",
                "Comprimir los valores distintos de cero hacia el principio de la línea, sin cambiar su orden relativo",
                "Eliminarlos y acortar la lista permanentemente",
                "Moverlos al principio de la línea",
            ],
            1,
        ),
        QuizQuestion(
            "Con la línea [2, 2, 2, 2], ¿cuál es el resultado correcto tras fusionar?",
            ["[8, 0, 0, 0]", "[4, 2, 2, 0]", "[4, 4, 0, 0]", "[2, 2, 2, 2] (no cambia)"],
            2,
        ),
        QuizQuestion(
            "¿Cuántas veces puede fusionarse una misma ficha en un solo movimiento?",
            [
                "Tantas veces como encuentre una ficha igual",
                "Dos veces como máximo",
                "Una sola vez",
                "Depende del valor de la ficha",
            ],
            2,
        ),
        QuizQuestion(
            "¿Qué representa el segundo elemento de la tupla que devuelve _compress_and_merge?",
            [
                "La cantidad de fichas que se fusionaron",
                "Los puntos obtenidos: la suma de los valores nuevos creados por cada fusión",
                "El índice de la última ficha movida",
                "El valor máximo alcanzado en la línea",
            ],
            1,
        ),
        QuizQuestion(
            "¿Cuándo debe ser False el \"hubo_cambio\" que devuelve la función?",
            [
                "Cuando la línea tiene algún cero",
                "Cuando el resultado es idéntico a la línea de entrada",
                "Cuando no hubo ninguna fusión, aunque se hayan movido fichas",
                "Siempre que la línea ya tenga 4 elementos",
            ],
            1,
        ),
        QuizQuestion(
            "¿Qué guarda cada elemento de la lista de \"desplazamientos\" que devuelve la función?",
            [
                "Solo el valor final de cada celda",
                "El índice de origen, el índice de destino, el valor y si esa ficha se fusionó",
                "Las coordenadas (fila, columna) reales del tablero",
                "La cantidad total de fichas en la línea",
            ],
            1,
        ),
        QuizQuestion(
            "¿La función puede modificar (mutar) la lista `line` que recibe como argumento?",
            [
                "Sí, para ahorrar memoria",
                "No, debe devolver un resultado nuevo sin mutar la entrada",
                "Solo si hay una fusión",
                "Sí, pero debe restaurarla al final",
            ],
            1,
        ),
    ],
    "Game-07": [
        QuizQuestion(
            "Según la regla B3/S23, ¿cuándo sobrevive una celda que ya está viva?",
            [
                "Con cualquier cantidad de vecinas vivas",
                "Con exactamente 3 vecinas vivas",
                "Con 2 o 3 vecinas vivas",
                "Con menos de 2 vecinas vivas",
            ],
            2,
        ),
        QuizQuestion(
            "¿Cuándo nace una celda que está muerta?",
            [
                "Con 2 o 3 vecinas vivas",
                "Con exactamente 3 vecinas vivas",
                "Con cualquier cantidad de vecinas vivas mayor a 0",
                "Nunca puede nacer una celda muerta",
            ],
            1,
        ),
        QuizQuestion(
            "¿Cuántas celdas vecinas se consideran para cada celda?",
            [
                "4 (arriba, abajo, izquierda, derecha)",
                "8, incluidas las diagonales",
                "6, sin contar las esquinas diagonales opuestas",
                "Depende del tamaño de la matriz",
            ],
            1,
        ),
        QuizQuestion(
            "¿Qué debe pasar con una celda cuya coordenada está en `blocked`?",
            [
                "Puede tener vida si cumple las reglas de nacimiento",
                "Nunca puede tener vida, sin importar las reglas",
                "Se ignora por completo y no aparece en el resultado",
                "Cuenta doble como vecina de las celdas cercanas",
            ],
            1,
        ),
        QuizQuestion(
            "¿La función puede modificar la matriz `matrix` que recibe?",
            [
                "Sí, actualiza las celdas en el lugar",
                "No, debe devolver una matriz nueva sin mutar la entrada",
                "Solo puede modificar las celdas bloqueadas",
                "Sí, pero solo si cambia de tamaño",
            ],
            1,
        ),
        QuizQuestion(
            "Al contar los vecinos vivos de una celda, ¿sobre qué generación deben contarse?",
            [
                "Sobre la matriz ya actualizada con los cambios de esta misma generación",
                "Sobre el mismo estado anterior para todas las celdas, nunca sobre resultados ya actualizados",
                "Sobre un promedio entre la generación actual y la anterior",
                "No importa, el resultado es el mismo de cualquier forma",
            ],
            1,
        ),
        QuizQuestion(
            "Las celdas fuera del borde de la matriz, ¿cuentan como vecinas vivas?",
            [
                "Sí, siempre se consideran vivas",
                "Sí, siempre se consideran muertas pero cuentan en el total",
                "No, no cuentan como vecinas",
                "Solo cuentan si la matriz es cuadrada",
            ],
            2,
        ),
    ],
}


def get_statement_questions(game_name: str) -> list[QuizQuestion]:
    return STATEMENT_QUESTIONS.get(game_name, [])
