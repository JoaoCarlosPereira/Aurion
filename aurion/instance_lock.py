"""Garante uma única instância do servidor Aurion por máquina."""

from __future__ import annotations

import atexit
import fcntl
import logging
import os
from pathlib import Path

logger = logging.getLogger("aurion.instance")


class InstanceLock:
    """Lock exclusivo via arquivo (fcntl) para evitar duas instâncias."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._handle = None

    def acquire(self) -> bool:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = open(self._path, "w", encoding="utf-8")
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._handle.close()
            self._handle = None
            return False

        self._handle.write(str(os.getpid()))
        self._handle.flush()
        atexit.register(self.release)
        logger.info("Lock de instância adquirido: %s (pid=%s)", self._path, os.getpid())
        return True

    def release(self) -> None:
        if not self._handle:
            return
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            self._handle.close()
        except OSError:
            pass
        finally:
            self._handle = None
        try:
            self._path.unlink(missing_ok=True)
        except OSError:
            pass


def default_lock_path() -> Path:
    return Path(os.getenv("AURION_LOCK_FILE", "/tmp/aurion.lock"))


def acquire_instance_lock(path: str | Path | None = None) -> InstanceLock | None:
    """Tenta adquirir o lock. Retorna None se outra instância já estiver ativa."""
    lock = InstanceLock(path or default_lock_path())
    if lock.acquire():
        return lock
    return None
