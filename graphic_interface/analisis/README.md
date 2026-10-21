# Módulo de análisis EEG (`analisis/`)

Calcula, a partir de las señales de NeuroSky que ya registra la sesión
guiada, las features de carga cognitiva **EEG1** y **EEG2** descritas en el
artículo *"No Vibe Without Comprehension"*, y las muestra en la pestaña
**📈 Análisis** del panel. Por ahora solo procesa y reporta: no entrena
ningún modelo.

## 1. Propósito

El artículo usa dos índices EEG como indicadores de la carga cognitiva de
quien programa con IA:

- **EEG1 = θ / (α + β)**: esfuerzo mental y control atencional.
- **EEG2 = θ / α**: carga de la memoria de trabajo.

Este módulo calcula esos índices (más **α/θ** como control) para cada etapa
de la sesión guiada. Así se puede comparar la carga cognitiva entre leer el
enunciado, escribir el prompt, evaluar la respuesta de la IA y entender su
razonamiento. También deja preparada la conexión con una puntuación de
comprensión (0–6) para entrenar clasificadores más adelante.

## 2. Datos de entrada

**Fuente:** `data/dataset_sesiones.csv`, el dataset consolidado que genera
`data/build_dataset.py` (pestaña Sesión → "Generar dataset"). Cada fila es
**participante × desafío × etapa × intento**, solo de las etapas 2 a 5 (la
1 y la 6 no capturan sensores).

Las columnas `NeuroSky_*_List` son texto con forma de lista de Python
(`"[1434041, 1308949, ...]"`), con una muestra por segundo aproximadamente.
El módulo las convierte a números con `ast.literal_eval`.

| Columna | Uso | Motivo |
| --- | --- | --- |
| `NeuroSky_Theta_List` | Feature principal | θ, numerador de EEG1 y EEG2 |
| `NeuroSky_LowAlpha_List`, `NeuroSky_HighAlpha_List` | Feature principal | Se suman para obtener α |
| `NeuroSky_LowBeta_List`, `NeuroSky_HighBeta_List` | Feature principal | Se suman para obtener β |
| `NeuroSky_PoorSignal_List` | Filtro de calidad | Indica si el electrodo tenía buen contacto en cada muestra |
| `NeuroSky_Delta_List` | Control de artefactos | Los parpadeos y movimientos en la frente inflan δ |
| `NeuroSky_Attention_List`, `NeuroSky_Meditation_List` | Opcional, se reporta aparte | Índices eSense **propietarios** de NeuroSky: no se sabe cómo se calculan, por eso no se mezclan con EEG1/EEG2 |
| `NeuroSky_LowGamma_List`, `NeuroSky_MidGamma_List` | Se ignoran | Gamma, en un electrodo frontal, está dominada por ruido muscular (frente, mandíbula) |
| `NeuroSky_*_Promedio` | Se ignoran | Incluyen las muestras con mala señal; aquí se recalcula todo desde las listas ya filtradas |

También se copian las columnas de identificación `Participante_ID`,
`Nivel_Experiencia`, `Desafio`, `Juego`, `Etapa` e `Intento`.

## 3. Pipeline paso a paso

Se aplica a cada fila del dataset, es decir, a cada etapa de cada intento.

1. **Parseo y alineación.** Las listas se convierten a números y se alinean
   por índice (la muestra *i* de cada banda es el mismo segundo). Si tienen
   largos distintos, se recortan a la más corta y se registra una
   advertencia en la columna `Advertencias`.
2. **Filtro de calidad.** Se conservan solo las muestras con
   `PoorSignal <= 0` (umbral configurable). Las de 200 (electrodo sin
   contacto) se descartan siempre. La etapa se marca como **datos
   insuficientes** si quedan menos de 10 muestras válidas o menos del 50 %
   del total. *Motivo:* con mal contacto, las potencias de banda son ruido.
3. **Bandas combinadas**, por muestra:
   - α = LowAlpha + HighAlpha
   - β = LowBeta + HighBeta
4. **Transformación logarítmica**, `log(x + 1)` sobre θ, α, β y δ.
   *Motivo:* las potencias de NeuroSky varían en varios órdenes de magnitud
   y tienen colas largas. El logaritmo evita que unos pocos picos dominen
   las medias. El `+1` evita `log(0)`.
