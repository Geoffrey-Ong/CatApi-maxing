import os
import psycopg
from dotenv import load_dotenv

from index import cats   # your existing list, already validated by your Cat model

load_dotenv()

COLUMNS = [
    "id", "name", "image", "breed", "age", "color", "gender", "prev_owner",
    "fav_treat", "likes", "dislikes", "previous_health_conditions",
    "friendliness_level", "prefered_environment", "good_for_adoption",
    "description",
]

placeholders = ", ".join(["%s"] * len(COLUMNS))
sql = (
    f"INSERT INTO cats ({', '.join(COLUMNS)}) VALUES ({placeholders}) "
    "ON CONFLICT (id) DO NOTHING"
)

with psycopg.connect(os.environ["Neondatabase"]) as conn:
    for cat in cats:
        conn.execute(sql, [cat[col] for col in COLUMNS])

print(f"Inserted {len(cats)} cats.")