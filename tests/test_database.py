"""Tests for Database layer."""

import sqlite3
import pytest

from aurion.database import (
    insert_command, get_command, list_commands,
    insert_log, list_logs, get_setting, set_setting,
    _SCHEMA,
)


def _make_db():
    """Cria um banco em-memory com tabelas e seeds."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("trigger_word", "ermes"))
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("tts_rate", "160"))
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("tts_volume", "1.0"))
    conn.commit()
    return conn


@pytest.fixture
def db():
    conn = _make_db()
    yield conn
    conn.close()


def test_insert_and_get_command(db):
    with db:
        cur = db.execute(
            "INSERT INTO commands (source, input_text) VALUES (?, ?)",
            ("web", "hello"),
        )
        db.commit()
        cmd_id = cur.lastrowid

    with db:
        row = db.execute("SELECT * FROM commands WHERE id = ?", (cmd_id,)).fetchone()
        assert row is not None
        assert row["input_text"] == "hello"
        assert row["source"] == "web"


def test_list_commands_filter_by_source(db):
    with db:
        db.execute("INSERT INTO commands (source, input_text) VALUES (?, ?)", ("voice", "cmd1"))
        db.execute("INSERT INTO commands (source, input_text) VALUES (?, ?)", ("web", "cmd2"))
        db.execute("INSERT INTO commands (source, input_text) VALUES (?, ?)", ("voice", "cmd3"))
        db.commit()

    with db:
        voice_cmds = db.execute("SELECT * FROM commands WHERE source = 'voice'").fetchall()
        web_cmds = db.execute("SELECT * FROM commands WHERE source = 'web'").fetchall()

    assert len(voice_cmds) == 2
    assert len(web_cmds) == 1
    assert all(r["source"] == "voice" for r in voice_cmds)
    assert all(r["source"] == "web" for r in web_cmds)


def test_list_commands_filter_by_date(db):
    with db:
        db.execute("INSERT INTO commands (source, input_text) VALUES (?, ?)", ("web", "old"))
        db.execute("INSERT INTO commands (source, input_text) VALUES (?, ?)", ("web", "new"))
        db.commit()

    import datetime
    today = datetime.date.today().isoformat()
    with db:
        rows = db.execute("SELECT * FROM commands WHERE timestamp >= ?", (today,)).fetchall()
    assert len(rows) >= 1


def test_insert_and_list_logs(db):
    with db:
        db.execute("INSERT INTO logs (level, component, message) VALUES (?, ?, ?)",
                   ("INFO", "api", "Request received"))
        db.execute("INSERT INTO logs (level, component, message) VALUES (?, ?, ?)",
                   ("ERROR", "hermes", "Connection failed"))
        db.commit()

    with db:
        all_logs = db.execute("SELECT * FROM logs").fetchall()
        error_logs = db.execute("SELECT * FROM logs WHERE level = 'ERROR'").fetchall()
        api_logs = db.execute("SELECT * FROM logs WHERE component = 'api'").fetchall()

    assert len(all_logs) == 2
    assert len(error_logs) == 1
    assert error_logs[0]["component"] == "hermes"
    assert len(api_logs) == 1


def test_setting_get_set(db):
    with db:
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                   ("custom_key", "custom_value"))
        db.commit()

    with db:
        row = db.execute("SELECT value FROM settings WHERE key = ?", ("custom_key",)).fetchone()

    assert row is not None
    assert row["value"] == "custom_value"


def test_setting_duplicate_updates(db):
    with db:
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                   ("dup_key", "first"))
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                   ("dup_key", "second"))
        db.commit()

    with db:
        row = db.execute("SELECT value FROM settings WHERE key = ?", ("dup_key",)).fetchone()

    assert row["value"] == "second"


def test_default_settings_exist(db):
    """Default seed settings estao presentes."""
    with db:
        trigger = db.execute("SELECT value FROM settings WHERE key = ?", ("trigger_word",)).fetchone()
        tts_rate = db.execute("SELECT value FROM settings WHERE key = ?", ("tts_rate",)).fetchone()
        tts_vol = db.execute("SELECT value FROM settings WHERE key = ?", ("tts_volume",)).fetchone()

    assert trigger is not None and trigger["value"] == "ermes"
    assert tts_rate is not None and tts_rate["value"] == "160"
    assert tts_vol is not None and tts_vol["value"] == "1.0"
