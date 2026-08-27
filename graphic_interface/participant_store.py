"""Persistencia de participantes en JSON con esquema extensible.

El esquema guarda los campos fijos (nombre, apellido, cedula) mas una
bolsa "attributes" de clave-valor libre, para poder agregar atributos
nuevos (edad, carrera, grupo experimental, etc.) en el futuro sin
romper los registros ya guardados.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = 1


class ParticipantStore:
    def __init__(self, data_path: Path):
        self.data_path = Path(data_path)
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if not self.data_path.exists():
            data = {"schema_version": SCHEMA_VERSION, "active_participant_id": None, "participants": []}
            self._data = data
            self._save()
            return data
        with open(self.data_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
        data.setdefault("schema_version", SCHEMA_VERSION)
        data.setdefault("active_participant_id", None)
        data.setdefault("participants", [])
        return data

    def _save(self) -> None:
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def list_participants(self) -> list[dict]:
        return list(self._data["participants"])

    def add_participant(self, nombre: str, apellido: str, cedula: str, **extra_attributes: Any) -> dict:
        cedula = cedula.strip()
        if any(p["cedula"] == cedula for p in self._data["participants"]):
            raise ValueError(f"Ya existe un participante con la cedula {cedula}")
        participant = {
            "id": str(uuid.uuid4()),
            "nombre": nombre.strip().upper(),
            "apellido": apellido.strip().upper(),
            "cedula": cedula,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "attributes": dict(extra_attributes),
        }
        self._data["participants"].append(participant)
        self._save()
        return participant

    def delete_participant(self, participant_id: str) -> None:
        self._data["participants"] = [p for p in self._data["participants"] if p["id"] != participant_id]
        if self._data.get("active_participant_id") == participant_id:
            self._data["active_participant_id"] = None
        self._save()

    def set_active(self, participant_id: Optional[str]) -> None:
        self._data["active_participant_id"] = participant_id
        self._save()

    def get_active(self) -> Optional[dict]:
        active_id = self._data.get("active_participant_id")
        if not active_id:
            return None
        for p in self._data["participants"]:
            if p["id"] == active_id:
                return p
        return None
