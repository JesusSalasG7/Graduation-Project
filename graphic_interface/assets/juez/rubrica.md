# Rúbrica y prompt del juez

El juez (Claude) puntúa cada prompt en cinco dimensiones y en un nivel global del 1 al 4, comparándolo con la especificación de referencia del desafío. El nivel global es el que se compara con el nivel pretendido del dataset sintético.

## Dimensiones

Cada dimensión se puntúa del 1 al 4 comparando el prompt con la ficha del desafío. Un dato **incorrecto** pesa más que uno ausente: si el prompt afirma algo que contradice la ficha, la dimensión no puede pasar de 2.

| Dimensión | 1 | 2 | 3 | 4 |
| --- | --- | --- | --- | --- |
| **Especificación** (firma, parámetros, tipos, retorno) | No nombra la función ni qué devuelve | Nombra la función, pero el retorno falta o es incorrecto | Firma y retorno correctos, sin tipos o con algún detalle impreciso | Firma completa con tipos y retorno exactos |
| **Comportamiento** (qué hace la función) | Describe el juego o pide "hazlo" sin regla | Idea general correcta, pero omite una regla central o contiene un error de comprensión | Reglas centrales correctas; falta algún detalle secundario | Todas las reglas de la ficha, sin errores |
| **Restricciones** (complejidad, qué usar o no, no mutar) | Ninguna | Alguna, o una que contradice la ficha | La mayoría, sin contradicciones | Todas las de la ficha |
| **Casos borde** | Ninguno | Uno, o uno tratado incorrectamente | Varios correctos; falta alguno relevante | Los de la ficha, correctos |
| **Contexto y verificación** (datos del juego, ejemplos, criterio de prueba) | Ningún dato que la IA aislada necesite | Algún dato, insuficiente para implementar sin adivinar | Contexto suficiente, sin ejemplos ni criterio de prueba | Contexto suficiente y al menos un ejemplo o criterio de prueba correcto |

Si la ficha de un desafío no tiene restricciones o casos borde aplicables, el juez puntúa esa dimensión según lo que la ficha sí exige y lo justifica en el razonamiento.

## Nivel global

El juez asigna el nivel global después de puntuar las cinco dimensiones, con las mismas definiciones que se usaron para generar el dataset sintético:

| Nivel | Definición |
| --- | --- |
| 1 · Pobre | Vago, sin firma ni reglas; una IA aislada no podría resolverlo sin adivinar. |
| 2 · Regular | Menciona la función y la idea general, pero omite reglas importantes, restricciones o casos borde, o contiene un error de comprensión. |
| 3 · Bueno | Firma y comportamiento correctos y la mayoría de las restricciones; le falta algún caso borde, ejemplo o detalle de contexto. |
| 4 · Excelente | Firma, comportamiento, restricciones, casos borde y contexto completos, con algún ejemplo o criterio para verificar. |

Dos reglas para que el nivel global sea coherente con las dimensiones:

- Un error de comprensión en Comportamiento o Restricciones limita el nivel global a 2.
- El nivel global no es el promedio de las dimensiones: es un juicio sobre si una IA que solo ve ese prompt podría implementar la función correctamente.

## Reglas del juez

Estas reglas van dentro del prompt del juez y apuntan a los sesgos que el estudio va a medir.

1. **Evalúa comprensión, no redacción.** No penalices errores de ortografía, falta de tildes, informalidad ni variantes regionales del español.
2. **No premies la longitud.** Un prompt corto y preciso puede obtener 4; uno largo con un error de comprensión no pasa de 2.
3. **Solo cuenta lo escrito.** No completes lo que el estudiante "probablemente quiso decir" con lo que sabes por la ficha.
4. **Equivalencias válidas.** Acepta descripciones correctas con otras palabras (por ejemplo, "se lee igual al revés" equivale a "palíndromo").
5. **Cita evidencia.** Antes de cada puntaje, copia el fragmento del prompt que lo justifica, o indica que no hay.
6. **Rutas de archivo.** Mencionar el archivo o la ruta no suma ni resta: la IA aislada no los necesita para implementar la función.

