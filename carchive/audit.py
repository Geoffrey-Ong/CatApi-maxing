"""Audit logging: a record of every change made to the database through the API.

Each change is recorded two ways:
  1. A row in the audit_log table, inserted in the SAME transaction as the change itself, so a
     change and its audit record either both exist or neither does. Neon keeps this durable.
  2. An entry appended to a JSON file (a valid JSON array). Locally that is logs/audit_log.json.
     On Vercel only /tmp is writable and it is wiped when an instance restarts, so the file is a
     convenience copy there; the table (and GET /api/v1/audit/export) is the permanent record.

Never recorded: passwords, password hashes, tokens, emails. Uploaded photos are summarized, not stored.
"""
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("carchive.audit")

_file_lock = threading.Lock()
_REPO_ROOT = Path(__file__).resolve().parent.parent


def _file_path() -> Path:
    configured = os.environ.get("AUDIT_LOG_FILE")
    if configured:
        return Path(configured)
    if os.environ.get("VERCEL"):
        return Path("/tmp/audit_log.json")
    return _REPO_ROOT / "logs" / "audit_log.json"


# ------------------------------------------------------------------ building entries

def image_note(value):
    """Describe a photo without storing it (uploads are large base64 strings)."""
    if not value:
        return "none"
    if value.startswith("data:"):
        return f"[uploaded image, {len(value)} characters]"
    return value[:200]


def describe_changes(old: dict, new: dict) -> dict:
    """{field: {"from": old, "to": new}} for the fields whose value actually changed."""
    changes = {}
    for field, new_value in new.items():
        old_value = old.get(field)
        if old_value == new_value:
            continue
        if field == "image":
            old_value, new_value = image_note(old_value), image_note(new_value)
        changes[field] = {"from": old_value, "to": new_value}
    return changes


def make_entry(action: str, actor, target_type: str, target_id, details: dict, ctx: dict) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "action": action,
        "actor": {"id": actor["id"], "username": actor["username"], "role": actor["role"]} if actor else None,
        "target": {"type": target_type, "id": target_id},
        "details": details,
        "ip_address": ctx.get("ip"),
        "request_id": ctx.get("request_id"),
    }


# ------------------------------------------------------------------ writing entries

def insert(conn, entry: dict) -> None:
    """Add the entry to audit_log using the caller's connection, so it commits with the change."""
    from psycopg.types.json import Jsonb      # imported here so the file helpers above work without psycopg
    actor = entry["actor"] or {}
    conn.execute(
        """INSERT INTO audit_log
               (occurred_at, action, actor_id, actor_username, actor_role,
                target_type, target_id, details, ip_address, request_id)
           VALUES (%s::timestamptz, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (entry["timestamp"], entry["action"], actor.get("id"), actor.get("username"), actor.get("role"),
         entry["target"]["type"], entry["target"]["id"], Jsonb(entry["details"]),
         entry["ip_address"], entry["request_id"]),
    )


def _read_entries(path: Path) -> list:
    if not path.exists():
        return []
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(entries, list):
            return entries
    except ValueError:
        pass
    # unreadable file: keep it for inspection instead of overwriting it
    aside = path.with_name(f"{path.stem}.corrupt-{int(time.time())}{path.suffix}")
    path.replace(aside)
    log.error("Audit file was not valid JSON; moved to %s", aside.name)
    return []


def write_file(entry: dict) -> None:
    """Call AFTER the database transaction has committed. Never raises: a file problem must not break a request."""
    log.info("AUDIT %s", json.dumps(entry, ensure_ascii=False))     # also lands in the hosting platform's logs
    path = _file_path()
    try:
        with _file_lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            entries = _read_entries(path)
            entries.append(entry)
            temp = path.with_name(path.name + ".tmp")
            temp.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(temp, path)                                   # atomic: readers never see half a file
    except OSError as exc:
        log.error("Could not write the audit file: %s", exc)
