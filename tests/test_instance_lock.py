"""Tests for single-instance lock."""

import os
from pathlib import Path

from aurion.instance_lock import InstanceLock, acquire_instance_lock


def test_instance_lock_exclusive(tmp_path):
    path = tmp_path / "aurion-test.lock"
    first = InstanceLock(path)
    second = InstanceLock(path)
    assert first.acquire() is True
    assert second.acquire() is False
    first.release()
    assert second.acquire() is True
    second.release()


def test_acquire_instance_lock_helper(tmp_path, monkeypatch):
    lock_file = tmp_path / "aurion.lock"
    monkeypatch.setenv("AURION_LOCK_FILE", str(lock_file))
    lock = acquire_instance_lock()
    assert lock is not None
    assert lock_file.exists()
    lock.release()
    again = acquire_instance_lock()
    assert again is not None
    again.release()