5. **Índices por muestra**, sobre las bandas ya transformadas:
   - EEG1 = θ / (α + β)
   - EEG2 = θ / α
   - AlphaTheta = α / θ

   Si un denominador es 0, el índice de esa muestra queda vacío (NaN) en
   lugar de producir un infinito.
6. **Agregados por etapa:** media, mediana, desviación estándar (muestral),
   mínimo y máximo de EEG1, EEG2 y AlphaTheta; mediana de log θ; media de
   log δ como indicador de artefactos; muestras válidas y % descartado.
7. **Normalización contra la línea base.** No se grabó una etapa de
   reposo, así que la línea base es la **Etapa 2 (leer el enunciado) del
   mismo participante y desafío**, en su primer intento:

   `cambio_% = (valor_etapa − valor_base) / valor_base × 100`

   *Motivo:* las potencias absolutas varían mucho entre personas (grosor
   del cráneo, colocación del electrodo). El cambio % expresa cada etapa
   respecto al propio participante. Si la línea base no existe o tiene datos
   insuficientes, el cambio % queda vacío y se avisa en la pestaña.
8. **Z-score y Min-Max dentro de cada participante**, en columnas
   separadas, usando solo sus etapas con datos suficientes:
   - `z = (x − media) / desviación estándar` (poblacional, ddof = 0)
   - `minmax = (x − mín) / (máx − mín)`, de 0 a 1

   Si todas las etapas del participante valen lo mismo, ambos dan 0.
9. **eSense.** Media y mediana de Attention y Meditation sobre las
   muestras válidas. También se descartan los 0, porque indican que el
   chip todavía no había calculado el valor.

Al final, el **indicador de δ alta** marca una etapa si la media de log δ
supera en más de 2 desviaciones estándar la media del participante.

## 4. Interpretación de resultados

- **EEG1 alto:** más θ en relación con α + β, lo que se asocia a mayor
  esfuerzo mental o mayor demanda de control atencional.
- **EEG2 alto:** más θ en relación con α, lo que se asocia a mayor carga
  de la memoria de trabajo. α suele bajar cuando la persona se concentra.
- **Valores bajos:** menor esfuerzo o carga, o un estado más relajado
  (α alta).
- **Miden esfuerzo, no comprensión.** Un participante puede esforzarse
  mucho y no entender, o entender sin esfuerzo. La relación con la
  comprensión es justamente lo que se quiere estudiar más adelante.
- **Solo son comparables dentro del mismo participante**, o entre
  participantes después de normalizar (cambio %, z-score o Min-Max). Los
  valores crudos de dos personas distintas no deben compararse
  directamente.
- Como los cocientes se calculan sobre bandas en escala logarítmica, sus
  valores varían poco (por ejemplo, EEG1 ≈ 0,51–0,56 en los datos
  actuales). Un cambio del 1–5 % ya es una diferencia apreciable dentro de
  un participante.

## 5. Salidas

### Tabla de features (CSV)

El botón **💾 Exportar CSV** guarda `data/analisis/eeg_features.csv`, con
una fila por participante × desafío × etapa × intento. La carpeta está en
el `.gitignore` porque son datos de participantes.

