"""CArchive API (FastAPI + Neon PostgreSQL). This is the only file in /api.

Routes live here; SQL lives in carchive/db.py; password/token helpers in carchive/security.py.
"""
import hmac
import json
import logging
import math
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, StringConstraints

try:                      # local development only; on Vercel the variables come from project settings
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# db.py and security.py live in the carchive/ package at the repo root, NOT in /api,
# because Vercel turns every file inside /api into its own serverless function.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from carchive import db, security  # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("carchive.api")

app = FastAPI(
    title="CArchive Cat API",
    description="Cats from all over the world, told in their owners' words.",
    version="2.0.0",
)

# ---------------------------------------------------------------------------
# CORS. Browsers need to be allowed to send the API key and the login token.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],                    # tighten to your deployed frontend URLs when they're final
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "x-api-key"],
)

# ---------------------------------------------------------------------------
# API keys: one per frontend, read from environment variables (never from code).
# The key says WHICH frontend is calling; the login token says WHO the user is.
# ---------------------------------------------------------------------------
KEY_VARIABLES = {
    "ARCHIVE_API_KEY": "archive",
    "ADOPTION_API_KEY": "adoption",
    "COLLECTION_API_KEY": "collection",
    "BATTLE_API_KEY": "battle",
}
API_KEYS = {scope: os.environ[var] for var, scope in KEY_VARIABLES.items() if os.environ.get(var)}
if not API_KEYS:
    log.warning("No API keys are configured; every protected request will be rejected.")

READ_SCOPES = ("adoption", "collection", "battle", "archive")
ORIGINALS_ONLY_SCOPES = ("collection", "battle")      # the Cat TCG sees only the original 20 cats


def verify_api_key(x_api_key: Optional[str] = Header(default=None)) -> str:
    if x_api_key:
        for scope, key in API_KEYS.items():
            if hmac.compare_digest(x_api_key.encode(), key.encode()):
                return scope
    raise HTTPException(status_code=401, detail="Invalid or missing API key.")


def require_scope(*allowed: str):
    def check(scope: str = Depends(verify_api_key)) -> str:
        if scope not in allowed:
            raise HTTPException(status_code=403, detail="This API key can't do that.")
        return scope
    return check


ReadScope = Depends(require_scope(*READ_SCOPES))
ArchiveOnly = Depends(require_scope("archive"))

# ---------------------------------------------------------------------------
# Logged-in user (Bearer token). The user is re-read from the database on every
# request, so deleted accounts and role changes take effect immediately.
# ---------------------------------------------------------------------------
bearer = HTTPBearer(auto_error=False)


def current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer)) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Please log in to do that.")
    user_id = security.read_token(credentials.credentials)
    user = db.get_user_by_id(user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(status_code=401, detail="Your session has expired. Please log in again.")
    return user


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admins only.")
    return user


# ---------------------------------------------------------------------------
# Who/where a request came from, recorded in the audit log.
# Vercel sets x-forwarded-for and x-vercel-id itself; locally we fall back to the socket address and a random id.
# ---------------------------------------------------------------------------
def request_context(request: Request) -> dict:
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "")
    return {
        "ip": ip[:64] or None,
        "request_id": (request.headers.get("x-vercel-id") or str(uuid.uuid4()))[:100],
    }


# ---------------------------------------------------------------------------
# Request models. Validation happens here, before anything reaches the database.
# ---------------------------------------------------------------------------
Required60 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Optional100 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
Optional200 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Story = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=600)]
Environment = Literal["Inside Only", "Outside Only", "Outside and Inside"]
CatId = Annotated[int, Path(ge=1, le=2_147_483_647)]

AuditAction = Literal["user.register", "cat.create", "cat.update", "cat.moderate", "cat.delete"]
ALLOWED_IMAGE_PREFIXES = ("https://", "data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")
MAX_IMAGE_LENGTH = 400_000        # characters; the frontend shrinks photos to well under this
MAX_PENDING_PER_USER = 10         # stops one account flooding the review queue


