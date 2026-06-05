"""Database layer — CRUD com SQLite para comandos, logs e configurações."""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── Pydantic models ──────────────────────────────────────────────

class CommandEntry(BaseModel):
    id: int | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    source: Literal["voice", "web"]
    input_text: str
    response_text: str | None = None
    hermes_status: str = "pending"
    device_id: str | None = None


class LogEntry(BaseModel):
    id: int | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    level: Literal["INFO", "WARNING", "ERROR"]
    component: str
    message: str


class SettingEntry(BaseModel):
    key: str
    value: str


# ── SQLite helpers ───────────────────────────────────────────────

DEFAULT_DB_PATH = "aurion/aurion.db"

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    ended_at DATETIME,
    source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    source TEXT NOT NULL,
    input_text TEXT NOT NULL,
    response_text TEXT,
    hermes_status TEXT DEFAULT 'pending',
    device_id TEXT,
    conversation_id INTEGER REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    level TEXT NOT NULL,
    component TEXT NOT NULL,
    message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@contextmanager
def _connect(db_path: str):
    """Context manager que abre e fecha conexões SQLite."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Inicializa o banco, criando tabelas e seeds."""
    import os
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)
        _migrate_db(conn)

    # Seed default settings (não sobrescreve valores já salvos)
    _seed_setting_if_missing(db_path, "trigger_word", os.getenv("TRIGGER_WORD", "hermes"))
    _seed_setting_if_missing(db_path, "tts_rate", "160")
    _seed_setting_if_missing(db_path, "tts_volume", "1.0")

    return sqlite3.connect(db_path)


