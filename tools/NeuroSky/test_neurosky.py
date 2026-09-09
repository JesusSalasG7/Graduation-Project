#!/usr/bin/env python3
"""
Script de prueba y verificacion para NeuroSky MindWave Mobile.
Permite validar la conexion serial/bluetooth, monitorear la calidad de la senal
en tiempo real y almacenar los datos en un archivo CSV.
"""

import sys
import os
import time
import csv
import argparse
from datetime import datetime

# Verificar dependencias
try:
    import serial
except ImportError:
    print("[ERROR] Falta la libreria 'pyserial'.")
    print("Instalala ejecutando en tu terminal: pip install pyserial")
    sys.exit(1)

try:
    from NeuroPy import NeuroPy
except ImportError:
    print("[ERROR] No se encontro 'NeuroPy.py'. Asegurate de colocarlo en la misma carpeta que este script.")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Prueba de conexion y adquisicion de datos NeuroSky MindWave")
    default_port = "COM3" if sys.platform.startswith("win") else "/dev/rfcomm0"
    parser.add_argument(
        "--port", "-p",
        default=default_port,
        help=f"Puerto serial del dispositivo (ej. /dev/rfcomm0 en Linux, COM3 en Windows). Por defecto: {default_port}"
    )
    parser.add_argument(
        "--output", "-o",
        default="test_neurodata.csv",
        help="Nombre del archivo CSV para guardar los datos. Por defecto: test_neurodata.csv"
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Si se especifica, grafica los datos con matplotlib al finalizar (Ctrl+C)"
    )
    args = parser.parse_args()

    port = args.port
    output_file = args.output
    do_plot = args.plot

    print("=" * 65)
    print("   TEST DE ADQUISICION DE DATOS - NEUROSKY MINDWAVE")
    print("=" * 65)
    print(f" Puerto configurado: {port}")
    print(f" Archivo de salida:  {output_file}")
    print(" Presiona Ctrl+C en cualquier momento para detener la grabacion.")
    print("-" * 65)

    # Inicializar conexion con NeuroSky
    try:
        neuropy = NeuroPy(port, baudRate=57600)
    except Exception as e:
        print(f"\n[ERROR] No se pudo inicializar la conexion en {port}: {e}")
        print("\nVerificaciones comunes:")
        print(" 1. ¿El dispositivo esta encendido y con bateria?")
        print(" 2. En Linux: ¿Ejecutaste 'sudo rfcomm bind /dev/rfcomm0 <MAC> 1'?")
        print(" 3. En Linux: ¿Tu usuario tiene permisos? ('sudo usermod -a -G dialout $USER')")
        print(" 4. En Windows: Revisa en el Administrador de Dispositivos cual puerto COM tiene asignado.")
        sys.exit(1)

    # Preparar archivo CSV
    file_handle = open(output_file, mode="w", newline="")
    csv_writer = csv.writer(file_handle)
    csv_writer.writerow([
        "Timestamp_Human", "Timestamp_Unix", "Poor_Signal", 
        "Attention", "Meditation", "Delta", "Theta", 
        "Low_Alpha", "High_Alpha", "Low_Beta", "High_Beta", 
        "Low_Gamma", "Mid_Gamma"
    ])

    timestamps = []
    attentions = []
    meditations = []
    thetas = []
    alphas = []
    betas = []

    # Callback ejecutado cada vez que NeuroSky envia una actualizacion de atencion
    # (NeuroSky actualiza atencion/meditacion y bandas aproximadamente 1 vez por segundo)
    def on_attention_update(val):
        human_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        unix_time = time.time()

        poor = neuropy.poorSignal
        att = neuropy.attention
        med = neuropy.meditation
        delta = neuropy.delta
        theta = neuropy.theta
        l_alpha = neuropy.lowAlpha
        h_alpha = neuropy.highAlpha
        l_beta = neuropy.lowBeta
        h_beta = neuropy.highBeta
        l_gamma = neuropy.lowGamma
        m_gamma = neuropy.midGamma

        # Guardar en listas de memoria para graficar
        timestamps.append(human_time)
        attentions.append(att)
        meditations.append(med)
        thetas.append(theta)
        alphas.append(l_alpha)
        betas.append(l_beta)

        # Guardar en CSV inmediatamente
        csv_writer.writerow([
            human_time, unix_time, poor,
            att, med, delta, theta,
            l_alpha, h_alpha, l_beta, h_beta,
            l_gamma, m_gamma
        ])
        file_handle.flush()

        # Diagnostico de calidad de senal:
        # poorSignal: 0 = contacto perfecto, 200 = sin contacto (en el aire)
        if poor == 0:
            signal_status = "[CONTACTO OK]"
        elif poor < 200:
            signal_status = f"[AJUSTANDO: {poor}]"
        else:
            signal_status = "[SIN CONTACTO (200)]"

        print(f"[{human_time}] {signal_status:<20} | Atencion: {att:3d} | Meditacion: {med:3d} | Alpha: {l_alpha:7d} | Beta: {l_beta:7d}")

    neuropy.setCallBack("attention", on_attention_update)

    # Iniciar hilo de lectura del puerto serie
    print(f"\n[INFO] Conectando a {port} e iniciando lectura...")
    try:
        neuropy.start()
    except Exception as e:
        print(f"\n[ERROR] Fallo al abrir el puerto {port}: {e}")
        file_handle.close()
        sys.exit(1)

    print("[INFO] Hilo lector iniciado. Esperando paquetes de datos del dispositivo...\n")
    print("NOTA: Si 'poorSignal' marca [SIN CONTACTO], asegurate de colocar el sensor")
    print("en la frente (Fp1) y la pinza metalica firmemente en el lobulo de la oreja.\n")

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n\n[INFO] Deteniendo adquisicion de datos...")
    finally:
        neuropy.stop()
        file_handle.close()
        print(f"[EXITO] Datos guardados exitosamente en '{output_file}'. Total muestras: {len(timestamps)}")

    # Opcion de graficar
    if do_plot and len(timestamps) > 0:
        try:
            import matplotlib.pyplot as plt
            print("[INFO] Generando graficos...")
            plt.figure(figsize=(12, 8))

            plt.subplot(3, 1, 1)
            plt.plot(timestamps, attentions, label="Atencion", color="tab:blue")
            plt.plot(timestamps, meditations, label="Meditacion", color="tab:orange")
            plt.ylabel("Nivel (0-100)")
            plt.title("Metricas eSense (NeuroSky)")
            plt.legend()
            plt.xticks(rotation=45)

            plt.subplot(3, 1, 2)
            plt.plot(timestamps, alphas, label="Low Alpha", color="tab:purple")
            plt.plot(timestamps, thetas, label="Theta", color="tab:red")
            plt.ylabel("Potencia (ASIC)")
            plt.legend()
            plt.xticks(rotation=45)

            plt.subplot(3, 1, 3)
            plt.plot(timestamps, betas, label="Low Beta", color="tab:green")
            plt.ylabel("Potencia (ASIC)")
            plt.xlabel("Tiempo")
            plt.legend()
            plt.xticks(rotation=45)

            plt.tight_layout()
            plt.show()
        except ImportError:
            print("[AVISO] matplotlib no esta instalado. Para ver graficos ejecuta: pip install matplotlib")


if __name__ == "__main__":
    main()