class RegisterRequest(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9_.-]{3,30}$")
    email: str = Field(max_length=120, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    identifier: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    password: str = Field(min_length=1, max_length=128)


class CatSubmission(BaseModel):
    name: Required60
    country: Required60
    breed: Required60
    age: int = Field(ge=1, le=40)
    color: Required60
    gender: Literal["Male", "Female"]
    fav_treat: Optional100 = "Unknown"
    likes: Optional200 = ""
    dislikes: Optional200 = ""
    friendliness_level: int = Field(default=3, ge=1, le=5)
    prefered_environment: Environment = "Inside Only"
    good_for_adoption: Literal["Yes", "No"] = "No"
    description: Story
    image: str = Field(default="", max_length=MAX_IMAGE_LENGTH)
    # Anything else a client sends (e.g. the old submitted_by) is ignored: the name always comes from the account.


class CatUpdate(BaseModel):
    """Every field optional: only the ones sent are changed."""
    name: Optional[Required60] = None
    country: Optional[Required60] = None
    breed: Optional[Required60] = None
    age: Optional[int] = Field(default=None, ge=1, le=40)
    color: Optional[Required60] = None
    gender: Optional[Literal["Male", "Female"]] = None
    fav_treat: Optional[Optional100] = None
    likes: Optional[Optional200] = None
    dislikes: Optional[Optional200] = None
    friendliness_level: Optional[int] = Field(default=None, ge=1, le=5)
    prefered_environment: Optional[Environment] = None
    good_for_adoption: Optional[Literal["Yes", "No"]] = None
    description: Optional[Story] = None
    image: Optional[str] = Field(default=None, max_length=MAX_IMAGE_LENGTH)
    status: Optional[Literal["pending", "approved", "rejected"]] = None   # admins only


def check_image(image: Optional[str]) -> None:
    if image and not image.startswith(ALLOWED_IMAGE_PREFIXES):
        raise HTTPException(status_code=422, detail="image: must be an https:// link or a JPEG, PNG or WebP upload.")


# ---------------------------------------------------------------------------
# Error handling. Clients get short, safe messages; the details go to the logs.
# ---------------------------------------------------------------------------
DUPLICATE_MESSAGES = {
    "users_username_lower_key": "That username is already taken.",
    "users_email_lower_key": "An account with that email already exists.",
    "cats_no_duplicates": "That cat has already been submitted (same name, breed, country and owner).",
}


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    """One readable string, built from field names and messages only. FastAPI's default echoes
    the submitted values back, which would include passwords."""
    parts = []
    for error in exc.errors():
        path = [str(p) for p in error.get("loc", ()) if p not in ("body", "query", "path")]
        message = error.get("msg", "Invalid value.")
        parts.append(f"{path[-1]}: {message}" if path else message)
    return JSONResponse(status_code=422, content={"detail": " | ".join(parts) or "Invalid request."})


@app.exception_handler(db.DuplicateRecord)
async def duplicate_error(request: Request, exc: db.DuplicateRecord):
    return JSONResponse(status_code=409, content={"detail": DUPLICATE_MESSAGES.get(exc.constraint, "That record already exists.")})


@app.exception_handler(db.DatabaseUnavailable)
async def database_unavailable(request: Request, exc: db.DatabaseUnavailable):
    return JSONResponse(status_code=503, content={"detail": "The archive is temporarily unavailable. Please try again shortly."})


@app.exception_handler(db.DatabaseError)
async def database_error(request: Request, exc: db.DatabaseError):
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on our side."})


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on our side."})


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    database_ok = db.ping()
    return {
        "status": "ok" if database_ok else "degraded",
        "service": "carchive-api",
        "version": app.version,
        "database": "ok" if database_ok else "unavailable",
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


@app.get("/")
def home():
    return {
        "message": "Welcome to the CArchive Cat API.",
        "docs": "/docs",
        "endpoints": {
            "health": "GET /health",
            "register": "POST /api/v1/auth/register",
            "login": "POST /api/v1/auth/login",
            "me": "GET /api/v1/auth/me (login required)",
            "list": "GET /api/v1/cats (optional: limit, offset, q, breed, country, good_for_adoption, sort)",
            "search": "GET /api/v1/cats/search?q=",
            "mine": "GET /api/v1/cats/mine (login required)",
            "pending": "GET /api/v1/cats/pending (admin)",
            "rejected": "GET /api/v1/cats/rejected (admin)",
            "filters": "GET /api/v1/cats/filters",
            "one": "GET /api/v1/cats/{id}",
            "submit": "POST /api/v1/cats (login required)",
            "update": "PATCH /api/v1/cats/{id} (owner or admin)",
            "delete": "DELETE /api/v1/cats/{id} (owner or admin)",
            "audit": "GET /api/v1/audit (admin)",
            "audit_export": "GET /api/v1/audit/export (admin, downloads audit_log.json)",
        },
    }


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------
def session_for(user: dict) -> dict:
    return {
        "token": security.create_token(user["id"]),
        "user": {"id": user["id"], "username": user["username"], "role": user["role"]},
    }


@app.post("/api/v1/auth/register", status_code=201, dependencies=[ArchiveOnly])
def register(body: RegisterRequest, ctx: dict = Depends(request_context)):
    user = db.create_user(body.username, body.email, security.hash_password(body.password), ctx)
    return session_for(user)


@app.post("/api/v1/auth/login", dependencies=[ArchiveOnly])
def login(body: LoginRequest, ctx: dict = Depends(request_context)):
    typed = body.identifier.lower()
    # too many recent failures for this account or this address: refuse before doing any password work
    wait = db.login_lock_seconds(typed, ctx["ip"])
    if wait > 0:
        minutes = max(1, math.ceil(wait / 60))
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed login attempts. Please try again in {minutes} minute{'s' if minutes != 1 else ''}.",
            headers={"Retry-After": str(wait)},
        )

    user = db.get_user_for_login(body.identifier)
    # same message and same work whether the account is missing or the password is wrong
    if not security.check_password(user["password_hash"] if user else None, body.password):
        db.record_failed_login(typed, ctx["ip"])
        raise HTTPException(status_code=401, detail="Incorrect email/username or password.")

    db.clear_failed_logins(typed)
    return session_for(user)


@app.get("/api/v1/auth/me", dependencies=[ArchiveOnly])
def whoami(user: dict = Depends(current_user)):
    """Who the token belongs to, with their current role. The admin page uses it to check access."""
    return {"id": user["id"], "username": user["username"], "role": user["role"]}


# ---------------------------------------------------------------------------
# Reading cats. Order matters: fixed paths (/search, /mine, /pending) come before /{cat_id}.
# ---------------------------------------------------------------------------
@app.get("/api/v1/cats")
def list_cats(
    limit: Optional[int] = Query(None, ge=1, le=50),
    offset: int = Query(0, ge=0, le=1_000_000),
    q: Optional[str] = Query(None, max_length=100),
    breed: Optional[str] = Query(None, max_length=60),
    country: Optional[str] = Query(None, max_length=60),
    good_for_adoption: Optional[Literal["Yes", "No"]] = None,
    sort: Literal["oldest", "newest", "name", "age_young", "age_old"] = "oldest",
    scope: str = ReadScope,
):
    originals_only = scope in ORIGINALS_ONLY_SCOPES
    q = (q or "").strip() or None
    # No paging, filter or sort parameters: the original behaviour (every approved cat), which the
    # other frontends rely on. Any of them switches on the paged response, which adds total/limit/offset.
    if limit is None and offset == 0 and not (q or breed or country or good_for_adoption) and sort == "oldest":
        cats = db.list_cats(originals_only=originals_only)
        return {"count": len(cats), "cats": cats}
    cats, total = db.list_cats_page(limit, offset, sort, q, breed, country, good_for_adoption, originals_only)
    return {"count": len(cats), "total": total, "limit": limit, "offset": offset, "cats": cats}


@app.get("/api/v1/cats/search")
def search_cats(
    q: str = Query(..., min_length=1, max_length=100),
    good_for_adoption: Optional[Literal["Yes", "No"]] = None,
    scope: str = ReadScope,
):
    term = q.strip()
    if not term:
        raise HTTPException(status_code=422, detail="q: enter something to search for.")
    results = db.search_cats(term, originals_only=scope in ORIGINALS_ONLY_SCOPES, good_for_adoption=good_for_adoption)
    return {"query": q, "count": len(results), "results": results}


@app.get("/api/v1/cats/mine", dependencies=[ArchiveOnly])
def my_cats(user: dict = Depends(current_user)):
    cats = db.list_cats_by_user(user["id"])
    return {"count": len(cats), "cats": cats}


@app.get("/api/v1/cats/pending", dependencies=[ArchiveOnly])
def pending_cats(admin: dict = Depends(require_admin)):
    cats = db.list_pending()
    return {"count": len(cats), "cats": cats}


@app.get("/api/v1/cats/filters")
def cat_filters(scope: str = ReadScope):
    """Breeds and countries present among approved cats, for the archive's filter dropdowns."""
    return db.list_filter_values(originals_only=scope in ORIGINALS_ONLY_SCOPES)


@app.get("/api/v1/cats/rejected", dependencies=[ArchiveOnly])
def rejected_cats(admin: dict = Depends(require_admin)):
    cats = db.list_rejected()
    return {"count": len(cats), "cats": cats}


@app.get("/api/v1/cats/{cat_id}")
def get_cat(cat_id: CatId, scope: str = ReadScope):
    cat = db.get_cat(cat_id, originals_only=scope in ORIGINALS_ONLY_SCOPES)
    if cat is None:
        raise HTTPException(status_code=404, detail="Cat not found.")
    return cat


# ---------------------------------------------------------------------------
# Writing cats (archive frontend only, and only for logged-in users)
# ---------------------------------------------------------------------------
@app.post("/api/v1/cats", status_code=201, dependencies=[ArchiveOnly])
def submit_cat(submission: CatSubmission, user: dict = Depends(current_user), ctx: dict = Depends(request_context)):
    check_image(submission.image)
    is_admin = user["role"] == "admin"
    if not is_admin and db.count_pending(user["id"]) >= MAX_PENDING_PER_USER:
        raise HTTPException(status_code=429, detail="You have several cats waiting for review. Please wait for them to be approved before adding more.")
    # new community cats wait for review; an admin's own submissions go straight in
    return db.create_cat(submission.model_dump(), user, "approved" if is_admin else "pending", ctx)


def load_editable_cat(cat_id: int, user: dict) -> dict:
    """The cat, if this user may change it. Admins can change any cat; owners can change their own."""
    cat = db.get_cat_internal(cat_id)
    if cat is None:
        raise HTTPException(status_code=404, detail="Cat not found.")
    if user["role"] == "admin" or cat["user_id"] == user["id"]:
        return cat
    if cat["status"] != "approved":
        raise HTTPException(status_code=404, detail="Cat not found.")     # don't reveal unapproved cats
    raise HTTPException(status_code=403, detail="You can only change cats you submitted.")


@app.patch("/api/v1/cats/{cat_id}", dependencies=[ArchiveOnly])
def update_cat(changes: CatUpdate, cat_id: CatId, user: dict = Depends(current_user), ctx: dict = Depends(request_context)):
    load_editable_cat(cat_id, user)
    fields = changes.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=422, detail="Send at least one field to change.")
    nulls = [name for name, value in fields.items() if value is None]
    if nulls:
        raise HTTPException(status_code=422, detail=f"{', '.join(nulls)}: can't be null.")
    check_image(fields.get("image"))

    if user["role"] == "admin":
        pass                                         # admins may also set status (approve / reject)
    elif "status" in fields:
        raise HTTPException(status_code=403, detail="Only admins can change a cat's status.")
    else:
        fields["status"] = "pending"                 # an edited cat goes back for review

    updated = db.update_cat(cat_id, fields, user, ctx)
    if updated is None:                              # deleted by someone else between the check and the update
        raise HTTPException(status_code=404, detail="Cat not found.")
    return updated


