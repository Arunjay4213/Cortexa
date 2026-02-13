"""FastAPI application factory with CORS and lifespan."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cortex.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: warm the embedding model in background
    yield
    # Shutdown: dispose DB engine
    from cortex.database import engine

    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="CortexOS Engine",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from cortex.api.memories import router as memories_router
    from cortex.api.transactions import router as transactions_router
    from cortex.api.attribution import router as attribution_router
    from cortex.api.health import router as health_router
    from cortex.api.dashboard import router as dashboard_router

    app.include_router(memories_router, prefix="/api/v1")
    app.include_router(transactions_router, prefix="/api/v1")
    app.include_router(attribution_router, prefix="/api/v1")
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    return app


app = create_app()