| Columna | Descripción |
| --- | --- |
| `Participante_ID`, `Nivel_Experiencia`, `Desafio`, `Juego`, `Etapa`, `Intento` | Identificación, copiada del dataset |
| `Muestras_Totales` | Muestras de la etapa después de alinear las listas |
| `Muestras_Validas` | Muestras que pasaron el filtro de PoorSignal |
| `Pct_Descartado` | % de muestras descartadas |
| `Datos_Insuficientes` | True si quedaron menos del mínimo de muestras o de % válido |
| `Advertencias` | Avisos de la etapa (listas recortadas, datos insuficientes, columnas faltantes) |
| `EEG1_Media`, `EEG1_Mediana`, `EEG1_DE`, `EEG1_Min`, `EEG1_Max` | Agregados de EEG1 = θ/(α+β) |
| `EEG2_Media` … `EEG2_Max` | Agregados de EEG2 = θ/α |
| `AlphaTheta_Media` … `AlphaTheta_Max` | Agregados de α/θ |
| `Theta_Mediana` | Mediana de log(θ + 1) |
| `Delta_Media` | Media de log(δ + 1): indicador de artefactos |
| `eSense_Attention_Media`, `eSense_Attention_Mediana` | Atención eSense (propietario NeuroSky) |
| `eSense_Meditation_Media`, `eSense_Meditation_Mediana` | Meditación eSense (propietario NeuroSky) |
| `<feature>_Cambio_Pct` | Cambio % contra la línea base, para `EEG1_Media`, `EEG1_Mediana`, `EEG2_Media`, `EEG2_Mediana`, `AlphaTheta_Media`, `AlphaTheta_Mediana` y `Theta_Mediana` |
| `Linea_Base_Disponible` | True si la fila tiene línea base válida y datos suficientes |
| `<feature>_Z` | Z-score de esas mismas 7 features dentro del participante |
| `<feature>_MinMax` | Min-Max (0–1) de esas mismas 7 features dentro del participante |
| `Delta_Media_Z` | Z-score de `Delta_Media` dentro del participante |
| `Delta_Atipica` | True si `Delta_Media_Z` > 2: posibles parpadeos o artefactos |
| `Comprension_Puntaje` | Puntuación de comprensión 0–6. Vacía por ahora (ver sección 9) |
| `Comprension_Alta` | Puntaje binarizado (> 3,5). Vacía por ahora |

### Pestaña "📈 Análisis"

- **Selector de participante:** "Todos" o un participante. Filtra el
  gráfico, la tabla y los indicadores.
- **🔄 Recalcular:** vuelve a leer el dataset (por ejemplo, después de
  regenerarlo). Las features se calculan solas la primera vez que se abre
  la pestaña.
- **💾 Exportar CSV:** guarda la tabla completa de features.
- **Cómo leer estos valores:** nota de que EEG1/EEG2 miden esfuerzo, no
  comprensión, y de cuándo son comparables.
- **Calidad de la señal:** % de muestras descartadas por etapa, lista de
  etapas con datos insuficientes, etapas con δ atípicamente alta y filas
  sin línea base.
- **Gráfico EEG1 y EEG2 por etapa:** barras con el cambio % medio contra la
  línea base (la Etapa 2 vale 0 por definición) y, encima de cada barra,
  el valor medio de EEG1/EEG2. Bajo cada etapa se indica *n*, las filas
  promediadas. Solo usa filas con datos suficientes. Si no hubiera línea
  base, grafica los valores medios y lo avisa.
- **Tabla de features por etapa:** las columnas principales. Las filas con
  datos insuficientes se ven en naranja y las de δ alta en rojo. El CSV
  trae todas las columnas.

## 6. Parámetros configurables

Están en `graphic_interface/analisis/config.py`. Se cambian editando la
constante; las funciones las reciben agrupadas en `AnalysisConfig`.

| Parámetro | Constante | Valor por defecto |
| --- | --- | --- |
| Umbral de PoorSignal (se conserva ≤ umbral; 200 siempre se descarta) | `POOR_SIGNAL_THRESHOLD` | `0` |
| Mínimo de muestras válidas por etapa | `MIN_VALID_SAMPLES` | `10` |
| Mínimo de fracción válida por etapa | `MIN_VALID_FRACTION` | `0.5` (50 %) |
| Etapa de línea base | `BASELINE_STAGE` | `2` (leer el enunciado, mismo desafío) |
| Umbral de la alerta de δ (z-score) | `DELTA_ALERT_Z` | `2.0` |
| Umbral de binarización de la comprensión | `COMPREHENSION_THRESHOLD` | `3.5` |
| Dataset de entrada | `DATASET_FILE` | `data/dataset_sesiones.csv` |
| CSV de salida | `FEATURES_OUT_FILE` | `data/analisis/eeg_features.csv` |

## 7. Limitaciones

- **Un solo electrodo en Fp1** (frente, lado izquierdo). El artículo mide θ
  en sitios frontales y centrales de la línea media (Fz/Cz), donde la
  actividad θ ligada a la carga cognitiva es más clara. Fp1 es una
  aproximación.