def _migrate_db(conn: sqlite3.Connection) -> None:
    """Aplica migrações incrementais em bancos existentes."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(commands)").fetchall()}
    if "conversation_id" not in cols:
        conn.execute("ALTER TABLE commands ADD COLUMN conversation_id INTEGER")

    orphans = conn.execute(
        "SELECT id, source, timestamp FROM commands WHERE conversation_id IS NULL"
    ).fetchall()
    for row in orphans:
        cur = conn.execute(
            "INSERT INTO conversations (started_at, ended_at, source) VALUES (?, ?, ?)",
            (row["timestamp"], row["timestamp"], row["source"]),
        )
        conn.execute(
            "UPDATE commands SET conversation_id = ? WHERE id = ?",
            (cur.lastrowid, row["id"]),
        )
    conn.commit()


# ── Conversations CRUD ───────────────────────────────────────────

def create_conversation(db_path: str, source: str) -> int:
    """Cria uma nova conversa e retorna o id."""
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO conversations (source) VALUES (?)",
            (source,),
        )
        conn.commit()
        return cur.lastrowid  # type: ignore[return-value]


def end_conversation(db_path: str, conversation_id: int) -> None:
    """Marca o fim de uma conversa."""
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE conversations SET ended_at = CURRENT_TIMESTAMP WHERE id = ? AND ended_at IS NULL",
            (conversation_id,),
        )
        conn.commit()


def list_conversations(
    db_path: str,
    source: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Lista conversas com mensagens user/assistant derivadas dos comandos."""
    clauses: list[str] = []
    params: list = []

    if source:
        clauses.append("c.source = ?")
        params.append(source)
    if date_from:
        clauses.append("c.started_at >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("c.started_at <= ?")
        params.append(date_to)

    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    query = f"""
        SELECT c.id, c.started_at, c.ended_at, c.source
        FROM conversations c
        {where}
        ORDER BY c.started_at DESC
        LIMIT ?
    """
    params.append(limit)

    with _connect(db_path) as conn:
        conv_rows = conn.execute(query, params).fetchall()
        conversations: list[dict] = []

        for conv in conv_rows:
            cmd_rows = conn.execute(
                """SELECT id, timestamp, input_text, response_text, hermes_status
                   FROM commands
                   WHERE conversation_id = ?
                   ORDER BY timestamp ASC, id ASC""",
                (conv["id"],),
            ).fetchall()

            messages: list[dict] = []
            for cmd in cmd_rows:
                ts = str(cmd["timestamp"])
                messages.append({
                    "role": "user",
                    "content": cmd["input_text"],
                    "timestamp": ts,
                })
                if cmd["response_text"]:
                    messages.append({
                        "role": "assistant",
                        "content": cmd["response_text"],
                        "timestamp": ts,
                        "status": cmd["hermes_status"],
                    })

            conversations.append({
                "id": conv["id"],
                "started_at": str(conv["started_at"]),
                "ended_at": str(conv["ended_at"]) if conv["ended_at"] else None,
                "source": conv["source"],
                "turn_count": len(cmd_rows),
                "messages": messages,
            })

        return conversations


def get_conversation(db_path: str, conversation_id: int) -> dict | None:
    """Busca uma conversa específica com mensagens."""
    with _connect(db_path) as conn:
        conv = conn.execute(
            "SELECT id, started_at, ended_at, source FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if not conv:
            return None

        cmd_rows = conn.execute(
            """SELECT id, timestamp, input_text, response_text, hermes_status
               FROM commands
               WHERE conversation_id = ?
               ORDER BY timestamp ASC, id ASC""",
            (conversation_id,),
        ).fetchall()

    messages: list[dict] = []
    for cmd in cmd_rows:
        ts = str(cmd["timestamp"])
        messages.append({"role": "user", "content": cmd["input_text"], "timestamp": ts})
        if cmd["response_text"]:
            messages.append({
                "role": "assistant",
                "content": cmd["response_text"],
                "timestamp": ts,
                "status": cmd["hermes_status"],
            })

    return {
        "id": conv["id"],
        "started_at": str(conv["started_at"]),
        "ended_at": str(conv["ended_at"]) if conv["ended_at"] else None,
        "source": conv["source"],
        "turn_count": len(cmd_rows),
        "messages": messages,
    }


# ── Commands CRUD ────────────────────────────────────────────────

def insert_command(db_path: str, source: str, input_text: str,
                   response_text: str | None = None,
                   hermes_status: str = "pending",
                   device_id: str | None = None,
                   conversation_id: int | None = None) -> int:
    """Insera um comando e retorna o id gerado."""
    with _connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO commands
               (source, input_text, response_text, hermes_status, device_id, conversation_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source, input_text, response_text, hermes_status, device_id, conversation_id),
        )
        conn.commit()
        return cur.lastrowid  # type: ignore[return-value]


def get_command(db_path: str, cmd_id: int) -> dict | None:
    """Busca um comando por ID."""
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM commands WHERE id = ?", (cmd_id,)).fetchone()
        return dict(row) if row else None


def list_commands(db_path: str, source: str | None = None,
                  date_from: str | None = None,
                  date_to: str | None = None,
                  limit: int = 100) -> list[dict]:
    """Lista comandos com filtros opcionais."""
    clauses: list[str] = []
    params: list = []

    if source:
        clauses.append("source = ?")
        params.append(source)
    if date_from:
        clauses.append("timestamp >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("timestamp <= ?")
        params.append(date_to)

    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    query = f"SELECT * FROM commands{where} ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    with _connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


# ── Logs CRUD ────────────────────────────────────────────────────

def insert_log(db_path: str, level: str, component: str,
               message: str) -> int:
    """Insera um log e retorna o id gerado."""
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO logs (level, component, message) VALUES (?, ?, ?)",
            (level, component, message),
        )
        conn.commit()
        return cur.lastrowid  # type: ignore[return-value]


def list_logs(db_path: str, level: str | None = None,
              component: str | None = None,
              limit: int = 200) -> list[dict]:
    """Lista logs com filtros opcionais."""
    clauses: list[str] = []
    params: list = []

    if level:
        clauses.append("level = ?")
        params.append(level)
    if component:
        clauses.append("component = ?")
        params.append(component)

    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    query = f"SELECT * FROM logs{where} ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    with _connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


# ── Settings CRUD ────────────────────────────────────────────────

def get_setting(db_path: str, key: str) -> str | None:
    """Busca o valor de uma configuração pela chave."""
    with _connect(db_path) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None


def set_setting(db_path: str, key: str, value: str) -> None:
    """Insere ou atualiza uma configuração (UPSERT)."""
    _upsert_setting(db_path, key, value)


def _seed_setting_if_missing(db_path: str, key: str, value: str) -> None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT 1 FROM settings WHERE key = ?", (key,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )
            conn.commit()


def _upsert_setting(db_path: str, key: str, value: str) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()
