"""Apply ARIA's ordered SQLite SaaS migrations."""

from pathlib import Path
import sqlite3
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from aria.config import DATA_ROOT


def migrate(path: Path) -> None:
    migrations = sorted((Path(__file__).parents[1] / "aria" / "api" / "migrations").glob("*.sql"))
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        applied = {row[0] for row in db.execute("SELECT version FROM schema_migrations")}
        for migration in migrations:
            if migration.name not in applied:
                db.executescript(migration.read_text(encoding="utf-8"))
                db.execute("INSERT INTO schema_migrations(version) VALUES (?)", (migration.name,))


if __name__ == "__main__":
    target = DATA_ROOT / "aria_saas.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    migrate(target)
    print(f"Applied SaaS migrations to {target}")
