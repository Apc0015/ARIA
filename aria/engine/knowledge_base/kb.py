"""
Persistent Knowledge Base — SQLite-backed cross-run document store.

Stores every document ever collected so subsequent runs skip known content
and can expand research without re-fetching the same pages.

Default location: ~/.aria/knowledge_base/aria_kb.db
Override via ARIA_KB_PATH env var.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Optional

logger = logging.getLogger("aria")

_DEFAULT_KB_PATH = Path.home() / ".aria" / "knowledge_base" / "aria_kb.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url_hash        TEXT NOT NULL,
    url             TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    title           TEXT,
    platform        TEXT,
    source_type     TEXT,
    word_count      INTEGER,
    language        TEXT DEFAULT 'en',
    collected_at    TEXT,
    text_snippet    TEXT,          -- first 500 chars for quick preview
    run_ids         TEXT DEFAULT '[]',   -- JSON list of run_ids that collected this
    topics          TEXT DEFAULT '[]',   -- JSON list of topics this appears in
    relevance_scores TEXT DEFAULT '{}',  -- JSON {topic: score}
    UNIQUE(url_hash)
);

CREATE TABLE IF NOT EXISTS topics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    created_at  REAL NOT NULL,
    last_run_at REAL,
    doc_count   INTEGER DEFAULT 0,
    run_ids     TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS content_hashes (
    hash    TEXT PRIMARY KEY,
    url     TEXT NOT NULL,
    added_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_docs_url_hash     ON documents(url_hash);
CREATE INDEX IF NOT EXISTS idx_docs_content_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_docs_platform     ON documents(platform);
CREATE INDEX IF NOT EXISTS idx_docs_topic        ON documents(topics);
"""


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().lower().encode()).hexdigest()


def _content_hash(text: str) -> str:
    """Fingerprint: length bucket + first 300 + last 100 chars."""
    t = text.strip()
    bucket = len(t) // 100  # group by 100-char buckets
    snippet = t[:300] + t[-100:] if len(t) > 400 else t
    return hashlib.sha256(f"{bucket}|{snippet}".encode()).hexdigest()