## Plantilla del prompt del juez

El script reemplaza `{rubrica}`, `{reglas}`, `{ficha}`, `{prompt}` y `{formato}`. Las dos primeras son las secciones Dimensiones, Nivel global y Reglas de este documento; `{ficha}` es la sección del desafío en las especificaciones de referencia y `{formato}` es el bloque JSON de la sección Formato de salida.

```text
Eres un evaluador experto en comprensión de programas. Evaluarás el prompt
que un estudiante de pregrado escribió para que una IA implemente una función.

Contexto del estudio: la IA que recibe el prompt está aislada. No ve el
enunciado ni el código del juego; solo ve el prompt. Por eso el prompt debe
comunicar todo lo necesario, y su calidad refleja cuánto entendió el
estudiante la tarea. Evalúa esa comprensión, no la calidad de la redacción.

<especificacion_de_referencia>
{ficha}
</especificacion_de_referencia>

<rubrica>
{rubrica}
</rubrica>

<reglas>
{reglas}
</reglas>

<prompt_del_estudiante>
{prompt}
</prompt_del_estudiante>

Instrucciones:
1. Para cada dimensión, en este orden: especificacion, comportamiento,
   restricciones, casos_borde, contexto_verificacion, escribe primero la
   evidencia (fragmentos textuales del prompt, o "ninguna"), luego un
   razonamiento breve que la compare con la especificación, y al final el
   puntaje del 1 al 4.
2. Después asigna el nivel_global del 1 al 4 con su justificación.
3. Responde únicamente con el JSON del formato indicado, sin texto antes
   ni después.

<formato_de_salida>
{formato}
</formato_de_salida>
```

## Formato de salida

El orden de los campos obliga al juez a citar evidencia y razonar antes de puntuar.

```json
{
  "dimensiones": {
    "especificacion":        {"evidencia": "...", "razonamiento": "...", "puntaje": 1},
    "comportamiento":        {"evidencia": "...", "razonamiento": "...", "puntaje": 1},
    "restricciones":         {"evidencia": "...", "razonamiento": "...", "puntaje": 1},
    "casos_borde":           {"evidencia": "...", "razonamiento": "...", "puntaje": 1},
    "contexto_verificacion": {"evidencia": "...", "razonamiento": "...", "puntaje": 1}
  },
  "nivel_global": {"justificacion": "...", "puntaje": 1}
}
```

El script valida que estén los seis puntajes y que sean enteros del 1 al 4. Si la respuesta no es JSON válido, reintenta una vez y, si vuelve a fallar, registra el error sin descartar el prompt.

## Configuración de las llamadas

| Parámetro | Valor |
| --- | --- |
| Acceso | API de Anthropic (no el CLI de la aplicación, que no permite fijar la temperatura) |
| Modelo | `claude-sonnet-5-5`, fijo durante todo el estudio (`JUDGE_MODEL` en `judge/judge_config.py`) |
| Temperatura | 0 |
| Repeticiones | 3 por prompt; se usa la mediana de cada puntaje |
| Orden | Aleatorio con semilla fija, para que los prompts de un mismo nivel o generador no vayan seguidos |
| Registro por llamada | id del prompt, repetición, modelo, versión de la plantilla, fecha, respuesta completa y puntajes |

**El juez no recibe:** el nivel pretendido, el generador, el número de palabras ni la nota de otras repeticiones. Esos campos se usan solo en el análisis.

## Decisiones para revisar con el tutor

- [ ] ¿Las cinco dimensiones cubren lo que la tesis entiende por comprensión del código, o falta alguna?
- [ ] ¿Un error de comprensión debe limitar el nivel global a 2, o solo bajar la dimensión afectada?
- [ ] ¿Una sola llamada con las cinco dimensiones, o una llamada por dimensión? Una llamada es más barata; separarlas reduce el efecto halo entre dimensiones.
- [ ] ¿Mediana de 3 repeticiones, o más repeticiones si la consistencia sale baja en la prueba?
- [ ] ¿Qué versión de Claude se usará como juez, y cómo se justifica en la tesis?
