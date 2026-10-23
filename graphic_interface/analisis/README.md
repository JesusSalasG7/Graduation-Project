# Módulo de análisis EEG (`analisis/`)

Mide la carga cognitiva durante el *vibe coding* con el NeuroSky (un solo
canal frontal, Fp1) y la relaciona con la comprensión. Replica la
metodología del artículo de referencia, que usa dos indicadores:

- **EEG1 = Alfa / Theta**: baja cuando aumenta la carga cognitiva.
- **EEG2 = Theta** (mediana de la potencia): sube con la demanda de
  memoria de trabajo.

Los resultados se ven en la pestaña **📈 Análisis** del panel y se
exportan a `data/analisis/` (en el `.gitignore`: son datos de
participantes).

## 1. Etapas

| Etapa | Descripción | Etiqueta en gráficos | Cuestionario |
| --- | --- | --- | --- |
| Etapa 2 | Lectura del problema | Etapa 2 / Problema | Sí |
| Etapa 3 | Escribir el prompt | Etapa 3 / Prompt | **No** |
| Etapa 4 | Lectura de la solución | Etapa 4 / Solución | Sí |
| Etapa 5 | Lectura del razonamiento | Etapa 5 / Razonamiento | Sí |

Cualquier otra etapa que aparezca en el dataset se ignora (y se avisa en
la pestaña), salvo que se configure como `ETAPA_LINEA_BASE`.

## 2. Datos de entrada

`data/dataset_sesiones.csv`, generado por `data/build_dataset.py`. Cada
fila es **participante × desafío × etapa × intento**. Las columnas usadas:

| Rol | Columna |
| --- | --- |
| Participante | `Participante_ID` |
| Etapa | `Etapa` (entero 2–5; se normaliza a "Etapa N") |
| Duración | `Duracion_Segundos` (si falta, `Hora_Fin − Hora_Inicio`; si tampoco hay, el número de muestras) |
| Puntaje | `Cuestionario_Correctas` / `Cuestionario_Total` × 100 (7 preguntas por cuestionario) |
| Bandas | `NeuroSky_Theta_List`, `NeuroSky_LowAlpha_List`, `NeuroSky_HighAlpha_List`, `NeuroSky_LowBeta_List`, `NeuroSky_HighBeta_List` |
| Calidad | `NeuroSky_PoorSignal_List` (0 = buena señal, 200 = sin contacto) |
| Control de artefactos | `NeuroSky_Delta_List` |
| Complementarias | `NeuroSky_Attention_List`, `NeuroSky_Meditation_List` |

Las listas vienen como texto con forma de lista de Python (`"[1, 2, 3]"`),
con ~1 muestra por segundo, alineadas por índice. Si las listas de una
fila tienen largos distintos, se recortan a la más corta y se avisa.
Gamma no se lee: en Fp1 está dominada por ruido muscular.

**Unidad de análisis:** todos los desafíos e intentos de un participante
en la misma etapa se juntan, para tener un valor por participante y etapa.
El puntaje es la suma de aciertos dividida por la suma de preguntas de
todos los cuestionarios de esa etapa.

## 3. Pipeline (`pipeline.py`)

1. **Cargar y expandir:** se filtran las Etapas 2–5 y cada fila se pasa a
   formato largo (una fila por participante, etapa y segundo).
2. **Control de calidad:** se conservan las muestras con
   `PoorSignal ≤ UMBRAL_POOR_SIGNAL` (0 por defecto; 49 equivale a "< 50")
   y con Theta > 0 y Alfa > 0. El reporte por participante y etapa incluye
   las muestras totales, las válidas y el % válido. Una etapa es de **baja
   calidad** si tiene menos del 50 % o menos de 30 muestras válidas, y se
   excluye si `EXCLUIR_BAJA_CALIDAD`. Como control de artefactos, también
   se informa el % de muestras con log Delta por encima de la media + 2 DE
   del participante.
3. **Indicadores por muestra:** alpha = LowAlpha + HighAlpha;
   EEG1 = alpha / Theta; EEG2 = Theta. Opcionales: theta_beta =
   Theta / (LowBeta + HighBeta) y engagement = beta / (alpha + Theta).
