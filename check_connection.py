"""Phase 4 evidence: connects as the limited app role and runs the first queries.

    python check_connection.py

Prints no secrets. Paste the output into the documentation.
"""
import os

import psycopg
from dotenv import load_dotenv

from carchive import db

load_dotenv()

print("DATABASE_URL set:", bool(os.environ.get("DATABASE_URL")))

with db.get_conn() as conn:
    row = conn.execute("SELECT current_user AS role, current_database() AS db, version() AS v").fetchone()
    print(f"Connected as role '{row['role']}' to database '{row['db']}'")
    print(row["v"].split(",")[0])

    for table in ("users", "cats"):
        n = conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
        print(f"{table}: {n} rows")

    # the app role must NOT be able to change the schema
    try:
        conn.execute("CREATE TABLE should_fail (x int)")
        print("WARNING: this role can create tables. DATABASE_URL should use carchive_app, not the owner.")
    except psycopg.errors.InsufficientPrivilege:
        print("DDL correctly denied for the app role")
    finally:
        conn.rollback()   # never leave the test table behind, whatever happened

cats = db.list_cats()
print(f"\nlist_cats() returned {len(cats)} approved cats. First three:")
for cat in cats[:3]:
    print(f"  #{cat['id']} {cat['name']} ({cat['breed']}, {cat['country']})")

one = db.get_cat(1)
print("\nget_cat(1):", one["name"] if one else None)
print("get_cat(9999):", db.get_cat(9999))
print("ping():", db.ping())