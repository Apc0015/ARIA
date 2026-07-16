"""Encryption-at-rest behavior of CredentialManager (ARIA_CREDENTIALS_KEY)."""

from __future__ import annotations

import json
import os
import stat

import pytest

from aria.engine.access.credential_manager import CredentialManager


@pytest.fixture()
def fernet_key(monkeypatch) -> str:
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ARIA_CREDENTIALS_KEY", key)
    return key


def test_encrypted_roundtrip(tmp_path, fernet_key):
    path = tmp_path / "credentials.json"
    manager = CredentialManager()
    manager.credentials = {"github_token": "ghp_secret1234567890abcdefgh"}
    manager.save(path)

    on_disk = json.loads(path.read_text())
    assert on_disk.get("encrypted") is True
    assert "ghp_secret" not in path.read_text()  # never plaintext on disk

    reloaded = CredentialManager(path)
    assert reloaded.credentials == {"github_token": "ghp_secret1234567890abcdefgh"}


def test_plaintext_files_still_load(tmp_path, monkeypatch):
    monkeypatch.delenv("ARIA_CREDENTIALS_KEY", raising=False)
    path = tmp_path / "credentials.json"
    path.write_text(json.dumps({"platforms": {"slack_token": "xoxb-1"}}))
    manager = CredentialManager(path)
    assert manager.credentials == {"slack_token": "xoxb-1"}


def test_wrong_key_fails_safe_not_crash(tmp_path, monkeypatch, fernet_key, caplog):
    path = tmp_path / "credentials.json"
    manager = CredentialManager()
    manager.credentials = {"notion_token": "secret"}
    manager.save(path)

    from cryptography.fernet import Fernet

    monkeypatch.setenv("ARIA_CREDENTIALS_KEY", Fernet.generate_key().decode())
    reloaded = CredentialManager(path)  # must not raise
    assert reloaded.credentials == {}
    assert any("decrypt" in r.message.lower() for r in caplog.records)


def test_saved_file_is_owner_only(tmp_path, monkeypatch):
    monkeypatch.delenv("ARIA_CREDENTIALS_KEY", raising=False)
    path = tmp_path / "credentials.json"
    manager = CredentialManager()
    manager.credentials = {"k": "v"}
    manager.save(path)
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600