4. **Logaritmo natural** de cada indicador, porque las potencias de
   NeuroSky están muy sesgadas.
5. **Normalización z por participante:** media y DE muestral (ddof = 1)
   de cada indicador logarítmico con **todas** las muestras válidas del
   participante en las Etapas 2–5. Con `ETAPA_LINEA_BASE` definida, la
   referencia es solo esa etapa, que luego no aparece en los resultados.
6. **Agregación:** la **mediana** de los z por participante y etapa, más la
   duración, el promedio de Attention y Meditation (sin los 0, que indican
   que el chip aún no calculó el valor) y el % de muestras válidas.
7. **Puntajes:** se unen por participante y etapa. La Etapa 3 queda en NaN.

Salida principal: `resultados_por_etapa.csv` con `participante, etapa,
EEG1_z, EEG2_z, theta_beta_z, engagement_z, duracion_s, attention_prom,
meditation_prom, puntaje, pct_muestras_validas`. También se genera
`reporte_calidad.csv`.

### Vista por desafío (`por_desafio.py`)

`resultados_por_desafio.csv` tiene una fila por participante × desafío ×
etapa, con las mismas columnas más `desafio`, `juego` y `n_muestras`. No
cambia el procesamiento: usa las mismas muestras filtradas y el mismo z
(calculado con todas las muestras del participante) y solo agrupa también
por desafío (mediana). El puntaje es el % de aciertos de ese desafío. Una
celda con menos de `MIN_MUESTRAS_VALIDAS` muestras queda sin z, y
`pct_muestras_validas` queda vacío porque la calidad se reporta por
etapa. En la pestaña, el selector "Desafío" recalcula los gráficos y la
tabla de resultados con un solo desafío. La tabla estadística sigue usando
todos los desafíos juntos.

## 4. Interpretación

- z = 0 es el nivel habitual del participante. Los valores son relativos a
  cada persona, nunca absolutos.
- **EEG1_z bajo** (negativo) = mayor carga; alto = menor carga o más
  relajación.
- **EEG2_z alto** (positivo) = mayor carga de memoria de trabajo o
  esfuerzo; bajo = menor demanda.
- **Alta carga** = EEG1_z < 0 y EEG2_z > 0 a la vez. Si se contradicen, el
  resultado es **no concluyente** (columna "Lectura" de la pestaña).
- Attention y Meditation son algoritmos propietarios. Se muestran solo
  como complementarios y no sustituyen a EEG1 ni a EEG2.
- La Etapa 3 implica teclear, lo que puede añadir ruido muscular.

## 5. Estadística (`estadistica.py`)

Todas las pruebas usan α = 0,05 e informan el tamaño de efecto junto al
valor p. Los resultados se exportan en `resultados_estadisticos.csv`.

- **Entre etapas:** Friedman para EEG1_z y EEG2_z con las Etapas 2–5, solo
  con los participantes que tienen datos en las 4 (se informa n), y W de
  Kendall = χ² / (n·(k − 1)). Si es significativa, se hace Wilcoxon por
  pares con corrección de Holm y r = Z/√n.
- **EEG–comprensión:** Spearman entre EEG1_z / EEG2_z y el puntaje, en cada
  etapa con cuestionario y agrupando las tres. El agrupado repite
  participantes, así que sus observaciones no son independientes.
- **Alta vs baja:** en cada etapa con cuestionario, se divide por la
  mediana del puntaje (≥ mediana = alta) y se aplica Mann-Whitney U con
  r = Z/√N.
- **Modelo lineal mixto:** `puntaje ~ EEG1_z + EEG2_z + etapa +
  (1 | participante)`, solo con 15 participantes o más (`statsmodels`).
  Con menos, no se ajusta y se marca "muestra pequeña: resultados
  exploratorios".

## 6. Gráficos (`graficos.py`)