class KnowledgeBase:
    """
    SQLite-backed persistent store for all collected documents.

    Usage:
        kb = KnowledgeBase()
        if kb.has_url("https://example.com"):
            ...  # already collected
        else:
            kb.add_document(doc, topic="AI healthcare", run_id="abc123")

        # Get all docs for a topic (for incremental expand)
        existing = kb.get_documents_for_topic("AI healthcare")

        # Stats
        print(kb.stats())
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        env_path = os.getenv("ARIA_KB_PATH")
        self._path = Path(env_path) if env_path else (Path(db_path) if db_path else _DEFAULT_KB_PATH)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _get_conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self._path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ─── URL / Content checks ───────────────────────────────────────────────

    def has_url(self, url: str) -> bool:
        """Return True if this URL was already collected."""
        h = _url_hash(url)
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM documents WHERE url_hash = ? LIMIT 1", (h,)
            ).fetchone()
        return row is not None

    def has_content(self, text: str) -> bool:
        """Return True if this content (by fingerprint) already exists."""
        if not text or len(text.strip()) < 50:
            return False
        h = _content_hash(text)
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM content_hashes WHERE hash = ? LIMIT 1", (h,)
            ).fetchone()
        return row is not None

    def get_cached_doc(self, url: str) -> Optional[dict[str, Any]]:
        """Return cached document for a URL, or None if not known."""
        h = _url_hash(url)
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE url_hash = ? LIMIT 1", (h,)
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    # ─── Write ──────────────────────────────────────────────────────────────

    def add_document(
        self,
        doc: dict[str, Any],
        topic: str = "",
        run_id: str = "",
    ) -> bool:
        """
        Add a document to the KB.

        Returns:
            True if document was new, False if URL already existed.
        """
        url = doc.get("url", "")
        text = doc.get("text", "")
        if not url and not text:
            return False

        uh = _url_hash(url) if url else hashlib.sha256(text[:200].encode()).hexdigest()
        ch = _content_hash(text) if text else uh
        now = time.time()

        with self._get_conn() as conn:
            # Check if already exists
            existing = conn.execute(
                "SELECT id, run_ids, topics FROM documents WHERE url_hash = ?", (uh,)
            ).fetchone()

            if existing:
                # Update run_ids and topics lists
                run_ids = json.loads(existing["run_ids"] or "[]")
                topics_list = json.loads(existing["topics"] or "[]")
                if run_id and run_id not in run_ids:
                    run_ids.append(run_id)
                if topic and topic not in topics_list:
                    topics_list.append(topic)
                conn.execute(
                    "UPDATE documents SET run_ids=?, topics=? WHERE id=?",
                    (json.dumps(run_ids), json.dumps(topics_list), existing["id"]),
                )
                return False  # not new

            # Insert new
            run_ids = [run_id] if run_id else []
            topics_list = [topic] if topic else []
            snippet = (text or "")[:500]

            conn.execute(
                """INSERT OR IGNORE INTO documents
                   (url_hash, url, content_hash, title, platform, source_type,
                    word_count, language, collected_at, text_snippet, run_ids, topics)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    uh, url, ch,
                    doc.get("title", ""),
                    doc.get("platform", ""),
                    doc.get("source_type", ""),
                    doc.get("word_count", 0),
                    doc.get("language", "en"),
                    doc.get("collected_at", ""),
                    snippet,
                    json.dumps(run_ids),
                    json.dumps(topics_list),
                ),
            )

            # Track content hash
            conn.execute(
                "INSERT OR IGNORE INTO content_hashes (hash, url, added_at) VALUES (?,?,?)",
                (ch, url, now),
            )

        # Update topic record
        if topic:
            self._upsert_topic(topic, run_id)

        return True  # new document

    def add_documents_batch(
        self,
        docs: list[dict[str, Any]],
        topic: str = "",
        run_id: str = "",
    ) -> tuple[int, int]:
        """
        Add multiple documents.
        Returns: (new_count, duplicate_count)
        """
        new_count = 0
        dup_count = 0
        for doc in docs:
            is_new = self.add_document(doc, topic=topic, run_id=run_id)
            if is_new:
                new_count += 1
            else:
                dup_count += 1
        return new_count, dup_count

    def _upsert_topic(self, topic: str, run_id: str = "") -> None:
        now = time.time()
        with self._get_conn() as conn:
            existing = conn.execute(
                "SELECT id, run_ids, doc_count FROM topics WHERE name = ?", (topic,)
            ).fetchone()
            if existing:
                run_ids = json.loads(existing["run_ids"] or "[]")
                if run_id and run_id not in run_ids:
                    run_ids.append(run_id)
                conn.execute(
                    "UPDATE topics SET last_run_at=?, run_ids=? WHERE name=?",
                    (now, json.dumps(run_ids), topic),
                )
            else:
                run_ids = [run_id] if run_id else []
                conn.execute(
                    "INSERT INTO topics (name, created_at, last_run_at, run_ids) VALUES (?,?,?,?)",
                    (topic, now, now, json.dumps(run_ids)),
                )

            # Update doc_count
            conn.execute(
                """UPDATE topics SET doc_count = (
                    SELECT COUNT(*) FROM documents WHERE topics LIKE ?
                ) WHERE name = ?""",
                (f'%"{topic}"%', topic),
            )

    # ─── Read ───────────────────────────────────────────────────────────────

    def get_documents_for_topic(
        self,
        topic: str,
        limit: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Return all documents previously collected for a topic.
        Used by incremental collection to skip known content.
        """
        with self._get_conn() as conn:
            if limit:
                rows = conn.execute(
                    "SELECT * FROM documents WHERE topics LIKE ? ORDER BY id DESC LIMIT ?",
                    (f'%"{topic}"%', limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM documents WHERE topics LIKE ? ORDER BY id DESC",
                    (f'%"{topic}"%',),
                ).fetchall()
        return [dict(r) for r in rows]

    def get_known_urls_for_topic(self, topic: str) -> set[str]:
        """Return set of URLs already collected for a topic."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT url FROM documents WHERE topics LIKE ?",
                (f'%"{topic}"%',),
            ).fetchall()
        return {r["url"] for r in rows}

    def list_topics(self) -> list[dict[str, Any]]:
        """Return all known topics with metadata."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT name, created_at, last_run_at, doc_count FROM topics ORDER BY last_run_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def search_by_platform(self, platform: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE platform = ? LIMIT ?", (platform, limit)
            ).fetchall()
        return [dict(r) for r in rows]

    # ─── Stats ──────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return KB statistics."""
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            topics = conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
            platforms = conn.execute(
                "SELECT platform, COUNT(*) as cnt FROM documents GROUP BY platform ORDER BY cnt DESC"
            ).fetchall()
        return {
            "total_documents": total,
            "total_topics": topics,
            "db_path": str(self._path),
            "db_size_mb": round(self._path.stat().st_size / 1024 / 1024, 2) if self._path.exists() else 0,
            "platforms": {r["platform"]: r["cnt"] for r in platforms},
        }

    def purge_topic(self, topic: str) -> int:
        """Remove all documents exclusively belonging to a topic. Returns count removed."""
        with self._get_conn() as conn:
            # Only remove docs where this is the ONLY topic
            rows = conn.execute(
                "SELECT id, topics FROM documents WHERE topics LIKE ?",
                (f'%"{topic}"%',),
            ).fetchall()
            removed = 0
            for row in rows:
                topics_list = json.loads(row["topics"] or "[]")
                if topics_list == [topic]:
                    conn.execute("DELETE FROM documents WHERE id = ?", (row["id"],))
                    removed += 1
                else:
                    topics_list.remove(topic)
                    conn.execute(
                        "UPDATE documents SET topics = ? WHERE id = ?",
                        (json.dumps(topics_list), row["id"]),
                    )
            conn.execute("DELETE FROM topics WHERE name = ?", (topic,))
        return removed
