from __future__ import annotations

import json

from aria.access.credentials import CredentialManager


def test_credential_manager_save_and_load(tmp_path):
    path = tmp_path / "credentials.json"
    manager = CredentialManager()
    manager.credentials = {"ieee": {"username": "user", "password": "secret"}}
    manager.save(path)

    loaded = CredentialManager(path)
    assert loaded.has("ieee")
    assert loaded.get("ieee")["username"] == "user"
    payload = json.loads(path.read_text())
    assert "platforms" in payload
