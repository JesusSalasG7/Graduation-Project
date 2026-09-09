# Guía Rápida: Uso y Prueba del NeuroSky MindWave Mobile

Esta guía explica cómo configurar el cintillo **NeuroSky MindWave Mobile**, validar que transmite datos en tiempo real a la computadora y utilizar la librería en cualquier experimento independiente en Python.

---

## 1. Archivos que debes transferir

Para que otra persona pueda usar el dispositivo en su propio proyecto, solo necesita estos archivos:

1. **`NeuroPy.py`**: Driver/librería en Python que implementa el protocolo de comunicación serial de NeuroSky (ThinkGear).
2. **`test_neurosky.py`**: Script de prueba autónomo para verificar la conexión, monitorear la calidad de la señal por terminal y exportar los datos a CSV (opcionalmente graficar).
3. **`GUIA_NEUROSKY.md`**: Este documento de instrucciones.

*(No es necesario pasar ningún archivo relacionado con la tarea cognitiva LetterWheel, PsychoPy ni OpenCV).*

---

## 2. Requisitos y Dependencias

* **Python:** 3.8 o superior (probado y recomendado en Python 3.10).
* **Librerías requeridas:**
  ```bash
  pip install pyserial
  ```
* **Librería opcional (para visualizar gráficos al final de la prueba):**
  ```bash
  pip install matplotlib
  ```

---

## 3. Conexión del Hardware

El NeuroSky MindWave Mobile se comunica mediante **Bluetooth Serial (SPP)** a **57600 baudios**.

### A) En Linux (Ubuntu / Debian)

1. **Permisos de usuario para puertos seriales (se hace una sola vez):**
   ```bash
   sudo usermod -a -G dialout $USER
   ```
   *(Nota: si acabas de agregar el grupo, debes cerrar sesión y volver a entrar o reiniciar).*

2. **Emparejar por Bluetooth:**
   * Enciende el cintillo (mantén presionado el interruptor en posición de encendido hasta que la luz azul parpadee rápido).
   * En el gestor de Bluetooth de tu sistema operativo (o mediante `bluetoothctl`), busca el dispositivo (suele llamarse `MindWave Mobile` o similar) y emparéjalo (el PIN suele ser `0000` o `1234` si lo solicita).
   * Copia la dirección MAC del dispositivo (ejemplo: `20:68:9D:79:DE:7C`).

3. **Vincular el dispositivo a un puerto virtual `rfcomm`:**
   ```bash
   # Reemplaza con la MAC de tu dispositivo
   sudo rfcomm bind /dev/rfcomm0 20:68:9D:79:DE:7C 1
   sudo chmod 666 /dev/rfcomm0
   ```

   *(Cuando termines de usarlo en el día, puedes liberarlo con `sudo rfcomm release /dev/rfcomm0`).*

---

### B) En Windows

1. Enciende el cintillo y ponlo en modo emparejamiento.
2. Ve a **Configuración > Bluetooth y otros dispositivos** y emparéjalo.
3. Abre el **Administrador de Dispositivos** (Device Manager) y despliega **Puertos (COM y LPT)**.
4. Identifica qué puerto COM entrante se le asignó (por ejemplo, `COM3`, `COM4` o `COM5`).
5. Ese será el nombre de puerto que usarás en tus scripts (ejemplo: `COM3`).

---

## 4. Probar la Adquisición de Datos (`test_neurosky.py`)

Para comprobar que el dispositivo está enviando datos correctamente a la máquina:

1. Colócate el cintillo:
   * El sensor metálico frontal debe estar apoyado firmemente sobre la frente (posición Fp1, arriba de la ceja izquierda).
   * La pinza metálica debe estar bien sujeta al **lóbulo de la oreja**.
   * Asegúrate de que no haya cabello entre el sensor y la piel.

2. Ejecuta el script de prueba:
   ```bash
   # En Linux (puerto por defecto /dev/rfcomm0):
   python test_neurosky.py

   # En Windows (especificando tu puerto COM):
   python test_neurosky.py --port COM3

   # Si deseas graficar las señales al terminar la sesión:
   python test_neurosky.py --plot
   ```

3. **Interpretación de la Calidad de Señal (`Poor_Signal`):**
   En la consola verás una línea por segundo con el estado:
   * `[CONTACTO OK]`: `Poor_Signal = 0`. El cintillo tiene contacto eléctrico óptimo con la piel. Las ondas cerebrales y niveles de atención/meditación son válidos.
   * `[AJUSTANDO: XX]`: `0 < Poor_Signal < 200`. Hay contacto pero con interferencia o mala conducción (ajustar posición o limpiar piel/sensor).
   * `[SIN CONTACTO (200)]`: `Poor_Signal = 200`. El sensor está en el aire o la pinza del lóbulo no está haciendo contacto.

4. **Detener la prueba:**
   Presiona `Ctrl + C`. El script cerrará la conexión de forma segura y guardará todas las lecturas en `test_neurodata.csv`.

---

## 5. Datos que entrega el NeuroSky

Cada muestra registrada contiene las siguientes variables:

| Variable | Tipo | Descripción |
| :--- | :--- | :--- |
| **`Timestamp_Human` / `Timestamp_Unix`** | Tiempo | Marca temporal precisa de cada muestra. |
| **`Poor_Signal`** | 0 a 200 | Calidad del contacto (0 = perfecto, 200 = sin contacto). |
| **`Attention`** | 0 a 100 | Algoritmo eSense de concentración/atención sostenida. |
| **`Meditation`** | 0 a 100 | Algoritmo eSense de relajación/calma mental. |
| **`Delta`** | Entero | Potencia espectral en ondas Delta (0.5 – 2.75 Hz). |
| **`Theta`** | Entero | Potencia espectral en ondas Theta (3.5 – 6.75 Hz). |
| **`Low_Alpha` / `High_Alpha`** | Entero | Potencia en bandas Alpha (7.5 – 9.25 Hz y 10 – 11.75 Hz). |
| **`Low_Beta` / `High_Beta`** | Entero | Potencia en bandas Beta (13 – 16.75 Hz y 18 – 29.75 Hz). |
| **`Low_Gamma` / `Mid_Gamma`** | Entero | Potencia en bandas Gamma (31 – 39.75 Hz y 41 – 49.75 Hz). |

---

## 6. Plantilla mínima para usar en su propio experimento

Si se desea importar `NeuroPy` dentro de su propio script de experimento, este es el patrón mínimo recomendado:

```python
import time
from NeuroPy import NeuroPy

# 1. Instanciar la clase indicando el puerto
puerto = "/dev/rfcomm0"  # En Windows usar por ejemplo "COM3"
neuropy = NeuroPy(puerto, baudRate=57600)

# 2. Definir una función callback para procesar datos cuando se actualicen
def mi_callback(valor_atencion):
    print(f"Atencion: {neuropy.attention} | Meditacion: {neuropy.meditation} | Theta: {neuropy.theta}")
    # Aqui puedes guardar los datos en una lista, base de datos o archivo CSV

# 3. Asignar el callback al evento deseado (ej. "attention" se emite ~1 vez por segundo)
neuropy.setCallBack("attention", mi_callback)

# 4. Iniciar la adquisicion en un hilo en segundo plano
neuropy.start()

try:
    # 5. Aqui corre el loop de tu experimento...
    print("Capturando datos durante 20 segundos...")
    time.sleep(20)

finally:
    # 6. Siempre detener la conexion al terminar
    neuropy.stop()
    print("Conexion finalizada con exito.")
```

