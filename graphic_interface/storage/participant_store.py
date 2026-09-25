"""Persistencia de participantes en JSON con esquema extensible.

Los participantes se registran de forma anonima: no se guarda nombre,
apellido ni cedula, solo un numero secuencial ("Participante 1",
"Participante 2", ...) que nunca se reutiliza aunque se borren
participantes, mas una bolsa "attributes" de clave-valor libre para
poder agregar atributos futuros (edad, grupo experimental, etc.) sin
romper los registros ya guardados.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = 2


def participant_label(participant: dict) -> str:
    """Nombre visible del participante, ej. "Participante 3"."""
    return f"Participante {participant['number']}"


def participant_file_stub(participant: dict) -> str:
    """Identificador "PARTICIPANTE_N" usado para nombrar los archivos de
    datos de este participante (log de emociones, log de frecuencia
    cardiaca) y la carpeta que debe traer el export del reloj.
    """
    return f"PARTICIPANTE_{participant['number']}"


class ParticipantStore:
    def __init__(self, data_path: Path):
        self.data_path = Path(data_path)
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if not self.data_path.exists():
            data = {
                "schema_version": SCHEMA_VERSION,
                "active_participant_id": None,
                "next_number": 1,
                "participants": [],
            }
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
        data.setdefault("next_number", len(data["participants"]) + 1)
        return data

    def _save(self) -> None:
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def list_participants(self) -> list[dict]:
        return list(self._data["participants"])

    def add_participant(self, **extra_attributes: Any) -> dict:
        number = self._data["next_number"]
        participant = {
            "id": str(uuid.uuid4()),
            "number": number,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "attributes": dict(extra_attributes),
        }
        self._data["participants"].append(participant)
        self._data["next_number"] = number + 1
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

    def set_attribute(self, participant_id: str, key: str, value: Any) -> None:
        for p in self._data["participants"]:
            if p["id"] == participant_id:
                p.setdefault("attributes", {})[key] = value
                self._save()
                return

    def clear_attribute(self, participant_id: str, key: str) -> None:
        for p in self._data["participants"]:
            if p["id"] == participant_id:
                if key in p.get("attributes", {}):
                    del p["attributes"][key]
                    self._save()
                return
