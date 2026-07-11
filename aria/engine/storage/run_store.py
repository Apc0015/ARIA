"""SQLite-backed persistent store for run history.

Runs are written on creation and updated on every state change, so
history survives server restarts. Documents are stored on disk as
JSONL (existing behaviour); only metadata lives in SQLite.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Optional

logger = logging.getLogger("aria")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,
    status          TEXT NOT NULL DEFAULT 'queued',
    stage           TEXT NOT NULL DEFAULT 'queued',
    message         TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    error           TEXT,
    topic           TEXT,
    output_dir      TEXT,
    mission_json    TEXT,
    stats_json      TEXT DEFAULT '{}',
    exports_json    TEXT DEFAULT '{}',
    report_path     TEXT DEFAULT '',
    docs_collected  INTEGER DEFAULT 0,
    docs_cleaned    INTEGER DEFAULT 0,
    source_stats_json TEXT DEFAULT '{}',
    query_plan_json TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_runs_status      ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_created_at  ON runs(created_at);
CREATE INDEX IF NOT EXISTS idx_runs_topic       ON runs(topic);
"""

_DEFAULT_DB_PATH = Path.home() / ".aria" / "runs.db"


class RunStore:
    """Persistent SQLite store for run metadata.

    Thread-safety: uses `check_same_thread=False` with WAL mode so
    multiple asyncio tasks can read/write concurrently.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._path = Path(db_path or _DEFAULT_DB_PATH)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._path),
            check_same_thread=False,
            timeout=10,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        logger.debug("RunStore: opened %s", self._path)

    @contextmanager
    def _tx(self) -> Generator[sqlite3.Cursor, None, None]:
        cur = self._conn.cursor()
        try:
            yield cur
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def upsert(self, run_id: str, **fields: Any) -> None:
        """Insert or update a run record. Only provided fields are updated."""
        now = datetime.now(timezone.utc).isoformat()
        fields["updated_at"] = now

        # Serialise dict/list values to JSON strings
        for key in ("mission_json", "stats_json", "exports_json",
                    "source_stats_json", "query_plan_json"):
            raw_key = key.replace("_json", "")
            if raw_key in fields and not isinstance(fields[raw_key], str):
                fields[key] = json.dumps(fields.pop(raw_key), default=str)
            elif raw_key in fields:
                fields[key] = fields.pop(raw_key)

        with self._tx() as cur:
            # Check existence
            cur.execute("SELECT run_id FROM runs WHERE run_id = ?", (run_id,))
            if cur.fetchone():
                set_clause = ", ".join(f"{k} = ?" for k in fields)
                values = list(fields.values()) + [run_id]
                cur.execute(f"UPDATE runs SET {set_clause} WHERE run_id = ?", values)
            else:
                fields.setdefault("created_at", now)
                fields["run_id"] = run_id
                cols = ", ".join(fields.keys())
                placeholders = ", ".join("?" * len(fields))
                cur.execute(
                    f"INSERT INTO runs ({cols}) VALUES ({placeholders})",
                    list(fields.values()),
                )

    def delete(self, run_id: str) -> None:
        with self._tx() as cur:
            cur.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get(self, run_id: str) -> Optional[dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM runs WHERE run_id = ?", (run_id,)
        )
        row = cur.fetchone()
        return _deserialise(dict(row)) if row else None

    def list_runs(
        self,
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Return runs ordered by created_at DESC, optionally filtered."""
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if search:
            clauses.append("topic LIKE ?")
            params.append(f"%{search}%")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params += [limit, offset]
        cur = self._conn.execute(
            f"SELECT * FROM runs {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        )
        return [_deserialise(dict(row)) for row in cur.fetchall()]

    def count(self, status: Optional[str] = None) -> int:
        if status:
            cur = self._conn.execute(
                "SELECT COUNT(*) FROM runs WHERE status = ?", (status,)
            )
        else:
            cur = self._conn.execute("SELECT COUNT(*) FROM runs")
        return cur.fetchone()[0]

    def close(self) -> None:
        self._conn.close()


def _deserialise(row: dict[str, Any]) -> dict[str, Any]:
    """Parse JSON string columns back to Python objects."""
    for key in ("mission_json", "stats_json", "exports_json",
                "source_stats_json", "query_plan_json"):
        if key in row and isinstance(row[key], str):
            try:
                row[key.replace("_json", "")] = json.loads(row[key])
            except (json.JSONDecodeError, TypeError):
                row[key.replace("_json", "")] = {}
            del row[key]
    return row