@app.delete("/api/v1/cats/{cat_id}", status_code=204, dependencies=[ArchiveOnly])
def delete_cat(cat_id: CatId, user: dict = Depends(current_user), ctx: dict = Depends(request_context)):
    load_editable_cat(cat_id, user)
    if not db.delete_cat(cat_id, user, ctx):
        raise HTTPException(status_code=404, detail="Cat not found.")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Audit log (admins only)
# ---------------------------------------------------------------------------
@app.get("/api/v1/audit", dependencies=[ArchiveOnly])
def audit_entries(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=1_000_000),
    action: Optional[AuditAction] = None,
    target_type: Optional[Literal["cat", "user"]] = None,
    target_id: Optional[int] = Query(None, ge=1, le=2_147_483_647),
    admin: dict = Depends(require_admin),
):
    entries = db.list_audit(limit, offset, action, target_type, target_id)
    return {"count": len(entries), "entries": entries}


@app.get("/api/v1/audit/export", dependencies=[ArchiveOnly])
def audit_export(admin: dict = Depends(require_admin)):
    """The full audit log as a downloadable audit_log.json file (read from the database, so it survives redeploys)."""
    body = json.dumps(jsonable_encoder(db.export_audit()), indent=2, ensure_ascii=False)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="audit_log.json"'},
    )