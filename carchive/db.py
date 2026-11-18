"""All database access for the CArchive API. Routes in index.py call these functions and contain no SQL.

Every value goes in through a %s placeholder, and the only identifiers built into SQL
(column names) come from fixed whitelists in this file, never from request data.
A connection is opened per request because Vercel instances are stateless. DATABASE_URL
should be Neon's pooled (-pooler) string for the limited carchive_app role.
"""
import logging
import os
from contextlib import contextmanager

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

log = logging.getLogger("carchive.db")


class DatabaseUnavailable(Exception):
    """Could not connect, or the connection dropped. The API answers 503."""


class DatabaseError(Exception):
    """Any other unexpected database failure. The API answers 500 with a generic message."""


class DuplicateRecord(Exception):
    """A unique index rejected the write. `constraint` names which one."""

    def __init__(self, constraint):
        super().__init__(constraint)
        self.constraint = constraint


@contextmanager
def get_conn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        log.error("DATABASE_URL is not set")
        raise DatabaseUnavailable("Database is not configured.")
    try:
        # prepare_threshold=None: safe with Neon's pooled (PgBouncer) connections.
        # Leaving the with-block normally commits; an exception rolls back.
        with psycopg.connect(url, row_factory=dict_row, prepare_threshold=None, connect_timeout=10) as conn:
            yield conn
    except psycopg.errors.UniqueViolation as exc:
        raise DuplicateRecord(exc.diag.constraint_name) from exc
    except psycopg.OperationalError as exc:
        log.error("Database connection/operation failed: %s", exc)
        raise DatabaseUnavailable("The database is temporarily unavailable.") from exc
    except psycopg.Error as exc:
        log.error("Database query failed: %s", exc)
        raise DatabaseError("Database query failed.") from exc


def ping() -> bool:
    """Cheap connectivity test for /health. Returns True/False, never raises, leaks nothing."""
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


# ------------------------------------------------------------------ column sets

# What any client may see. prev_owner is also exposed as submitted_by (app.js reads either).
PUBLIC_COLUMNS = """
    id, name, image, breed, age, color, gender, country,
    prev_owner, prev_owner AS submitted_by,
    fav_treat, likes, dislikes, previous_health_conditions,
    friendliness_level, prefered_environment, good_for_adoption, description
"""

# What an owner or an admin sees: public columns plus moderation info.
OWNER_COLUMNS = PUBLIC_COLUMNS + ", status, source, created_at, updated_at"

# Columns a client may set when submitting a cat (fixed whitelist).
CAT_INPUT_COLUMNS = (
    "name", "image", "breed", "age", "color", "gender", "country", "fav_treat",
    "likes", "dislikes", "friendliness_level", "prefered_environment",
    "good_for_adoption", "description",
)
# Columns PATCH may change. status is further restricted to admins by the route.
EDITABLE_COLUMNS = CAT_INPUT_COLUMNS + ("status",)


# ------------------------------------------------------------------ cats: public reads

def list_cats(originals_only: bool = False):
    query = f"SELECT {PUBLIC_COLUMNS} FROM cats WHERE status = 'approved'"
    if originals_only:                       # the Cat TCG scopes only see the original 20
        query += " AND source = 'original'"
    query += " ORDER BY id"
    with get_conn() as conn:
        return conn.execute(query).fetchall()


def get_cat(cat_id: int, originals_only: bool = False):
    query = f"SELECT {PUBLIC_COLUMNS} FROM cats WHERE id = %s AND status = 'approved'"
    if originals_only:
        query += " AND source = 'original'"
    with get_conn() as conn:
        return conn.execute(query, (cat_id,)).fetchone()   # None -> the route returns 404


def search_cats(term: str, originals_only: bool = False, good_for_adoption: str = None):
    # escape LIKE wildcards so a search for "100%" or "_" means those literal characters
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    query = f"""SELECT {PUBLIC_COLUMNS} FROM cats
                WHERE status = 'approved'
                  AND concat_ws(' ', name, breed, color, gender, prefered_environment, country, prev_owner) ILIKE %s"""
    params = [f"%{escaped}%"]
    if originals_only:
        query += " AND source = 'original'"
    if good_for_adoption:
        query += " AND good_for_adoption = %s"
        params.append(good_for_adoption)
    query += " ORDER BY id"
    with get_conn() as conn:
        return conn.execute(query, params).fetchall()


# ------------------------------------------------------------------ cats: owner / admin

def list_cats_by_user(user_id: int):
    """Everything this user submitted, whatever its status."""
    with get_conn() as conn:
        return conn.execute(
            f"SELECT {OWNER_COLUMNS} FROM cats WHERE user_id = %s ORDER BY created_at DESC, id DESC",
            (user_id,),
        ).fetchall()


def list_pending():
    with get_conn() as conn:
        return conn.execute(
            f"SELECT {OWNER_COLUMNS}, user_id FROM cats WHERE status = 'pending' ORDER BY created_at, id"
        ).fetchall()


def get_cat_internal(cat_id: int):
    """Any cat in any status, with ownership info. For permission checks only; never return it as-is."""
    with get_conn() as conn:
        return conn.execute(
            f"SELECT {OWNER_COLUMNS}, user_id FROM cats WHERE id = %s", (cat_id,)
        ).fetchone()


def count_pending(user_id: int) -> int:
    with get_conn() as conn:
        return conn.execute(
            "SELECT count(*) AS n FROM cats WHERE user_id = %s AND status = 'pending'", (user_id,)
        ).fetchone()["n"]


def create_cat(data: dict, user_id: int, owner_name: str, status: str = "pending"):
    columns = list(CAT_INPUT_COLUMNS)
    query = sql.SQL(
        "INSERT INTO cats ({cols}, prev_owner, user_id, status, source) "
        "VALUES ({marks}, %s, %s, %s, 'community') RETURNING {returning}"
    ).format(
        cols=sql.SQL(", ").join(sql.Identifier(c) for c in columns),
        marks=sql.SQL(", ").join([sql.Placeholder()] * len(columns)),
        returning=sql.SQL(OWNER_COLUMNS),
    )
    params = [data[c] for c in columns] + [owner_name, user_id, status]
    with get_conn() as conn:
        return conn.execute(query, params).fetchone()


def update_cat(cat_id: int, changes: dict):
    unknown = set(changes) - set(EDITABLE_COLUMNS)
    if unknown or not changes:
        raise ValueError(f"Cannot update columns: {sorted(unknown)}")
    query = sql.SQL("UPDATE cats SET {sets}, updated_at = now() WHERE id = %s RETURNING {returning}").format(
        sets=sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(c)) for c in changes),
        returning=sql.SQL(OWNER_COLUMNS),
    )
    with get_conn() as conn:
        return conn.execute(query, [*changes.values(), cat_id]).fetchone()


def delete_cat(cat_id: int) -> bool:
    with get_conn() as conn:
        return conn.execute("DELETE FROM cats WHERE id = %s RETURNING id", (cat_id,)).fetchone() is not None


# ------------------------------------------------------------------ users

def create_user(username: str, email: str, password_hash: str):
    with get_conn() as conn:
        return conn.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) "
            "RETURNING id, username, role",
            (username, email, password_hash),
        ).fetchone()


def get_user_for_login(identifier: str):
    """Match on username or email, case-insensitively. Usernames can't contain '@', so the two never clash."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, username, role, password_hash FROM users "
            "WHERE lower(username) = lower(%s) OR lower(email) = lower(%s) LIMIT 1",
            (identifier, identifier),
        ).fetchone()


def get_user_by_id(user_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT id, username, role FROM users WHERE id = %s", (user_id,)).fetchone()