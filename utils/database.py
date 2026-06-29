"""
Database — SQLite helper.

FIX: DB_PATH is now resolved relative to the project root (this file's parent/parent),
so 'data/newsletter.db' always points to the same file regardless of the working
directory the pipeline is launched from.  This was the root cause of sent-article
deduplication not working — the pipeline was creating a fresh DB in a different
location each run.
"""

import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path

from config.settings import DB_PATH

logger  = logging.getLogger(__name__)

# ── Resolve DB path relative to project root (2 levels up from utils/database.py) ──
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DB_FILE      = _PROJECT_ROOT / DB_PATH


def _get_conn() -> sqlite3.Connection:
    _DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_FILE)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrent read performance
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS employees (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id TEXT UNIQUE NOT NULL,
                name        TEXT NOT NULL,
                email       TEXT UNIQUE NOT NULL,
                department  TEXT DEFAULT '',
                status      TEXT DEFAULT 'active'
                            CHECK(status IN ('active', 'inactive'))
            );

            CREATE TABLE IF NOT EXISTS sent_articles (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                url           TEXT UNIQUE NOT NULL,
                title         TEXT,
                source        TEXT,
                category      TEXT,
                summary       TEXT,
                published_at  TEXT,
                card_path     TEXT,
                sent_at       TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_sent_articles_url
                ON sent_articles(url);

            CREATE INDEX IF NOT EXISTS idx_sent_articles_sent_at
                ON sent_articles(sent_at);

            CREATE TABLE IF NOT EXISTS run_log (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at           TEXT NOT NULL,
                articles_fetched INTEGER DEFAULT 0,
                articles_sent    INTEGER DEFAULT 0,
                recipients       TEXT,
                status           TEXT DEFAULT 'ok',
                error_msg        TEXT
            );
        """)
    logger.info(f"[DB] Initialized SQLite database at {_DB_FILE}")


# ─── Employee helpers ──────────────────────────────────────────────────────────

def get_active_recipients() -> list[str]:
    try:
        with _get_conn() as conn:
            rows   = conn.execute("SELECT email FROM employees WHERE status='active' ORDER BY name").fetchall()
            emails = [r["email"] for r in rows]
            logger.info(f"[DB] {len(emails)} active recipients loaded")
            return emails
    except Exception as e:
        logger.error(f"[DB] get_active_recipients error: {e}")
        return []


def add_employee(employee_id: str, name: str, email: str, department: str = "", status: str = "active") -> bool:
    try:
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO employees (employee_id,name,email,department,status) VALUES (?,?,?,?,?)",
                (employee_id, name, email, department, status),
            )
        logger.info(f"[DB] Added: {name} ({email})")
        return True
    except sqlite3.IntegrityError as e:
        logger.error(f"[DB] Duplicate ID or email: {e}")
        return False
    except Exception as e:
        logger.error(f"[DB] add_employee: {e}")
        return False


def update_employee_status(employee_id: str, status: str) -> bool:
    if status not in ("active", "inactive"):
        return False
    try:
        with _get_conn() as conn:
            conn.execute("UPDATE employees SET status=? WHERE employee_id=?", (status, employee_id))
        return True
    except Exception as e:
        logger.error(f"[DB] update_employee_status: {e}")
        return False


def update_employee_email(employee_id: str, new_email: str) -> bool:
    try:
        with _get_conn() as conn:
            conn.execute("UPDATE employees SET email=? WHERE employee_id=?", (new_email, employee_id))
        return True
    except Exception as e:
        logger.error(f"[DB] update_employee_email: {e}")
        return False


def remove_employee(employee_id: str) -> bool:
    try:
        with _get_conn() as conn:
            conn.execute("DELETE FROM employees WHERE employee_id=?", (employee_id,))
        return True
    except Exception as e:
        logger.error(f"[DB] remove_employee: {e}")
        return False


def list_employees(status_filter: str = None) -> list[dict]:
    try:
        with _get_conn() as conn:
            if status_filter:
                rows = conn.execute("SELECT * FROM employees WHERE status=? ORDER BY name", (status_filter,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM employees ORDER BY name").fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"[DB] list_employees: {e}")
        return []


# ─── Article helpers ───────────────────────────────────────────────────────────

def is_already_sent(url: str) -> bool:
    """
    Check if a URL was already sent in a previous newsletter run.
    Uses an indexed lookup for performance.
    Returns True if the article should be skipped.
    """
    if not url:
        return False
    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM sent_articles WHERE url=? LIMIT 1", (url,)
            ).fetchone()
            return row is not None
    except Exception as e:
        logger.error(f"[DB] is_already_sent error: {e}")
        # On DB error, allow the article through rather than silently blocking all
        return False


def mark_articles_sent(articles: list[dict]):
    """
    Persist all sent article URLs so they are filtered out in future runs.
    Uses INSERT OR IGNORE to handle race conditions gracefully.
    """
    if not articles:
        return
    now = datetime.now(timezone.utc).isoformat()
    try:
        with _get_conn() as conn:
            conn.executemany(
                """INSERT OR IGNORE INTO sent_articles
                   (url, title, source, category, summary, published_at, card_path, sent_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                [
                    (
                        a.get("url", ""),
                        (a.get("title", "") or "")[:500],
                        a.get("source", ""),
                        a.get("category", ""),
                        (a.get("llm_summary") or a.get("summary", "") or "")[:1000],
                        str(a.get("published_at", ""))[:30],
                        a.get("card_path", ""),
                        now,
                    )
                    for a in articles
                    if a.get("url")   # only insert rows with a valid URL
                ],
            )
        logger.info(f"[DB] Marked {len(articles)} articles as sent.")
    except Exception as e:
        logger.error(f"[DB] mark_articles_sent error: {e}")


def purge_old_articles():
    """Deletes sent article records older than 15 days to keep DB footprint minimal."""
    logger.info("[DB] Purging records older than 15 days...")
    try:
        with _get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM sent_articles WHERE datetime(sent_at) < datetime('now', '-15 days')"
            )
            logger.info(f"[DB] Purged {cursor.rowcount} expired records.")
    except Exception as e:
        logger.error(f"[DB] purge_old_articles error: {e}")


def log_run(fetched: int, sent: int, recipients: list[str], status: str = "ok", error: str = ""):
    now = datetime.now(timezone.utc).isoformat()
    try:
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO run_log (run_at,articles_fetched,articles_sent,recipients,status,error_msg) VALUES (?,?,?,?,?,?)",
                (now, fetched, sent, ",".join(recipients), status, error),
            )
    except Exception as e:
        logger.error(f"[DB] log_run error: {e}")


def get_recent_runs(limit: int = 10) -> list[dict]:
    try:
        with _get_conn() as conn:
            rows = conn.execute("SELECT * FROM run_log ORDER BY run_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []