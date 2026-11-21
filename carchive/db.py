"""All database access for the CArchive API. Routes in index.py call these functions and contain no SQL.

Every value goes in through a %s placeholder, and the only identifiers built into SQL
(column names) come from fixed whitelists in this file, never from request data.
A connection is opened per request because Vercel instances are stateless. DATABASE_URL
should be Neon's pooled (-pooler) string for the limited carchive_app role.
"""
import logging
import math
import os
from contextlib import contextmanager

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from . import audit

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


# Whitelisted ORDER BY clauses: the request picks a KEY, never any SQL text.
CAT_SORTS = {
    "oldest": "id",
    "newest": "id DESC",
    "name": "lower(name), id",
    "age_young": "age, id",
    "age_old": "age DESC, id",
}


def _cat_filters(originals_only, q, breed, country, good_for_adoption):
    """The WHERE text (fixed pieces only) and its parameters for the filtered archive listing."""
    clauses, params = ["status = 'approved'"], []
    if originals_only:
        clauses.append("source = 'original'")
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        clauses.append("concat_ws(' ', name, breed, color, gender, prefered_environment, country, prev_owner) ILIKE %s")
        params.append(f"%{escaped}%")
    if breed:
        clauses.append("lower(breed) = lower(%s)")
        params.append(breed)
    if country:
        clauses.append("lower(country) = lower(%s)")
        params.append(country)
    if good_for_adoption:
        clauses.append("good_for_adoption = %s")
        params.append(good_for_adoption)
    return " AND ".join(clauses), params


def list_cats_page(limit, offset, sort="oldest", q=None, breed=None, country=None,
                   good_for_adoption=None, originals_only=False):
    """One page of approved cats plus the total that match. limit=None means every match."""
    where, params = _cat_filters(originals_only, q, breed, country, good_for_adoption)
    with get_conn() as conn:
        total = conn.execute(f"SELECT count(*) AS n FROM cats WHERE {where}", params).fetchone()["n"]
        rows = conn.execute(
            f"SELECT {PUBLIC_COLUMNS} FROM cats WHERE {where} ORDER BY {CAT_SORTS[sort]} LIMIT %s OFFSET %s",
            [*params, limit, offset],            # LIMIT NULL means no limit in PostgreSQL
        ).fetchall()
    return rows, total


def list_filter_values(originals_only: bool = False):
    """The breeds and countries that exist among approved cats, for the filter dropdowns."""
    extra = " AND source = 'original'" if originals_only else ""
    with get_conn() as conn:
        out = {}
        for key, column in (("breeds", "breed"), ("countries", "country")):
            rows = conn.execute(
                f"SELECT min({column}) AS value FROM cats "
                f"WHERE status = 'approved' AND {column} <> ''{extra} "
                f"GROUP BY lower({column}) ORDER BY lower({column})"
            ).fetchall()
            out[key] = [row["value"] for row in rows]
    return out


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


def list_rejected():
    with get_conn() as conn:
        return conn.execute(
            f"SELECT {OWNER_COLUMNS}, user_id FROM cats WHERE status = 'rejected' ORDER BY updated_at DESC, id DESC"
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


def create_cat(data: dict, user: dict, status: str, ctx: dict):
    columns = list(CAT_INPUT_COLUMNS)
    query = sql.SQL(
        "INSERT INTO cats ({cols}, prev_owner, user_id, status, source) "
        "VALUES ({marks}, %s, %s, %s, 'community') RETURNING {returning}"
    ).format(
        cols=sql.SQL(", ").join(sql.Identifier(c) for c in columns),
        marks=sql.SQL(", ").join([sql.Placeholder()] * len(columns)),
        returning=sql.SQL(OWNER_COLUMNS),
    )
    params = [data[c] for c in columns] + [user["username"], user["id"], status]
    with get_conn() as conn:
        row = conn.execute(query, params).fetchone()
        entry = audit.make_entry("cat.create", user, "cat", row["id"], {
            "name": row["name"], "breed": row["breed"], "country": row["country"],
            "status": row["status"], "image": audit.image_note(data["image"]),
        }, ctx)
        audit.insert(conn, entry)          # same transaction: both commit, or neither does
    audit.write_file(entry)
    return row


def update_cat(cat_id: int, changes: dict, user: dict, ctx: dict):
    """Returns the updated cat, or None if it no longer exists."""
    unknown = set(changes) - set(EDITABLE_COLUMNS)
    if unknown or not changes:
        raise ValueError(f"Cannot update columns: {sorted(unknown)}")
    update = sql.SQL("UPDATE cats SET {sets}, updated_at = now() WHERE id = %s RETURNING {returning}").format(
        sets=sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(c)) for c in changes),
        returning=sql.SQL(OWNER_COLUMNS),
    )
    read_old = sql.SQL("SELECT {cols} FROM cats WHERE id = %s FOR UPDATE").format(
        cols=sql.SQL(", ").join(sql.Identifier(c) for c in changes)
    )
    with get_conn() as conn:
        old = conn.execute(read_old, (cat_id,)).fetchone()      # locks the row so "before" is accurate
        if old is None:
            return None
        row = conn.execute(update, [*changes.values(), cat_id]).fetchone()
        action = "cat.moderate" if "status" in changes and user["role"] == "admin" else "cat.update"
        entry = audit.make_entry(action, user, "cat", cat_id, {"changes": audit.describe_changes(old, changes)}, ctx)
        audit.insert(conn, entry)
    audit.write_file(entry)
    return row


def delete_cat(cat_id: int, user: dict, ctx: dict) -> bool:
    with get_conn() as conn:
        gone = conn.execute(
            "DELETE FROM cats WHERE id = %s "
            "RETURNING id, name, breed, country, prev_owner, user_id, status, source",
            (cat_id,),
        ).fetchone()
        if gone is None:
            return False
        entry = audit.make_entry("cat.delete", user, "cat", cat_id, {"deleted": {
            "name": gone["name"], "breed": gone["breed"], "country": gone["country"],
            "owner": gone["prev_owner"], "owner_id": gone["user_id"],
            "status": gone["status"], "source": gone["source"],
        }}, ctx)
        audit.insert(conn, entry)
    audit.write_file(entry)
    return True


# ------------------------------------------------------------------ users

def create_user(username: str, email: str, password_hash: str, ctx: dict):
    with get_conn() as conn:
        user = conn.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) "
            "RETURNING id, username, role",
            (username, email, password_hash),
        ).fetchone()
        # the new account is its own actor; the email and password hash are deliberately not logged
        entry = audit.make_entry("user.register", user, "user", user["id"], {"username": user["username"]}, ctx)
        audit.insert(conn, entry)
    audit.write_file(entry)
    return user


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


# ------------------------------------------------------------------ login rate limiting
# Failed attempts live in the database (not in memory) because Vercel runs many short-lived instances
# that share nothing. Counted per typed username/email AND per IP address.

LOGIN_WINDOW_MINUTES = 15
MAX_FAILURES_PER_IDENTIFIER = 5      # stops guessing one account's password
MAX_FAILURES_PER_IP = 20             # stops one address trying many accounts


def login_lock_seconds(identifier: str, ip) -> int:
    """0 if this login may be attempted; otherwise how many seconds until it may be tried again."""
    wait = 0.0
    with get_conn() as conn:
        for column, value, limit in (
            ("identifier", identifier, MAX_FAILURES_PER_IDENTIFIER),
            ("ip_address", ip, MAX_FAILURES_PER_IP),
        ):
            if value is None:
                continue
            rows = conn.execute(
                f"""SELECT extract(epoch FROM (attempted_at + make_interval(mins => %s) - now())) AS remaining
                    FROM failed_logins
                    WHERE {column} = %s AND attempted_at > now() - make_interval(mins => %s)
                    ORDER BY attempted_at""",
                (LOGIN_WINDOW_MINUTES, value, LOGIN_WINDOW_MINUTES),
            ).fetchall()
            if len(rows) >= limit:
                # unlocked once enough of the oldest failures age out of the window
                wait = max(wait, float(rows[len(rows) - limit]["remaining"]))
    return max(0, math.ceil(wait))


def record_failed_login(identifier: str, ip, user, ctx: dict) -> None:
    """Store the failure for rate limiting and audit it (also audits the moment a lock begins).

    The typed text is NOT put in the audit log: people sometimes type a password into the username box
    and the log is append-only. An existing account is identified by its id instead."""
    account_id = user["id"] if user else None
    entries = [audit.make_entry("auth.login_failed", None, "user", account_id,
                                {"reason": "wrong_password" if user else "unknown_account"}, ctx)]
    with get_conn() as conn:
        conn.execute("INSERT INTO failed_logins (identifier, ip_address) VALUES (%s, %s)", (identifier, ip))
        conn.execute("DELETE FROM failed_logins WHERE attempted_at < now() - interval '1 day'")   # keep the table small
        for scope, column, value, limit in (
            ("account", "identifier", identifier, MAX_FAILURES_PER_IDENTIFIER),
            ("ip address", "ip_address", ip, MAX_FAILURES_PER_IP),
        ):
            if value is None:
                continue
            count = conn.execute(
                f"SELECT count(*) AS n FROM failed_logins "
                f"WHERE {column} = %s AND attempted_at > now() - make_interval(mins => %s)",
                (value, LOGIN_WINDOW_MINUTES),
            ).fetchone()["n"]
            if count == limit:      # this failure starts the lock; attempts refused afterwards are not logged
                entries.append(audit.make_entry(
                    "auth.locked", None, "user", account_id if scope == "account" else None,
                    {"scope": scope, "minutes": LOGIN_WINDOW_MINUTES}, ctx))
        for entry in entries:
            audit.insert(conn, entry)           # same transaction as the failure record
    for entry in entries:
        audit.write_file(entry)


def record_login_success(identifier: str, user: dict, ctx: dict) -> None:
    """Clear this account's recent failures and audit the login."""
    entry = audit.make_entry("auth.login", user, "user", user["id"], {}, ctx)
    with get_conn() as conn:
        conn.execute("DELETE FROM failed_logins WHERE identifier = %s", (identifier,))
        audit.insert(conn, entry)
    audit.write_file(entry)


# ------------------------------------------------------------------ audit log reads

AUDIT_COLUMNS = ("id, occurred_at, action, actor_id, actor_username, actor_role, "
                 "target_type, target_id, details, ip_address, request_id")


def list_audit(limit: int, offset: int, action=None, target_type=None, target_id=None):
    clauses, params = [], []
    if action:
        clauses.append("action = %s")
        params.append(action)
    if target_type:
        clauses.append("target_type = %s")
        params.append(target_type)
    if target_id is not None:
        clauses.append("target_id = %s")
        params.append(target_id)
    query = f"SELECT {AUDIT_COLUMNS} FROM audit_log"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)       # clause text is fixed above; values are parameters
    query += " ORDER BY occurred_at DESC, id DESC LIMIT %s OFFSET %s"
    with get_conn() as conn:
        return conn.execute(query, [*params, limit, offset]).fetchall()


def export_audit(max_rows: int = 10000):
    """The whole log, oldest first, for the downloadable .json file."""
    with get_conn() as conn:
        return conn.execute(
            f"SELECT {AUDIT_COLUMNS} FROM audit_log ORDER BY occurred_at, id LIMIT %s", (max_rows,)
        ).fetchall()