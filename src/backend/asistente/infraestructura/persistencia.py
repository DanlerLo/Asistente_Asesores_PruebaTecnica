"""Persistencia de consultas en SQLite (biblioteca estándar, sin dependencias).

Cada consulta atendida se registra con: pregunta, fecha y hora (UTC, ISO 8601),
respuesta generada, fuentes utilizadas (JSON), estado, latencia y modo de
generación. Es la base de la observabilidad del sistema.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..dominio import ESTADOS

_ESQUEMA = f"""
CREATE TABLE IF NOT EXISTS consultas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pregunta    TEXT    NOT NULL,
    fecha_hora  TEXT    NOT NULL,
    respuesta   TEXT    NOT NULL,
    fuentes     TEXT    NOT NULL DEFAULT '[]',
    estado      TEXT    NOT NULL CHECK (estado IN ({", ".join("'" + e + "'" for e in ESTADOS)})),
    latencia_ms INTEGER NOT NULL DEFAULT 0,
    modo        TEXT    NOT NULL DEFAULT 'extractivo'
);
CREATE INDEX IF NOT EXISTS idx_consultas_fecha ON consultas (fecha_hora);
CREATE INDEX IF NOT EXISTS idx_consultas_estado ON consultas (estado);
"""


@dataclass(frozen=True)
class RegistroConsulta:
    pregunta: str
    respuesta: str
    fuentes: list[dict]
    estado: str
    latencia_ms: int
    modo: str
    fecha_hora: str


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class RepositorioConsultas:
    """Acceso a la tabla ``consultas``. Seguro para uso desde varios hilos."""

    def __init__(self, ruta: Path | str = ":memory:") -> None:
        self.ruta = str(ruta)
        if self.ruta != ":memory:":
            Path(self.ruta).parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(self.ruta, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._con.executescript(_ESQUEMA)

    def guardar(self, registro: RegistroConsulta) -> int:
        if registro.estado not in ESTADOS:
            raise ValueError(f"Estado inválido: {registro.estado}")
        with self._lock:
            cursor = self._con.execute(
                "INSERT INTO consultas (pregunta, fecha_hora, respuesta, fuentes, estado, latencia_ms, modo) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    registro.pregunta,
                    registro.fecha_hora,
                    registro.respuesta,
                    json.dumps(registro.fuentes, ensure_ascii=False),
                    registro.estado,
                    registro.latencia_ms,
                    registro.modo,
                ),
            )
            self._con.commit()
            return int(cursor.lastrowid or 0)

    def obtener(self, id_consulta: int) -> dict | None:
        with self._lock:
            fila = self._con.execute("SELECT * FROM consultas WHERE id = ?", (id_consulta,)).fetchone()
        return self._a_dict(fila) if fila else None

    def listar(self, limite: int = 20) -> list[dict]:
        limite = max(1, min(int(limite), 200))
        with self._lock:
            filas = self._con.execute(
                "SELECT * FROM consultas ORDER BY id DESC LIMIT ?", (limite,)
            ).fetchall()
        return [self._a_dict(f) for f in filas]

    def estadisticas(self) -> dict:
        with self._lock:
            total = self._con.execute("SELECT COUNT(*) AS n FROM consultas").fetchone()["n"]
            por_estado = {
                f["estado"]: f["n"]
                for f in self._con.execute(
                    "SELECT estado, COUNT(*) AS n FROM consultas GROUP BY estado"
                ).fetchall()
            }
            latencia = self._con.execute(
                "SELECT COALESCE(AVG(latencia_ms), 0) AS promedio, COALESCE(MAX(latencia_ms), 0) AS maxima "
                "FROM consultas"
            ).fetchone()
        return {
            "total": total,
            "por_estado": {estado: por_estado.get(estado, 0) for estado in ESTADOS},
            "latencia_ms_promedio": round(float(latencia["promedio"]), 1),
            "latencia_ms_maxima": int(latencia["maxima"]),
        }

    def cerrar(self) -> None:
        with self._lock:
            self._con.close()

    @staticmethod
    def _a_dict(fila: sqlite3.Row) -> dict:
        datos = dict(fila)
        datos["fuentes"] = json.loads(datos["fuentes"])
        return datos
