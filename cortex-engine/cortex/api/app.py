"""FastAPI application factory with CORS, auth, and lifespan."""

from contextlib import asynccontextmanager
import traceback
import sys

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from cortex.auth import add_rate_limit_headers, require_api_key
from cortex.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging
    log = logging.getLogger("cortex")

    # Models load lazily on first request (via @lru_cache in
    # cortex.attribution and cortex.attribution.entailment).
    # Do NOT preload here — Railway free tier has 512MB RAM.
    log.info("CortexOS Engine starting (models will load on first request)")

    # Startup: attempt to load calibrator from DB pairs (best-effort)
    try:
        from cortex.attribution.calibrator import refresh_calibrator_on_startup
        await refresh_calibrator_on_startup()
    except Exception:
        pass  # Non-blocking — calibrator is optional

    yield

    # Shutdown: dispose DB engine
    from cortex.database import engine
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="CortexOS Engine",
        version="0.2.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(BaseHTTPMiddleware, dispatch=add_rate_limit_headers)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        print(f"\n{'='*80}", file=sys.stderr)
        print(f"ERROR in {request.method} {request.url}", file=sys.stderr)
        print(f"Exception: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print(f"{'='*80}\n", file=sys.stderr)
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": type(exc).__name__}
        )

    from cortex.api.memories import router as memories_router
    from cortex.api.transactions import router as transactions_router
    from cortex.api.attribution import router as attribution_router
    from cortex.api.health import router as health_router
    from cortex.api.dashboard import router as dashboard_router
    from cortex.api.agents import router as agents_router
    from cortex.api.websocket import router as websocket_router
    from cortex.api.lifecycle import router as lifecycle_router
    from cortex.api.snapshots import router as snapshots_router
    from cortex.api.counterfactual import router as counterfactual_router
    from cortex.api.grounding import router as grounding_router
    from cortex.api.api_keys import router as api_keys_router

    # All /api/v1/* routes require a valid API key (except /healthz below)
    _auth = [Depends(require_api_key)]

    app.include_router(memories_router, prefix="/api/v1", dependencies=_auth)
    app.include_router(transactions_router, prefix="/api/v1", dependencies=_auth)
    app.include_router(attribution_router, prefix="/api/v1", dependencies=_auth)
    app.include_router(health_router, prefix="/api/v1", dependencies=_auth)
    app.include_router(dashboard_router, prefix="/api/v1", dependencies=_auth)
    app.include_router(agents_router, prefix="/api/v1", dependencies=_auth)
    app.include_router(websocket_router, prefix="/api/v1", dependencies=_auth)
    app.include_router(lifecycle_router, prefix="/api/v1", dependencies=_auth)
    app.include_router(snapshots_router, prefix="/api/v1", dependencies=_auth)
    app.include_router(counterfactual_router, prefix="/api/v1", dependencies=_auth)
    app.include_router(grounding_router, prefix="/api/v1", dependencies=_auth)
    # Admin endpoints use their own admin-secret dependency (no api-key required)
    app.include_router(api_keys_router)

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    return app


app = create_app()
