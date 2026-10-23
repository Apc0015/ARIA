"""Durable tenant, user, and server-side session storage for ARIA SaaS."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_password(password: str, salt: bytes | None = None) -> str:
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters.")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        _algorithm, salt_text, digest_text = encoded.split("$", 2)
        actual = hashlib.scrypt(
            password.encode(), salt=base64.b64decode(salt_text), n=2**14, r=8, p=1
        )
        return hmac.compare_digest(actual, base64.b64decode(digest_text))
    except (ValueError, TypeError):
        return False


class TenantStore:
    """Small durable auth store. Run artifacts remain filesystem-based per tenant."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        # SQLite is retained for the controlled single-instance deployment,
        # so every short-lived request connection needs the same integrity and
        # contention settings. Foreign keys are otherwise disabled by default.
        timeout_seconds = float(os.getenv("ARIA_SQLITE_BUSY_TIMEOUT_SECONDS", "5"))
        connection = sqlite3.connect(self.path, timeout=timeout_seconds)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {int(timeout_seconds * 1000)}")
        return connection

    def healthcheck(self) -> bool:
        """Return whether the tenant metadata database accepts a query."""
        try:
            with self._connect() as db:
                db.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False

    def _init_schema(self) -> None:
        migration_dir = Path(__file__).with_name("migrations")
        with self._connect() as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.execute("PRAGMA synchronous = NORMAL")
            db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
            applied = {row[0] for row in db.execute("SELECT version FROM schema_migrations")}
            for migration in sorted(migration_dir.glob("*.sql")):
                if migration.name not in applied:
                    db.executescript(migration.read_text(encoding="utf-8"))
                    db.execute("INSERT INTO schema_migrations(version) VALUES (?)", (migration.name,))

    def bootstrap_from_env(self) -> None:
        """Create the first administrator only when deployment explicitly requests it."""
        email = os.getenv("ARIA_BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
        password = os.getenv("ARIA_BOOTSTRAP_ADMIN_PASSWORD", "")
        tenant_name = os.getenv("ARIA_BOOTSTRAP_TENANT", "ARIA").strip() or "ARIA"
        if email and password:
            self.create_tenant_admin(tenant_name, email, password)

    def create_tenant_admin(self, tenant_name: str, email: str, password: str) -> dict:
        email = email.strip().lower()
        with self._connect() as db:
            existing = db.execute("SELECT id, tenant_id, role FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                return dict(existing)
            tenant_id = secrets.token_urlsafe(12)
            user_id = secrets.token_urlsafe(12)
            db.execute("INSERT INTO tenants VALUES (?, ?, ?)", (tenant_id, tenant_name, _now()))
            db.execute(
                "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, NULL)",
                (user_id, tenant_id, email, _hash_password(password), "admin", _now()),
            )
            return {"id": user_id, "tenant_id": tenant_id, "role": "admin"}

    def authenticate(self, email: str, password: str) -> dict | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT id, tenant_id, email, password_hash, role, disabled_at FROM users WHERE email = ?",
                (email.strip().lower(),),
            ).fetchone()
        if not row or row["disabled_at"] or not _verify_password(password, row["password_hash"]):
            return None
        return {key: row[key] for key in ("id", "tenant_id", "email", "role")}

    def create_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expiry = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
        with self._connect() as db:
            db.execute("DELETE FROM sessions WHERE expires_at <= ?", (_now(),))
            db.execute("INSERT INTO sessions VALUES (?, ?, ?, ?)", (token_hash, user_id, expiry, _now()))
        return token

    def change_password(self, user_id: str, current_password: str, new_password: str) -> bool:
        """Change one user's password after verifying their current password."""
        with self._connect() as db:
            row = db.execute(
                "SELECT password_hash, disabled_at FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if not row or row["disabled_at"] or not _verify_password(current_password, row["password_hash"]):
                return False
            # _hash_password enforces the minimum password length before an
            # update is committed.
            db.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (_hash_password(new_password), user_id),
            )
        return True

    def delete_user_sessions(self, user_id: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))

    def reset_user_password(self, tenant_id: str, user_id: str, new_password: str) -> dict | None:
        """Set a tenant member's temporary password and revoke their sessions."""
        password_hash = _hash_password(new_password)
        with self._connect() as db:
            row = db.execute(
                "SELECT id, email, role, created_at, disabled_at FROM users WHERE id = ? AND tenant_id = ?",
                (user_id, tenant_id),
            ).fetchone()
            if not row:
                return None
            db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
            db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        return dict(row)

    def get_session_user(self, token: str) -> dict | None:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with self._connect() as db:
            row = db.execute(
                """SELECT u.id, u.tenant_id, u.email, u.role FROM sessions s
                   JOIN users u ON u.id = s.user_id
                   WHERE s.token_hash = ? AND s.expires_at > ? AND u.disabled_at IS NULL""",
                (token_hash, _now()),
            ).fetchone()
        return dict(row) if row else None

    def delete_session(self, token: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),))

    def list_users(self, tenant_id: str) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT id, email, role, created_at, disabled_at FROM users WHERE tenant_id = ? ORDER BY email", (tenant_id,)).fetchall()
        return [dict(row) for row in rows]

    def create_user(self, tenant_id: str, email: str, password: str, role: str = "member") -> dict:
        if role not in {"admin", "member", "viewer"}:
            raise ValueError("Role must be admin, member, or viewer.")
        user_id = secrets.token_urlsafe(12)
        with self._connect() as db:
            try:
                db.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, NULL)", (user_id, tenant_id, email.strip().lower(), _hash_password(password), role, _now()))
            except sqlite3.IntegrityError as exc:
                raise ValueError("A user with that email already exists.") from exc
        return {"id": user_id, "email": email.strip().lower(), "role": role}

    def update_user(self, tenant_id: str, user_id: str, *, role: str | None = None, disabled: bool | None = None) -> dict | None:
        if role and role not in {"admin", "member", "viewer"}:
            raise ValueError("Role must be admin, member, or viewer.")
        with self._connect() as db:
            row = db.execute(
                "SELECT id, role, disabled_at FROM users WHERE id = ? AND tenant_id = ?",
                (user_id, tenant_id),
            ).fetchone()
            if not row:
                return None
            # Avoid an unrecoverable tenant: the final enabled administrator
            # cannot be disabled or changed to a non-admin role.
            removes_last_admin = (
                row["role"] == "admin"
                and row["disabled_at"] is None
                and (disabled is True or (role is not None and role != "admin"))
            )
            if removes_last_admin:
                active_admins = db.execute(
                    "SELECT COUNT(*) FROM users WHERE tenant_id = ? AND role = 'admin' AND disabled_at IS NULL",
                    (tenant_id,),
                ).fetchone()[0]
                if active_admins <= 1:
                    raise ValueError("An organization must retain at least one active administrator.")
            if role:
                db.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
            if disabled is not None:
                db.execute("UPDATE users SET disabled_at = ? WHERE id = ?", (_now() if disabled else None, user_id))
                if disabled:
                    db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            result = db.execute("SELECT id, email, role, created_at, disabled_at FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(result)

    def get_setting(self, tenant_id: str, setting_key: str, default: dict) -> dict:
        with self._connect() as db:
            row = db.execute("SELECT value_json FROM tenant_settings WHERE tenant_id = ? AND setting_key = ?", (tenant_id, setting_key)).fetchone()
        if not row:
            return default
        try:
            value = json.loads(row["value_json"])
            return value if isinstance(value, dict) else default
        except json.JSONDecodeError:
            return default

    def set_setting(self, tenant_id: str, setting_key: str, value: dict) -> None:
        with self._connect() as db:
            db.execute("INSERT INTO tenant_settings (tenant_id, setting_key, value_json, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(tenant_id, setting_key) DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at", (tenant_id, setting_key, json.dumps(value), _now()))

    def audit(self, tenant_id: str, user_id: str | None, event_type: str, metadata: dict | None = None) -> None:
        with self._connect() as db:
            db.execute("INSERT INTO audit_events VALUES (?, ?, ?, ?, ?, ?)", (secrets.token_urlsafe(12), tenant_id, user_id, event_type, json.dumps(metadata or {}), _now()))

    def list_audit_events(self, tenant_id: str, limit: int = 100) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT id, user_id, event_type, metadata_json, created_at FROM audit_events WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?", (tenant_id, min(max(limit, 1), 500))).fetchall()
        return [{**dict(row), "metadata": json.loads(row["metadata_json"])} for row in rows]
