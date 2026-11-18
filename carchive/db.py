"""All database access for the CArchive API. Routes in index.py call these functions and contain no SQL.

Every query is parameterized (%s placeholders): user input is never formatted into SQL text.
A connection is opened per request, because Vercel instances are stateless and cannot be
relied on to keep one alive. DATABASE_URL should be Neon's pooled (-pooler) string for the
limited carchive_app role.
"""
import logging
import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

log = logging.getLogger("carchive.db")


class DatabaseUnavailable(Exception):
    """Raised for connection/query failures. The message is generic; details go to the log only."""


# Columns returned to API clients. user_id, status and source stay internal.
# prev_owner is also exposed as submitted_by because app.js reads either name.
PUBLIC_COLUMNS = """
    id, name, image, breed, age, color, gender, country,
    prev_owner, prev_owner AS submitted_by,
    fav_treat, likes, dislikes, previous_health_conditions,
    friendliness_level, prefered_environment, good_for_adoption, description
"""


@contextmanager
def get_conn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        log.error("DATABASE_URL is not set")
        raise DatabaseUnavailable("Database is not configured.")
    try:
        # prepare_threshold=None: safe with Neon's pooled (PgBouncer) connections
        with psycopg.connect(url, row_factory=dict_row, prepare_threshold=None, connect_timeout=10) as conn:
            yield conn
    except psycopg.OperationalError as exc:
        log.error("Database connection/operation failed: %s", exc)
        raise DatabaseUnavailable("The database is temporarily unavailable.") from exc


def ping() -> bool:
    """Cheap connectivity test for /health. Returns True/False, never raises, leaks nothing."""
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


# ------------------------------------------------------------------ reads (Phase 4)

def list_cats(originals_only: bool = False):
    sql = f"SELECT {PUBLIC_COLUMNS} FROM cats WHERE status = 'approved'"
    if originals_only:                       # the Cat TCG scopes only see the original 20
        sql += " AND source = 'original'"
    sql += " ORDER BY id"
    with get_conn() as conn:
        return conn.execute(sql).fetchall()


def get_cat(cat_id: int, originals_only: bool = False):
    sql = f"SELECT {PUBLIC_COLUMNS} FROM cats WHERE id = %s AND status = 'approved'"
    if originals_only:
        sql += " AND source = 'original'"
    with get_conn() as conn:
        return conn.execute(sql, (cat_id,)).fetchone()   # None -> the route returns 404
