"""Registro de tiempos de la sesión guiada de un participante, acumulado
entre sesiones: Participante_N/tiempos_sesion.json (junto a sus
Desafio_N, ver stage_capture.participant_session_dir).

Una "sesión" va desde la Etapa 1 del primer juego que se juega al entrar
a la sesión guiada hasta que el investigador presiona "Guardar progreso"
o "Terminar sesión guiada" (ahí se pausa el cronómetro). Al volver a
entrar, el participante retoma en el desafío siguiente y el tiempo total
sigue sumando desde donde quedó, hasta terminar los 7 juegos.

Cómo se cierra cada sesión (campo "cierre"):
    - "guardar_progreso": se guardó el progreso para retomar después.
    - "sesion_terminada": se terminaron los 7 juegos.
    - "salida_sin_guardar": se salió con "Salir de la sesión guiada" sin
      guardar el progreso (esos desafíos se vuelven a jugar al retomar).
    - "interrumpida": la app se cerró de golpe a mitad de la sesión (se
      detecta al empezar la siguiente).
Solo las dos primeras cuentan para los totales: en las otras dos el
progreso no se guardó y los desafíos se repiten, así que contarlas
duplicaría tiempos. Igual quedan registradas con sus etapas.

Se reescribe el archivo en cada cambio de etapa, para no perder lo ya
medido si la app se cierra de golpe.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

TIMING_FILENAME = "tiempos_sesion.json"

CLOSE_SAVED = "guardar_progreso"
CLOSE_FINISHED = "sesion_terminada"
CLOSE_ABANDONED = "salida_sin_guardar"
CLOSE_INTERRUPTED = "interrumpida"
COUNTED_CLOSES = (CLOSE_SAVED, CLOSE_FINISHED)
_OPEN = "en_curso"


def format_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _seconds_between(start: str, end: str) -> float:
    return (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()


class SessionTimingLog:
    def __init__(self, participant_folder: Path, participant_number: int):
        self.path = participant_folder / TIMING_FILENAME
        self.data = self._load(participant_number)
        self._session: Optional[dict] = None
        self._stage: Optional[dict] = None
        self._paused_at: Optional[str] = None
        # Una sesión que quedó "en_curso" es de una corrida que se cortó
        # de golpe (cierre de la app, corte de luz...).
        changed = False
        for session in self.data["sesiones"]:
            if session["cierre"] == _OPEN:
                session["cierre"] = CLOSE_INTERRUPTED
                session.setdefault("fin", session["inicio"])
                changed = True
        for stage in self.data["etapas"]:
            if stage.get("fin") is None:
                stage["fin"] = stage["inicio"]
                stage["duracion_s"] = 0
                changed = True
        if changed:
            self._save()

    def _load(self, participant_number: int) -> dict:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                data.setdefault("sesiones", [])
                data.setdefault("etapas", [])
                return data
            except (OSError, ValueError):
                # No se pisa un archivo que no se pudo leer: se aparta.
                self.path.rename(self.path.with_suffix(f".corrupto_{datetime.now():%Y%m%d%H%M%S}.json"))
        return {"participante": participant_number, "sesiones": [], "etapas": []}

    # ---------------- consultas ----------------
    @property
    def session_running(self) -> bool:
        return self._session is not None and self._paused_at is None

    def counted_total_seconds(self) -> float:
        """Tiempo ya acumulado en sesiones cerradas que cuentan."""
        return sum(s["duracion_s"] for s in self.data["sesiones"] if s["cierre"] in COUNTED_CLOSES)

    def counted_sessions(self) -> int:
        return sum(1 for s in self.data["sesiones"] if s["cierre"] in COUNTED_CLOSES)

    def next_session_number(self) -> int:
        return len(self.data["sesiones"]) + 1

    # ---------------- registro ----------------
    def start_stage(self, challenge: int, game: str, stage: int, attempt: Optional[int]) -> None:
        """Cierra la etapa anterior y abre esta. La primera etapa que se
        muestra abre la sesión si todavía no está abierta (el cronómetro
        arranca con el juego) -- la 1, o la etapa inicial que eligió el
        evaluador (ver session_wizard.STARTABLE_STAGES)."""
        if self._paused_at is not None:
            return
        now = _now()
        if self._session is None:
            self._session = {
                "numero": self.next_session_number(), "inicio": now, "fin": None,
                "duracion_s": 0, "cierre": _OPEN, "desafios": [],
            }
            self.data["sesiones"].append(self._session)
        self._end_stage(now)
        if challenge not in self._session["desafios"]:
            self._session["desafios"].append(challenge)
        self._stage = {
            "sesion": self._session["numero"], "desafio": challenge, "juego": game,
            "etapa": stage, "intento": attempt, "inicio": now, "fin": None, "duracion_s": None,
        }
        self.data["etapas"].append(self._stage)
        self._save()

    def pause(self) -> None:
        """Detiene el reloj (se presionó "Guardar progreso" o "Terminar
        sesión guiada"); el cierre se confirma después con close()."""
        if self._session is None or self._paused_at is not None:
            return
        self._paused_at = _now()
        self._end_stage(self._paused_at)
        self._session["fin"] = self._paused_at
        self._session["duracion_s"] = round(_seconds_between(self._session["inicio"], self._paused_at))
        self._save()

    def close(self, how: str) -> None:
        if self._session is None:
            return
        self.pause()
        self._session["cierre"] = how
        self._session = None
        self._paused_at = None
        self._save()

    def _end_stage(self, at: str) -> None:
        if self._stage is not None and self._stage["fin"] is None:
            self._stage["fin"] = at
            self._stage["duracion_s"] = round(_seconds_between(self._stage["inicio"], at))
        self._stage = None

    # ---------------- resumen + guardado ----------------
    def _summary(self) -> dict:
        counted_numbers = {s["numero"] for s in self.data["sesiones"] if s["cierre"] in COUNTED_CLOSES}
        per_challenge: dict[str, dict] = {}
        for stage in self.data["etapas"]:
            if stage["sesion"] not in counted_numbers or stage["duracion_s"] is None:
                continue
            entry = per_challenge.setdefault(str(stage["desafio"]), {
                "juego": stage["juego"], "tiempo_s": 0, "etapas_s": {},
            })
            entry["tiempo_s"] += stage["duracion_s"]
            key = str(stage["etapa"])
            entry["etapas_s"][key] = entry["etapas_s"].get(key, 0) + stage["duracion_s"]
        for entry in per_challenge.values():
            entry["tiempo"] = format_duration(entry["tiempo_s"])
            entry["etapas_s"] = dict(sorted(entry["etapas_s"].items(), key=lambda kv: int(kv[0])))

        total = self.counted_total_seconds()
        completed = any(s["cierre"] == CLOSE_FINISHED for s in self.data["sesiones"])
        counted = self.counted_sessions()
        return {
            "sesiones_contadas": counted,
            "veces_retomada": max(counted - 1, 0),
            "tiempo_total_s": total,
            "tiempo_total": format_duration(total),
            "completo_los_7_juegos": completed,
            "tiempo_total_7_juegos": format_duration(total) if completed else None,
            "por_desafio": dict(sorted(per_challenge.items(), key=lambda kv: int(kv[0]))),
        }

    def _save(self) -> None:
        self.data["resumen"] = self._summary()
        self.data["actualizado"] = _now()
        payload = {"participante": self.data["participante"], "resumen": self.data["resumen"]}
        payload.update({k: v for k, v in self.data.items() if k not in payload})
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)
