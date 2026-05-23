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
from backend.api import local as local_api
from backend.api import privacy as privacy_api
from backend.api import takedown as takedown_api
from backend.api.auth import DEFAULT_OWNER_ID, _ALGORITHM
from backend.config import settings
from backend.logging import setup_logging, request_user

setup_logging()
logger = logging.getLogger("novotree.backend")
access_logger = logging.getLogger("novotree.access")


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize global system database (auth)
    init_system_db()
    logger.info("System database initialized")

    # Suppress uvicorn's own access log. We emit our own from inside owner_db_router
    # middleware where request_user ContextVar is already set, so _UserFilter can inject
    # the username. Uvicorn emits its access log from a different asyncio task context
    # (the protocol handler), so the ContextVar would be empty there.
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.setLevel(logging.WARNING)
    uvicorn_access.propagate = False

    if not settings.cookie_secure and not settings.is_dev:
        logger.warning(
            "COOKIE_SECURE=false in public mode — auth cookies are sent over plain HTTP. "
            "Safe only behind an HTTPS-terminating proxy (Caddy). "
            "Remove COOKIE_SECURE=false before exposing this server to the internet."
        )

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

    # Takedown SLA sweeper — in-process reminder/escalation loop. Only meaningful
    # when the public takedown endpoint is exposed (i.e. not the local desktop app).
    # The standalone scheduled-jobs backstop covers the case where this process is
    # not running; see tools/operational/scheduled_jobs/.
    if not settings.is_local:
        takedown_api.start_in_process_sweeper()

    yield

    if not settings.is_local:
        await takedown_api.stop_in_process_sweeper()
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
    # Auth endpoints — no tree DB needed
    "/auth/login", "/auth/logout", "/auth/refresh",
    "/auth/me", "/auth/set-password", "/auth/public-config", "/auth/share-info",
    "/auth/owner-signup", "/auth/verify-owner-email", "/auth/resend-owner-verification",
    "/auth/contributor-signup", "/auth/verify-contributor-email", "/auth/resend-contributor-verification",
    "/privacy/config",
    "/privacy/policy",
    "/privacy/takedown",
    "/takedown",
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

    # Inject current user into logging context
    access_token = request.cookies.get("access_token")
    if settings.is_dev:
        request_user.set(DEFAULT_OWNER_ID)
    elif access_token:
        try:
            payload = jwt.decode(access_token, settings.jwt_secret_key, algorithms=[_ALGORITHM])
            request_user.set(payload.get("sub", ""))
        except JWTError:
            request_user.set("")
    elif request.query_params.get("share"):
        request_user.set("viewer")
    else:
        request_user.set("")

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

            # Ensure the owner's DB engine is in the pool (idempotent — no-op if already cached).
            try:
                db.init_db_once(OwnerInfo(owner_id=owner_id))
            except Exception as e:
                logger.error(f"Failed to open database for owner '{owner_id}': {e}")
                return JSONResponse(status_code=500, content={"detail": "Database unavailable"})

    response = await call_next(request)

    # Emit access log from here so request_user ContextVar (set above) is visible to _UserFilter.
    access_logger.info(
        '%s - "%s %s HTTP/%s" %d',
        _get_client_ip(request),
        request.method,
        path,
        request.scope.get("http_version", "1.1"),
        response.status_code,
    )

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
app.include_router(local_api.router)
app.include_router(privacy_api.router)
if not settings.is_local:
    # Takedown endpoints are only meaningful in network-reachable deployments.
    # In the local desktop app the user is also the controller — there is no
    # second party to file a takedown against, and the Owner's "queue" is empty
    # by definition.
    app.include_router(takedown_api.public_router)   # POST /privacy/takedown
    app.include_router(takedown_api.owner_router)    # GET/PATCH/DELETE /takedown


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
