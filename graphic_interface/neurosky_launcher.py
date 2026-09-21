"""Vinculacion Bluetooth + lanzador de tools/NeuroSky/test_neurosky.py.

El NeuroSky MindWave Mobile se conecta por Bluetooth SPP: antes de poder
leerlo como puerto serial hay que "bindearlo" a /dev/rfcomm0 con su MAC
(ver tools/NeuroSky/GUIA_NEUROSKY.md), y eso requiere permisos de root.
Este modulo automatiza esos dos comandos (pidiendo la contraseña de sudo
por stdin, nunca por linea de comando, solo si hace falta) y despues
lanza test_neurosky.py con el .venv unificado del proyecto.
"""

import subprocess
from pathlib import Path
from typing import Callable, Optional

from game_launcher import PROJECT_ROOT, venv_python

NEUROSKY_DIR = PROJECT_ROOT / "tools" / "NeuroSky"
NEUROSKY_TEST_SCRIPT = NEUROSKY_DIR / "test_neurosky.py"
# test_neurosky.py abre este archivo en modo "w" (trunca) cada vez que
# arranca -- nunca acumula datos de corridas anteriores, asi que borrarlo
# borra exactamente (y solamente) lo capturado en la sesion que se acaba
# de abandonar.
NEUROSKY_DATA_FILE = NEUROSKY_DIR / "test_neurodata.csv"
NEUROSKY_MAC = "20:68:9D:79:DE:7C"
RFCOMM_DEVICE = "/dev/rfcomm0"


def sudo_needs_password() -> bool:
    """True si sudo va a pedir contraseña (no hay credencial de sudo
    cacheada ni una regla NOPASSWD para este usuario)."""
    try:
        result = subprocess.run(
            ["sudo", "-n", "true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return False
    return result.returncode != 0


def bind_neurosky(on_output: Callable[[str], None], password: Optional[str] = None) -> bool:
    """Corre `sudo rfcomm bind /dev/rfcomm0 <MAC> 1` y despues
    `sudo chmod 666 /dev/rfcomm0`, en ese orden, cortando en el primero que
    falle. La contraseña (si hace falta) se le pasa a `sudo -S` por stdin,
    nunca como argumento -- asi no queda visible en la lista de procesos.

    Si /dev/rfcomm0 ya existe (p.ej. un reintento despues de haber
    encendido el dispositivo) se salta el bind -- repetirlo falla con
    "Device or resource busy" -- y solo se corre el chmod.

    Devuelve True si los comandos corridos terminaron con codigo 0.
    """
    commands = []
    if not Path(RFCOMM_DEVICE).exists():
        commands.append(["sudo", "-S", "rfcomm", "bind", RFCOMM_DEVICE, NEUROSKY_MAC, "1"])
    else:
        on_output(f"[INFO] {RFCOMM_DEVICE} ya estaba vinculado, no hace falta repetir el bind.")
    commands.append(["sudo", "-S", "chmod", "666", RFCOMM_DEVICE])
    stdin_data = f"{password}\n" if password else "\n"

    for cmd in commands:
        on_output(f"$ {' '.join(cmd)}")
        try:
            process = subprocess.run(cmd, input=stdin_data, capture_output=True, text=True)
        except FileNotFoundError as exc:
            on_output(f"[ERROR] {exc}")
            return False

        for line in (process.stdout + process.stderr).splitlines():
            if "password for" in line.lower():
                continue
            on_output(line)

        if process.returncode != 0:
            on_output(f"[ERROR] '{' '.join(cmd)}' termino con codigo {process.returncode}.")
            return False

    return True


def release_neurosky(on_output: Callable[[str], None], password: Optional[str] = None) -> bool:
    """Corre `sudo rfcomm release /dev/rfcomm0` -- la contraparte de
    `bind_neurosky`, para dejar el dispositivo Bluetooth desvinculado de
    forma prolija en vez de dejarlo bindeado sin nadie leyendolo.

    Si el puerto ya no existe (nunca se bindeo, o ya se libero antes) no
    hace nada y devuelve True -- no hay nada que liberar.
    """
    if not Path(RFCOMM_DEVICE).exists():
        return True

    cmd = ["sudo", "-S", "rfcomm", "release", RFCOMM_DEVICE]
    stdin_data = f"{password}\n" if password else "\n"

    on_output(f"$ {' '.join(cmd)}")
    try:
        process = subprocess.run(cmd, input=stdin_data, capture_output=True, text=True)
    except FileNotFoundError as exc:
        on_output(f"[ERROR] {exc}")
        return False

    for line in (process.stdout + process.stderr).splitlines():
        if "password for" in line.lower():
            continue
        on_output(line)

    if process.returncode != 0:
        on_output(f"[ERROR] '{' '.join(cmd)}' termino con codigo {process.returncode}.")
        return False
    return True


def delete_neurosky_data() -> None:
    """Borra el CSV con las lecturas capturadas en la sesion (se usa
    cuando la sesion guiada se abandona sin terminar los desafios)."""
    try:
        NEUROSKY_DATA_FILE.unlink()
    except FileNotFoundError:
        pass


def start_neurosky_test() -> subprocess.Popen:
    """Lanza tools/NeuroSky/test_neurosky.py en segundo plano con el .venv
    unificado (pyserial ya esta instalado ahi), con su salida como pipe de
    texto linea a linea para poder mostrarla en vivo.

    El flag `-u` es necesario: al no estar conectado a una terminal, el
    stdout del proceso hijo queda bufferizado por bloques (no por linea),
    asi que sin esto los `print()` de test_neurosky.py no llegan por el
    pipe en tiempo real -- se acumulan y aparecen todos juntos recien al
    terminar el proceso.
    """
    if not NEUROSKY_TEST_SCRIPT.exists():
        raise FileNotFoundError("No se encontro tools/NeuroSky/test_neurosky.py")

    return subprocess.Popen(
        [str(venv_python()), "-u", str(NEUROSKY_TEST_SCRIPT)],
        cwd=str(NEUROSKY_DIR),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
