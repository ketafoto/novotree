# run "uvicorn backend.main:app --host 0.0.0.0 --port 8000" from the root folder to start the webserver
# run "uvicorn backend.main:app --reload" for dev with auto-reload
#
# Open http://localhost:8000 for API info
# Open http://localhost:8000/docs for interactive Swagger UI (admin mode only)
#
# NOVOTREE_APP_MODE=admin  (default) — auth bypassed, uses DEFAULT_OWNER_ID database
# NOVOTREE_APP_MODE=<anything else>  — full JWT authentication required
#
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from sqlalchemy import text

from database import db
from database.owner_info import OwnerInfo
from database.system_db import get_system_session, init_system_db
from database.system_models import AuthShareToken
from backend.api import individuals, families, events, media, header, auth, types, export, import_api, tree
from backend.api import users as users_api
from backend.api.auth import DEFAULT_OWNER_ID, _ALGORITHM
from backend.config import settings
from backend.logging import setup_logging

setup_logging()
logger = logging.getLogger("gedcom.backend")


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize global system database (auth)
    init_system_db()
    logger.info("System database initialized")

    if settings.is_dev:
        # Dev mode: initialize default owner's database directly
        owner_info = OwnerInfo(owner_id=DEFAULT_OWNER_ID)
        try:
            engine = db.init_db_once(owner_info)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1 FROM main_individuals LIMIT 1"))
            logger.info(f"Dev mode: database ready for owner '{DEFAULT_OWNER_ID}'")
        except Exception as e:
            logger.error(f"Dev mode database initialization failed: {e}")
            raise

    yield
    db.reset_engine()


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Genealogy Database API",
    description="REST API for managing genealogical data in GEDCOM 5.5.1 format",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url="/redoc" if settings.enable_api_docs else None,
    openapi_url="/openapi.json" if settings.enable_api_docs else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Per-request owner DB routing middleware
# ---------------------------------------------------------------------------

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Paths that don't need an owner database
AUTH_ONLY_PATHS = {
    "/auth/login", "/auth/signup", "/auth/logout", "/auth/refresh",
    "/auth/me", "/auth/set-password", "/auth/verify-email",
    "/auth/resend-verification", "/auth/public-config",
    "/users/invitations",    # POST from public (Contribute button)
    "/health",
}
_request_windows: dict[str, deque[float]] = defaultdict(deque)


def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _resolve_owner_id_from_request(request: Request) -> str | None:
    """
    Determine which owner's database to open for this request.

    Priority:
    1. Dev mode → DEFAULT_OWNER_ID
    2. Access token cookie → owner_id claim
    3. share query param → look up in system DB
    """
    if settings.is_dev:
        return DEFAULT_OWNER_ID

    # Try JWT access token
    access_token = request.cookies.get("access_token")
    if access_token:
        try:
            payload = jwt.decode(access_token, settings.jwt_secret_key, algorithms=[_ALGORITHM])
            return payload.get("owner_id")
        except JWTError:
            pass

    # Try share token in query string
    share = request.query_params.get("share")
    if share:
        try:
            sys_db = get_system_session()
            try:
                from datetime import datetime, timedelta, timezone
                token_row = sys_db.query(AuthShareToken).filter(
                    AuthShareToken.token == share,
                    AuthShareToken.is_active == True,
                ).first()
                if token_row:
                    anchor = token_row.last_used_at or token_row.created_at
                    expiry = datetime.fromisoformat(anchor) + timedelta(days=token_row.expires_after_days)
                    if datetime.now(timezone.utc) <= expiry:
                        return token_row.owner_id
            finally:
                sys_db.close()
        except Exception as e:
            logger.warning(f"Share token lookup failed: {e}")

    return None


@app.middleware("http")
async def owner_db_router(request: Request, call_next):
    """
    Per-request middleware:
    1. Rate limiting (production only)
    2. Resolve owner_id and switch the active database
    3. Block writes from viewer (share-token) sessions
    4. Add security headers
    """
    path = request.url.path

    # Rate limiting in production
    if not settings.is_dev:
        ip = _get_client_ip(request)
        now = time.time()
        window = _request_windows[ip]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= settings.rate_limit_per_minute:
            return JSONResponse(status_code=429, content={"detail": "Too many requests"})
        window.append(now)

    # Skip DB routing for pure-auth and health paths
    is_auth_path = any(path == p or path.startswith(p + "/") for p in AUTH_ONLY_PATHS)
    if not is_auth_path:
        owner_id = _resolve_owner_id_from_request(request)

        if owner_id:
            # Check if this is a share-token (viewer) session trying to write
            is_share_token = (
                not settings.is_dev
                and not request.cookies.get("access_token")
                and request.query_params.get("share")
            )
            if is_share_token and request.method in WRITE_METHODS:
                return JSONResponse(status_code=403, content={"detail": "Read-only viewer access"})

            # Switch active owner database for this request
            current_owner = db.get_active_owner()
            if not current_owner or current_owner.owner_id != owner_id:
                try:
                    db.reset_engine()
                    db.init_db_once(OwnerInfo(owner_id=owner_id))
                except Exception as e:
                    logger.error(f"Failed to open database for owner '{owner_id}': {e}")
                    return JSONResponse(status_code=500, content={"detail": "Database unavailable"})

    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: blob:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self';"
    )
    if not settings.is_dev:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth.router)
app.include_router(users_api.router)
app.include_router(types.router)
app.include_router(individuals.router)
app.include_router(families.router)
app.include_router(events.router)
app.include_router(media.router)
app.include_router(header.router)
app.include_router(export.router)
app.include_router(import_api.router)
app.include_router(tree.router)
app.include_router(tree.full_tree_router)


# ---------------------------------------------------------------------------
# Info endpoints
# ---------------------------------------------------------------------------

@app.get("/")
def read_root():
    owner = db.get_active_owner()
    return {
        "message": "Genealogy Database API — see /docs for documentation",
        "current_owner": owner.owner_id if owner else None,
        "version": "1.0.0",
        "mode": settings.app_mode,
    }


@app.get("/owner")
def get_owner_endpoint():
    owner = db.get_active_owner()
    if not owner:
        return {"error": "No owner initialized"}
    return {
        "owner_id": owner.owner_id,
        "db_file": str(owner.db_file),
        "gedcom_file": str(owner.gedcom_file),
        "media_dir": str(owner.media_dir),
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}
