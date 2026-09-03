"""Persistencia de sesiones de experimento.

Una sesion es la ventana de tiempo [start_time, end_time] durante la cual
un participante estuvo siendo grabado (emociones por camara + frecuencia
cardiaca del reloj). Esa ventana es la que luego se usa para filtrar, del
export de Samsung Health, solo las lecturas de BPM que ocurrieron durante
la sesion.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

SCHEMA_VERSION = 1
TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S"


def now_str() -> str:
    return datetime.now().strftime(TIMESTAMP_FMT)


class SessionStore:
    def __init__(self, data_path: Path):
        self.data_path = Path(data_path)
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if not self.data_path.exists():
            data = {"schema_version": SCHEMA_VERSION, "sessions": []}
            self._data = data
            self._save()
            return data
        with open(self.data_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
        data.setdefault("schema_version", SCHEMA_VERSION)
        data.setdefault("sessions", [])
        return data

    def _save(self) -> None:
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def start_session(self, participant_id: str, label: str = "") -> dict:
        session = {
            "id": str(uuid.uuid4()),
            "participant_id": participant_id,
            "label": label,
            "start_time": now_str(),
            "end_time": None,
        }
        self._data["sessions"].append(session)
        self._save()
        return session

    def end_session(self, session_id: str) -> Optional[dict]:
        for s in self._data["sessions"]:
            if s["id"] == session_id:
                s["end_time"] = now_str()
                self._save()
                return s
        return None

    def list_sessions(self, participant_id: Optional[str] = None) -> list[dict]:
        sessions = self._data["sessions"]
        if participant_id:
            sessions = [s for s in sessions if s["participant_id"] == participant_id]
        return list(sessions)

    def get_last_session(self, participant_id: str) -> Optional[dict]:
        sessions = self.list_sessions(participant_id)
        return sessions[-1] if sessions else None

    def get_open_session(self, participant_id: str) -> Optional[dict]:
        """Sesion sin end_time (activa) del participante, si hay alguna."""
        for s in reversed(self.list_sessions(participant_id)):
            if s["end_time"] is None:
                return s
        return None
