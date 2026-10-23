from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from aria.api.tenancy import TenantStore


def test_tenant_store_enforces_foreign_keys_and_uses_wal(tmp_path: Path):
    store = TenantStore(tmp_path / "tenant.db")
    with store._connect() as db:
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert db.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        with pytest.raises(Exception):
            db.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?)",
                ("orphan", "missing-user", "2099-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
            )


def test_session_creation_prunes_expired_sessions(tmp_path: Path):
    store = TenantStore(tmp_path / "tenant.db")
    admin = store.create_tenant_admin("Test tenant", "admin@example.com", "correct-horse-battery-staple")
    with store._connect() as db:
        db.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?)",
            (
                "expired-session",
                admin["id"],
                (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    store.create_session(admin["id"])
    with store._connect() as db:
        assert db.execute("SELECT COUNT(*) FROM sessions WHERE token_hash = 'expired-session'").fetchone()[0] == 0