Se exportan en PNG a 300 dpi y se muestran en la pestaña. EEG1 va en
morado (#7F77DD) y EEG2 en verde azulado (#1D9E75); el grupo de
comparación, en gris (#B4B2A9). El eje Y de las barras es "z (0 = nivel
habitual del participante)", con una línea sólida en 0 y límites
simétricos. Junto al eje hay dos flechas de texto que explican qué
significa subir o bajar en cada indicador. Debajo de cada figura se
genera un texto de interpretación (reglas en `patron_carga`: EEG1 < 0 y
EEG2 > 0 = mayor carga, el patrón inverso = menor carga, si se
contradicen = no concluyente, y |mediana| < 0,2 en ambos = cercano al
nivel habitual).

Barras: altura = mediana del grupo, un punto oscuro por participante
(con jitter) y el valor de la mediana encima o debajo. `MOSTRAR_RIC =
True` agrega barras de error Q1–Q3.

1. `perfil_etapas.png`: barras por etapa (Etapas 2–5) en dos paneles.
   Incluye cuántos participantes van en la misma dirección que la mediana.
2. `comprension_alta_vs_baja.png`: barras agrupadas alta (≥ mediana del
   puntaje de la etapa, en color) vs baja (gris) en las Etapas 2, 4 y 5,
   con el p de Mann-Whitney (* p<0,05, ** p<0,01, n.s.).
3. `eeg_vs_comprension.png`: dispersión de 2 × 3, con ρ de Spearman y p
   en el título. Debajo, una frase como "a menor carga, mejor
   comprensión" (+ "tendencia no significativa" si p ≥ 0,05).
4. `resumen_etapas.png`: EEG1 y EEG2 por etapa en un solo gráfico, más
   la etapa de mayor carga (mayor EEG2_z − EEG1_z).

Vista por participante (selector "Participante" de la pestaña): las
Figuras 1 y 4 muestran solo los valores z de esa persona, con la escala
ajustada a ellos y su propia etapa de mayor carga. La Figura 2 muestra su
% de aciertos (alta o baja frente a la mediana del grupo) junto a su
EEG en las Etapas 2, 4 y 5. La Figura 3 sigue siendo del grupo, porque
la correlación necesita a todos, y marca a la persona con un anillo
naranja. Los PNG exportados son siempre los del grupo.

`TIPO_GRAFICO = "boxplot"` o `"lineas"` reactiva los gráficos anteriores
(boxplots o líneas por participante).

## 7. Parámetros (`config.py`)

`RUTA_DATASET`, `RUTA_SALIDA`, `UMBRAL_POOR_SIGNAL` (0),
`MIN_MUESTRAS_VALIDAS` (30), `MIN_PCT_VALIDO` (50), `EXCLUIR_BAJA_CALIDAD`
(True), `ETAPAS_ANALISIS`, `ETAPAS_CON_CUESTIONARIO`,
`ETAPA_SIN_CUESTIONARIO`, `ETAPA_LINEA_BASE` (None),
`DESCRIPCION_CORTA_ETAPA`, `DESCRIPCION_ETAPA`, `DELTA_Z_ARTEFACTO` (2),
`ALFA` (0,05), `MIN_PARTICIPANTES_MODELO_MIXTO` (15), los colores,
`TIPO_GRAFICO` ("barras"), `MOSTRAR_RIC` (False) y `UMBRAL_CERCANO_Z` (0,2). Las
funciones los reciben agrupados en `ConfigAnalisis`.

## 8. Limitaciones

- Un solo electrodo en Fp1, sobre el ojo: los parpadeos inflan las bandas
  lentas (Delta y Theta). Por eso se filtra por PoorSignal, se usa la
  mediana y Delta se reporta como control.
- Las bandas las calcula el chip de NeuroSky (no hay PSD propia) y no
  tienen unidades físicas. Solo valen las comparaciones dentro de cada
  participante.
- No hay una etapa de reposo grabada: la referencia del z es el promedio
  de las propias Etapas 2–5.
- Con la muestra actual (10 participantes) los resultados son
  exploratorios.

## 9. Uso

```
# Pruebas (raíz del proyecto)
.venv/bin/python -m unittest discover -s graphic_interface/analisis/tests -t graphic_interface
# Correr el análisis y exportar sin abrir la interfaz
.venv/bin/python graphic_interface/analisis/loader.py
```
