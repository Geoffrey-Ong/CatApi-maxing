import os
import psycopg
from fastapi import FastAPI, HTTPException, Header, Query, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Literal
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()   # reads .env when running locally; on Vercel the real env var is used

# Each frontend gets its own key. The value is that key's "scope" — which
# routes it's allowed to call (see require_scope below). Both frontends
# currently read the same cat data, so both scopes are accepted on the
# existing routes; a future battle-only route (submitting a move, starting
# a match, etc.) can be locked to just "battle" by passing require_scope("battle").
API_KEYS = {
    "adoption-api-key-9770": "adoption",                # Cat Adoption 
    "catTCGcollection-api-key-6767": "collection",      # Cat TCG Home / Collection frontend
    "catTCGbattle-api-key-4242": "battle",              # Cat TCG Battle Owners frontend
}

# Browser origins each scope may call from (scheme + host + port, no trailing
# slash). Browsers set the Origin header themselves and page JavaScript can't
# change it, so a key used from the wrong site is rejected. A scope that isn't
# listed here (adoption) has no origin restriction.
SCOPE_ORIGINS = {
    "collection": {
        "https://cat-tcg-collection.vercel.app",
        "http://localhost:8000",
    },
    "battle": {
        "https://cat-tcg-battle.vercel.app",
        "http://localhost:8001",
    },
}

# Optional key for server-side callers with no browser Origin, like the
# frontends' build-time cache refresh. Keep it in an environment variable
# (CAT_API_BUILD_KEY), never in frontend code.
BUILD_KEY = os.environ.get("CAT_API_BUILD_KEY")

ALL_SCOPES = ("adoption", "collection", "battle", "build")
API_VERSION = "1.0"


app = FastAPI(
    title="Simple Cat API",
    description="A beginner-friendly REST API containing information about cats.",
    version= API_VERSION
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_conn():
    return psycopg.connect(os.environ["Neondatabase"], row_factory=dict_row)

#DATA MODEL
class Cat(BaseModel): 
    id: int
    name: str = Field(min_length=1)
    image: str = Field(min_length=1)
    breed: str = Field(min_length=1)
    age: int = Field(gt=0)
    color: str = Field(min_length=1)
    gender: str = Field(min_length=1)
    prev_owner: str = Field(min_length=1)
    fav_treat: str = Field(min_length=1)
    likes: str 
    dislikes: str 
    previous_health_conditions: str = Field(min_length=1)
    friendliness_level: int = Field(ge=1, le=5)
    prefered_environment: Literal["Inside Only", "Outside Only", "Outside and Inside"]
    good_for_adoption: str = Field(min_length=1)
    description: str = Field(min_length=1)


def verify_api_key(request: Request, x_api_key: Optional[str] = Header(default=None)):
    if BUILD_KEY and x_api_key == BUILD_KEY:
        return "build"

    scope = API_KEYS.get(x_api_key)
    if scope is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key."
        )

    allowed_origins = SCOPE_ORIGINS.get(scope)
    if allowed_origins is not None and request.headers.get("origin") not in allowed_origins:
        raise HTTPException(
            status_code=403,
            detail="This API key isn't valid for this site."
        )
    return scope

# Use as Depends(require_scope("collection")), Depends(require_scope("battle")),
# or Depends(require_scope("collection", "battle")) to accept either key.
def require_scope(*allowed_scopes: str):
    def dependency(scope: str = Depends(verify_api_key)):
        if scope not in allowed_scopes:
            raise HTTPException(
                status_code=403,
                detail="This API key isn't authorized for this endpoint."
            )
        return scope
    return dependency

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "Simple Cat API",
        "version": API_VERSION,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

# HOME
@app.get("/api/v1", dependencies=[Depends(require_scope(*ALL_SCOPES))])
def home():
    return {
        "message": "Welcome to the Simple Cat API!",
        "endpoints": [
            "/cats",
            "/cats/{id}",
            "/cats/search"
        ]
    }


# GET ALL CATS
@app.get("/api/v1/cats", dependencies=[Depends(require_scope(*ALL_SCOPES))])
def get_cats():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM cats ORDER BY id").fetchall()
    return {
        "count": len(rows),
        "cats": rows
    }


    
# SEARCH CATS
@app.get("/api/v1/cats/search", dependencies=[Depends(require_scope(*ALL_SCOPES))])
def search_cats(q: str = Query(..., min_length=1)):
    like = f"%{q}%"
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM cats
            WHERE name ILIKE %s
               OR breed ILIKE %s
               OR color ILIKE %s
               OR gender ILIKE %s
               OR prefered_environment ILIKE %s
            ORDER BY id
            """,
            (like, like, like, like, like),
        ).fetchall()
    return {
        "query": q.lower(),
        "count": len(rows),
        "results": rows
    }


# GET ONE CAT
@app.get("/api/v1/cats/{cat_id}", dependencies=[Depends(require_scope(*ALL_SCOPES))])
def get_cat(cat_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM cats WHERE id = %s", (cat_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Cat not found.")
    return row