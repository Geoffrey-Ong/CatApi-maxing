"""One-off migration: load the 20 original cats from seed_cats.json into Neon.

Run locally with the ADMIN connection string, never from the deployed API:
    DATABASE_URL_ADMIN=... python seed.py
Safe to re-run: existing ids are skipped (ON CONFLICT DO NOTHING).
"""
import json
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("DATABASE_URL_ADMIN")
if not url:
    sys.exit("Set DATABASE_URL_ADMIN (the admin/owner connection string) in .env first.")

ENV_FIX = {"Inside only": "Inside Only", "Outside only": "Outside Only"}  # the casing bug from Phase 1

cats = json.loads(Path(__file__).with_name("seed_cats.json").read_text(encoding="utf-8"))

COLUMNS = ["id", "name", "image", "breed", "age", "color", "gender", "country", "prev_owner",
           "fav_treat", "likes", "dislikes", "previous_health_conditions", "friendliness_level",
           "prefered_environment", "good_for_adoption", "description"]

with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        inserted = 0
        for cat in cats:
            cat["prefered_environment"] = ENV_FIX.get(cat["prefered_environment"], cat["prefered_environment"])
            cat["likes"] = cat["likes"].strip()
            cat["dislikes"] = cat["dislikes"].strip()
            cur.execute(
                f"""INSERT INTO cats ({", ".join(COLUMNS)}, status, source)
                    OVERRIDING SYSTEM VALUE
                    VALUES ({", ".join(["%s"] * len(COLUMNS))}, 'approved', 'original')
                    ON CONFLICT (id) DO NOTHING""",
                [cat[c] for c in COLUMNS],
            )
            inserted += cur.rowcount

        # next generated id continues after the highest seeded one
        cur.execute("SELECT setval(pg_get_serial_sequence('cats', 'id'), (SELECT MAX(id) FROM cats))")
        cur.execute("SELECT count(*) FROM cats")
        total = cur.fetchone()[0]

print(f"Inserted {inserted} new cats; the table now holds {total}.")
