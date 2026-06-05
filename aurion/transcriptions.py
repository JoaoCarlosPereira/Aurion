"""Transcriptions — armazena e consulta todas as transcrições de áudio."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal


@contextmanager
def _connect(db_path: str):
    """Context manager que abre e fecha conexões SQLite."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _ensure_table(db_path: str) -> None:
    """Cria a tabela de transcrições se não existir."""
    with _connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transcriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                transcript TEXT NOT NULL,
                mode TEXT NOT NULL,
                confidence REAL
            );
        """)
        conn.commit()


def insert_transcription(
    db_path: str,
    transcript: str,
    mode: Literal["wake", "command", "unknown"],
    confidence: float | None = None,
) -> int:
    """Insere uma transcrição no banco de dados."""
    _ensure_table(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO transcriptions (transcript, mode, confidence)
               VALUES (?, ?, ?)""",
            (transcript, mode, confidence),
        )
        conn.commit()
        return cur.lastrowid


def list_transcriptions(
    db_path: str,
    mode: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """Lista transcrições com filtro opcional por modo."""
    _ensure_table(db_path)
    clauses: list[str] = []
    params: list = []
    if mode:
        clauses.append("mode = ?")
        params.append(mode)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    query = f"SELECT * FROM transcriptions{where} ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    with _connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