- **Contaminación por parpadeos y movimientos oculares.** Fp1 está justo
  sobre el ojo, y los parpadeos agregan potencia de baja frecuencia (δ y θ),
  lo que puede inflar EEG1 y EEG2. La alerta de δ ayuda a detectarlos, pero
  no los elimina.
- **Bandas calculadas por el chip de NeuroSky** (ThinkGear), no con una PSD
  de Welch sobre la señal cruda. No se controlan la ventana, el solapamiento
  ni los límites exactos de cada banda.
- **Sin ICA ni otra limpieza de artefactos**: con un solo canal no es
  posible separar componentes.
- **Unidades relativas:** las potencias de NeuroSky no tienen unidad física
  (no son µV²). Solo tienen sentido las comparaciones relativas, por eso se
  normaliza dentro de cada participante.
- **Línea base no ideal:** la Etapa 2 no es un reposo, porque el
  participante está leyendo. El cambio % mide "respecto a leer el
  enunciado", no "respecto al reposo".
- **Muestra pequeña** (4 participantes al momento de escribir esto): los
  promedios por etapa son descriptivos, no inferenciales.

## 8. Estructura del código

| Archivo | Contenido |
| --- | --- |
| `analisis/config.py` | Parámetros y rutas (`AnalysisConfig`) |
| `analisis/eeg_features.py` | Funciones puras del pipeline: parseo, alineación, filtro, bandas, log, cocientes, agregados, línea base, z-score, Min-Max, alerta de δ y `build_feature_table` |
| `analisis/report.py` | Funciones puras de resumen para la interfaz: filtro por participante, resumen por etapa e indicadores de calidad |
| `analisis/comprehension.py` | Punto de extensión: columnas de comprensión, binarización, interfaz `ComprehensionClassifier` y `training_table` |
| `analisis/loader.py` | Única parte que toca disco: lee el dataset, arma la tabla y exporta el CSV |
| `analisis/tests/test_eeg_features.py` | Pruebas unitarias con datos sintéticos (`unittest`) |
| `ui/analysis_view.py` | Pestaña "Análisis": controles, nota, calidad, gráfico (matplotlib) y tabla |
| `ui/app.py` | Solo registra la pestaña: botón "📈 Análisis" en el menú lateral, su frame y el cálculo al abrirla por primera vez |

Para correr las pruebas desde la raíz del proyecto:

```
.venv/bin/python -m unittest discover -s graphic_interface/analisis/tests -t graphic_interface
```

La única dependencia nueva es `matplotlib` (en `requirements.txt`), usada
solo para el gráfico. Si faltara, la pestaña funciona igual y muestra un
aviso en lugar del gráfico.

## 9. Próximos pasos: comprensión y clasificadores

El punto de extensión está en `analisis/comprehension.py`:

1. **Cargar las puntuaciones.** Armar un diccionario
   `{(participante, desafío, etapa, intento): puntaje}` con valores de 0 a
   6 y pasarlo a `attach_comprehension(features, scores)`. Hoy `loader.py`
   la llama sin puntuaciones, por eso las columnas salen vacías. Ese es el
   lugar donde conectar la fuente real (por ejemplo, los cuestionarios o el
   juez de prompts).
2. **Binarización.** `binarize_comprehension` convierte el puntaje en
   comprensión alta (> 3,5) o baja. El umbral se cambia en
   `COMPREHENSION_THRESHOLD`. Un puntaje fuera de 0–6 produce un error.
3. **Datos de entrenamiento.** `training_table(features, columnas)` devuelve
   `X` (las features elegidas, por ejemplo `EEG1_Media_Z` y `EEG2_Media_Z`)
   e `y` (`Comprension_Alta`), solo con las filas que tienen puntaje y datos
   suficientes.
4. **Clasificador.** Cualquier objeto con `fit(X, y)` y `predict(X)` cumple
   la interfaz `ComprehensionClassifier`, por ejemplo un modelo de
   scikit-learn, que ya está en `requirements.txt`. Conviene validarlo
   dejando un participante fuera en cada vuelta (*leave-one-subject-out*),
   para no evaluar con datos de la misma persona con la que se entrenó.
